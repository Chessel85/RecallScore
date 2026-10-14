# models/attribute_scopes.py
"""Ref 15 AC4's attribute scope menu, without Qt: which add/remove scopes
Region 4's context menu (and the Attribute Management dialog's Add/Remove
button) offers, and how each is worded. Shared by the desktop's
AttributeController and the browser bridge, so the two can never drift onto
different wording or different scopes for the same action."""
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Broader-or-equal-to-node-level check for the Attribute Management dialog's
# Add/Remove button (filter_scopes_for_node_level below). Region2Node.node_type
# spells the middle level "staff", the attribute-scope vocabulary spells it
# "stave" (D-15's own dialect-free choice); these two dicts are the one place
# that difference has to be bridged.
SCOPE_LEVEL = {"voice": 0, "stave": 1, "part": 2, "score": 3}
NODE_TYPE_LEVEL = {"voice": 0, "staff": 1, "part": 2}


def scope_action_labels(already_present: bool) -> List[Tuple[str, str]]:
    """(scope, label) pairs for the four fan-out scopes, worded for either
    direction of the toggle. D-15: "stave" is deliberately not
    dialect-translated here."""
    if already_present:
        return [
            ("score", "Remove for notes in the whole score"),
            ("part", "Remove for notes in current part"),
            ("stave", "Remove for notes in current stave"),
            ("voice", "Remove for notes in current voice"),
        ]
    return [
        ("score", "Add to notes in the whole score"),
        ("part", "Add to notes in the same part"),
        ("stave", "Add to notes in same stave"),
        ("voice", "Add to notes for this voice"),
    ]


def filter_scopes_for_node_level(scopes: list, node_type: str) -> list:
    """Reported: the Attribute Management dialog can be opened at any Region 2
    level (voice/staff/part), but every scope was always offered regardless -
    "Add to notes for this voice" from a STAVE-level dialog with two voices
    underneath is genuinely ambiguous (which voice?). Only scopes at or
    broader than the dialog's own node level are unambiguous: a stave-level
    dialog offers stave/part/score; a part-level dialog offers only
    part/score. A voice-level dialog (the common case) is unaffected."""
    floor = NODE_TYPE_LEVEL.get(node_type, 0)
    return [(scope, label) for scope, label in scopes if SCOPE_LEVEL[scope] >= floor]


def filter_scopes_for_part(scopes: list, part_id: str, collapsed_part_ids) -> list:
    """Reported: a part with no real stave/voice concept underneath it (a MIDI
    track, a pure Ultimate Guitar import, or one of the synthetic Chords/
    Lyrics parts - see MusicData.collapsed_part_ids, the same check Region 2
    uses to decide whether to show a staff/voice tree under that part)
    offered "current voice"/"current stave" scopes that acted on exactly the
    same notes as "current part" - redundant menu clutter with nothing real
    behind it. Those two scopes are dropped for such a part; "part" and
    "score" still apply normally."""
    if collapsed_part_ids is True or part_id in collapsed_part_ids:
        return [(scope, label) for scope, label in scopes if scope not in ("voice", "stave")]
    return scopes


@dataclass(frozen=True)
class Region4ScopeMenu:
    """What Region 4's context menu offers for one row: the attribute it
    acts on, whether choosing a scope adds (True) or removes it, the
    (scope, label) entries in menu order, and the selected notes the change
    fans out from."""
    attribute_key: str
    add: bool
    scopes: List[Tuple[str, str]]
    notes: list


def region_4_scope_menu(music_data, selected_indices: List[int], row: int) -> Optional[Region4ScopeMenu]:
    """The menu for Region 4's row `row` while Region 3 has
    `selected_indices` selected, or None when there is nothing to act on.
    The row's anchor note decides "already present" (a chord's one-anchor
    simplification, as note_has_display_attribute makes)."""
    if not music_data:
        return None
    targets = music_data.get_region_4_row_targets(selected_indices)
    if not (0 <= row < len(targets)):
        return None
    attribute_key, anchor_note = targets[row]
    already_present = music_data.note_has_display_attribute(anchor_note, attribute_key)
    scopes = filter_scopes_for_part(
        scope_action_labels(already_present), anchor_note.part_id, music_data.collapsed_part_ids
    )
    return Region4ScopeMenu(
        attribute_key=attribute_key,
        add=not already_present,
        scopes=scopes,
        notes=music_data.notes_for_indices(selected_indices),
    )
