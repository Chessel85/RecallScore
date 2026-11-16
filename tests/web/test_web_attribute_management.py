"""Attribute Management through the bridge (web_api.attribute_*)."""
import json
from pathlib import Path

import web_api


def _load(path):
    path = Path(path)
    assert web_api.load(path.read_bytes(), path.name)["ok"]


def _node():
    return web_api._region_2.roots[0].node_id


def test_form_lists_the_part_attributes(minimal_score):
    _load(minimal_score)
    form = web_api.attribute_management_form(_node(), "octave")
    json.dumps(form)
    keys = [r["key"] for r in form["rows"]]
    assert "octave" in keys
    assert form["rows"][form["current"]]["key"] == "octave"
    assert form["label"].startswith("Attribute order for ")
    step = next(r for r in form["rows"] if r["key"] == "step")
    assert step["text"] == "*step"  # shown in the note list
    assert next(r for r in form["rows"] if r["key"] == "octave")["text"] == "octave"


def test_hide_then_unhide_and_cancel_restores(minimal_score):
    _load(minimal_score)
    form = web_api.attribute_management_form(_node(), None)
    part, key = form["part_id"], "octave"
    row = web_api.attribute_hide(part, key)["row"]
    assert row["text"] == "octave (hidden)"
    assert web_api.attribute_hide(part, key)["row"]["text"] == "octave"
    web_api.attribute_hide(part, key)
    row = web_api.attribute_hide_for_all(part, key)["row"]
    assert row["text"] == "octave (hidden for all)"
    web_api.attribute_management_cancel([0])
    assert not web_api._music_data.hidden_attributes_by_part.get(part)
    assert not web_api._music_data.hidden_attributes_for_all


def test_add_remove_marks_elevated_and_cannot_hide(minimal_score):
    _load(minimal_score)
    node = _node()
    form = web_api.attribute_management_form(node, "octave")
    part = form["part_id"]
    menu = web_api.attribute_add_remove_menu(node, "octave")
    assert menu["items"][0]["label"].startswith("Add to notes")
    row = web_api.attribute_add_remove_apply(node, "octave", menu["items"][-1]["scope"])["row"]
    assert row["elevated"] and row["text"].startswith("*")
    assert "can't be hidden" in web_api.attribute_hide(part, "octave")["error"]
    result = web_api.attribute_management_cancel([0])
    assert result["regions"]["3"][0]["text"] == "C"


def test_ok_applies_the_order(minimal_score):
    _load(minimal_score)
    form = web_api.attribute_management_form(_node(), None)
    keys = [r["key"] for r in form["rows"]]
    result = web_api.attribute_management_apply(form["part_id"], list(reversed(keys)), [0])
    json.dumps(result)
    assert web_api._music_data.attribute_keys_for_part(form["part_id"]) == list(reversed(keys))


def test_no_score_gives_an_error():
    web_api.unload() if hasattr(web_api, "unload") else None
    assert "error" in web_api.attribute_management_form("part_X", None)
