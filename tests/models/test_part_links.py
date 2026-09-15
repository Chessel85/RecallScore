# tests/models/test_part_links.py
"""PerformanceMarkingsImplementationPlanV2.md stage 9 (PITweaksImplementation
Plan.md item 1): PartLinks' rules, exercised both as the plain module
functions widgets/link_parts_dialog.py's working copy runs and through
MusicData's own delegators, so the two are proven to share one rule set
(invariant 8)."""
from models.music_data import MusicData
from models.parts_structure import PartStructureInfo
from models.part_links import link_group_number, link_parts, link_partners, unlink_part


def _md(part_ids):
    return MusicData(
        parts_info=[PartStructureInfo(part_id=pid, name=f"Part {pid}") for pid in part_ids]
    )


def test_link_two_parts():
    md = _md(["P1", "P2", "P3"])
    assert md.link_parts(["P1", "P2"]) is True
    assert md.part_link_groups == [["P1", "P2"]]
    assert md.link_group_number("P1") == 1
    assert md.link_group_number("P2") == 1
    assert md.link_group_number("P3") is None


def test_link_three_parts_at_once():
    md = _md(["P1", "P2", "P3"])
    assert md.link_parts(["P1", "P2", "P3"]) is True
    assert md.part_link_groups == [["P1", "P2", "P3"]]


def test_link_refuses_a_single_id():
    md = _md(["P1", "P2"])
    assert md.link_parts(["P1"]) is False
    assert md.part_link_groups == []


def test_link_refuses_an_unknown_id():
    md = _md(["P1", "P2"])
    assert md.link_parts(["P1", "PX"]) is False
    assert md.part_link_groups == []


def test_link_refuses_an_already_linked_id():
    md = _md(["P1", "P2", "P3"])
    md.link_parts(["P1", "P2"])
    assert md.link_parts(["P2", "P3"]) is False
    assert md.part_link_groups == [["P1", "P2"]]


def test_unlink_from_a_pair_dissolves_the_group():
    md = _md(["P1", "P2"])
    md.link_parts(["P1", "P2"])
    assert md.unlink_part("P1") is True
    assert md.part_link_groups == []
    assert md.link_group_number("P2") is None


def test_unlink_from_a_triple_leaves_a_pair():
    md = _md(["P1", "P2", "P3"])
    md.link_parts(["P1", "P2", "P3"])
    assert md.unlink_part("P1") is True
    assert md.part_link_groups == [["P2", "P3"]]


def test_unlink_unknown_part_returns_false():
    md = _md(["P1", "P2"])
    md.link_parts(["P1", "P2"])
    assert md.unlink_part("PX") is False


def test_group_numbers_renumber_after_a_dissolve():
    md = _md(["P1", "P2", "P3", "P4"])
    md.link_parts(["P1", "P2"])
    md.link_parts(["P3", "P4"])
    assert md.link_group_number("P3") == 2
    md.unlink_part("P1")  # dissolves group 1 entirely
    assert md.part_link_groups == [["P3", "P4"]]
    assert md.link_group_number("P3") == 1


def test_partners_are_symmetric():
    md = _md(["P1", "P2", "P3"])
    md.link_parts(["P1", "P2", "P3"])
    assert md.link_partners("P1") == ["P2", "P3"]
    assert md.link_partners("P2") == ["P1", "P3"]
    assert md.link_partners("P3") == ["P1", "P2"]
    assert md.link_partners("P4") == []


def test_module_functions_match_the_delegators():
    groups = []
    assert link_parts(groups, ["P1", "P2"], ["P1", "P2"]) is True
    assert link_group_number(groups, "P1") == 1
    assert link_partners(groups, "P1") == ["P2"]
    assert unlink_part(groups, "P2") is True
    assert groups == []


def test_set_part_link_groups_drops_unknown_and_repeated_and_short_groups():
    md = _md(["P1", "P2", "P3"])
    md.set_part_link_groups([["P1", "P2"], ["P2", "P3"], ["PX"], ["P3"]])
    # "P2" already used by the first group - the second is dropped whole;
    # "PX" is unknown; the bare "P3" group has under two members.
    assert md.part_link_groups == [["P1", "P2"]]
