# models/part_links.py
"""PITweaksImplementationPlan.md stage 7 (item 1), applied per
PerformanceMarkingsImplementationPlanV2.md stage 9: marking a group of parts
as "the same music" so each shows the others' performance markings in the
note list (models/marking_rows.py) - display only, never touching
parts_info.name or NoteData.part_name (invariant 8).

Membership is by part_id only. Rules live as plain module functions so
widgets/link_parts_dialog.py's working copy can run the exact same
validation as the live MusicData.part_link_groups (invariant 8) without
importing Qt into this Qt-free module. `PartLinks` wraps them as one-line
MusicData delegators (invariant 4).

Group number = 1 + its index in the outer list, in creation order.
Dissolving a group (unlinking down to fewer than two members) closes the
gap - later groups renumber down by one, per the user's 2026-09-14
decision."""
from typing import List, Optional


def link_parts(groups: List[List[str]], known_part_ids: List[str], part_ids: List[str]) -> bool:
    """Appends a new group of part_ids to `groups` in place. Refuses (no
    change, returns False) when fewer than two distinct ids are given, any
    id isn't a real part, or any id is already linked."""
    distinct = list(dict.fromkeys(part_ids))
    if len(distinct) < 2:
        return False
    known = set(known_part_ids)
    if any(pid not in known for pid in distinct):
        return False
    already_linked = {pid for group in groups for pid in group}
    if any(pid in already_linked for pid in distinct):
        return False
    groups.append(distinct)
    return True


def unlink_part(groups: List[List[str]], part_id: str) -> bool:
    """Removes `part_id` from whichever group holds it, in place. Drops the
    group entirely (renumbering every later group down by one, since group
    number is just list position) if that leaves it under two members.
    Returns False if `part_id` wasn't linked at all."""
    for i, group in enumerate(groups):
        if part_id in group:
            group.remove(part_id)
            if len(group) < 2:
                groups.pop(i)
            return True
    return False


def link_group_number(groups: List[List[str]], part_id: str) -> Optional[int]:
    for i, group in enumerate(groups):
        if part_id in group:
            return i + 1
    return None


def link_partners(groups: List[List[str]], part_id: str) -> List[str]:
    """Every OTHER part_id in `part_id`'s group, in that group's stored
    order - [] when `part_id` isn't linked."""
    for group in groups:
        if part_id in group:
            return [pid for pid in group if pid != part_id]
    return []


def set_part_link_groups(groups_field: List[List[str]], new_groups: List[List[str]]) -> None:
    """Replaces `groups_field`'s contents wholesale (in place, so the
    MusicData field object identity is preserved) with `new_groups`,
    exactly as given - the caller (LinkPartsDialog's working copy) has
    already applied link_parts/unlink_part's own rules while building it,
    so this is a plain assignment, not re-validated."""
    groups_field[:] = new_groups


class PartLinks:
    """MusicData collaborator, in the style of marking_rows.py - owns no
    state of its own, reads/writes data.part_link_groups directly."""

    def __init__(self, data):
        self.data = data

    def link_parts(self, part_ids: List[str]) -> bool:
        known_part_ids = [p.part_id for p in self.data.parts_info]
        return link_parts(self.data.part_link_groups, known_part_ids, part_ids)

    def unlink_part(self, part_id: str) -> bool:
        return unlink_part(self.data.part_link_groups, part_id)

    def link_group_number(self, part_id: str) -> Optional[int]:
        return link_group_number(self.data.part_link_groups, part_id)

    def link_partners(self, part_id: str) -> List[str]:
        return link_partners(self.data.part_link_groups, part_id)

    def set_part_link_groups(self, groups: List[List[str]]) -> None:
        known_part_ids = {p.part_id for p in self.data.parts_info}
        validated: List[List[str]] = []
        for group in groups:
            distinct = list(dict.fromkeys(pid for pid in group if pid in known_part_ids))
            already_linked = {pid for g in validated for pid in g}
            if len(distinct) < 2 or any(pid in already_linked for pid in distinct):
                continue
            validated.append(distinct)
        self.data.part_link_groups = validated
