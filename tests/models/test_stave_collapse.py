# tests/models/test_stave_collapse.py
"""Parts > Collapse staves (models/stave_collapse.py) and the "playing"
attribute (s2f3g4m, models/note_renderer.py).

parts_info is built directly rather than through MusicXMLReader.load(), so
these stay on the fast ElementTree-only path (the reader's own reading of
<staff-type>alternate is tested in tests/parsers/test_musicxml_reader.py)."""
from models.music_data import MusicData
from models.note_renderer import NoteRenderer
from models.parts_structure import PartStructureInfo
from models.score_config_data import ScoreConfig


def _guitar_parts():
    return [
        PartStructureInfo(
            part_id="P1", name="Guitar",
            staves_clefs={1: "Treble stave", 2: "Tab stave"},
            staves_voices={1: [1], 2: [5]},
            alternate_staves={2: 1},
        )
    ]


def _md(timeline, path, collapsed=True):
    md = timeline(path, parts_info=_guitar_parts())
    if collapsed:
        assert md.set_staves_collapsed("P1", True) is True
        md.set_active_voice_filter({("P1", 1, 1)})
    return md


def _treble_notes(md, slice_index):
    return [n for n in md.timeline_slices[slice_index].notes if n.staff == 1]


def _pairs_at(md, slice_index):
    return [md._note_attribute_pairs(n) for n in _treble_notes(md, slice_index)]


def test_a_collapsed_note_shows_its_tab_partners_string_and_fret(
    timeline, guitar_alternate_tab_stave_score
):
    md = _md(timeline, guitar_alternate_tab_stave_score)

    (pairs,) = _pairs_at(md, 0)

    assert pairs["string"] == "1"
    assert pairs["fret"] == "12"
    assert pairs["fingering"] == "1"
    # Identity keys stay the kept note's own.
    assert pairs["stave"] == "Treble stave"
    assert pairs["voice"] == "1"
    assert pairs["playing"] == "s1f12g1im"


def test_chord_notes_pair_by_pitch_and_an_unmatched_note_keeps_only_its_own(
    timeline, guitar_alternate_tab_stave_score
):
    """The TAB chord is written E4, C4 (no A4): pairing must go by pitch,
    not position, and A4 borrows nothing."""
    md = _md(timeline, guitar_alternate_tab_stave_score)

    by_step = {p["step"]: p for p in _pairs_at(md, 1)}

    assert by_step["C"]["playing"] == "s5f3g3"
    assert by_step["E"]["playing"] == "s4f2g2"
    assert "string" not in by_step["A"]
    assert "fret" not in by_step["A"]
    assert by_step["A"]["playing"] == "g1"


def test_a_tie_stop_note_gives_string_and_fret_without_a_finger(
    timeline, guitar_alternate_tab_stave_score
):
    md = _md(timeline, guitar_alternate_tab_stave_score)

    (pairs,) = _pairs_at(md, 3)

    assert pairs["playing"] == "s2f12"
    assert "fingering" not in pairs


def test_uncollapsed_notes_borrow_nothing(timeline, guitar_alternate_tab_stave_score):
    md = _md(timeline, guitar_alternate_tab_stave_score, collapsed=False)

    (pairs,) = _pairs_at(md, 0)

    assert "string" not in pairs
    assert pairs["playing"] == "g1im"
    # The TAB note's own playing code works without collapsing too.
    tab = next(n for n in md.timeline_slices[0].notes if n.staff == 2)
    assert md._note_attribute_pairs(tab)["playing"] == "s1f12"


def test_borrowing_never_writes_onto_the_kept_note(timeline, guitar_alternate_tab_stave_score):
    """Invariant 8: string/fret stay one fact on the TAB note."""
    md = _md(timeline, guitar_alternate_tab_stave_score)

    (note,) = _treble_notes(md, 0)
    md._note_attribute_pairs(note)

    assert note.string is None
    assert note.fret is None


def test_playing_code_formatting():
    code = NoteRenderer._playing_code
    assert code({"string": "2", "fret": "3", "fingering": "4", "pluck": "m"}) == "s2f3g4m"
    assert code({"string": "2", "fret": "3"}) == "s2f3"
    assert code({"string": "6", "fret": "0", "pluck": "p, i, m"}) == "s6f0pim"
    assert code({"fingering": "1, 2"}) == "g1g2"
    assert code({"fingering": "0"}) == "g0"
    assert code({"step": "C"}) == ""


def test_playing_sits_before_string_and_reads_unprefixed_in_region_3(
    timeline, guitar_alternate_tab_stave_score
):
    order = MusicData.DISPLAY_ATTRIBUTE_ORDER
    assert order.index("playing") == order.index("string") - 1

    md = _md(timeline, guitar_alternate_tab_stave_score)
    md.set_display_attribute_for_voice("playing", "part", "P1", 1, 1, True)

    assert md.get_region_3_data() == ["E, s1f12g1im"]


def test_collapsing_drops_the_alternate_stave_from_the_structure(
    timeline, guitar_alternate_tab_stave_score
):
    md = _md(timeline, guitar_alternate_tab_stave_score, collapsed=False)
    assert [s["id"] for s in md.get_score_structure()[0]["staves"]] == [1, 2]

    md.set_staves_collapsed("P1", True)
    assert [s["id"] for s in md.get_score_structure()[0]["staves"]] == [1]

    md.set_staves_collapsed("P1", False)
    assert [s["id"] for s in md.get_score_structure()[0]["staves"]] == [1, 2]


def test_only_a_part_with_an_alternate_stave_is_collapsible(
    timeline, guitar_alternate_tab_stave_score
):
    parts = _guitar_parts()
    parts[0].alternate_staves = {}
    md = timeline(guitar_alternate_tab_stave_score, parts_info=parts)

    assert md.is_stave_collapsible("P1") is False
    assert md.set_staves_collapsed("P1", True) is False
    assert md.collapsed_stave_parts == set()


def test_config_round_trips_collapsed_stave_parts(timeline, guitar_alternate_tab_stave_score):
    md = _md(timeline, guitar_alternate_tab_stave_score)
    config = md.export_config()
    assert config.collapsed_stave_parts == ["P1"]

    fresh = _md(timeline, guitar_alternate_tab_stave_score, collapsed=False)
    fresh.apply_config(config)

    assert fresh.is_staves_collapsed("P1") is True
    assert [s["id"] for s in fresh.get_score_structure()[0]["staves"]] == [1]


def test_apply_config_drops_a_part_that_is_not_collapsible(
    timeline, guitar_alternate_tab_stave_score
):
    md = _md(timeline, guitar_alternate_tab_stave_score, collapsed=False)

    md.apply_config(ScoreConfig(collapsed_stave_parts=["P1", "ghost"]))

    assert md.collapsed_stave_parts == {"P1"}


def test_an_old_saved_attribute_order_gains_playing_beside_string(
    timeline, guitar_alternate_tab_stave_score
):
    """A .rsc saved before "playing" existed has a full per-part order
    without it - the new key lands just before "string", not at the end."""
    md = _md(timeline, guitar_alternate_tab_stave_score, collapsed=False)
    saved = [k for k in MusicData.DISPLAY_ATTRIBUTE_ORDER if k != "playing"]

    md.apply_config(ScoreConfig(attribute_order_by_part={"P1": saved}))

    order = md.attribute_order_by_part["P1"]
    assert order.index("playing") == order.index("string") - 1


# --- "playing" is for plucked parts only --------------------------------

def _piano_and_guitar(program=25):
    return [
        PartStructureInfo(part_id="P1", name="Piano", gmidi_program=1,
                          staves_clefs={1: "Treble stave", 2: "Bass stave"}),
        PartStructureInfo(part_id="P2", name="Guitar", gmidi_program=program,
                          staves_clefs={1: "Treble stave"}),
    ]


def _playing_by_part(md):
    return {
        n.part_id: md._note_attribute_pairs(n).get("playing")
        for s in md.timeline_slices for n in s.notes
        if n.fingering or n.pluck
    }


def test_a_piano_part_has_no_playing_code_but_a_guitar_part_does(
    timeline, dynamics_articulation_fingering_score
):
    md = timeline(dynamics_articulation_fingering_score, parts_info=_piano_and_guitar())

    playing = _playing_by_part(md)

    assert playing["P1"] is None
    assert playing["P2"]


def test_plucked_follows_the_gm_program(timeline, dynamics_articulation_fingering_score):
    """A part changed to a non-plucked sound (Instruments dialog) loses
    "playing"; a banjo has it."""
    assert timeline(
        dynamics_articulation_fingering_score, parts_info=_piano_and_guitar(program=41)
    ).is_plucked_part("P2") is False
    assert timeline(
        dynamics_articulation_fingering_score, parts_info=_piano_and_guitar(program=106)
    ).is_plucked_part("P2") is True


def test_a_tab_stave_makes_a_part_plucked_whatever_its_program(
    timeline, guitar_alternate_tab_stave_score
):
    parts = _guitar_parts()
    parts[0].gmidi_program = 1
    md = timeline(guitar_alternate_tab_stave_score, parts_info=parts)

    assert md.is_plucked_part("P1") is True


def test_percussion_and_unknown_parts_are_not_plucked(timeline, guitar_alternate_tab_stave_score):
    parts = _guitar_parts()
    parts[0].is_percussion = True
    md = timeline(guitar_alternate_tab_stave_score, parts_info=parts)

    assert md.is_plucked_part("P1") is False
    assert md.is_plucked_part("nope") is False
