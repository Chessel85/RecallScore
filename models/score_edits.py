# models/score_edits.py
"""The score edits behind the Instruments, Key Signature, Reorder Parts and
Link Parts dialogs, Region 2's Unlink and Parts > Collapse staves: what each
dialog lists and what applying its result does to MusicData.

Shared by the desktop's ScoreEditController and the web bridge
(web/py/web_api.py), so both versions edit a score the same way. Each apply
function changes MusicData only and says what changed; refreshing Region 2
and the other regions is the caller's job (the desktop's RegionPresenter,
the web page's renderer), and so is Region 2's own tree, which is mutated
in place, never rebuilt with fresh state (invariant 11).

Takes the MusicData per call and never keeps it (invariant 3).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# --- Instruments dialog (S5, wishlist #8) ------------------------------------

def instrument_rows(music_data) -> List[Tuple[str, str, int]]:
    """(part_id, current name, current GM program) per part - the
    dialog's main row list."""
    return [(p.part_id, p.name, p.gmidi_program) for p in music_data.parts_info]


def percussion_part_ids(music_data) -> List[str]:
    return [p.part_id for p in music_data.parts_info if p.is_percussion]


def percussion_toggle_part_ids(music_data) -> List[str]:
    """Parts the Instruments dialog may flag/un-flag as percussion: every
    part the file itself does not declare percussion (a part the user has
    flagged already still counts, so it can be un-flagged)."""
    flagged = music_data.part_percussion_overrides
    return [
        p.part_id for p in music_data.parts_info
        if not p.is_percussion or p.part_id in flagged
    ]


def percussion_rows(music_data) -> Dict[str, list]:
    """Per-item rows for each percussion part, keyed by part_id - a
    percussion part contributes one row per distinct drum/cymbal on top
    of its own part row (see MusicData.get_percussion_items_for_part)."""
    return {
        part_id: music_data.get_percussion_items_for_part(part_id)
        for part_id in percussion_part_ids(music_data)
    }


@dataclass
class InstrumentEdit:
    """What apply_instrument_overrides changed, for the caller's refresh.

    renamed_parts: part_id -> new name, for Region 2's part rows.
    structure_changed: a part was flagged or un-flagged as percussion, so
        Region 2's voice rows change shape and its tree must be rebuilt
        (carrying mute/solo/links across).
    percussion_changed: percussion item names may have changed; without a
        structure change, Region 2's percussion voice rows are renamed in
        place from voice_renames.
    """
    changed: bool = False
    renamed_parts: Dict[str, str] = field(default_factory=dict)
    structure_changed: bool = False
    percussion_changed: bool = False

    def voice_renames(self, music_data) -> List[Tuple[str, int, int, str]]:
        """(part_id, staff_id, voice_id, label) for every percussion voice
        row, read after the edit (apply_percussion_overrides re-ran
        _set_percussion_voice_names, so the labels are already current)."""
        return [
            (part.part_id, staff_id, voice_id, label)
            for part in music_data.parts_info if part.is_percussion
            for (staff_id, voice_id), label in part.voice_names.items()
        ]


def apply_instrument_overrides(
    music_data,
    name_overrides: Dict[str, str],
    program_overrides: Dict[str, int],
    item_name_overrides: Dict[Tuple[str, int], str],
    item_sound_overrides: Dict[Tuple[str, int], int],
    auto_correct_enabled: bool,
    part_percussion_changes: Optional[Dict[str, bool]] = None,
) -> InstrumentEdit:
    """Apply the Instruments dialog's five results. `changed` is False
    when nothing actually changed, so a dialog dismissed with no edits
    doesn't trigger a pointless rebuild."""
    part_percussion_changes = part_percussion_changes or {}
    structure_changed = bool(part_percussion_changes)
    percussion_changed = structure_changed or bool(
        item_name_overrides
        or item_sound_overrides
        or auto_correct_enabled != music_data.percussion_auto_correct_enabled
    )
    parts_changed = bool(name_overrides or program_overrides)
    if not (parts_changed or percussion_changed):
        return InstrumentEdit()

    if parts_changed:
        music_data.apply_part_overrides(name_overrides, program_overrides)

    if structure_changed:
        for part_id, flagged in part_percussion_changes.items():
            if flagged:
                music_data.part_percussion_overrides.add(part_id)
            else:
                music_data.part_percussion_overrides.discard(part_id)
        music_data.apply_part_percussion_overrides()

    if percussion_changed:
        music_data.percussion_item_name_overrides.update(item_name_overrides)
        music_data.percussion_item_overrides.update(item_sound_overrides)
        music_data.percussion_auto_correct_enabled = auto_correct_enabled
        # Recomputes every percussion item's effective sound AND its voice
        # label (apply_percussion_overrides ends by re-running
        # _set_percussion_voice_names).
        music_data.apply_percussion_overrides()

    return InstrumentEdit(
        changed=True,
        renamed_parts=dict(name_overrides),
        structure_changed=structure_changed,
        percussion_changed=percussion_changed,
    )


# --- Key Signature dialog (S6) -----------------------------------------------

def current_key_override(music_data) -> Tuple[Optional[int], Optional[str]]:
    """(fifths, mode) currently overridden, or (None, None) for "use the
    file's own key" - what the dialog opens on and compares against."""
    return (
        music_data.key_signature_override_fifths,
        music_data.key_signature_override_mode,
    )


def apply_key_signature_override(music_data, fifths: Optional[int], mode: Optional[str]) -> bool:
    """Set or clear the whole-piece key override. Returns whether it
    changed. Region 1 and the status bar show the key too, so the caller
    refreshes them as well as the note regions (for a MIDI score the
    override also re-spells every note, see
    OverrideManager.apply_key_signature_override)."""
    if (fifths, mode) == current_key_override(music_data):
        return False
    music_data.apply_key_signature_override(fifths, mode)
    return True


# --- Reorder Parts dialog ----------------------------------------------------

def part_rows(music_data) -> List[Tuple[str, str]]:
    """(part_id, name) per part, in current order - the dialog's list."""
    return [(p.part_id, p.name) for p in music_data.parts_info]


def current_part_order(music_data) -> List[str]:
    return [p.part_id for p in music_data.parts_info]


def reorder_parts(music_data, new_order: List[str]) -> bool:
    """Apply a new part order (MusicData.reorder_parts re-sorts every
    slice's notes). Returns whether it changed; the caller moves Region 2's
    rows in place to match."""
    if new_order == current_part_order(music_data):
        return False
    music_data.reorder_parts(new_order)
    return True


# --- Link Parts dialog (stage 9) and Region 2's Unlink -----------------------
#
# The dialog only ever CREATES one new group - a part already in a group
# can't join another, so link_dialog_rows omits it. Dissolving a group is
# Region 2's context menu's Unlink, a single-part action.

def link_dialog_rows(music_data) -> List[Tuple[str, str]]:
    """(part_id, part name) for every currently UNLINKED part, in
    current part order - the Link Parts dialog's row list."""
    return [
        (p.part_id, p.name) for p in music_data.parts_info
        if music_data.link_group_number(p.part_id) is None
    ]


def link_group_numbers(music_data) -> Dict[str, int]:
    """part_id -> group number for every currently linked part - what
    Region2HierarchyModel.apply_link_groups needs."""
    return {
        part_id: i + 1
        for i, group in enumerate(music_data.part_link_groups)
        for part_id in group
    }


def link_new_group(music_data, part_ids: List[str]) -> bool:
    """The Link Parts dialog's result. Fails (per PartLinks.link_parts)
    only if fewer than two distinct ids were checked. Returns whether it
    changed anything."""
    return bool(music_data.link_parts(part_ids))


def unlink_part(music_data, part_id: str) -> bool:
    """Dissolves `part_id` out of its link group (the whole group if that
    leaves fewer than two members). Returns whether anything changed."""
    return bool(music_data.unlink_part(part_id))


def can_unlink(music_data, part_id: Optional[str]) -> bool:
    """Whether Region 2's Unlink applies to this part: it is linked."""
    return part_id is not None and music_data.link_group_number(part_id) is not None


# --- Parts > Collapse staves -------------------------------------------------

def collapse_staves_state(music_data, part_id: Optional[str]) -> Tuple[bool, bool]:
    """(enabled, checked) for the Collapse staves menu item, given the
    part holding Region 2's current row (None for no row)."""
    if part_id is None or not music_data.is_stave_collapsible(part_id):
        return False, False
    return True, music_data.is_staves_collapsed(part_id)


def toggle_staves_collapsed(music_data, part_id: str) -> Optional[bool]:
    """Collapse or uncollapse `part_id`'s alternate stave. Returns the new
    collapsed state, or None when nothing changed (a part with none). The
    alternate stave's Region 2 rows come and go, so the caller rebuilds
    Region 2 carrying mute/solo/links across, and re-applies its voice
    filter, which drops (or restores) that stave's notes."""
    collapsed = not music_data.is_staves_collapsed(part_id)
    if not music_data.set_staves_collapsed(part_id, collapsed):
        return None
    return collapsed
