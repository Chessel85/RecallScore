# tests/models/test_stage10_key_time_levels.py
"""PerformanceMarkingsImplementationPlanV2.md stage 10 rule 2:
KeyChangeMark/TimeChangeMark carry their own resolved is_score_level
(set by TimelineBuilder._resolve_key_time_levels once every part is
walked), and MarkingRows.level_of reads it directly rather than going
through the classification/system/staff rules every other family uses -
see tests/parsers/test_key_time_change_marks.py for the parser side
(detection and agreement resolution) and the note-list/Region 5 rows this
drives."""
from models.event_slice import EventSlice
from models.key_change_mark import KeyChangeMark
from models.music_data import MusicData
from models.note_data import NoteData
from models.time_change_mark import TimeChangeMark


def _note(measure, part_id):
    return NoteData(
        step_name="C", measure=measure, beat_position=1.0,
        ts_duration=4.0, quarter_length=4.0, part_id=part_id,
        part_name=part_id, staff=1, voice=1, midi_pitch=60,
    )


def _slice(measure, quarters, part_ids):
    return EventSlice(
        measure=measure, beat_position=1.0, quarter_length=4.0,
        quarters_from_start=quarters, notes=[_note(measure, pid) for pid in part_ids],
    )


def test_score_level_key_change_mark_is_score():
    mark = KeyChangeMark(
        part_id="P1", fifths=2, previous_fifths=0, measure=2, beat_position=1.0,
        quarters_from_start=4.0, is_score_level=True,
    )
    md = MusicData(timeline_slices=[_slice(1, 0.0, ["P1"])])
    assert md.marking_rows.level_of(mark) == ("score",)


def test_differing_key_change_mark_is_its_own_part():
    mark = KeyChangeMark(
        part_id="P1", fifths=2, previous_fifths=0, measure=2, beat_position=1.0,
        quarters_from_start=4.0, is_score_level=False,
    )
    md = MusicData(timeline_slices=[_slice(1, 0.0, ["P1"])])
    assert md.marking_rows.level_of(mark) == ("part", "P1")


def test_differing_time_change_mark_is_its_own_part():
    mark = TimeChangeMark(
        part_id="P2", ts_num=3, ts_den=4, measure=3, beat_position=1.0,
        quarters_from_start=8.0, is_score_level=False,
    )
    md = MusicData(timeline_slices=[_slice(1, 0.0, ["P2"])])
    assert md.marking_rows.level_of(mark) == ("part", "P2")


def test_has_key_or_time_change_at_true_only_at_the_minority_marks_own_anchor():
    mark = KeyChangeMark(
        part_id="P1", fifths=2, previous_fifths=0, measure=2, beat_position=1.0,
        quarters_from_start=4.0, is_score_level=False,
    )
    slices = [_slice(1, 0.0, ["P1"]), _slice(2, 4.0, ["P1"])]
    md = MusicData(timeline_slices=slices, key_change_marks=[mark])
    assert md.has_key_or_time_change_at(slices[1]) is True
    assert md.has_key_or_time_change_at(slices[0]) is False


def test_has_key_or_time_change_at_true_for_a_majority_mark_too():
    mark = KeyChangeMark(
        part_id="P1", fifths=2, previous_fifths=0, measure=2, beat_position=1.0,
        quarters_from_start=4.0, is_score_level=True,
    )
    slices = [_slice(1, 0.0, ["P1"]), _slice(2, 4.0, ["P1"])]
    md = MusicData(timeline_slices=slices, key_change_marks=[mark])
    assert md.has_key_or_time_change_at(slices[1]) is True
    assert md.has_key_or_time_change_at(slices[0]) is False
