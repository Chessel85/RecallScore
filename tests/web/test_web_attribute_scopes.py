"""Region 4's scope menu through the bridge (web_api.region4_menu/apply)."""
import json
from pathlib import Path

import web_api


def _load(path):
    path = Path(path)
    assert web_api.load(path.read_bytes(), path.name)["ok"]


def test_menu_lists_the_desktop_scopes(minimal_score):
    _load(minimal_score)
    menu = web_api.region4_menu(1, [0])  # row 1 = octave
    json.dumps(menu)
    assert menu["title"] == "octave"  # as Region 4's row names it
    assert [item["label"] for item in menu["items"]] == [
        "Add to notes in the whole score",
        "Add to notes in the same part",
        "Add to notes in same stave",
        "Add to notes for this voice",
    ]


def test_apply_adds_then_menu_offers_remove(minimal_score):
    _load(minimal_score)
    assert web_api.region_rows(3)[0]["text"] == "C"
    result = web_api.region4_apply(1, [0], "voice")
    json.dumps(result)
    assert result["regions"]["3"][0]["text"] == "C4"
    assert set(result["regions"]) == {"3", "4"}
    labels = [item["label"] for item in web_api.region4_menu(1, [0])["items"]]
    assert labels[-1] == "Remove for notes in current voice"
    result = web_api.region4_apply(1, [0], "voice")
    assert result["regions"]["3"][0]["text"] == "C"


def test_nothing_to_act_on(minimal_score):
    _load(minimal_score)
    assert web_api.region4_menu(99, [0]) == {"title": "", "items": []}
    assert "error" in web_api.region4_apply(99, [0], "voice")
    assert "error" in web_api.region4_apply(1, [0], "nonsense")
