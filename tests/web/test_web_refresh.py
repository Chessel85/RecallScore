"""Refresh on Playback (Ctrl+Alt+H) and Delay Refresh (Ctrl+Alt+D) through
the browser bridge. The decision itself is models/refresh_settings
(refresh_decision), shared with the desktop's RefreshDelayController."""
import json
from pathlib import Path

import web_api
from models.refresh_settings import RefreshSettings

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _load():
    path = FIXTURES / "minimal_4_4.musicxml"
    assert web_api.load(path.read_bytes(), path.name)["ok"]
    return web_api._music_data


def _started():
    session = web_api.play_toggle()["session"]
    return session, web_api.play_plan(session, 10 ** 9)["entries"]


def test_the_defaults_refresh_at_once_as_before():
    md = _load()
    session, _ = _started()

    assert "held" not in web_api.play_cursor(session, 2, True, False)
    assert md.active_event_index == 2


def test_refresh_off_holds_every_step_until_the_stop_puts_the_cursor_back():
    md = _load()
    assert web_api.toggle_refresh_on_playback()["announce"] == "Region refresh off."
    session, _ = _started()

    held = web_api.play_cursor(session, 2, True, False)

    assert held == {"held": True, "arm_ms": None}
    assert md.active_event_index == 0
    web_api.play_toggle()
    assert md.active_event_index == 0


def test_a_loop_restart_is_never_held():
    md = _load()
    web_api.toggle_refresh_on_playback()
    session, _ = _started()

    result = web_api.play_cursor(session, 1, False, False)

    assert "held" not in result and md.active_event_index == 1


def test_a_positive_delay_arms_once_and_the_timer_shows_the_latest_step():
    md = _load()
    md.refresh_settings = RefreshSettings(True, 300)
    session, _ = _started()

    assert web_api.play_cursor(session, 1, True, False) == {"held": True, "arm_ms": 300}
    assert web_api.play_cursor(session, 2, True, True) == {"held": True, "arm_ms": None}
    assert md.active_event_index == 0

    shown = web_api.play_refresh(session)

    assert md.active_event_index == 2
    assert shown["regions"]["6"][0]["text"].startswith("Measure 1 beat 3")
    assert web_api.play_refresh(session) == {"idle": True}


def test_pause_drops_the_held_step_and_lands_on_the_paused_one():
    md = _load()
    md.refresh_settings = RefreshSettings(False, 0)
    session, entries = _started()
    steps = [e for e in entries if e["kind"] == "step"]
    web_api.play_cursor(session, 3, True, False)

    assert web_api.play_pause(session, steps[1]["seq"])["paused"] is True

    assert md.active_event_index == 1
    assert web_api.play_refresh(session) == {"idle": True}


def test_a_negative_delay_holds_the_sounds_back_not_the_cursor():
    md = _load()
    md.refresh_settings = RefreshSettings(True, -200)
    session, entries = _started()
    json.dumps(entries)

    steps = [e for e in entries if e["kind"] == "step"]
    assert [e["at"] for e in steps] == [0, 500, 1000, 1500]
    assert [e["sound_at"] for e in steps] == [200, 700, 1200, 1700]
    end = entries[-1]
    assert end["kind"] == "end" and end["at"] == end["sound_at"]
    assert "held" not in web_api.play_cursor(session, 1, True, False)


def test_a_negative_delay_runs_the_count_in_straight_into_the_first_note():
    md = _load()
    md.play_settings = md.play_settings.with_lead_in_enabled(True)
    plain_session, plain = _started()
    first_plain = next(e for e in plain if e["kind"] == "step")["at"]
    web_api.play_toggle()

    md.refresh_settings = RefreshSettings(True, -200)
    _, shifted = _started()
    first = next(e for e in shifted if e["kind"] == "step")

    assert first["sound_at"] == first_plain
    assert first["at"] == first_plain - 200


def test_toggling_while_a_step_is_held_shows_it_at_once():
    md = _load()
    web_api.toggle_refresh_on_playback()
    session, _ = _started()
    web_api.play_cursor(session, 2, True, False)

    on = web_api.toggle_refresh_on_playback()

    assert on["announce"] == "Region refresh on."
    assert md.active_event_index == 2 and "regions" in on


def test_the_toggle_shows_on_the_options_state_and_is_saved_with_the_score():
    md = _load()
    assert web_api.options_state()["refresh_on_playback"] is True

    web_api.toggle_refresh_on_playback()

    assert web_api.options_state()["refresh_on_playback"] is False
    assert json.loads(web_api.score_settings_json())["refresh_settings"] == {
        "refresh_during_playback": False, "delay_ms": 0}


def test_the_dialog_form_and_ok():
    md = _load()
    form = web_api.delay_refresh_form()
    assert [f["name"] for f in form["fields"]] == ["refresh_during_playback", "delay_seconds"]
    assert form["fields"][1]["value"] == 0.0 and form["enabled"] == {"delay_seconds": True}
    assert web_api.delay_refresh_enabled(False) == {"delay_seconds": False}

    web_api.apply_delay_refresh({"refresh_during_playback": True, "delay_seconds": "-0.25"})
    assert md.refresh_settings == RefreshSettings(True, -250)

    web_api.apply_delay_refresh({"refresh_during_playback": True, "delay_seconds": "9"})
    assert md.refresh_settings.delay_ms == 1000

    web_api.apply_delay_refresh({"refresh_during_playback": False, "delay_seconds": ""})
    assert md.refresh_settings == RefreshSettings(False, 1000)
