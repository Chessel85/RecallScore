# tests/models/test_stage5_marking_rows.py
"""PI tweaks implementation plan stage 5: the marking families that used to
be Region 5/report only (pedal, octave shift, dashed/bracket lines,
dynamics/tempo/other-direction points, measure style) now also get a
note-list row via MarkingRows._add_span_rows/_add_point_row - the same
generalised anchoring the hairpin/clef/pedal-change families already used
(see tests/models/test_hairpin_marking_rows.py).

Follow-up (manual review of stage 5): a piano pedal instruction and a
fermata both apply to the whole part, never to one stave/hand alone, even
though the file may record the <direction>/<fermata> against just one
staff or one of several simultaneous notes. Both are elevated to
MarkingRows.part_level_rows - surfaced once, above the FIRST staff group a
part shows, regardless of which staff that happens to be."""
from models.direction_mark import DirectionMark
from models.direction_span import DirectionSpan
from models.event_slice import EventSlice
from models.measure_style_mark import MeasureStyleMark
from models.music_data import MusicData
from models.note_data import NoteData
from models.region3_row import MarkingRow


def _note(measure, staff, part_id="P1"):
    return NoteData(
        step_name="C", measure=measure, beat_position=1.0,
        ts_duration=4.0, quarter_length=4.0, part_id=part_id,
        part_name="Piano", staff=staff, voice=1, midi_pitch=60,
    )


def _slice(measure, quarters, staff=1):
    return EventSlice(
        measure=measure, beat_position=1.0, quarter_length=4.0,
        quarters_from_start=quarters, notes=[_note(measure, staff)],
    )


def _texts(rows):
    return [r.text for r in rows]


def _marking_row_texts(md):
    return [r.text for r in md.get_region_3_rows() if isinstance(r, MarkingRow)]


# --- pedal: part-level (PI tweaks follow-up), no Region 5 row (D15) ------

def _two_staff_slice(measure, quarters):
    """Staff 1 (right hand) and staff 2 (left hand) both have a note - lets
    a test prove a pedal row keyed to staff 2 in the file still surfaces
    once, above staff 1's group (the first one NoteRenderer encounters)."""
    return EventSlice(
        measure=measure, beat_position=1.0, quarter_length=4.0,
        quarters_from_start=quarters,
        notes=[_note(measure, 1), _note(measure, 2)],
    )


def test_pedal_span_is_part_level_and_surfaces_above_the_first_staff_group():
    """A sustain pedal is a whole-piano control - even though the file
    records the <direction> against one staff (staff 2/LH here), the
    note-list row must appear once, above the FIRST staff group the reader
    reaches (staff 1/RH), not buried in the LH's own group."""
    span = DirectionSpan(
        kind="pedal", part_id="P1", staff=2, label="",
        start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=2, end_beat_position=1.0, end_quarters_from_start=4.0,
    )
    md = MusicData(
        timeline_slices=[_two_staff_slice(1, 0.0), _two_staff_slice(2, 4.0)],
        direction_spans=[span],
    )
    md.active_event_index = 0
    assert _texts(md.get_region_3_rows()) == ["Pedal start", "C", "C"]
    md.active_event_index = 1
    assert _texts(md.get_region_3_rows()) == ["Pedal end", "C", "C"]

    md.marking_categories_off = {"lines", "hairpins", "repeats_endings"}
    md.active_event_index = 0
    assert "Pedal start" in _marking_row_texts(md)


def test_pedal_change_is_also_part_level():
    mark = DirectionMark(
        kind="pedal_change", part_id="P1", staff=2, label="",
        measure=1, beat_position=1.0, quarters_from_start=0.0,
    )
    md = MusicData(
        timeline_slices=[_two_staff_slice(1, 0.0)], direction_marks=[mark],
    )
    md.active_event_index = 0
    assert _texts(md.get_region_3_rows()) == ["Pedal change", "C", "C"]


def test_octave_shift_span_is_a_bare_point_row_when_start_equals_end():
    span = DirectionSpan(
        kind="octave_shift", part_id="P1", staff=1, label="8vb",
        start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=1, end_beat_position=1.0, end_quarters_from_start=0.0,
    )
    md = MusicData(timeline_slices=[_slice(1, 0.0)], direction_spans=[span])
    md.active_event_index = 0
    assert _texts(md.get_region_3_rows()) == ["Octave shift 8vb", "C"]


# --- dashed / bracket lines: the "lines" category, like Region 5 ---------

def test_dashed_and_bracket_lines_are_note_list_rows_filtered_by_lines_category():
    dash = DirectionSpan(
        kind="dashes", part_id="P1", staff=1, label="",
        start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=2, end_beat_position=1.0, end_quarters_from_start=4.0,
    )
    bracket = DirectionSpan(
        kind="bracket", part_id="P1", staff=1, label="cresc.",
        start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=2, end_beat_position=1.0, end_quarters_from_start=4.0,
    )
    md = MusicData(
        timeline_slices=[_slice(1, 0.0), _slice(2, 4.0)],
        direction_spans=[dash, bracket],
    )
    md.active_event_index = 0
    assert _texts(md.get_region_3_rows()) == [
        "Dashed line start", "cresc. start", "C",
    ]

    md.marking_categories_off = {"lines"}
    assert not any(
        t.startswith("Dashed") or t.startswith("Bracket") for t in _marking_row_texts(md)
    )


# --- dynamics word / tempo word / other-direction points ------------------

def test_dynamics_tempo_and_other_direction_points_and_their_categories():
    dyn = DirectionMark(
        kind="dynamics_word", part_id="P1", staff=1, label="cresc.",
        measure=1, beat_position=1.0, quarters_from_start=0.0,
    )
    tempo = DirectionMark(
        kind="tempo_word", part_id="P1", staff=1, label="rall.",
        measure=1, beat_position=1.0, quarters_from_start=0.0,
    )
    other = DirectionMark(
        kind="other_direction", part_id="P1", staff=1, label="harp pedals",
        measure=1, beat_position=1.0, quarters_from_start=0.0,
    )
    md = MusicData(timeline_slices=[_slice(1, 0.0)], direction_marks=[dyn, tempo, other])
    md.active_event_index = 0
    assert _texts(md.get_region_3_rows()) == [
        'Crescendo (marked "cresc.")', "Tempo instruction: rall.",
        "Direction: harp pedals", "C",
    ]

    md.marking_categories_off = {"dynamics_words"}
    assert 'Crescendo (marked "cresc.")' not in _marking_row_texts(md)
    md.marking_categories_off = {"tempo_words"}
    assert "Tempo instruction: rall." not in _marking_row_texts(md)
    md.marking_categories_off = {"other_directions"}
    assert "Direction: harp pedals" not in _marking_row_texts(md)


# --- measure style: no quarters of its own -------------------------------

def test_measure_style_lands_on_the_next_real_event_of_that_staff():
    """A multi-bar rest has no events of its own (rests are skipped) - it
    is read as you arrive after it. Staff 1 keeps playing through measure 1
    (which is what gives the score index a first-quarters entry for measure
    1 at all); staff 2's own rest ends at measure 2, where its row lands."""
    mark = MeasureStyleMark(
        kind="multi_measure_rest", part_id="P1", staff=2, label="8-bar rest", measure=1
    )
    md = MusicData(
        timeline_slices=[_slice(1, 0.0, staff=1), _slice(2, 4.0, staff=2)],
        measure_style_marks=[mark],
    )
    md.active_event_index = 0
    assert "8-bar rest" not in _marking_row_texts(md)
    md.active_event_index = 1
    assert "8-bar rest" in _marking_row_texts(md)

    md.marking_categories_off = {"measure_styles"}
    assert "8-bar rest" not in _marking_row_texts(md)


# --- fixed row order -----------------------------------------------------

def test_pedal_change_precedes_pedal_span_within_part_level_rows():
    """Both pedal families live in part_level_rows now (PI tweaks
    follow-up) - the change point still precedes the span's own row, the
    same relative order staff_level_rows used to give them."""
    slice_ = _slice(1, 0.0, staff=1)
    pedal = DirectionSpan(
        kind="pedal", part_id="P1", staff=1, label="",
        start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=1, end_beat_position=1.0, end_quarters_from_start=0.0,
    )
    pedal_change = DirectionMark(
        kind="pedal_change", part_id="P1", staff=1, label="",
        measure=1, beat_position=1.0, quarters_from_start=0.0,
    )
    md = MusicData(
        timeline_slices=[slice_], direction_spans=[pedal], direction_marks=[pedal_change],
    )
    rows = md.marking_rows.part_level_rows(slice_)["P1"]
    assert _texts(rows) == ["Pedal change", "Pedal"]


def test_stage5_staff_families_are_appended_after_hairpins_and_clef_changes():
    """The two remaining pre-existing staff-level families (hairpins, clef
    changes - pedal moved out to part_level_rows) still precede the stage 5
    additions, in the plan's table order.

    Implementation plan V2 stage 2's ground rule 3 ("stave if ... the part
    has more than one staff"): P1 here has only ONE staff, so all three
    families land in part_level_rows, not staff_level_rows - see
    test_stage2_marking_levels.py for the multi-staff case that DOES land
    in staff_level_rows."""
    from models.clef_change_mark import ClefChangeMark
    from models.hairpin_span import HairpinSpan

    slice_ = _slice(1, 0.0, staff=1)
    hairpin = HairpinSpan(
        kind="crescendo", start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=1, end_beat_position=1.0, end_quarters_from_start=0.0,
        part_id="P1", staff=1,
    )
    clef = ClefChangeMark(
        part_id="P1", staff=1, label="bass", measure=1, beat_position=1.0, quarters_from_start=0.0
    )
    dashes = DirectionSpan(
        kind="dashes", part_id="P1", staff=1, label="",
        start_measure=1, start_beat_position=1.0, start_quarters_from_start=0.0,
        end_measure=1, end_beat_position=1.0, end_quarters_from_start=0.0,
    )
    md = MusicData(
        timeline_slices=[slice_], hairpin_spans=[hairpin], clef_change_marks=[clef],
        direction_spans=[dashes],
    )
    rows = md.marking_rows.part_level_rows(slice_)["P1"]
    assert _texts(rows) == ["Crescendo", "Clef change: bass", "Dashed line"]


# --- fermata: part-level, deduped, not inline (PI tweaks follow-up) ------

def _fermata_note(measure, staff, part_id="P1", fermata="fermata"):
    return NoteData(
        step_name="C", measure=measure, beat_position=1.0,
        ts_duration=4.0, quarter_length=4.0, part_id=part_id,
        part_name="Piano", staff=staff, voice=1, midi_pitch=60, fermata=fermata,
    )


def test_fermata_is_a_deduped_part_level_row_not_inline_text():
    """A fermata pauses the whole texture, not one hand - even though the
    file stamps a <fermata> on a note in EACH staff, it must surface once,
    above the first staff group, and must not repeat inline on every note
    that carries it (that inline rendering was reverted - see
    test_tied_continuation_step_text_reads_pitch_then_tied)."""
    slice_ = EventSlice(
        measure=1, beat_position=1.0, quarter_length=4.0, quarters_from_start=0.0,
        notes=[_fermata_note(1, 1), _fermata_note(1, 2)],
    )
    md = MusicData(timeline_slices=[slice_])
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    assert _texts(rows) == ["Fermata", "C", "C"]
    assert md._format_note_for_region_3(slice_.notes[0]) == "C"


def test_fermata_shape_is_capitalised_in_the_row():
    slice_ = EventSlice(
        measure=1, beat_position=1.0, quarter_length=4.0, quarters_from_start=0.0,
        notes=[_fermata_note(1, 1, fermata="short fermata")],
    )
    md = MusicData(timeline_slices=[slice_])
    md.active_event_index = 0
    assert _texts(md.get_region_3_rows()) == ["Short fermata", "C"]


def test_fermata_row_never_filtered_by_a_category():
    slice_ = EventSlice(
        measure=1, beat_position=1.0, quarter_length=4.0, quarters_from_start=0.0,
        notes=[_fermata_note(1, 1)],
    )
    md = MusicData(timeline_slices=[slice_])
    md.marking_categories_off = {"lines", "hairpins", "repeats_endings"}
    md.active_event_index = 0
    assert "Fermata" in _marking_row_texts(md)


def test_fermata_row_carries_no_note_index_so_it_does_not_sound():
    slice_ = EventSlice(
        measure=1, beat_position=1.0, quarter_length=4.0, quarters_from_start=0.0,
        notes=[_fermata_note(1, 1)],
    )
    md = MusicData(timeline_slices=[slice_])
    md.active_event_index = 0
    rows = md.get_region_3_rows()
    fermata_row = next(r for r in rows if r.text == "Fermata")
    assert fermata_row.note_index is None
    assert md.note_indices_from_selection([0]) == []
