# models/attribute_management.py
"""The Attribute Management dialog's logic, without Qt (Ref 15 AC4): the
rows it lists, the hide / hide-for-all toggles and their refusal wording,
and the Add/Remove scope choices. Shared by the desktop's AttributeController
and the browser bridge, so the two can't drift apart."""
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from models.attribute_scopes import (
    filter_scopes_for_node_level, filter_scopes_for_part, scope_action_labels,
)
from models.region2_manager import voice_tuples_for_node
from models.vocabulary import attribute_label


def part_name(music_data, part_id: str) -> str:
    for p in music_data.parts_info:
        if p.part_id == part_id:
            return p.name
    return part_id


def hidden_state(music_data, part_id: str, attribute_key: str) -> str:
    """"all" / "part" / "visible"."""
    if attribute_key in music_data.hidden_attributes_for_all:
        return "all"
    if attribute_key in music_data.hidden_attributes_by_part.get(part_id, set()):
        return "part"
    return "visible"


def order_rows_for_part(music_data, part_id: str) -> List[Tuple[str, str, bool, str]]:
    """(attribute_key, label, elevated, hidden_state) in current order for
    every attribute present anywhere in `part_id`. `elevated` is part-local
    (any of the four add/remove scopes, anywhere under the part)."""
    return [
        (
            key,
            attribute_label(key, music_data.uk_terms),
            music_data.attribute_elevated_for_part(key, part_id),
            hidden_state(music_data, part_id, key),
        )
        for key in music_data.attribute_keys_for_part(part_id)
    ]


@dataclass
class Toggle:
    """The outcome of a hide toggle: `error` is the refusal message (the
    model is untouched), else `undo` puts the model back."""
    error: Optional[str] = None
    undo: Optional[Callable[[], None]] = None


def toggle_hidden_for_part(music_data, part_id: str, attribute_key: str) -> Toggle:
    """Hide or unhide `attribute_key` for `part_id`, whichever the live
    state calls for."""
    md = music_data
    if attribute_key in md.hidden_attributes_by_part.get(part_id, set()):
        md.set_attribute_hidden_for_part(attribute_key, part_id, False)
        return Toggle(undo=lambda: md.set_attribute_hidden_for_part(attribute_key, part_id, True))
    if not md.set_attribute_hidden_for_part(attribute_key, part_id, True):
        label = attribute_label(attribute_key, md.uk_terms)
        return Toggle(error=f"{label} can't be hidden while it's shown in the note list.")
    return Toggle(undo=lambda: md.set_attribute_hidden_for_part(attribute_key, part_id, False))


def toggle_hidden_for_all(music_data, attribute_key: str) -> Toggle:
    """Hide or unhide `attribute_key` for the whole score."""
    md = music_data
    if attribute_key in md.hidden_attributes_for_all:
        md.set_attribute_hidden_for_all(attribute_key, False)
        return Toggle(undo=lambda: md.set_attribute_hidden_for_all(attribute_key, True))
    if not md.set_attribute_hidden_for_all(attribute_key, True):
        label = attribute_label(attribute_key, md.uk_terms)
        names = ", ".join(part_name(md, p) for p in md.attribute_elevated_parts(attribute_key))
        return Toggle(error=(
            f"{label} can't be hidden for the whole score while it's "
            f"shown in the note list for: {names}."
        ))
    return Toggle(undo=lambda: md.set_attribute_hidden_for_all(attribute_key, False))


@dataclass(frozen=True)
class OrderScopeMenu:
    """The Add/Remove button's choices: (scope, label) pairs, whether a
    choice adds (True) or removes, and the voice they fan out from."""
    scopes: List[Tuple[str, str]]
    add: bool
    part_id: str
    staff: int
    voice: int


def order_scope_menu(music_data, node, attribute_key: str) -> Optional[OrderScopeMenu]:
    """None when there is nothing to act on. "Already present" is read off
    the lowest-sorted voice under `node`."""
    if not music_data or node is None:
        return None
    voice_tuples = voice_tuples_for_node(node)
    if not voice_tuples:
        return None
    part_id, staff, voice = sorted(voice_tuples)[0]
    already_present = music_data.display_attribute_present_for_voice(
        attribute_key, part_id, staff, voice
    )
    scopes = scope_action_labels(already_present)
    scopes = filter_scopes_for_node_level(scopes, node.node_type)
    scopes = filter_scopes_for_part(scopes, part_id, music_data.collapsed_part_ids)
    return OrderScopeMenu(scopes, not already_present, part_id, staff, voice)
