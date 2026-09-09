# tests/parsers/test_score_sections.py
"""Splitting a multi-section MusicXML document (UserPlans/MultiSectionScores.md
task 1). Pure ElementTree - no music21, no Qt - so these are fast."""
import xml.etree.ElementTree as ET

from parsers.score_sections import (
    CARRIED_MARKER,
    detect_section_boundaries,
    split_score_sections,
)
from parsers.timeline_builder import TimelineBuilder
from parsers.xml_source import read_musicxml_root


def _root(path: str) -> ET.Element:
    return read_musicxml_root(path)


# --- boundary detection -----------------------------------------------------


def test_boundaries_split_at_the_measure_number_restart(two_sections_score):
    assert detect_section_boundaries(_root(two_sections_score)) == [(0, 3), (3, 5)]


def test_single_section_score_is_one_range(minimal_score):
    assert detect_section_boundaries(_root(minimal_score)) == [(0, 1)]


def test_two_bar_single_section_score_is_one_range(flute_crotchets_viola_semibreves_score):
    assert detect_section_boundaries(_root(flute_crotchets_viola_semibreves_score)) == [
        (0, 2)
    ]


def test_real_two_flute_exercises_file_splits_into_two(two_flute_exercises_score):
    assert detect_section_boundaries(_root(two_flute_exercises_score)) == [(0, 3), (3, 5)]


# --- labelling ------------------------------------------------------------


def test_labels_come_from_the_first_words_direction(two_sections_score):
    sections = split_score_sections(_root(two_sections_score))
    assert [s.label for s in sections] == ["Exercise 1", "Exercise 2"]


def test_label_collapses_a_trailing_newline_and_a_whitespace_only_sibling(
    two_sections_score,
):
    """Section 2's <words> is "Exercise 2\\n" followed by a "  " <words>
    sibling - both must be handled, yielding a clean "Exercise 2"."""
    sections = split_score_sections(_root(two_sections_score))
    assert sections[1].label == "Exercise 2"
    assert "\n" not in sections[1].label
    assert sections[1].label == sections[1].label.strip()


def test_real_file_labels(two_flute_exercises_score):
    sections = split_score_sections(_root(two_flute_exercises_score))
    assert [s.label for s in sections] == ["Exercise 1", "Exercise 2"]


def test_single_section_falls_back_to_movement_or_generic_label(minimal_score):
    sections = split_score_sections(_root(minimal_score))
    assert len(sections) == 1
    # minimal_4_4.musicxml has no <words> direction and no <movement-title>.
    assert sections[0].label in ("Section 1", "")  # tolerate a movement-title if added


# --- sub-root shape ------------------------------------------------------


def test_single_section_reuses_the_original_root_untouched(minimal_score):
    root = _root(minimal_score)
    sections = split_score_sections(root)
    assert len(sections) == 1
    assert sections[0].root is root


def test_every_sub_root_carries_the_shared_header_and_part_list(two_sections_score):
    sections = split_score_sections(_root(two_sections_score))
    assert len(sections) == 2
    for section in sections:
        assert section.root.tag == "score-partwise"
        assert section.root.find("work") is not None
        assert section.root.find("work/work-title").text == "Two Sections"
        assert section.root.find("part-list/score-part[@id='P1']") is not None
        assert section.root.find("identification") is not None
        assert section.root.find("defaults") is not None


def test_each_sub_root_holds_only_its_own_measures(two_sections_score):
    first, second = split_score_sections(_root(two_sections_score))
    assert len(first.root.findall("part/measure")) == 3
    assert len(second.root.findall("part/measure")) == 2


def test_section_one_gets_no_synthesised_attributes(two_sections_score):
    first = split_score_sections(_root(two_sections_score))[0]
    first_measure = first.root.find("part/measure")
    assert first_measure.find(f"attributes[@{CARRIED_MARKER}]") is None


def test_section_two_carries_the_treble_clef_forward(two_sections_score):
    second = split_score_sections(_root(two_sections_score))[1]
    first_measure = second.root.find("part/measure")

    carried = first_measure.find(f"attributes[@{CARRIED_MARKER}]")
    assert carried is not None
    assert carried.get(CARRIED_MARKER) == "yes"
    assert carried.findtext("clef/sign") == "G"
    assert carried.findtext("clef/line") == "2"

    # The carried block is first; the section's own <attributes> (which
    # re-declares divisions/key/time but NOT clef) follows and overrides it.
    children = list(first_measure)
    assert children[0] is carried
    own_attrs = first_measure.findall("attributes")[1]
    assert own_attrs.get(CARRIED_MARKER) is None
    assert own_attrs.findtext("key/fifths") == "1"
    assert own_attrs.findtext("time/beats") == "3"


def test_real_file_section_two_carries_the_clef(two_flute_exercises_score):
    second = split_score_sections(_root(two_flute_exercises_score))[1]
    carried = second.root.find(f"part/measure/attributes[@{CARRIED_MARKER}]")
    assert carried is not None
    assert carried.findtext("clef/sign") == "G"


def test_original_root_is_not_mutated_by_the_split(two_sections_score):
    root = _root(two_sections_score)
    split_score_sections(root)
    # The document-order 4th measure (section 2, bar 1) must still have
    # exactly one <attributes> child - no carried block leaked back in.
    fourth_measure = root.findall("part/measure")[3]
    assert len(fourth_measure.findall("attributes")) == 1
    assert fourth_measure.find(f"attributes[@{CARRIED_MARKER}]") is None


# --- the _handle_attributes suppression --------------------------------


def test_carried_attributes_do_not_emit_a_clef_change_mark(two_sections_score):
    """A fresh TimelineBuilder over section 2's sub-root must not report the
    carried treble clef as a mid-part clef change (M7)."""
    second = split_score_sections(_root(two_sections_score))[1]
    builder = TimelineBuilder(two_sections_score, parts_info=[], root=second.root)
    builder.build()
    assert builder.clef_change_marks == []
    assert builder.measure_style_marks == []
