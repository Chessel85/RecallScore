# tests/models/test_linked_parts_marking_rows.py
"""PerformanceMarkingsImplementationPlanV2.md stage 9 (PITweaksImplementation
Plan.md item 1): linking two parts as "the same music" borrows each other's
part- and stave-level marking rows (models/marking_rows.py -
_levels_including_borrows). Score-level rows and clef changes are never
borrowed; a borrowed row is anchored at the BORROWING part's own nearest
event, not the source part's."""
from models.clef_change_mark import ClefChangeMark
from models.direction_mark import DirectionMark
from models.direction_span import DirectionSpan
from models.event_slice import EventSlice
from models.music_data import MusicData
from models.note_data import NoteData
from models.parts_structure import PartStructureInfo
from models.region3_row import MarkingRow


def _note(measure, quarters, part_id, staff=1):
    return NoteData(
        step_name="C", measure=measure, beat_position=1.0,
        ts_duration=4.0, quarter_length=4.0, part_id=part_id,
        part_name=f"Part {part_id}", staff=staff, voice=1, midi_pitch=60,
    )


def _slice(measure, quarters, notes):
    return EventSlice(
        measure=measure, beat_position=1.0, quarter_length=4.0,
        quarters_from_start=quarters, notes=notes,
    )


def _two_part_md(part_ids=("P1", "P2")):
    """Two single-staff parts, each with one note per bar across three
    bars - enough events for a span to anchor start/end independently for
    each part."""
    notes_by_slice = [
        [_note(m, q, pid) for pid in part_ids]
        for m, q in ((1, 0.0), (2, 4.0), (3, 8.0))
    ]
    return MusicData(
        parts_info=[PartStructureInfo(part_id=pid, name=f"Part {pid}") for pid in part_ids],
        timeline_slices=[_slice(m, q, notes) for (m, q), notes in zip(((1, 0.0), (2, 4.0), (3, 8.0)), notes_by_slice)],
    )


def _pedal_span(part_id, start_q=0.0, end_q=8.0, start_m=1, end_m=3):
    return DirectionSpan(
        kind="pedal", part_id=part_id, staff=1, label="",
        start_measure=start_m, start_beat_position=1.0, start_quarters_from_start=start_q,
        end_measure=end_m, end_beat_position=1.0, end_quarters_from_start=end_q,
    )


def _marking_texts(md, index):
    md.active_event_index = index
    return [r.text for r in md.get_region_3_rows() if isinstance(r, MarkingRow)]


def test_pedal_span_is_borrowed_onto_the_linked_partner():
    md = _two_part_md()
    md.direction_spans = [_pedal_span("P1")]
    md.link_parts(["P1", "P2"])

    assert _marking_texts(md, 0) == ["Pedal, start", "Pedal, start"]  # own (P1) + borrowed (P2)
    assert _marking_texts(md, 2) == ["Pedal, end", "Pedal, end"]


def test_pedal_span_not_borrowed_when_unlinked():
    md = _two_part_md()
    md.direction_spans = [_pedal_span("P1")]

    assert _marking_texts(md, 0) == ["Pedal, start"]


def test_borrowed_row_survives_the_source_part_being_muted():
    """_staff_quarters (what the borrow anchor reads) comes from the
    unfiltered real timeline, not the active voice filter - a borrowed row
    shows regardless of the SOURCE part's visibility."""
    md = _two_part_md()
    md.direction_spans = [_pedal_span("P1")]
    md.link_parts(["P1", "P2"])
    md.set_active_voice_filter({("P2", 1, 1)})  # P1 fully muted

    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert [r.text for r in rows if isinstance(r, MarkingRow)] == ["Pedal, start"]


def test_dashes_line_borrowed_onto_a_stave_level_partner():
    """Two two-staff parts: a dashed line on P1's staff 2 borrows onto P2's
    lowest staff (staff 1)."""
    part_ids = ("P1", "P2")
    slices = []
    for m, q in ((1, 0.0), (2, 4.0)):
        notes = []
        for pid in part_ids:
            notes.append(_note(m, q, pid, staff=1))
            notes.append(_note(m, q, pid, staff=2))
        slices.append(_slice(m, q, notes))
    md = MusicData(
        parts_info=[PartStructureInfo(part_id=pid, name=f"Part {pid}") for pid in part_ids],
        timeline_slices=slices,
    )
    md.direction_spans = [
        DirectionSpan(
            kind="dashes", part_id="P1", staff=2, label="",
            start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
            end_measure=2, end_beat_position=1.0, end_quarters_from_start=4.0,
            staff_given=True,
        )
    ]
    md.link_parts(["P1", "P2"])

    md.active_event_index = 0
    texts = [r.text for r in md.get_region_3_rows() if isinstance(r, MarkingRow)]
    assert "Dashed line, start" in texts
    assert texts.count("Dashed line, start") == 2  # P1's own + P2's borrow


def test_dynamics_word_point_is_borrowed():
    md = _two_part_md()
    md.direction_marks = [
        DirectionMark(
            kind="dynamics_word", part_id="P1", staff=1, label="cresc.",
            measure=1, beat_position=1.0, quarters_from_start=0.0,
        )
    ]
    md.link_parts(["P1", "P2"])

    texts = _marking_texts(md, 0)
    assert texts.count('Crescendo (marked "cresc.")') == 2


def test_other_direction_point_is_borrowed():
    md = _two_part_md()
    md.direction_marks = [
        DirectionMark(
            kind="other_direction", part_id="P1", staff=1, label="Solo",
            measure=1, beat_position=1.0, quarters_from_start=0.0,
        )
    ]
    md.link_parts(["P1", "P2"])

    texts = _marking_texts(md, 0)
    assert texts.count("Direction: Solo") == 2


def test_clef_change_is_never_borrowed():
    md = _two_part_md()
    md.show_engraving_details_enabled = True
    md.clef_change_marks = [
        ClefChangeMark(
            part_id="P1", staff=1, label="Bass Clef",
            measure=2, beat_position=1.0, quarters_from_start=4.0,
        )
    ]
    md.link_parts(["P1", "P2"])

    texts = _marking_texts(md, 1)
    assert texts == ["Clef change: Bass Clef"]


def test_score_level_row_is_never_borrowed():
    """Rehearsal marks classify as score-level - they already show once,
    unprefixed by any part, so linking must not duplicate them."""
    md = _two_part_md()
    md.direction_marks = [
        DirectionMark(
            kind="rehearsal", part_id="P1", staff=1, label="A",
            measure=1, beat_position=1.0, quarters_from_start=0.0,
        )
    ]
    md.link_parts(["P1", "P2"])

    texts = _marking_texts(md, 0)
    assert texts == ["Rehearsal mark A"]


def test_same_marking_on_both_parts_gives_one_row_each():
    md = _two_part_md()
    md.direction_spans = [_pedal_span("P1"), _pedal_span("P2")]
    md.link_parts(["P1", "P2"])

    assert _marking_texts(md, 0) == ["Pedal, start", "Pedal, start"]  # not four rows


def test_category_off_hides_borrowed_rows():
    md = _two_part_md()
    md.direction_spans = [_pedal_span("P1")]
    md.link_parts(["P1", "P2"])
    md.marking_categories_off = {"pedal"}

    assert _marking_texts(md, 0) == []
