# tests/models/test_marking_rows.py
"""PerformanceMarkingsImplementationPlan.md stage 3: repeats, endings and
sections as note-list rows (score level - strategy section 5)."""
from models.ending_span import EndingSpan
from models.event_slice import EventSlice
from models.music_data import MusicData
from models.note_data import NoteData
from models.region3_row import MarkingRow, NoteRow
from models.repeat_span import RepeatSpan
from models.section_span import SectionSpan


def _note(measure, quarters, part_id="P1"):
    return NoteData(
        step_name="C", measure=measure, beat_position=1.0,
        ts_duration=4.0, quarter_length=4.0, part_id=part_id,
        part_name="Part", staff=1, voice=1, midi_pitch=60,
    )


def _slice(measure, quarters):
    return EventSlice(
        measure=measure, beat_position=1.0, quarter_length=4.0,
        quarters_from_start=quarters, notes=[_note(measure, quarters)],
    )


def _md(**spans):
    return MusicData(
        timeline_slices=[_slice(m, q) for m, q in [(1, 0.0), (2, 4.0), (3, 8.0), (4, 12.0)]],
        **spans,
    )


def test_repeat_start_and_end_rows_anchor_to_the_right_bars():
    md = _md(repeat_spans=[RepeatSpan(start_measure=2, end_measure=3)])

    md.active_event_index = 1  # bar 2, where the repeat opens
    rows = md.get_region_3_rows()
    assert [r.text for r in rows if isinstance(r, MarkingRow)] == ["Repeat start"]

    md.active_event_index = 2  # bar 3, where the repeat closes
    rows = md.get_region_3_rows()
    assert [r.text for r in rows if isinstance(r, MarkingRow)] == ["Repeat end"]

    md.active_event_index = 0  # bar 1: neither
    rows = md.get_region_3_rows()
    assert not any(isinstance(r, MarkingRow) for r in rows)


def test_ending_row_wording_and_position():
    md = _md(ending_spans=[EndingSpan(number=1, start_measure=4, end_measure=4)])
    md.active_event_index = 3
    rows = md.get_region_3_rows()
    marking_texts = [r.text for r in rows if isinstance(r, MarkingRow)]
    assert marking_texts == ["Ending 1 end", "Ending 1 start"]


def test_section_row_survives_region_2_filtering_to_no_visible_notes():
    md = _md(section_spans=[SectionSpan(label="Verse", start_measure=1, end_measure=2)])
    md.active_event_index = 0
    md.set_active_voice_filter(set())  # every voice hidden
    rows = md.get_region_3_rows()
    assert [r.text for r in rows] == ["Section Verse start"]


def test_note_rows_keep_their_visible_notes_index_after_marking_rows_prepended():
    md = _md(repeat_spans=[RepeatSpan(start_measure=1, end_measure=1)])
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    note_rows = [r for r in rows if isinstance(r, NoteRow)]
    assert len(note_rows) == 1
    assert note_rows[0].note_index == 0


def test_note_selection_still_resolves_correctly_past_prepended_marking_rows():
    md = _md(repeat_spans=[RepeatSpan(start_measure=1, end_measure=1)])
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert isinstance(rows[0], MarkingRow) and isinstance(rows[1], MarkingRow)
    # rows: [Repeat end, Repeat start, note]
    note_row_index = next(i for i, r in enumerate(rows) if isinstance(r, NoteRow))
    indices = md.note_indices_from_selection([note_row_index])
    assert indices == [0]  # the note's own position in _visible_notes()


def test_span_marking_selection_resolves_to_no_note():
    md = _md(repeat_spans=[RepeatSpan(start_measure=1, end_measure=1)])
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    marking_row_index = next(i for i, r in enumerate(rows) if isinstance(r, MarkingRow))
    assert md.note_indices_from_selection([marking_row_index]) == []
