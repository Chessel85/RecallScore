# tests/models/test_score_sections.py
"""MusicData holding several sections and switching between them
(UserPlans/MultiSectionScores.md task 3).

Built with MusicData(file_path=...) so they stay on the ~1ms ElementTree
path - no music21, no Qt.
"""
from models.music_data import MusicData


# --- the section list ---------------------------------------------------


def test_two_sections_detected_and_labelled(timeline, two_sections_score):
    md = timeline(two_sections_score)

    assert len(md.sections) == 2
    assert md.has_multiple_sections is True
    assert [s.label for s in md.sections] == ["Exercise 1", "Exercise 2"]
    assert [s.index for s in md.sections] == [0, 1]
    assert md.active_section_index == 0
    assert md.active_section is md.sections[0]


def test_single_section_fixture_has_one_section(timeline, minimal_score):
    md = timeline(minimal_score)

    assert len(md.sections) == 1
    assert md.has_multiple_sections is False
    assert md.active_section_index == 0


def test_directly_built_music_data_still_has_one_section():
    md = MusicData()

    assert len(md.sections) == 1
    assert md.has_multiple_sections is False


# --- section 0 is live on load ---------------------------------------------


def test_section_zero_is_the_default(timeline, two_sections_score):
    md = timeline(two_sections_score)

    assert md.measure_numbers() == [1, 2, 3]
    assert md.total_measures == 3
    assert md.timeline_slices[0].time_sig == (4, 4)
    assert md.timeline_slices[0].key_fifths == 0

    assert md.move_timeline_end() is True
    end = md.get_current_slice()
    assert end.measure == 3
    assert end.notes[0].step_name == "C"


# --- switching -----------------------------------------------------------


def test_set_active_section_switches_the_live_timeline(timeline, two_sections_score):
    md = timeline(two_sections_score)

    assert md.set_active_section(1) is True
    assert md.active_section_index == 1
    assert md.active_event_index == 0

    assert md.measure_numbers() == [1, 2]
    assert md.total_measures == 2
    assert md.timeline_slices[0].time_sig == (3, 4)
    assert md.timeline_slices[0].key_fifths == 1
    # Section 2 never re-declares <clef>; the carried treble clef must not
    # surface as a spurious mid-part clef change.
    assert md.clef_change_marks == []

    assert md.move_timeline_end() is True
    end = md.get_current_slice()
    assert end.measure == 2
    assert end.notes[0].step_name == "G"


def test_switching_back_restores_section_zero(timeline, two_sections_score):
    """Proves _adopt_timeline_build drops every timeline-derived cache -
    a stale _measure_numbers_cache would leave section 0 reading section
    1's bars."""
    md = timeline(two_sections_score)

    assert md.set_active_section(1) is True
    assert md.set_active_section(0) is True

    assert md.active_section_index == 0
    assert md.measure_numbers() == [1, 2, 3]
    assert md.total_measures == 3
    assert md.timeline_slices[0].time_sig == (4, 4)
    assert md.timeline_slices[0].key_fifths == 0

    assert md.move_timeline_end() is True
    assert md.get_current_slice().measure == 3


def test_set_active_section_is_a_no_op_for_unchanged_or_out_of_range(
    timeline, two_sections_score
):
    md = timeline(two_sections_score)

    assert md.set_active_section(0) is False   # already active
    assert md.set_active_section(2) is False   # out of range
    assert md.set_active_section(-1) is False
    assert md.active_section_index == 0
    assert md.measure_numbers() == [1, 2, 3]


def test_switch_survives_the_metronome_being_on(timeline, two_sections_score):
    """The metronome splices synthetic beat markers into timeline_slices;
    a section switch has to rebuild them against the new timeline rather
    than leave section 1's slices carrying section 0's markers."""
    md = timeline(two_sections_score)
    md.set_metronome_enabled(True)
    with_markers_section_0 = len(md.timeline_slices)

    assert md.set_active_section(1) is True
    assert md.metronome_enabled is True
    # Every slice belongs to section 1's two bars, markers included.
    assert {s.measure for s in md.timeline_slices} <= {1, 2}

    md.set_metronome_enabled(False)
    assert {s.measure for s in md.timeline_slices} == {1, 2}
    assert with_markers_section_0 > 0
