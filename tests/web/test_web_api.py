"""The browser bridge (web/py/web_api.py) in plain CPython: no browser, no music21."""
import json
from pathlib import Path

import pytest

import web_api
from audio.barline_patterns import plain_barline_event
from audio.boundary_cue import boundary_cue_event

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _load(path: Path):
    return web_api.load(path.read_bytes(), path.name)


@pytest.mark.parametrize("path", [
    FIXTURES / "chord.musicxml",
    FIXTURES / "chords_and_lyrics.musicxml",
    FIXTURES / "grace_note.musicxml",
    REPO_ROOT / "examples" / "bach-bourree-tab.mxl",
], ids=lambda p: p.name)
def test_load_returns_json_summary(path):
    result = _load(path)
    assert result["ok"] is True
    summary = result["summary"]
    json.dumps(summary)  # plain data only: JavaScript never holds Python objects
    assert isinstance(summary["credits"], dict)
    assert summary["slices"] > 0
    assert summary["parts"]
    for part in summary["parts"]:
        assert set(part) == {"part_id", "name"}


def test_chords_and_lyrics_fixture_reports_its_parts():
    summary = _load(FIXTURES / "chords_and_lyrics.musicxml")["summary"]
    assert len(summary["parts"]) >= 2


def test_summary_matches_last_load():
    _load(FIXTURES / "chord.musicxml")
    first = web_api.score_summary()
    _load(REPO_ROOT / "examples" / "bach-bourree-tab.mxl")
    assert web_api.score_summary() != first


def test_broken_file_returns_error_dict_and_keeps_previous_score():
    _load(FIXTURES / "chord.musicxml")
    before = web_api.score_summary()
    result = web_api.load(b"<not-a-score", "broken.musicxml")
    assert set(result) == {"error"}
    assert "broken.musicxml" in result["error"]
    assert web_api.score_summary() == before


def test_unsupported_suffix_returns_error_dict():
    result = web_api.load(b"data", "song.pdf")
    assert set(result) == {"error"}
    assert ".musicxml" in result["error"]


def test_summary_without_a_score_is_an_error(monkeypatch):
    monkeypatch.setattr(web_api, "_music_data", None)
    assert web_api.score_summary() == {"error": "No score is loaded."}


# --- regions and navigation (RSBV 2.2) ---------------------------------------

def test_load_returns_every_region_as_plain_rows():
    result = _load(FIXTURES / "rehearsal_mark.musicxml")
    view = result["view"]
    json.dumps(view)
    assert set(view["regions"]) == {"1", "2", "3", "4", "5", "6"}
    for key in ("1", "3", "4", "5", "6"):
        assert all(isinstance(row["text"], str) for row in view["regions"][key])
    # Region 3 selects every row after a load or move (invariant 10's intent).
    assert view["selection"] == list(range(len(view["regions"]["3"])))
    assert len(view["regions"]["6"]) == 8


def test_region_2_is_the_shared_tree_with_status_labels():
    tree = _load(FIXTURES / "two_parts_chord.musicxml")["view"]["regions"]["2"]
    assert [node["type"] for node in tree] == ["part", "part"]
    staff = tree[0]["children"][0]
    assert staff["type"] == "staff"
    assert staff["children"][0]["type"] == "voice"
    assert staff["children"][0]["children"] == []


def test_regions_match_the_desktop_accessors():
    _load(FIXTURES / "chord.musicxml")
    md = web_api._music_data
    assert [r["text"] for r in web_api.region_rows(3)] == md.get_region_3_data()
    assert [r["text"] for r in web_api.region_rows(6)][:4] == md.get_status_bar_fields()
    region_4 = md.get_region_4_rows_for_region_3_selection([0])
    assert [r["text"] for r in web_api.region_rows(4, [0])] == [f"{k}: {v}" for k, _a, v in region_4]


def test_region_4_follows_the_selection():
    _load(FIXTURES / "rehearsal_mark.musicxml")  # two notes at the first position
    everything = web_api.region_rows(4)
    first_only = web_api.selection_changed([0])["regions"]["4"]
    assert first_only != everything


def test_plain_step_reports_a_crossed_bar_line():
    _load(FIXTURES / "many_measures.musicxml")
    result = web_api.move("right")
    assert result["moved"] and not result["boundary"]
    assert result["barline"] == [1, 2]
    assert result["announce"] is None
    assert set(result["regions"]) == {"3", "4", "5", "6"}
    assert result["regions"]["6"][0]["text"] == "Measure 2 beat 1"


def test_step_past_the_start_sounds_the_boundary_and_sends_nothing():
    _load(FIXTURES / "many_measures.musicxml")
    result = web_api.move("left")
    sound = result.pop("sound")
    assert result == {"moved": False, "boundary": True, "announce": None, "barline": None}
    assert sound["stop"] is False and sound["notes"] == []
    assert sound["oneshots"] == [{"slot": "boundary", "event": list(boundary_cue_event()), "delay_ms": 0}]


def test_bar_moves_and_ends_speak_the_bar():
    _load(FIXTURES / "many_measures.musicxml")
    assert web_api.move("bar_right")["announce"] == "Measure 2."
    last = web_api.move("last")
    assert last["moved"] and not last["boundary"]
    assert last["announce"].startswith("Measure ")
    assert web_api.move("first")["announce"] == "Measure 1."


def test_uk_terms_say_bar():
    web_api.set_uk_terms(True)
    try:
        _load(FIXTURES / "many_measures.musicxml")
        assert web_api.goto_bar(3)["announce"] == "Bar 3."
    finally:
        web_api.set_uk_terms(False)


def test_goto_unknown_bar_is_a_boundary():
    _load(FIXTURES / "many_measures.musicxml")
    assert web_api.goto_bar(999)["boundary"] is True
    assert web_api.goto_bar(2)["moved"] is True


def test_jump_point_steps_to_a_rehearsal_mark():
    _load(FIXTURES / "rehearsal_mark.musicxml")
    md = web_api._music_data
    targets = sorted(
        md.first_visible_event_index_of_measure(m.measure)
        for m in md.direction_marks if m.kind == "rehearsal"
    )
    ahead = [i for i in targets if i > md.active_event_index]
    result = web_api.jump_point(1)
    assert result["moved"] is bool(ahead)
    if ahead:
        assert md.active_event_index == ahead[0]


def test_section_step_resends_every_region_and_is_spoken():
    view = _load(FIXTURES / "two_sections.musicxml")["view"]
    assert view["regions"]["1"][0] == {"text": "Exercise 1, section 1 of 2", "kind": "section"}
    assert web_api.section(-1)["boundary"] is True
    result = web_api.section(1)
    assert result["announce"] == "Exercise 2, section 2 of 2."
    assert set(result["regions"]) == {"1", "2", "3", "4", "5", "6"}
    assert web_api.section(1)["boundary"] is True


def test_attribute_announcement_reads_region_4_by_number():
    _load(FIXTURES / "minimal_4_4.musicxml")
    first = web_api.region_rows(4)[0]["text"]
    assert web_api.attribute_announcement(1) == first
    assert web_api.attribute_announcement(999) is None


def test_navigation_without_a_score_is_quiet(monkeypatch):
    monkeypatch.setattr(web_api, "_music_data", None)
    assert web_api.move("right") == {"moved": False, "boundary": False, "announce": None, "barline": None, "sound": None}
    assert web_api.region_rows(3) == {"error": "No score is loaded."}


# --- typed bar number and Go to bar (task 2.5) ---------------------------------

def test_goto_info_names_the_word_and_current_bar():
    _load(FIXTURES / "many_measures.musicxml")
    web_api.goto_bar(3)
    assert web_api.goto_info() == {"word": "Measure", "current": 3}


def test_typed_digits_show_in_region_6_and_enter_jumps():
    _load(FIXTURES / "many_measures.musicxml")
    first = web_api.append_digit("3")
    assert first["regions"]["6"][0]["text"] == "Go to measure: 3"
    assert web_api.append_digit("x") != first  # not a digit: ignored, no crash
    result = web_api.commit_digits()
    assert result["pending"] is True and result["moved"] is True
    assert result["announce"] == "Measure 3."
    assert web_api.region_rows(6)[0]["text"] != "Go to measure: 3"


def test_commit_with_nothing_typed_falls_through():
    _load(FIXTURES / "many_measures.musicxml")
    assert web_api.commit_digits() == {"pending": False}
    assert web_api.clear_digits() == {"pending": False}


def test_unknown_typed_bar_is_a_boundary_and_clears_region_6():
    _load(FIXTURES / "many_measures.musicxml")
    web_api.append_digit("9")
    web_api.append_digit("9")
    result = web_api.commit_digits()
    assert result["moved"] is False and result["boundary"] is True
    assert not result["regions"]["6"][0]["text"].startswith("Go to")


def test_a_move_cancels_a_half_typed_number():
    _load(FIXTURES / "many_measures.musicxml")
    web_api.append_digit("4")
    result = web_api.move("right")
    assert not web_api.region_rows(6)[0]["text"].startswith("Go to")
    assert web_api.commit_digits() == {"pending": False}
    assert result["moved"] in (True, False)


def test_backspace_cancels_a_typed_number():
    _load(FIXTURES / "many_measures.musicxml")
    web_api.append_digit("4")
    result = web_api.clear_digits()
    assert result["pending"] is True
    assert not result["regions"]["6"][0]["text"].startswith("Go to")


# --- Region 2 mute and solo (task 2.4) -----------------------------------------

def _two_part_view():
    view = _load(FIXTURES / "flute_crotchets_viola_semibreves.musicxml")["view"]
    return view["regions"]["2"]


def test_mute_puts_the_word_in_the_row_text_and_filters_region_3():
    tree = _two_part_view()
    assert len(tree) == 2
    before = web_api.region_rows(3)
    result = web_api.region2_toggle(tree[0]["id"], "mute")
    assert result["regions"]["2"][0]["text"].endswith(" muted")
    assert "announce" not in result  # the row text says it; nothing spoken
    assert result["regions"]["3"] != before
    assert set(result["regions"]) == {"2", "3", "4", "5", "6"}
    again = web_api.region2_toggle(tree[0]["id"], "mute")
    assert again["regions"]["3"] == before


def test_solo_and_clear_all_are_spoken():
    tree = _two_part_view()
    soloed = web_api.region2_toggle(tree[1]["id"], "solo")
    assert soloed["regions"]["2"][1]["text"].endswith(" soloed")
    web_api.region2_toggle(tree[0]["id"], "mute")
    cleared = web_api.region2_clear("solo")
    assert cleared["announce"] == "unsoloed all"
    texts = [row["text"] for row in cleared["regions"]["2"]]
    assert texts[0].endswith(" muted") and not texts[1].endswith("soloed")
    assert web_api.region2_clear("mute")["announce"] == "unmuted all"


def test_region2_toggle_rejects_bad_input():
    tree = _two_part_view()
    assert "error" in web_api.region2_toggle("no-such-node", "mute")
    assert "error" in web_api.region2_toggle(tree[0]["id"], "bogus")
    assert "error" in web_api.region2_clear("bogus")


# --- sound plans (Phase 3) ------------------------------------------------------

def test_a_move_sounds_the_new_slice_like_the_desktop():
    """The plan is exactly what PlaybackController.audition_selection would
    hand play_chord for the same MusicData and select-all."""
    _load(FIXTURES / "many_measures.musicxml")
    sound = web_api.move("right")["sound"]
    md = web_api._music_data
    rows = list(range(len(md.get_region_3_rows())))
    events = md.get_playback_events_for_indices(md.note_indices_from_selection(rows))
    assert events[0][1] == 0  # <midi-program>1</midi-program>, 0-indexed once (invariant 9)
    assert sound["stop"] is True
    assert [(n["channel"], n["program"], n["pitches"], n["ms"]) for n in sound["notes"]] == [
        (e[0], e[1], list(e[2]), e[3]) for e in events
    ]
    assert sound["oneshots"] == []  # metronome, announcer and indicator all start off
    json.dumps(sound)


def test_bar_line_indicator_sounds_after_the_audition_and_is_spoken():
    _load(FIXTURES / "many_measures.musicxml")
    toggled = web_api.toggle("bar_line_indicator")
    assert toggled["announce"] == "Bar line indicator on"
    assert set(toggled["regions"]) == {"6"}
    sound = web_api.move("right")["sound"]  # crosses bar 1 to 2
    assert sound["notes"]
    assert sound["oneshots"] == [{"slot": "click", "event": list(plain_barline_event()), "delay_ms": 0}]
    # Ctrl+Right is not a plain step: no indicator.
    assert web_api.move("bar_right")["sound"]["oneshots"] == []


def test_metronome_and_announcer_cue_each_move_in_their_own_slots():
    _load(FIXTURES / "many_measures.musicxml")
    assert web_api.toggle("metronome")["announce"] == "Metronome on"
    assert web_api.toggle("position_announcer")["announce"] == "Position announcer on"
    region_6 = [row["text"] for row in web_api.region_rows(6)]
    assert "Metronome: On" in region_6 and "Position Announcer: On" in region_6
    slots = [shot["slot"] for shot in web_api.move("right")["sound"]["oneshots"]]
    assert slots == ["click", "word"]


def test_audition_sounds_the_selection_with_or_without_position_cues():
    _load(FIXTURES / "rehearsal_mark.musicxml")  # two notes at the first position
    web_api.toggle("metronome")
    every = web_api.audition(None, True)["sound"]
    one = web_api.audition([0], False)["sound"]
    assert sum(len(n["pitches"]) for n in every["notes"]) == 2
    assert sum(len(n["pitches"]) for n in one["notes"]) == 1
    assert [s["slot"] for s in every["oneshots"]] == ["click"]
    assert one["oneshots"] == []


def test_grace_note_plan_carries_its_pre_note():
    _load(FIXTURES / "grace_note.musicxml")
    plans = [web_api.audition(None)["sound"]]
    while web_api.move("right")["moved"]:
        plans.append(web_api.audition(None)["sound"])
    graced = [p for p in plans if p["grace"]]
    assert graced and all(p["grace_ms"] > 0 for p in graced)


def test_toggle_rejects_bad_input_and_needs_a_score(monkeypatch):
    _load(FIXTURES / "chord.musicxml")
    assert "error" in web_api.toggle("loudness")
    monkeypatch.setattr(web_api, "_music_data", None)
    assert "error" in web_api.toggle("metronome")
    assert web_api.audition(None) == {"sound": None}


def test_synth_setup_pans_click_right_and_announcer_left():
    pans = dict(web_api.synth_setup()["pans"])
    assert pans[255] == 127 and pans[254] == 0
