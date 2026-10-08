"""The browser bridge (web/py/web_api.py) in plain CPython: no browser, no music21."""
import json
from pathlib import Path

import pytest

import web_api

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _load(path: Path):
    return web_api.load(path.read_bytes(), path.name)


@pytest.mark.parametrize("path", [
    FIXTURES / "chord.musicxml",
    FIXTURES / "chords_and_lyrics.musicxml",
    FIXTURES / "grace_note.musicxml",
    REPO_ROOT / "examples" / "bach-bourree-tab.mxl",
], ids=lambda p: p.name)
def test_load_returns_json_summary(path):
    result = _load(path)
    assert result["ok"] is True
    summary = result["summary"]
    json.dumps(summary)  # plain data only: JavaScript never holds Python objects
    assert isinstance(summary["credits"], dict)
    assert summary["slices"] > 0
    assert summary["parts"]
    for part in summary["parts"]:
        assert set(part) == {"part_id", "name"}


def test_chords_and_lyrics_fixture_reports_its_parts():
    summary = _load(FIXTURES / "chords_and_lyrics.musicxml")["summary"]
    assert len(summary["parts"]) >= 2


def test_summary_matches_last_load():
    _load(FIXTURES / "chord.musicxml")
    first = web_api.score_summary()
    _load(REPO_ROOT / "examples" / "bach-bourree-tab.mxl")
    assert web_api.score_summary() != first


def test_broken_file_returns_error_dict_and_keeps_previous_score():
    _load(FIXTURES / "chord.musicxml")
    before = web_api.score_summary()
    result = web_api.load(b"<not-a-score", "broken.musicxml")
    assert set(result) == {"error"}
    assert "broken.musicxml" in result["error"]
    assert web_api.score_summary() == before


def test_unsupported_suffix_returns_error_dict():
    result = web_api.load(b"data", "song.pdf")
    assert set(result) == {"error"}
    assert ".musicxml" in result["error"]


def test_summary_without_a_score_is_an_error(monkeypatch):
    monkeypatch.setattr(web_api, "_music_data", None)
    assert web_api.score_summary() == {"error": "No score is loaded."}
