# tests/models/test_hairpin_marking_rows.py
"""PerformanceMarkingsImplementationPlan.md stage 5: hairpins as note-list
rows (strategy section 11), with per-part/per-staff placement (section 4.1)."""
from models.event_slice import EventSlice
from models.hairpin_span import HairpinSpan
from models.music_data import MusicData
from models.note_data import NoteData
from models.region3_row import MarkingRow, NoteRow


def _note(measure, quarters, staff, part_id="P1"):
    return NoteData(
        step_name="C", measure=measure, beat_position=1.0,
        ts_duration=4.0, quarter_length=4.0, part_id=part_id,
        part_name="Piano", staff=staff, voice=1, midi_pitch=60,
    )


def _slice(measure, quarters):
    # staff 1 (right hand) note first, staff 2 (left hand) second - so a
    # left-hand-only marking row must land between them, not before staff 1.
    return EventSlice(
        measure=measure, beat_position=1.0, quarter_length=4.0,
        quarters_from_start=quarters,
        notes=[_note(measure, quarters, 1), _note(measure, quarters, 2)],
    )


def _md(hairpin_spans):
    return MusicData(
        timeline_slices=[_slice(1, 0.0), _slice(2, 4.0), _slice(3, 8.0)],
        hairpin_spans=hairpin_spans,
    )


def _texts(rows):
    return [r.text for r in rows]


def test_hairpin_start_appears_only_above_the_left_hand_staff():
    span = HairpinSpan(
        kind="crescendo", start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=3, end_beat_position=1.0, end_quarters_from_start=8.0,
        part_id="P1", staff=2,
    )
    md = _md([span])
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["C", "Crescendo start", "C"]
    assert isinstance(rows[0], NoteRow) and rows[0].note_index == 0  # staff 1's note
    assert isinstance(rows[2], NoteRow) and rows[2].note_index == 1  # staff 2's note


def test_hairpin_end_row_at_the_last_event():
    span = HairpinSpan(
        kind="diminuendo", start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=3, end_beat_position=1.0, end_quarters_from_start=8.0,
        part_id="P1", staff=2,
    )
    md = _md([span])
    md.active_event_index = 2
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["C", "Diminuendo end", "C"]


def test_no_hairpin_row_at_a_position_merely_inside_the_span():
    span = HairpinSpan(
        kind="crescendo", start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=3, end_beat_position=1.0, end_quarters_from_start=8.0,
        part_id="P1", staff=2,
    )
    md = _md([span])
    md.active_event_index = 1
    rows = md.get_region_3_rows()
    assert not any(isinstance(r, MarkingRow) for r in rows)


def test_zero_length_wedge_reads_as_a_bare_point_with_no_start_or_end_word():
    span = HairpinSpan(
        kind="crescendo", start_measure=2, start_beat_position=1.0, start_quarters_from_start=4.0,
        end_measure=2, end_beat_position=1.0, end_quarters_from_start=4.0,
        part_id="P1", staff=1,
    )
    md = _md([span])
    md.active_event_index = 1
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["Crescendo", "C", "C"]


def test_swell_produces_two_point_rows_in_file_order():
    cresc = HairpinSpan(
        kind="crescendo", start_measure=2, start_beat_position=1.0, start_quarters_from_start=4.0,
        end_measure=2, end_beat_position=1.0, end_quarters_from_start=4.0,
        part_id="P1", staff=1,
    )
    dim = HairpinSpan(
        kind="diminuendo", start_measure=2, start_beat_position=1.0, start_quarters_from_start=4.0,
        end_measure=2, end_beat_position=1.0, end_quarters_from_start=4.0,
        part_id="P1", staff=1,
    )
    md = _md([cresc, dim])
    md.active_event_index = 1
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["Crescendo", "Diminuendo", "C", "C"]


def test_unmatched_stop_reads_as_a_bare_point():
    """Stage 6: an unpartnered stop is a point, pinned to its own known
    position (start == end) - a bare "Hairpin" row, no "start"/"end" suffix."""
    span = HairpinSpan(
        kind="", start_measure=2, start_beat_position=1.0, start_quarters_from_start=4.0,
        end_measure=2, end_beat_position=1.0, end_quarters_from_start=4.0,
        part_id="P1", staff=1,
    )
    md = _md([span])
    md.active_event_index = 0
    assert not any(isinstance(r, MarkingRow) for r in md.get_region_3_rows())
    md.active_event_index = 1
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["Hairpin", "C", "C"]


def test_hairpin_row_not_repeated_per_voice_of_the_same_staff():
    """4.1: a marking that belongs to a staff appears once, however many
    voices of that staff are visible."""
    two_voice_slice = EventSlice(
        measure=1, beat_position=1.0, quarter_length=4.0, quarters_from_start=0.0,
        notes=[
            NoteData(step_name="C", measure=1, beat_position=1.0, ts_duration=4.0,
                     quarter_length=4.0, part_id="P1", part_name="Piano", staff=1,
                     voice=1, midi_pitch=60),
            NoteData(step_name="E", measure=1, beat_position=1.0, ts_duration=4.0,
                     quarter_length=4.0, part_id="P1", part_name="Piano", staff=1,
                     voice=2, midi_pitch=64),
        ],
    )
    span = HairpinSpan(
        kind="crescendo", start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=2, end_beat_position=1.0, end_quarters_from_start=4.0,
        part_id="P1", staff=1,
    )
    md = MusicData(
        timeline_slices=[two_voice_slice, _slice(2, 4.0)], hairpin_spans=[span]
    )
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["Crescendo start", "C", "E"]
