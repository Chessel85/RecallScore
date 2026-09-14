# tests/models/test_stage2_marking_levels.py
"""PerformanceMarkingsImplementationPlanV2.md stage 2: MarkingRows.level_of
and the unified score/part/stave placement path it drives."""
from models.direction_mark import DirectionMark
from models.direction_span import DirectionSpan
from models.event_slice import EventSlice
from models.hairpin_span import HairpinSpan
from models.music_data import MusicData
from models.note_data import NoteData
from models.region3_row import MarkingRow
from models.repeat_span import RepeatSpan


def _note(measure, staff, part_id="P1"):
    return NoteData(
        step_name="C", measure=measure, beat_position=1.0,
        ts_duration=4.0, quarter_length=4.0, part_id=part_id,
        part_name="Piano", staff=staff, voice=1, midi_pitch=60,
    )


def _slice(measure, quarters, notes):
    return EventSlice(
        measure=measure, beat_position=1.0, quarter_length=4.0,
        quarters_from_start=quarters, notes=notes,
    )


def _texts(rows):
    return [r.text for r in rows]


def _marking_row_texts(md):
    return [r.text for r in md.get_region_3_rows() if isinstance(r, MarkingRow)]


# --- ground rule 1: system="only-top"/"also-top" promotes to score --------

def test_words_direction_with_system_only_top_is_score_level():
    """Real files never produce a generic `words` DirectionMark yet (stage
    5 wires that up - see tests/parsers/test_direction_system_attribute.py's
    "Allegro"/"not a vocabulary match" note), so this exercises level_of()
    directly rather than through score_level_rows/region_3_data."""
    mark = DirectionMark(
        kind="words", part_id="P1", staff=1, label="Allegro",
        measure=1, beat_position=1.0, quarters_from_start=0.0, system="only-top",
    )
    md = MusicData(timeline_slices=[_slice(1, 0.0, [_note(1, 1)])])
    assert md.marking_rows.level_of(mark) == ("score",)


def test_dynamics_word_with_system_also_top_is_score_level():
    mark = DirectionMark(
        kind="dynamics_word", part_id="P1", staff=1, label="cresc.",
        measure=1, beat_position=1.0, quarters_from_start=0.0, system="also-top",
    )
    md = MusicData(
        timeline_slices=[_slice(1, 0.0, [_note(1, 1), _note(1, 2)])],
        direction_marks=[mark],
    )
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert isinstance(rows[0], MarkingRow)
    assert rows[0].text == 'Crescendo (marked "cresc.")'


def test_hairpin_with_system_only_top_is_score_level_even_on_a_multi_staff_part():
    span = HairpinSpan(
        kind="crescendo", start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=1, end_beat_position=1.0, end_quarters_from_start=0.0,
        part_id="P1", staff=2, system="only-top",
    )
    md = MusicData(
        timeline_slices=[_slice(1, 0.0, [_note(1, 1), _note(1, 2)])],
        hairpin_spans=[span],
    )
    assert md.marking_rows.level_of(span) == ("score",)


# --- ground rule 3: stave only when the part has more than one staff ------

def test_hairpin_on_a_two_staff_part_renders_above_only_that_staff():
    span = HairpinSpan(
        kind="crescendo", start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=1, end_beat_position=1.0, end_quarters_from_start=0.0,
        part_id="P1", staff=2,
    )
    md = MusicData(
        timeline_slices=[_slice(1, 0.0, [_note(1, 1), _note(1, 2)])],
        hairpin_spans=[span],
    )
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["C", "Crescendo", "C"]  # between staff 1's and staff 2's notes
    assert md.marking_rows.level_of(span) == ("stave", "P1", 2)


def test_same_hairpin_on_a_one_staff_part_renders_as_a_part_level_row():
    span = HairpinSpan(
        kind="crescendo", start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=1, end_beat_position=1.0, end_quarters_from_start=0.0,
        part_id="P1", staff=1,
    )
    md = MusicData(
        timeline_slices=[_slice(1, 0.0, [_note(1, 1)])],
        hairpin_spans=[span],
    )
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["Crescendo", "C"]
    assert md.marking_rows.level_of(span) == ("part", "P1")


def test_pedal_on_staff_2_still_surfaces_once_above_staff_1():
    span = DirectionSpan(
        kind="pedal", part_id="P1", staff=2, label="",
        start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=1, end_beat_position=1.0, end_quarters_from_start=0.0,
    )
    md = MusicData(
        timeline_slices=[_slice(1, 0.0, [_note(1, 1), _note(1, 2)])],
        direction_spans=[span],
    )
    md.active_event_index = 0
    assert _texts(md.get_region_3_rows()) == ["Pedal", "C", "C"]
    assert md.marking_rows.level_of(span) == ("part", "P1")


# --- rule 4 fallback: score-only spans/marks with no part_id stay score ---

def test_repeat_in_a_quartet_is_read_once_at_the_top():
    span = RepeatSpan(start_measure=1, end_measure=1)
    notes = [_note(1, 1, part_id=p) for p in ("P1", "P2", "P3", "P4")]
    md = MusicData(timeline_slices=[_slice(1, 0.0, notes)], repeat_spans=[span])
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["Repeat", "C", "C", "C", "C"]
    assert len([r for r in rows if isinstance(r, MarkingRow)]) == 1


# --- note fermata aggregate rule -------------------------------------------

def _fermata_note(measure, part_id, fermata="fermata"):
    return NoteData(
        step_name="C", measure=measure, beat_position=1.0,
        ts_duration=4.0, quarter_length=4.0, part_id=part_id,
        part_name="Piano", staff=1, voice=1, midi_pitch=60, fermata=fermata,
    )


def test_fermata_on_every_part_gives_one_score_level_row():
    notes = [_fermata_note(1, "P1"), _fermata_note(1, "P2"), _fermata_note(1, "P3")]
    md = MusicData(timeline_slices=[_slice(1, 0.0, notes)])
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["Fermata", "C", "C", "C"]
    assert len([r for r in rows if isinstance(r, MarkingRow)]) == 1


def test_fermata_on_only_one_part_gives_a_part_level_row_for_that_part_only():
    notes = [_fermata_note(1, "P1"), _note(1, 1, part_id="P2")]
    md = MusicData(timeline_slices=[_slice(1, 0.0, notes)])
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    # Part-level: the row surfaces immediately above P1's own note, not at
    # the very top the way a score-level aggregate row would.
    assert _texts(rows) == ["Fermata", "C", "C"]
    part_rows = md.marking_rows.part_level_rows(md.get_current_slice())
    assert "P1" in part_rows and part_rows["P1"][0].text == "Fermata"
    assert "P2" not in part_rows
