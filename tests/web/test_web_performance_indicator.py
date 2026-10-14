"""The performance indicator (Ctrl+C) and Region 5's marking categories
(Alt+N on the web, Ctrl+N on the desktop; Shift+F10's one-item menu)
through the bridge. Which cue fires is audio/navigation_cues.py's
performance_indicator_cue, shared with the desktop presenter."""
import json
from pathlib import Path

import pytest

import web_api
from audio.performance_cue import performance_cue_event
from models import announcements
from models.app_settings_data import AppSettings
from models.marking_categories import ALL_CATEGORIES
from models.performance_indicator_mode import (
    PERFORMANCE_INDICATOR_ALWAYS_ON,
    PERFORMANCE_INDICATOR_OFF,
    PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING,
)
from models.play_settings import PlaySettings

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
CHANGE_INDEX = 4  # ts_change.musicxml: the first slice of bar 2, a 6/8 change


@pytest.fixture(autouse=True)
def _fresh_globals(monkeypatch):
    """The two settings outlive a load, so each test starts from the defaults."""
    monkeypatch.setattr(web_api, "_performance_indicator_mode", AppSettings().performance_indicator_mode)
    monkeypatch.setattr(web_api, "_marking_categories_off", set(ALL_CATEGORIES))


def _load(name="ts_change.musicxml"):
    path = FIXTURES / name
    assert web_api.load(path.read_bytes(), path.name)["ok"]
    return web_api._music_data


def _cues(sound):
    return [shot for shot in (sound or {}).get("oneshots", []) if shot["slot"] == "cue"]


def _structural_row():
    """Region 5's row for the time signature change, with the cursor on it."""
    rows = web_api.region_rows(5)
    return next(i for i, row in enumerate(rows) if row["category"] == "structural_changes")


def _go_to_change(md):
    md.active_event_index = CHANGE_INDEX - 1
    return web_api.move("right")


def test_ctrl_c_cycles_and_says_the_mode():
    said = [web_api.cycle_performance_indicator()["announce"] for _ in range(3)]
    assert web_api._performance_indicator_mode == PERFORMANCE_INDICATOR_OFF
    assert said == [announcements.performance_indicator_mode(mode) for mode in (
        PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING,
        PERFORMANCE_INDICATOR_ALWAYS_ON,
        PERFORMANCE_INDICATOR_OFF,
    )]


def test_region_5_menu_and_toggle_bring_the_change_into_the_note_list():
    md = _load()
    _go_to_change(md)
    row = _structural_row()

    menu = web_api.region5_menu(row)
    json.dumps(menu)
    assert menu == {"title": "Structural changes",
                    "items": [{"label": "Add Structural changes to note list"}]}
    before = [r["text"] for r in web_api.region_rows(3)]

    result = web_api.toggle_marking_category(row)

    json.dumps(result)
    assert result["done"] is True
    assert result["announce"] == "Structural changes, in note list"
    assert set(result["regions"]) == {"3", "4", "5", "6"}
    assert any(r["kind"] == "marking" for r in result["regions"]["3"])
    assert len(result["regions"]["3"]) > len(before)
    assert result["regions"]["5"][row]["text"].startswith("* ")
    assert web_api.region5_menu(row)["items"] == [{"label": "Remove Structural changes from note list"}]


def test_a_new_load_inherits_the_categories():
    md = _load()
    _go_to_change(md)
    web_api.toggle_marking_category(_structural_row())

    md = _load()
    assert "structural_changes" not in md.marking_categories_off


def test_a_row_without_a_category_does_nothing():
    _load()
    assert web_api.toggle_marking_category(99) == {"done": False}
    assert web_api.region5_menu(99) == {"title": "", "items": []}


def test_off_never_sounds_the_cue_on_a_move():
    md = _load()
    md.marking_categories_off.discard("structural_changes")
    assert _cues(_go_to_change(md)["sound"]) == []


def test_on_sounds_the_cue_on_a_move_onto_a_marking_row():
    md = _load()
    md.marking_categories_off.discard("structural_changes")
    web_api.cycle_performance_indicator()  # on except when playing

    cues = _cues(_go_to_change(md)["sound"])

    assert [shot["event"] for shot in cues] == [list(performance_cue_event())]


def test_no_cue_while_the_category_is_out_of_the_note_list():
    md = _load()
    web_api.cycle_performance_indicator()
    assert _cues(_go_to_change(md)["sound"]) == []


def _step_cues(mode):
    md = _load()
    md.marking_categories_off.discard("structural_changes")
    md.play_settings = PlaySettings(lead_in_enabled=False)
    web_api._performance_indicator_mode = mode
    session = web_api.play_toggle()["session"]
    entries = web_api.play_plan(session, 10 ** 9)["entries"]
    web_api.play_stop()
    return {e["cursor"]: _cues(e["sound"]) for e in entries if e["kind"] == "step"}, md


def test_always_on_sounds_the_cue_with_the_playback_step():
    by_step, md = _step_cues(PERFORMANCE_INDICATOR_ALWAYS_ON)
    assert by_step[CHANGE_INDEX]
    assert md.active_event_index == 0  # planning ahead left the cursor alone


def test_on_except_when_playing_is_silent_during_playback():
    by_step, _ = _step_cues(PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING)
    assert not any(by_step.values())
