"""Stored settings through the bridge (task 5.3): the global settings as
settings.json text, each score's as desktop .rsc text, restored on load in
MainWindow._on_score_loaded's order. storage.js only keeps the text."""
import json
from pathlib import Path

import pytest

import web_api
from models.app_settings_data import AppSettings
from models.marking_categories import ALL_CATEGORIES
from models.performance_indicator_mode import PERFORMANCE_INDICATOR_ALWAYS_ON
from models.score_config_json import config_from_dict, config_to_dict

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
SCORE = FIXTURES / "hairpins_two_parts.musicxml"


@pytest.fixture(autouse=True)
def _fresh_globals(monkeypatch):
    """Global settings outlive a load, so each test starts from the defaults."""
    defaults = AppSettings()
    monkeypatch.setattr(web_api, "_app_settings", defaults)
    monkeypatch.setattr(web_api, "_performance_indicator_mode", defaults.performance_indicator_mode)
    monkeypatch.setattr(web_api, "_marking_categories_off", set(ALL_CATEGORIES))
    monkeypatch.setattr(web_api, "_uk_terms", False)


def _load(saved=None, path=SCORE):
    result = web_api.load(path.read_bytes(), path.name, saved)
    assert result["ok"], result
    return result


def test_global_settings_round_trip():
    web_api.cycle_performance_indicator()
    web_api.cycle_performance_indicator()
    web_api.set_uk_terms(True)
    text = web_api.global_settings_json()
    data = json.loads(text)
    assert data["performance_indicator_mode"] == PERFORMANCE_INDICATOR_ALWAYS_ON
    assert data["uk_terms"] is True
    assert set(data) == set(AppSettings().to_dict())  # the desktop settings.json shape

    web_api._performance_indicator_mode = AppSettings().performance_indicator_mode
    web_api._uk_terms = False
    assert web_api.apply_global_settings(text) == {"ok": True}
    assert web_api._performance_indicator_mode == PERFORMANCE_INDICATOR_ALWAYS_ON
    assert web_api._uk_terms is True


def test_global_settings_keep_unknown_desktop_fields():
    """A desktop settings.json carries fields the web never uses; they go
    back out unchanged."""
    desktop = AppSettings(recent_files=["C:/scores/a.musicxml"], musescore_path="ms.exe").to_dict()
    web_api.apply_global_settings(json.dumps(desktop))
    data = json.loads(web_api.global_settings_json())
    assert data["recent_files"] == ["C:/scores/a.musicxml"]
    assert data["musescore_path"] == "ms.exe"


def test_no_saved_uk_terms_leaves_the_current_choice():
    web_api.set_uk_terms(True)
    web_api.apply_global_settings(json.dumps({"uk_terms": None}))
    assert web_api._uk_terms is True


@pytest.mark.parametrize("text", ["not json", "[1, 2]", "42"])
def test_unreadable_global_settings_change_nothing(text):
    web_api._performance_indicator_mode = PERFORMANCE_INDICATOR_ALWAYS_ON
    assert "error" in web_api.apply_global_settings(text)
    assert web_api._performance_indicator_mode == PERFORMANCE_INDICATOR_ALWAYS_ON


def test_empty_global_settings_are_fine():
    assert web_api.apply_global_settings(None) == {"ok": True}
    assert web_api.apply_global_settings("") == {"ok": True}


def test_global_marking_categories_reach_the_next_load():
    off = set(ALL_CATEGORIES) - {"structural_changes"}
    web_api.apply_global_settings(json.dumps({"marking_categories_off": sorted(off)}))
    _load()
    assert web_api._music_data.marking_categories_off == off


def test_no_score_has_no_score_settings():
    web_api._music_data = None
    assert web_api.score_settings_json() is None


def test_score_settings_are_rsc_text():
    _load()
    data = json.loads(web_api.score_settings_json())
    assert data == config_to_dict(config_from_dict(data))  # the desktop .rsc shape


def _change_everything():
    """Metronome, tempo, play mode, cursor, and a part muted in Region 2."""
    md = web_api._music_data
    web_api.toggle("metronome")
    web_api.tempo("faster")
    web_api.play_setting("play_mode")
    md.active_event_index = 3
    part = web_api._region_2.roots[0]
    web_api.region2_toggle(part.node_id, "mute")


def test_saved_score_settings_are_restored_on_load():
    _load()
    _change_everything()
    md = web_api._music_data
    expected = (md.metronome_enabled, md.playback_tempo_bpm, md.play_settings.play_mode,
                md.active_event_index, md.active_voice_filter)
    saved = web_api.score_settings_json()

    _load()  # a fresh load without its settings is back to the defaults
    assert web_api._music_data.metronome_enabled is False
    assert web_api._region_2.roots[0].muted is False

    result = _load(saved)
    md = web_api._music_data
    assert (md.metronome_enabled, md.playback_tempo_bpm, md.play_settings.play_mode,
            md.active_event_index, md.active_voice_filter) == expected
    assert web_api._region_2.node(web_api._region_2.roots[0].node_id).muted is True
    tree = result["view"]["regions"]["2"]
    assert "muted" in tree[0]["text"]


def test_mute_and_solo_are_each_nodes_own():
    """Region 2's per-node state, not MusicData's derived voices_muted, so a
    voice soloed under a muted part comes back as both."""
    _load()
    part = web_api._region_2.roots[0]
    voice = part.children[0].children[0]
    web_api.region2_toggle(voice.node_id, "solo")
    web_api.region2_toggle(part.node_id, "mute")
    saved = web_api.score_settings_json()
    _load(saved)
    part = web_api._region_2.node(part.node_id)
    assert part.muted is True and part.children[0].children[0].soloed is True


def test_unreadable_score_settings_open_with_defaults():
    result = _load("{broken")
    assert "settings_error" in result
    assert web_api._music_data.metronome_enabled is False


def test_a_desktop_rsc_for_another_score_applies_what_it_can():
    """Best-effort, as the desktop's apply_config: unknown parts are dropped."""
    rsc = {"metronome_enabled": True, "parts_muted": ["NoSuchPart"],
           "voices_muted": ["NoSuchPart|1|1"], "last_position_index": 99999}
    _load(json.dumps(rsc))
    md = web_api._music_data
    assert md.metronome_enabled is True
    assert md.active_event_index == 0
    assert not any(part.muted for part in web_api._region_2.roots)
