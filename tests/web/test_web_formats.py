"""MIDI and Guitar Pro in the browser bridge (RSBV 6.1): web_api.load picks
the reader by extension, as the desktop's ScoreLoadThread does."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import web_api
from parsers.gp_reader import GpReader
from parsers.midi_reader import MidiReader


def _load(path: str):
    p = Path(path)
    return web_api.load(p.read_bytes(), p.name)


@pytest.mark.parametrize("fixture", [
    "midi_test1", "midi_test2", "midi_bach_bourree", "midi_blue_peter", "gp_ripple",
])
def test_load_matches_the_desktop_reader(fixture, request):
    path = request.getfixturevalue(fixture)
    result = _load(path)
    assert result["ok"] is True
    json.dumps(result)  # plain data only
    reader = GpReader if path.endswith(".gp") else MidiReader
    desktop = reader(path).load()
    summary = result["summary"]
    assert summary["credits"] == dict(desktop.get_region_1_data())
    assert [p["part_id"] for p in summary["parts"]] == [p.part_id for p in desktop.parts_info]
    assert summary["slices"] == len(desktop.timeline_slices) > 0


def test_midi_title_is_the_uploaded_file_name(midi_test1):
    """MIDI has no title, so it falls back to the file name: the temp copy
    must keep the uploaded name, not a random one."""
    result = _load(midi_test1)
    assert result["summary"]["credits"]["Title"] == Path(midi_test1).stem


def test_upper_case_extension_is_accepted(midi_test3):
    assert Path(midi_test3).suffix == ".MID"
    assert _load(midi_test3)["ok"] is True


@pytest.mark.parametrize("name", ["broken.mid", "broken.gp"])
def test_broken_file_says_why_and_keeps_previous_score(name, midi_test2):
    _load(midi_test2)
    before = web_api.score_summary()
    result = web_api.load(b"not a score", name)
    assert set(result) == {"error"}
    assert name in result["error"]
    assert "could not be read" in result["error"]
    assert web_api.score_summary() == before


def test_desktop_only_formats_are_refused():
    for name in ("song.mscz", "song.ug"):
        result = web_api.load(b"data", name)
        assert set(result) == {"error"}
        assert "not a supported score" in result["error"]


_BLOCKED_LOAD = r"""
import importlib.abc, json, sys
from pathlib import Path

class _BlockMusic21(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "music21" or name.startswith("music21."):
            raise ImportError(f"music21 is blocked in this test: {name}")
        return None

sys.meta_path.insert(0, _BlockMusic21())
sys.path.insert(0, "web/py")

import web_api

p = Path(sys.argv[1])
result = web_api.load(p.read_bytes(), p.name)
print(json.dumps({
    "music21_loaded": any(m == "music21" or m.startswith("music21.") for m in sys.modules),
    "ok": result.get("ok", False),
    "error": result.get("error"),
}))
"""


@pytest.mark.parametrize("fixture", ["midi_bach_bourree", "gp_ripple"])
def test_loads_with_music21_blocked(fixture, request):
    """The browser has no music21. Runs in a subprocess, as
    tests/parsers/test_musicxml_without_music21.py does, because this
    session has music21 loaded already."""
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", _BLOCKED_LOAD, request.getfixturevalue(fixture)],
        cwd=root, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out == {"music21_loaded": False, "ok": True, "error": None}
