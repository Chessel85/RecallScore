# tests/parsers/test_timewise.py
"""Task 4 of userPlans/timewiseMusicXML.md: prove a timewise MusicXML file
loads identically to its partwise equivalent.

Parts A/B: for every existing (partwise) fixture, round-trip it through the
test-only inverse and back, and prove the resulting timeline is identical.
Part C: the same, but through MusicXMLReader.load() (music21), on the two
fixtures where music21 actually contributes something (tempo/key/time).
Part D: a hand-written, genuine on-disk timewise fixture.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from models.music_data import MusicData
from parsers.musicXML_reader import MusicXMLReader
from parsers.xml_source import timewise_to_partwise
from tests.support.timewise import partwise_to_timewise

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
ALL_FIXTURES = sorted(FIXTURES_DIR.glob("*.musicxml"))

TIMELINE_FIELDS = [
    "timeline_slices",
    "total_measures",
    "tempo_changes",
    "repeat_spans",
    "ending_spans",
    "hairpin_spans",
    "segno_marks",
    "coda_marks",
    "to_coda_marks",
    "fine_marks",
    "navigation_jumps",
]


def _canonical(el: ET.Element):
    """(tag, attrib, stripped text, children) - ignores whitespace-only text
    and tails, which differ because partwise_to_timewise/timewise_to_partwise
    build fresh part/measure elements rather than reusing whitespace-formatted
    ones."""
    return (
        el.tag,
        el.attrib,
        (el.text or "").strip(),
        [_canonical(c) for c in el],
    )


def _is_timewise_on_disk(path: Path) -> bool:
    return ET.parse(path).getroot().tag == "score-timewise"


PARTWISE_FIXTURES = [p for p in ALL_FIXTURES if not _is_timewise_on_disk(p)]


@pytest.mark.parametrize("path", PARTWISE_FIXTURES, ids=lambda p: p.name)
def test_structural_round_trip(path):
    root = ET.parse(path).getroot()
    round_tripped = timewise_to_partwise(partwise_to_timewise(root))

    assert _canonical(round_tripped) == _canonical(root)


@pytest.mark.parametrize("path", PARTWISE_FIXTURES, ids=lambda p: p.name)
def test_timewise_copy_yields_identical_timeline(path, tmp_path):
    root = ET.parse(path).getroot()
    timewise_root = partwise_to_timewise(root)

    timewise_copy = tmp_path / path.name
    ET.ElementTree(timewise_root).write(timewise_copy, encoding="utf-8", xml_declaration=True)

    original_md = MusicData(file_path=str(path))
    timewise_md = MusicData(file_path=str(timewise_copy))

    for field_name in TIMELINE_FIELDS:
        assert getattr(timewise_md, field_name) == getattr(original_md, field_name), field_name


@pytest.mark.slow
@pytest.mark.parametrize("fixture_name", ["key_change.musicxml", "tempo_change.musicxml"])
def test_reader_gives_music21_the_converted_tree(fixture_name, tmp_path):
    """Without Task 2 (feeding music21 the converted tree via parseData),
    a timewise file's key/time/tempo come from the ElementTree fallback
    instead of music21 and may render differently - this is what actually
    exercises that path, unlike the fast MusicData(file_path=...) tests
    above which never call MusicXMLReader.load() at all."""
    original_path = FIXTURES_DIR / fixture_name
    root = ET.parse(original_path).getroot()
    timewise_root = partwise_to_timewise(root)

    timewise_copy = tmp_path / fixture_name
    ET.ElementTree(timewise_root).write(timewise_copy, encoding="utf-8", xml_declaration=True)

    original = MusicXMLReader(str(original_path)).load()
    timewise = MusicXMLReader(str(timewise_copy)).load()

    assert timewise.credits == original.credits
    assert timewise.tempo_bpm == original.tempo_bpm
    assert timewise.parts_info == original.parts_info


def test_timewise_two_parts_fixture_is_skipped_by_round_trip():
    """The hand-written on-disk timewise fixture is already timewise, so
    partwise_to_timewise would no-op on it (wrong direction) rather than
    reflect a genuine round trip - it must not appear in PARTWISE_FIXTURES."""
    assert (FIXTURES_DIR / "timewise_two_parts.musicxml") not in PARTWISE_FIXTURES


def test_timewise_two_parts_fixture_loads(timewise_two_parts_score):
    md = MusicData(file_path=timewise_two_parts_score)

    assert md.total_measures == 2

    first_slice = md.timeline_slices[0]
    assert first_slice.measure == 1
    assert first_slice.beat_position == 1.0
    assert sorted(n.step_name for n in first_slice.notes) == ["C", "C"]

    measure_1_flute_notes = [
        note.step_name
        for s in md.timeline_slices
        if s.measure == 1
        for note in s.notes
        if note.part_name == "Flute"
    ]
    assert measure_1_flute_notes == ["C", "D", "E", "F"]

    measure_2_beats = sorted(
        s.beat_position for s in md.timeline_slices if s.measure == 2
    )
    assert measure_2_beats == [1.0, 3.0]
