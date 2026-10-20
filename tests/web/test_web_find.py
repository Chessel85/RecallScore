"""Find through the browser bridge (RSBV 6.2): the dialog's rows, OK
arming a target and jumping, Alt+Right/Left stepping, the boundary cue
with nothing armed or on a wrap. The targets, counts and row wording are
models/ (FindIndex, find_target.py), shared with the desktop's FindDialog."""
import json
from pathlib import Path

import pytest

import web_api
from models.find_target import find_row_label, find_row_text

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
SCORE = "dynamics_articulation_fingering.musicxml"


@pytest.fixture(autouse=True)
def _nothing_armed():
    web_api._find_target = None
    yield
    web_api._find_target = None


def _load(name=SCORE):
    path = FIXTURES / name
    result = web_api.load(path.read_bytes(), path.name)
    assert result["ok"]


def _row(form, text_start):
    return next(i for i, row in enumerate(form["rows"]) if row["text"].startswith(text_start))


def _slots(result):
    return [shot["slot"] for shot in result["sound"]["oneshots"]]


def test_the_form_lists_the_desktops_rows_with_counts():
    _load()
    form = web_api.find_form()
    json.dumps(form)
    pairs = web_api._music_data.available_find_targets_with_counts()
    assert [row["text"] for row in form["rows"]] == [find_row_text(t, c) for t, c in pairs]
    assert [row["filter"] for row in form["rows"]] == [find_row_label(t).lower() for t, _ in pairs]
    assert "Attribute: articulation: staccato, 1 occurrence" in [row["text"] for row in form["rows"]]


def test_ok_arms_the_target_and_jumps_forward_from_the_cursor():
    _load()
    md = web_api._music_data
    assert md.get_current_slice().beat_position == 1.0
    form = web_api.find_form()
    result = web_api.find_choose(_row(form, "Attribute: articulation (any)"))
    assert result["moved"] and not result["boundary"]
    assert md.get_current_slice().beat_position == 2.0
    assert web_api._find_target.key == "articulation"
    assert result["regions"]["3"] and "boundary" not in _slots(result)


def test_with_nothing_armed_next_is_the_boundary_cue():
    _load()
    result = web_api.find_step(1)
    assert not result["moved"] and result["boundary"]
    assert _slots(result) == ["boundary"]
    assert web_api._music_data.active_event_index == 0


def test_a_single_occurrence_wraps_onto_itself_with_the_boundary_cue_after_the_note():
    _load()
    web_api.find_choose(_row(web_api.find_form(), "Attribute: articulation (any)"))
    index = web_api._music_data.active_event_index
    for direction in (1, -1):
        result = web_api.find_step(direction)
        assert result["moved"] and result["boundary"]
        assert result["sound"]["notes"], "the note sounds first"
        assert _slots(result)[-1] == "boundary"
        assert web_api._music_data.active_event_index == index


def test_the_armed_target_outlives_a_load():
    _load()
    web_api.find_choose(_row(web_api.find_form(), "Attribute: articulation (any)"))
    _load("hairpins_two_parts.musicxml")
    assert web_api._find_target.key == "articulation"
    result = web_api.find_step(1)
    assert not result["moved"] and result["boundary"]


def test_a_row_out_of_range_does_nothing():
    _load()
    web_api.find_form()
    result = web_api.find_choose(999)
    assert not result["moved"] and web_api._find_target is None


def test_no_score():
    web_api._music_data = None
    assert "error" in web_api.find_form()
    assert web_api.find_step(1)["moved"] is False
