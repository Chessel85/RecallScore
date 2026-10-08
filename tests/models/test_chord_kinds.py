# tests/models/test_chord_kinds.py
"""RSBV 1.4: models/chord_kinds.py answers exactly what
music21.harmony.ChordSymbol(root=..., kind=..., bass=...) does, so desktop
chords sound as they did when _resolve_harmony asked music21 directly.

The slow test sweeps the whole table (every root spelling, every kind and
every bass, about 69,000 chords, a few minutes). The fast tests pin a
handful of cases by hand, including music21's quirks the table must keep."""
import pytest

from models.chord_kinds import FALLBACK_KIND, KIND_SUFFIX, chord_symbol

STEPS = "CDEFGAB"
ACCIDENTALS = {-2: "--", -1: "-", 0: "", 1: "#", 2: "##"}
SPELLINGS = [(step, alter) for step in STEPS for alter in ACCIDENTALS]


@pytest.mark.parametrize("args, expected", [
    (("C", 0, "major"), ([48, 52, 55], "C")),
    (("G", 0, "major"), ([55, 59, 62], "G")),          # voicing depends on the root letter
    (("A", 0, "minor"), ([45, 48, 52], "Am")),
    (("F", 1, "minor-seventh"), ([42, 45, 49, 52], "F#m7")),
    (("E", 0, "major", "G"), ([55, 44, 47, 52], "E/G")),  # music21's order, not sorted
    (("G", 0, "major", "G"), ([55, 59, 62], "G")),      # bass equal to root: no slash
    (("C", 0, "dominant"), ([48, 52, 55, 58], "C7")),   # MusicXML alias of dominant-seventh
    (("B", -1, "half-diminished"), ([46, 49, 52, 56], "B-ø7")),
])
def test_known_chords(args, expected):
    assert chord_symbol(*args) == expected


def test_unknown_kind_sounds_the_root_alone():
    assert chord_symbol("D", 0, "foo") == chord_symbol("D", 0, FALLBACK_KIND) == ([50], "D")
    assert chord_symbol("D", 0, "maj7", "E") == ([40, 40, 50], "D/E")


def test_lowercase_steps_read_as_capitals():
    assert chord_symbol("c", 0, "minor", "e") == chord_symbol("C", 0, "minor", "E")


def test_out_of_range_alter_reads_as_natural():
    assert chord_symbol("C", 3, "major") == chord_symbol("C", 0, "major")


def test_unreadable_root_and_bass():
    assert chord_symbol("H", 0, "major") == ([], "")
    assert chord_symbol("C", 0, "major", "H") == ([48], "Cpedal")


def test_lookup_returns_a_fresh_list():
    pitches, _ = chord_symbol("C", 0, "major")
    pitches.append(99)
    assert chord_symbol("C", 0, "major")[0] == [48, 52, 55]


@pytest.mark.slow
def test_whole_table_matches_music21():
    """A failure after a music21 upgrade means its voicing changed: rerun
    tools/gen_chord_kinds.py (the table was built from MUSIC21_VERSION)."""
    pytest.importorskip("music21")
    from music21 import harmony

    def name(step, alter):
        return step + ACCIDENTALS[alter]

    kinds = list(KIND_SUFFIX) + ["foo", "Major"]
    mismatches = []
    for kind in kinds:
        for root in SPELLINGS:
            for bass in [None] + SPELLINGS:
                kwargs = {"root": name(*root), "kind": kind}
                if bass:
                    kwargs["bass"] = name(*bass)
                cs = harmony.ChordSymbol(**kwargs)
                expected = ([p.midi for p in cs.pitches], cs.figure)
                actual = chord_symbol(*root, kind, *(bass or (None, 0)))
                if actual != expected:
                    mismatches.append((kwargs, expected, actual))
    assert not mismatches, f"{len(mismatches)} mismatches, first: {mismatches[:3]}"
