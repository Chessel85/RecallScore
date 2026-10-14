"""models/attribute_scopes.py: the Region 4 scope menu's wording and filters,
shared by the desktop's AttributeController and the browser bridge."""
from models.attribute_scopes import (
    filter_scopes_for_node_level, filter_scopes_for_part, region_4_scope_menu, scope_action_labels,
)
from models.music_data import MusicData


def _scopes(pairs):
    return [scope for scope, _ in pairs]


def test_labels_flip_with_presence():
    assert scope_action_labels(False)[0] == ("score", "Add to notes in the whole score")
    assert scope_action_labels(True)[-1] == ("voice", "Remove for notes in current voice")
    assert _scopes(scope_action_labels(False)) == ["score", "part", "stave", "voice"]


def test_node_level_keeps_scopes_at_or_above_it():
    labels = scope_action_labels(False)
    assert _scopes(filter_scopes_for_node_level(labels, "voice")) == ["score", "part", "stave", "voice"]
    assert _scopes(filter_scopes_for_node_level(labels, "staff")) == ["score", "part", "stave"]
    assert _scopes(filter_scopes_for_node_level(labels, "part")) == ["score", "part"]


def test_collapsed_part_drops_voice_and_stave():
    labels = scope_action_labels(False)
    assert _scopes(filter_scopes_for_part(labels, "P1", {"P1"})) == ["score", "part"]
    assert _scopes(filter_scopes_for_part(labels, "P1", True)) == ["score", "part"]
    assert _scopes(filter_scopes_for_part(labels, "P1", {"P2"})) == ["score", "part", "stave", "voice"]


def test_region_4_menu_for_a_row(minimal_score):
    md = MusicData(file_path=minimal_score)
    menu = region_4_scope_menu(md, [0], 1)  # row 1 = octave
    assert menu.attribute_key == "octave"
    assert menu.add is True
    assert _scopes(menu.scopes) == ["score", "part", "stave", "voice"]
    assert len(menu.notes) == 1


def test_region_4_menu_out_of_range_or_no_score(minimal_score):
    md = MusicData(file_path=minimal_score)
    assert region_4_scope_menu(md, [0], 99) is None
    assert region_4_scope_menu(None, [0], 0) is None
