"""Play commands and settings through the browser bridge (RSBV 4.3, 4.4):
the free metronome (Ctrl+Alt+Space), tempo (F, S, D), Ctrl+L, Ctrl+I,
Ctrl+R, the loop length keys and the Play Settings dialog. Wording and
rules come from models/, shared with the desktop."""
import json
from pathlib import Path

import web_api
from audio.metronome import METRONOME_ACCENT_NOTE, METRONOME_OFFBEAT_NOTE

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _load(name="minimal_4_4.musicxml"):
    path = FIXTURES / name
    assert web_api.load(path.read_bytes(), path.name)["ok"]
    return web_api._music_data


def _status(result=None, field=4):
    rows = result["regions"]["6"] if result else web_api.region_rows(6)
    return rows[field]["text"]


# --- free metronome -------------------------------------------------------------

def test_the_free_metronome_clicks_each_beat_with_the_downbeat_accented():
    _load()

    started = web_api.play_metronome()

    assert started["action"] == "start"
    assert _status(started) == "Playback: Stopped"  # not playback, as on the desktop
    entries = web_api.play_plan(started["session"], 2001)["entries"]
    json.dumps(entries)
    assert [e["at"] for e in entries] == [0, 500, 1000, 1500, 2000]
    assert {e["kind"] for e in entries} == {"click"}
    assert all(e["cursor"] is None for e in entries)
    pitches = [e["sound"]["oneshots"][0]["event"][3] for e in entries]
    assert pitches == [METRONOME_ACCENT_NOTE] + [METRONOME_OFFBEAT_NOTE] * 3 + [METRONOME_ACCENT_NOTE]
    assert all(e["sound"]["oneshots"][0]["slot"] == "click" for e in entries)


def test_the_free_metronome_picks_up_a_tempo_change_on_the_next_planned_beat():
    _load()
    session = web_api.play_metronome()["session"]
    web_api.play_plan(session, 1)  # beat at 0, next due at 500

    web_api.tempo("reset")
    web_api._music_data.set_playback_tempo_display_bpm(60)

    entries = web_api.play_plan(session, 2600)["entries"]
    assert [e["at"] for e in entries] == [500, 1500, 2500]


def test_ctrl_alt_space_again_or_space_stops_the_free_metronome_without_moving():
    md = _load()
    session = web_api.play_metronome()["session"]
    md.active_event_index = 2

    assert web_api.play_metronome()["action"] == "stop"
    assert web_api.play_plan(session, 1000) == {"stale": True}

    web_api.play_metronome()
    stopped = web_api.play_toggle()
    assert stopped["action"] == "stop"
    assert md.active_event_index == 2
    assert web_api.play_toggle()["action"] == "start"  # Space now plays


def test_the_free_metronome_cannot_pause():
    _load()
    session = web_api.play_metronome()["session"]
    web_api.play_plan(session, 1000)
    assert web_api.play_pause(session, 1) == {"paused": False}


def test_the_free_metronome_is_unavailable_while_playback_is_going():
    """The desktop greys out Play Metronome then, so the Menu shows it as
    unavailable and its key does nothing (user's decision, 2026-10-14)."""
    md = _load()
    assert web_api.disabled_commands() == []
    play = web_api.play_toggle()["session"]
    web_api.play_plan(play, 600)
    web_api.play_cursor(play, 1)

    assert web_api.disabled_commands() == ["play.metronome"]
    assert web_api.play_metronome() == {"action": "none"}
    assert md.active_event_index == 1
    assert web_api.play_plan(play, 1200)["entries"]  # playback carries on

    web_api.play_pause(play, 2)
    assert web_api.disabled_commands() == ["play.metronome"]
    web_api.play_stop()
    assert web_api.disabled_commands() == []


def test_the_running_free_metronome_leaves_play_metronome_available_to_stop_it():
    _load()
    web_api.play_metronome()
    assert web_api.disabled_commands() == []


# --- tempo ------------------------------------------------------------------------

def test_f_s_d_change_the_tempo_and_say_the_new_number():
    md = _load()
    start = md.playback_tempo_display_bpm()

    faster = web_api.tempo("faster")
    assert faster["announce"] == f"{int(start) + 10}."
    assert md.playback_tempo_display_bpm() == start + 10

    assert web_api.tempo("slower")["announce"] == f"{int(start)}."
    web_api.tempo("slower")
    reset = web_api.tempo("reset")
    assert md.playback_tempo_display_bpm() == start
    assert reset["regions"]["6"] == web_api.region_rows(6)


# --- Ctrl+L, Ctrl+I, Ctrl+R, loop length ---------------------------------------------

def test_ctrl_l_cycles_the_play_mode():
    md = _load()
    said = [web_api.play_setting("play_mode")["announce"] for _ in range(3)]
    assert said == [
        "Play mode: play loop once.",
        "Play mode: play loop until stopped.",
        "Play mode: play to end.",
    ]
    assert md.play_settings.play_mode == "to_end"


def test_ctrl_i_toggles_the_lead_in():
    md = _load()
    assert web_api.play_setting("lead_in")["announce"] == "Lead in on"
    assert md.play_settings.lead_in_enabled
    assert web_api.play_setting("lead_in")["announce"] == "Lead in off"


def test_ctrl_r_says_why_it_does_nothing():
    md = _load()
    assert web_api.play_setting("loop_repeat") == {"announce": "Looping is off"}
    web_api.play_setting("play_mode")
    assert web_api.play_setting("loop_repeat") == {"announce": "This score has no repeats"}
    assert md.play_settings.loop_repeat_mode == "first"


def test_ctrl_r_cycles_repeat_handling_on_a_score_with_repeats():
    md = _load("repeats_and_endings.musicxml")
    web_api.play_setting("play_mode")
    result = web_api.play_setting("loop_repeat")
    assert result["announce"] == "Loop repeat handling: repeat the second play-through."
    assert md.play_settings.loop_repeat_mode == "second"


def test_alt_page_up_and_down_change_the_loop_length_within_its_bounds():
    md = _load()
    longer = web_api.play_setting("loop_longer")
    assert longer["announce"] == "Loop length 2 measures."
    assert _status(longer, 7) == "Loop length: 2 measures"
    web_api.play_setting("loop_shorter")
    assert web_api.play_setting("loop_shorter")["announce"] == "Loop length 1 measure."
    assert md.play_settings.loop_length_bars == 1


def test_ctrl_enter_sets_the_typed_number_as_the_loop_length():
    md = _load()
    assert web_api.commit_loop_length() == {"pending": False}

    web_api.append_digit("4")
    off = web_api.commit_loop_length()
    assert off["announce"] == "Looping is off" and off["pending"] is True
    assert md.play_settings.loop_length_bars == 1

    web_api.play_setting("play_mode")
    web_api.append_digit("1")
    web_api.append_digit("2")
    result = web_api.commit_loop_length()
    assert result["announce"] == "Loop length 12 measures."
    assert md.play_settings.loop_length_bars == 12
    assert not _status(result, 0).startswith("Go to")  # the typed number is gone


# --- Play Settings dialog ----------------------------------------------------------------

def test_the_form_has_the_desktop_fields_in_tab_order_with_current_values():
    md = _load()
    form = web_api.play_settings_form()
    json.dumps(form)
    names = [f["name"] for f in form["fields"]]
    assert names == [
        "tempo", "lead_in_enabled", "lead_in_bars", "lead_in_beats",
        "play_mode", "loop_length_bars", "loop_repeat_mode", "loop_lead_in",
    ]
    fields = {f["name"]: f for f in form["fields"]}
    assert fields["tempo"]["value"] == round(md.playback_tempo_display_bpm())
    assert fields["lead_in_enabled"]["label"] == "Play a lead-in metronome click"  # no "&"
    assert fields["loop_length_bars"]["label"] == "Loop length in measures:"
    assert [o["label"] for o in fields["play_mode"]["options"]][0] == "Play to end"
    assert form["enabled"]["lead_in_bars"] is False  # lead-in is off by default
    assert form["enabled"]["loop_length_bars"] is False  # play to end


def test_enabled_states_follow_lead_in_and_play_mode():
    _load()
    states = web_api.play_settings_enabled(True, "loop_forever")
    assert states == {
        "lead_in_bars": True, "lead_in_beats": True, "loop_length_bars": True,
        "loop_repeat_mode": False,  # no repeats in this score
        "loop_lead_in": True,
    }


def test_ok_applies_the_settings_and_the_tempo_clamped():
    md = _load()
    result = web_api.apply_play_settings({
        "tempo": "400", "lead_in_enabled": True, "lead_in_bars": "2", "lead_in_beats": "99",
        "play_mode": "loop_once", "loop_length_bars": "3", "loop_repeat_mode": "alternate",
        "loop_lead_in": False,
    })
    s = md.play_settings
    assert (s.lead_in_enabled, s.lead_in_bars, s.lead_in_beats) == (True, 2, 15)
    assert (s.play_mode, s.loop_length_bars, s.loop_repeat_mode) == ("loop_once", 3, "alternate")
    assert md.playback_tempo_display_bpm() == 300
    assert _status(result, 7) == "Loop length: 3 measures"


def test_an_empty_tempo_keeps_the_current_one():
    md = _load()
    before = md.playback_tempo_display_bpm()
    web_api.apply_play_settings({"tempo": "", "play_mode": "to_end"})
    assert md.playback_tempo_display_bpm() == before
