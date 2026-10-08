"""The browser bridge (web/py/web_api.py) in plain CPython: no browser, no music21."""
import json
from pathlib import Path

import pytest

import web_api

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
    assert result == {"moved": False, "boundary": True, "announce": None, "barline": None}


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
    assert web_api.move("right") == {"moved": False, "boundary": False, "announce": None, "barline": None}
    assert web_api.region_rows(3) == {"error": "No score is loaded."}
