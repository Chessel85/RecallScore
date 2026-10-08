# tests/parsers/test_musicxml_without_music21.py
"""RSBV 1.1: the browser version has no music21, so the MusicXML path -
parsers/musicxml_metadata.py's loader, the timeline builder factory and
TimelineBuilder - must import and load a score with music21 unavailable.

Runs in a subprocess for the same reason as the Qt-free guard in
tests/test_harness.py: this test session has music21 loaded already, so
sys.modules in-process can't prove anything."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_BLOCKED_LOAD = r"""
import importlib.abc, json, sys

class _BlockMusic21(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "music21" or name.startswith("music21."):
            raise ImportError(f"music21 is blocked in this test: {name}")
        return None

sys.meta_path.insert(0, _BlockMusic21())

from parsers.musicxml_metadata import load_musicxml_without_music21

md = load_musicxml_without_music21(sys.argv[1])
chords = [
    {"label": n.step_name, "pitches": n.chord_pitches}
    for s in md.timeline_slices for n in s.notes if n.part_id == "chords"
]
print(json.dumps({
    "music21_loaded": any(m == "music21" or m.startswith("music21.") for m in sys.modules),
    "parts": [p.name for p in md.parts_info],
    "region_1": md.get_region_1_data(),
    "slices": len(md.timeline_slices),
    "chords": chords,
}))
"""


def _load_with_music21_blocked(fixture: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-c", _BLOCKED_LOAD, str(PROJECT_ROOT / "tests" / "fixtures" / fixture)],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_musicxml_score_loads_with_music21_blocked():
    out = _load_with_music21_blocked("minimal_4_4.musicxml")

    assert out["music21_loaded"] is False
    assert out["parts"] == ["Test Part"]
    assert out["region_1"]["Time Signature"] == "4/4"
    assert "notes per minute" in out["region_1"]["Tempo"]
    assert out["slices"] == 4


def test_score_with_chord_symbols_loads_with_music21_blocked():
    """<harmony> is the one MusicXML feature that reaches for music21
    (_resolve_harmony). Blocked, it must degrade, not fail the load. Until
    the chord table (RSBV 1.4) lands, the chords resolve to no pitches and
    the builder skips them, so the Chords part is listed but empty."""
    out = _load_with_music21_blocked("chords_and_lyrics.musicxml")

    assert out["music21_loaded"] is False
    assert out["parts"] == ["Piano", "Chords", "Lyrics"]
    assert out["chords"] == []


@pytest.mark.slow
@pytest.mark.parametrize("fixture", ["minimal_4_4.musicxml", "chords_and_lyrics.musicxml"])
def test_music21_free_loader_matches_desktop_reader_on_shared_fields(fixture):
    """Everything the two loaders read from ElementTree must agree; only
    tempo/key/time may differ (desktop prefers music21's reading)."""
    from parsers.musicXML_reader import MusicXMLReader
    from parsers.musicxml_metadata import load_musicxml_without_music21

    path = str(PROJECT_ROOT / "tests" / "fixtures" / fixture)
    desktop = MusicXMLReader(path).load()
    web = load_musicxml_without_music21(path)

    assert web.parts_info == desktop.parts_info
    assert web.voice_display_attributes == desktop.voice_display_attributes
    assert web.score is None
    shared = {"Key Signature", "Time Signature", "Tempo"}
    assert {k: v for k, v in web.credits.items() if k not in shared} == {
        k: v for k, v in desktop.credits.items() if k not in shared
    }
    assert len(web.timeline_slices) == len(desktop.timeline_slices)
