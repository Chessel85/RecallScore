# tests/test_region_presenter_region5.py
"""P2: Region 5's live Jump Point/Chord/Lyric context rows (UG "Tab" import).

An intra-jump-point chord or lyric change relabels the context rows in
place; crossing a jump point boundary rebuilds the whole list. Neither one
touches the performance-indicator cue, which moved off refresh_region_5
entirely and onto RegionPresenter.update_timeline_views (PerformanceIndicator
Cue.md) - see tests/test_performance_indicator_cue.py for that behaviour.
"""
from controllers.region_presenter import RegionPresenter
from models.event_slice import EventSlice
from models.music_data import MusicData
from models.note_data import NoteData
from models.parts_structure import PartStructureInfo
from models.jump_point import JumpPoint
from models.synthetic_parts import CHORDS_PART_ID, LYRICS_PART_ID
from widgets.region5_list_widget import Region5ListWidget


class _FakeSession:
    def __init__(self, music_data, synth):
        self.music_data = music_data
        self.synth = synth
        self.uk_terms = False


def _chord_slice(measure, quarters, sym, words):
    return EventSlice(
        measure=measure, beat_position=1.0, quarter_length=4.0,
        quarters_from_start=quarters, time_sig=(4, 4),
        notes=[
            NoteData(step_name=sym, measure=measure, beat_position=1.0,
                     ts_duration=4.0, quarter_length=4.0, part_id=CHORDS_PART_ID,
                     part_name="Chords", staff=1, voice=1, midi_pitch=60,
                     chord_symbol=sym),
            NoteData(step_name=words, measure=measure, beat_position=1.0,
                     ts_duration=4.0, quarter_length=4.0, part_id=LYRICS_PART_ID,
                     part_name="Lyrics", staff=1, voice=1, midi_pitch=None),
        ],
    )


def _music_data():
    return MusicData(
        parts_info=[
            PartStructureInfo(part_id=CHORDS_PART_ID, name="Chords"),
            PartStructureInfo(part_id=LYRICS_PART_ID, name="Lyrics"),
        ],
        timeline_slices=[
            _chord_slice(1, 0.0, "D", "one"),
            _chord_slice(2, 4.0, "G", "two"),
            _chord_slice(3, 8.0, "A", "three"),
        ],
        jump_points=[
            JumpPoint(label="Verse 1", start_measure=1, end_measure=2),
            JumpPoint(label="Chorus", start_measure=3, end_measure=3),
        ],
    )


def _presenter(qtbot, null_synth):
    md = _music_data()
    region_5 = Region5ListWidget()
    qtbot.addWidget(region_5)
    presenter = RegionPresenter(
        _FakeSession(md, null_synth),
        None, None, None, None, region_5, None, lambda: ("", "", ""),
    )
    return presenter, md, region_5


def _row_texts(region_5):
    return [region_5.item(i).text() for i in range(region_5.count())]


def test_intra_jump_point_chord_change_relabels_in_place_with_no_cue(qtbot, null_synth):
    presenter, md, region_5 = _presenter(qtbot, null_synth)

    md.active_event_index = 0
    presenter.refresh_region_5()
    assert null_synth.performance_cues == []  # no key/time/tempo change here
    assert "Chord: D" in _row_texts(region_5)

    md.active_event_index = 1  # bar 2 - still Verse 1, chord D -> G
    presenter.refresh_region_5()

    assert null_synth.performance_cues == []
    texts = _row_texts(region_5)
    assert "Chord: G" in texts and "Lyric: two" in texts
    assert "Chord: D" not in texts


def test_crossing_a_jump_point_boundary_rebuilds_without_a_cue(qtbot, null_synth):
    """A jump point is not one of the three structural changes the cue was
    narrowed to (stage 6) - the list still rebuilds, but nothing sounds."""
    presenter, md, region_5 = _presenter(qtbot, null_synth)

    md.active_event_index = 1
    presenter.refresh_region_5()
    null_synth.performance_cues.clear()

    md.active_event_index = 2  # bar 3 - Verse 1 -> Chorus
    presenter.refresh_region_5()

    assert null_synth.performance_cues == []
    texts = _row_texts(region_5)
    assert "Jump Point: Chorus" in texts
    assert any(t.startswith("* Jump Point Chorus") for t in texts)
