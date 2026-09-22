# tests/models/test_structural_change_cue.py
"""PerformanceMarkingsImplementationPlan.md stage 6: key/time/tempo changes
become note-list rows - one source (MusicData.structural_change_labels) feeds
both Region 5's own row and the note list's row. The performance-indicator
cue itself moved off this trigger entirely (PerformanceIndicatorCue.md) - see
tests/test_performance_indicator_cue.py for its own coverage."""
from models.direction_mark import DirectionMark
from models.event_slice import EventSlice
from models.music_data import MusicData
from models.note_data import NoteData
from models.region3_row import MarkingRow
from models.tempo_change import TempoChange


def _note(measure, quarters):
    return NoteData(
        step_name="C", measure=measure, beat_position=1.0,
        ts_duration=4.0, quarter_length=4.0, part_id="P1",
        part_name="Part", staff=1, voice=1, midi_pitch=60,
    )


def _slice(measure, quarters, time_sig=(4, 4), key_fifths=0):
    return EventSlice(
        measure=measure, beat_position=1.0, quarter_length=4.0,
        quarters_from_start=quarters, time_sig=time_sig, key_fifths=key_fifths,
        notes=[_note(measure, quarters)],
    )


def _md_with_key_change():
    return MusicData(
        timeline_slices=[
            _slice(1, 0.0, key_fifths=0),
            _slice(2, 4.0, key_fifths=2),
        ],
    )


def _md_with_time_sig_change():
    return MusicData(
        timeline_slices=[
            _slice(1, 0.0, time_sig=(4, 4)),
            _slice(2, 4.0, time_sig=(3, 4)),
        ],
    )


def _md_with_tempo_change():
    return MusicData(
        timeline_slices=[_slice(1, 0.0), _slice(2, 4.0)],
        tempo_changes=[
            TempoChange(quarters_from_start=4.0, tempo_bpm=96,
                        beat_unit_quarter_length=1.0, beat_unit_name="quarter",
                        display_number="96"),
        ],
    )


def test_key_signature_change_becomes_a_note_list_row():
    md = _md_with_key_change()
    md.active_event_index = 1
    rows = md.get_region_3_rows()
    marking_texts = [r.text for r in rows if isinstance(r, MarkingRow)]
    assert any(t.startswith("Key signature change:") for t in marking_texts)


def test_time_signature_change_becomes_a_note_list_row():
    md = _md_with_time_sig_change()
    md.active_event_index = 1
    rows = md.get_region_3_rows()
    marking_texts = [r.text for r in rows if isinstance(r, MarkingRow)]
    assert "Time signature change: 3/4" in marking_texts


def test_tempo_change_becomes_a_note_list_row():
    md = _md_with_tempo_change()
    md.active_event_index = 1
    rows = md.get_region_3_rows()
    marking_texts = [r.text for r in rows if isinstance(r, MarkingRow)]
    assert any(t.startswith("Tempo change:") for t in marking_texts)


def test_no_structural_row_at_index_zero_even_with_a_notional_change():
    md = _md_with_key_change()
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert not any(isinstance(r, MarkingRow) for r in rows)


def test_a_words_only_tempo_instruction_produces_no_structural_row_or_cue():
    """A rall./accel. written as words is a DirectionMark, not a
    TempoChange - it never counts as the "immediate" change the cue and the
    note-list row are limited to (strategy section 7)."""
    md = MusicData(
        timeline_slices=[_slice(1, 0.0), _slice(2, 4.0)],
        direction_marks=[
            DirectionMark(kind="tempo_word", part_id="P1", staff=1, label="rall.",
                          measure=2, beat_position=1.0, quarters_from_start=4.0),
        ],
    )
    md.active_event_index = 1
    assert md.structural_change_labels() == []
    rows = md.get_region_3_rows()
    assert not any(isinstance(r, MarkingRow) and r.text.startswith("Tempo change") for r in rows)
