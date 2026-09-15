# tests/parsers/test_key_time_change_marks.py
import pytest

from parsers.musicXML_reader import MusicXMLReader

"""PerformanceMarkingsImplementationPlanV2.md stage 10 rule 2: a part's own
key/time signature change is now tracked (KeyChangeMark/TimeChangeMark,
TimelineBuilder._handle_attributes), and TimelineBuilder._resolve_key_time_
levels decides, once every part is walked, whether a given bar's change was
a MAJORITY (one score row) or carried a MINORITY (one row per differing
part) - majority-wins, not strict unanimity, because a real file (Dvorak's
New World Symphony, bar 46) has 11 of 12 parts agree and 1 not, and a
literal "score only if EVERY part agrees" would have spoiled the row for
the 11 that genuinely agree with each other.

tests/fixtures/key_time_disagreement.musicxml: three parts, all C major/4-4
in bar 1 (the seed - never a change). Bar 2: Violin and Cello move to D
major together (the majority), Viola alone moves to F major (the
minority). Bar 3: Violin and Cello move to 3/4 (majority), Viola alone to
2/4 (minority). Bar 4: all three move by the same +1-fifth change from
wherever they already were, and to 4/4 together - unanimous."""
from models.marking_rows import MarkingRows
from models.music_data import MusicData
from models.region3_row import MarkingRow

FIXTURE = "tests/fixtures/key_time_disagreement.musicxml"


def _index_at_measure_start(md: MusicData, measure: int) -> int:
    for i, s in enumerate(md.timeline_slices):
        if s.measure == measure:
            return i
    raise AssertionError(f"no slice for measure {measure}")


def _marking_row_texts(rows):
    return [r.text for r in rows if isinstance(r, MarkingRow)]


def test_bar_1_seed_produces_no_change_marks():
    md = MusicData(file_path=FIXTURE)
    assert all(m.measure != 1 for m in md.key_change_marks)
    assert all(m.measure != 1 for m in md.time_change_marks)


def test_bar_2_key_majority_collapses_minority_keeps_its_own_row():
    md = MusicData(file_path=FIXTURE)
    marks = {m.part_id: m for m in md.key_change_marks if m.measure == 2}
    # Cello (P3) agreed with Violin (P1) and was absorbed into the single
    # majority representative - it does not survive as its own mark.
    assert set(marks) == {"P1", "P2"}
    assert marks["P1"].fifths == 2 and marks["P1"].is_score_level is True
    assert marks["P2"].fifths == -1 and marks["P2"].is_score_level is False


def test_bar_3_time_majority_collapses_minority_keeps_its_own_row():
    md = MusicData(file_path=FIXTURE)
    marks = {m.part_id: m for m in md.time_change_marks if m.measure == 3}
    assert set(marks) == {"P1", "P2"}
    assert (marks["P1"].ts_num, marks["P1"].ts_den) == (3, 4)
    assert marks["P1"].is_score_level is True
    assert (marks["P2"].ts_num, marks["P2"].ts_den) == (2, 4)
    assert marks["P2"].is_score_level is False


def test_bar_4_unanimous_change_collapses_to_one_mark_of_each_kind():
    md = MusicData(file_path=FIXTURE)
    bar4_keys = [m for m in md.key_change_marks if m.measure == 4]
    bar4_times = [m for m in md.time_change_marks if m.measure == 4]
    assert len(bar4_keys) == 1 and bar4_keys[0].is_score_level and bar4_keys[0].fifths == 3
    assert len(bar4_times) == 1 and bar4_times[0].is_score_level
    assert (bar4_times[0].ts_num, bar4_times[0].ts_den) == (4, 4)


def test_bar_2_note_list_gives_one_score_row_and_one_minority_part_row():
    md = MusicData(file_path=FIXTURE)
    idx = _index_at_measure_start(md, 2)
    slice_ = md.timeline_slices[idx]
    md.active_event_index = idx

    score_rows = _marking_row_texts(md.marking_rows.score_level_rows(slice_))
    assert "Key signature change: D major / B minor" in score_rows

    part_rows = md.marking_rows.part_level_rows(slice_)
    assert "Key signature change: F major / D minor" in _marking_row_texts(part_rows.get("P2", []))
    assert not any(
        "signature change" in t
        for part_id, rows in part_rows.items() if part_id != "P2"
        for t in _marking_row_texts(rows)
    )

    assert md.has_key_or_time_change_at(slice_) is True


def test_bar_4_unanimous_change_gives_a_single_score_row_no_part_rows():
    md = MusicData(file_path=FIXTURE)
    idx = _index_at_measure_start(md, 4)
    md.active_event_index = idx
    slice_ = md.timeline_slices[idx]

    score_rows = _marking_row_texts(md.marking_rows.score_level_rows(slice_))
    assert "Key signature change: A major / F sharp minor" in score_rows
    assert "Time signature change: 4/4" in score_rows

    part_rows = md.marking_rows.part_level_rows(slice_)
    assert not any(
        "signature change" in t
        for rows in part_rows.values()
        for t in _marking_row_texts(rows)
    )


@pytest.mark.slow
def test_region_5_shows_one_score_row_and_prefixes_the_minority_row():
    # Part-name prefixing reads data.parts_info, which the fast
    # MusicData(file_path=...) timeline path never populates (see
    # tests/conftest.py's `timeline` fixture) - needs the real reader.
    md = MusicXMLReader(FIXTURE).load()
    idx = _index_at_measure_start(md, 2)
    md.active_event_index = idx
    labels = [r.label for r in md.get_performance_region_rows(idx)]
    assert "* Key signature change: D major / B minor" in labels
    assert "* Viola: Key signature change: F major / D minor" in labels
    assert not any(l.startswith("* Violin:") or l.startswith("* Cello:") for l in labels)
