"""Playback through the browser bridge (Space, Ctrl+Space): web_api.play_*,
planned by models/play_plan.py's PlayTimeline. The timing itself is
checked against the desktop in tests/models/test_play_plan.py; this covers
the transport and the JSON the page gets."""
import json
from pathlib import Path

import web_api
from audio.boundary_cue import boundary_cue_event
from models.play_settings import PlaySettings

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _load(name="minimal_4_4.musicxml"):
    path = FIXTURES / name
    assert web_api.load(path.read_bytes(), path.name)["ok"]
    return web_api._music_data


def _status():
    return web_api.region_rows(6)[4]["text"]


def _all_entries(session):
    return web_api.play_plan(session, 10 ** 9)["entries"]


def test_space_plays_from_the_cursor_and_says_playing():
    md = _load()

    started = web_api.play_toggle()

    assert started["action"] == "start"
    assert started["regions"]["6"][4]["text"] == "Playback: Playing"
    entries = _all_entries(started["session"])
    json.dumps(entries)  # plain data only
    steps = [e for e in entries if e["kind"] == "step"]
    assert [e["cursor"] for e in steps] == [0, 1, 2, 3]
    assert [e["at"] for e in steps] == [0, 500, 1000, 1500]
    assert steps[0]["sound"]["stop"] is True and steps[1]["sound"]["stop"] is False
    assert steps[0]["sound"]["notes"][0]["pitches"] == [60]
    assert entries[-1]["kind"] == "end" and entries[-1]["cursor"] == 0
    assert md.active_event_index == 0


def test_the_cursor_follows_and_the_end_puts_it_back():
    md = _load()
    session = web_api.play_toggle()["session"]
    _all_entries(session)

    followed = web_api.play_cursor(session, 2)
    assert md.active_event_index == 2
    assert followed["regions"]["6"][0]["text"].startswith("Measure 1 beat 3")

    ended = web_api.play_ended(session)
    assert md.active_event_index == 0
    assert ended["regions"]["6"][4]["text"] == "Playback: Stopped"
    assert web_api.play_cursor(session, 3) == {"stale": True}


def test_a_second_space_stops_and_puts_the_cursor_back():
    md = _load()
    session = web_api.play_toggle()["session"]
    _all_entries(session)
    web_api.play_cursor(session, 2)

    stopped = web_api.play_toggle()

    assert stopped["action"] == "stop"
    assert md.active_event_index == 0
    assert web_api.play_plan(session, 10 ** 9) == {"stale": True}


def test_ctrl_space_pauses_on_the_heard_step_and_space_resumes_there():
    md = _load()
    session = web_api.play_toggle()["session"]
    steps = [e for e in _all_entries(session) if e["kind"] == "step"]
    web_api.play_cursor(session, steps[2]["cursor"])

    paused = web_api.play_pause(session, steps[2]["seq"])

    assert paused["paused"] is True
    assert md.active_event_index == 2
    assert _status() == "Playback: Paused"
    resumed = web_api.play_toggle()
    assert resumed["action"] == "resume" and resumed["session"] != session
    again = [e for e in _all_entries(resumed["session"]) if e["kind"] == "step"]
    assert [(e["at"], e["cursor"], e["sound"]["stop"]) for e in again] == [
        (0, 2, True), (500, 3, False)
    ]


def test_ctrl_space_during_the_count_in_does_nothing():
    md = _load()
    md.play_settings = PlaySettings(lead_in_enabled=True)
    session = web_api.play_toggle()["session"]
    assert _status() == "Playback: Lead-in"
    entries = _all_entries(session)
    count = next(e for e in entries if e["kind"] == "count")

    assert web_api.play_pause(session, count["seq"]) == {"paused": False}
    # The count-in always clicks, whatever the metronome toggle says.
    assert count["sound"]["oneshots"][0]["slot"] == "click"


def test_a_paused_looping_run_stops_on_space():
    md = _load("many_measures.musicxml")
    md.play_settings = PlaySettings(play_mode="loop_forever", loop_length_bars=1)
    session = web_api.play_toggle()["session"]
    step = next(e for e in web_api.play_plan(session, 5000)["entries"] if e["kind"] == "step")
    assert web_api.play_pause(session, step["seq"])["paused"] is True

    assert web_api.play_toggle()["action"] == "stop"


def test_a_move_while_paused_drops_to_stopped_where_the_cursor_lands():
    md = _load()
    session = web_api.play_toggle()["session"]
    steps = [e for e in _all_entries(session) if e["kind"] == "step"]
    web_api.play_pause(session, steps[1]["seq"])

    moved = web_api.move("right")

    assert moved["transport"] == "stopped"
    assert md.active_event_index == 2
    assert moved["regions"]["6"][4]["text"] == "Playback: Stopped"


def test_space_on_the_last_note_sounds_the_boundary_cue():
    md = _load()
    md.move_timeline_end()

    result = web_api.play_toggle()

    assert result["action"] == "boundary"
    assert result["sound"]["oneshots"][0]["event"] == list(boundary_cue_event())


def test_loading_a_score_stops_playback():
    _load()
    session = web_api.play_toggle()["session"]

    _load()

    assert web_api.play_plan(session, 1000) == {"stale": True}
    assert _status() == "Playback: Stopped"
