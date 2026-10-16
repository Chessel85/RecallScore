"""The Options menu's global settings through the bridge (task 5.4):
Terminology (UK/US) with its browser-region default, the performance
indicator's three direct choices, and Show Engraving Details (Ctrl+V)."""
import json
from pathlib import Path

import pytest

import web_api
from models import announcements
from models.app_settings_data import AppSettings
from models.marking_categories import ALL_CATEGORIES
from models.performance_indicator_mode import (
    PERFORMANCE_INDICATOR_ALWAYS_ON,
    PERFORMANCE_INDICATOR_OFF,
)
from models.vocabulary import default_uk_terms

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


@pytest.fixture(autouse=True)
def _fresh_globals(monkeypatch):
    """Global settings outlive a load, so each test starts from the defaults."""
    defaults = AppSettings()
    monkeypatch.setattr(web_api, "_app_settings", defaults)
    monkeypatch.setattr(web_api, "_performance_indicator_mode", defaults.performance_indicator_mode)
    monkeypatch.setattr(web_api, "_marking_categories_off", set(ALL_CATEGORIES))
    monkeypatch.setattr(web_api, "_uk_terms", False)
    monkeypatch.setattr(web_api, "_music_data", None)


def _load(name):
    path = FIXTURES / name
    assert web_api.load(path.read_bytes(), path.name)["ok"]
    return web_api._music_data


# --- terminology ---------------------------------------------------------------

@pytest.mark.parametrize("territory, uk", [("US", False), ("us", False), ("GB", True),
                                           ("AU", True), ("", True), (None, True)])
def test_default_uk_terms_is_uk_unless_us(territory, uk):
    assert default_uk_terms(territory) is uk


def test_terminology_without_a_score_is_spoken_and_kept():
    result = web_api.set_uk_terms(True)
    assert result == {"announce": announcements.terminology(True)}
    assert web_api._uk_terms is True
    assert json.loads(web_api.global_settings_json())["uk_terms"] is True


def test_terminology_redraws_the_words():
    md = _load("many_measures.musicxml")
    us = web_api.set_uk_terms(False)
    uk = web_api.set_uk_terms(True, [0])
    assert md.uk_terms is True
    assert set(uk["regions"]) == {"1", "3", "4", "5", "6"}
    assert uk["regions"]["6"] != us["regions"]["6"]  # "Loop length: 1 bar" vs "1 measure"
    assert any("bar" in row["text"] for row in uk["regions"]["6"])
    assert uk["regions"]["4"] == web_api.region_rows(4, [0])


def test_browser_region_sets_the_default_without_saving_it():
    assert web_api.apply_global_settings(None, "GB") == {"ok": True}
    assert web_api._uk_terms is True
    assert json.loads(web_api.global_settings_json())["uk_terms"] is None
    web_api.apply_global_settings(None, "US")
    assert web_api._uk_terms is False


def test_a_saved_choice_beats_the_browser_region():
    web_api.apply_global_settings(json.dumps({"uk_terms": False}), "GB")
    assert web_api._uk_terms is False


def test_terminology_reaches_the_next_load():
    web_api.set_uk_terms(True)
    assert _load("many_measures.musicxml").uk_terms is True


# --- performance indicator choices ----------------------------------------------

def test_performance_indicator_choice_is_spoken_and_kept():
    result = web_api.set_performance_indicator(PERFORMANCE_INDICATOR_ALWAYS_ON)
    assert result == {"announce": announcements.performance_indicator_mode(PERFORMANCE_INDICATOR_ALWAYS_ON)}
    assert web_api.options_state()["performance_indicator"] == PERFORMANCE_INDICATOR_ALWAYS_ON
    assert json.loads(web_api.global_settings_json())["performance_indicator_mode"] == PERFORMANCE_INDICATOR_ALWAYS_ON


def test_unknown_performance_indicator_changes_nothing():
    assert "error" in web_api.set_performance_indicator("loud")
    assert web_api._performance_indicator_mode == PERFORMANCE_INDICATOR_OFF


# --- engraving details (Ctrl+V) -----------------------------------------------------

def test_engraving_details_without_a_score():
    result = web_api.toggle_engraving_details()
    assert result == {"announce": "Engraving details on"}
    assert json.loads(web_api.global_settings_json())["show_engraving_details_enabled"] is True
    assert web_api.toggle_engraving_details() == {"announce": "Engraving details off"}


def _texts(rows):
    return [row["text"] for row in rows]


def test_engraving_details_surface_a_clef_change():
    md = _load("clef_change.musicxml")
    seen_before = set()
    seen_after = set()
    for index in range(len(md.timeline_slices)):
        md.active_event_index = index
        seen_before.update(_texts(web_api.region_rows(5)))
    md.active_event_index = 0
    result = web_api.toggle_engraving_details()
    assert result["announce"] == "Engraving details on"
    assert set(result["regions"]) == {"3", "4", "5", "6"}
    assert md.show_engraving_details_enabled is True
    for index in range(len(md.timeline_slices)):
        md.active_event_index = index
        seen_after.update(_texts(web_api.region_rows(5)))
    assert seen_after - seen_before, "a clef change row appears somewhere in Region 5"


def test_engraving_details_reach_the_next_load():
    web_api.toggle_engraving_details()
    assert _load("clef_change.musicxml").show_engraving_details_enabled is True


# --- what the menu shows as checked --------------------------------------------------

def test_options_state_without_a_score():
    assert web_api.options_state() == {
        "uk_terms": False,
        "performance_indicator": PERFORMANCE_INDICATOR_OFF,
        "show_engraving_details": False,
    }


def test_options_state_with_a_score_has_its_toggles():
    md = _load("many_measures.musicxml")
    web_api.toggle("metronome")
    state = web_api.options_state()
    assert state["metronome"] is md.metronome_enabled is True
    assert state["position_announcer"] is md.position_announcer_enabled
    assert state["bar_line_indicator"] is md.bar_line_indicator_enabled
