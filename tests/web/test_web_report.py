"""The Performance Report through the browser bridge (RSBV 6.3): the rows,
levels and which rows go somewhere, a Parts row selecting its Region 2
node, a marking row moving the cursor, the boundary cue for a target that
resolves nowhere. The rows are models/ (PerformanceRows), and the jump is
MusicData.report_row_index, shared with the desktop's jump_to_report_row."""
import json
from pathlib import Path

import web_api
from models.report_row import ReportRow

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _load(name):
    path = FIXTURES / name
    result = web_api.load(path.read_bytes(), path.name)
    assert result["ok"]


def _row(form, text):
    return next(i for i, row in enumerate(form["rows"]) if row["text"] == text)


def test_the_form_is_the_desktops_rows():
    _load("hairpins_two_parts.musicxml")
    form = web_api.report_form()
    json.dumps(form)
    rows = web_api._music_data.get_performance_report_rows()
    assert form["rows"] == [
        {"text": r.text, "level": r.level, "jumps": r.has_jump_target()} for r in rows
    ]
    assert form["rows"][_row(form, "Parts: 2")] == {"text": "Parts: 2", "level": 0, "jumps": False}


def test_a_parts_row_selects_the_part_in_region_2():
    _load("hairpins_two_parts.musicxml")
    md = web_api._music_data
    before = md.active_event_index
    form = web_api.report_form()
    result = web_api.report_choose(_row(form, "Cello: 8 notes"))
    cello = next(p for p in md.parts_info if p.name == "Cello")
    assert result["focus"] == 2
    assert result["node"] == f"part_{cello.part_id}"
    assert not result["moved"] and not result["boundary"]
    assert md.active_event_index == before


def test_a_marking_row_moves_the_cursor_there():
    _load("hairpins_two_parts.musicxml")
    md = web_api._music_data
    form = web_api.report_form()
    result = web_api.report_choose(_row(form, "Cello: Crescendo: Measure 1 beat 3 to Measure 2 beat 2"))
    assert result["focus"] == 3 and result["moved"]
    current = md.get_current_slice()
    assert (current.measure, current.beat_position) == (1, 3.0)
    assert result["regions"]["3"] and result["sound"]


def test_a_row_with_no_target_does_nothing():
    _load("hairpins_two_parts.musicxml")
    md = web_api._music_data
    before = md.active_event_index
    form = web_api.report_form()
    result = web_api.report_choose(_row(form, "Dynamics: 2"))
    assert "focus" not in result
    assert not result["moved"] and not result["boundary"] and result["sound"] is None
    assert md.active_event_index == before


def test_a_target_that_resolves_nowhere_sounds_the_boundary_cue():
    _load("minimal_4_4.musicxml")
    web_api.report_form()
    web_api._report_rows = [ReportRow(text="bogus", level=1, jump_index=9999)]
    result = web_api.report_choose(0)
    assert "focus" not in result
    assert not result["moved"] and result["boundary"]
    assert result["sound"]["oneshots"][0]["slot"] == "boundary"


def test_a_barline_mark_jumps_to_its_own_index():
    _load("stage7_barline_jump_marks.musicxml")
    md = web_api._music_data
    form = web_api.report_form()
    row = _row(form, "Coda: Measure 2")
    result = web_api.report_choose(row)
    assert result["moved"]
    assert md.active_event_index == web_api._report_rows[row].jump_index


def test_no_score():
    web_api._music_data = None
    assert "error" in web_api.report_form()
    assert web_api.report_choose(0)["moved"] is False
