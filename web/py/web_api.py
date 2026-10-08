"""The browser bridge: the web version's controller layer, run inside Pyodide.

Holds the current MusicData (replaced wholesale on every load, CLAUDE.md
invariant 3) and returns only plain dicts, so JavaScript never holds Python
objects. A failure comes back as {"error": message}, never an exception.
"""
import os
import tempfile
from typing import Any, Dict, Optional

from models.music_data import MusicData
from parsers.musicxml_metadata import load_musicxml_without_music21

SUPPORTED_SUFFIXES = (".musicxml", ".xml", ".mxl")

_music_data: Optional[MusicData] = None


def load(data: bytes, filename: str) -> Dict[str, Any]:
    """Parse an uploaded score. The reader takes a path, so the bytes are
    written to a temp file that keeps the original suffix (.mxl is a zip)."""
    global _music_data
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return {"error": f"{filename or 'This file'} is not a supported score. "
                         f"Supported types: {', '.join(SUPPORTED_SUFFIXES)}."}
    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(bytes(data))
            path = handle.name
        loaded = load_musicxml_without_music21(path)
    except Exception as exc:  # noqa: BLE001 - every failure must reach the user
        return {"error": f"Could not open {filename}: {exc}"}
    finally:
        if path and os.path.exists(path):
            os.remove(path)
    _music_data = loaded
    return {"ok": True, "summary": score_summary()}


def score_summary() -> Dict[str, Any]:
    """Region 1's text plus the counts a loading message needs."""
    if _music_data is None:
        return {"error": "No score is loaded."}
    return {
        "credits": dict(_music_data.get_region_1_data()),
        "parts": [{"part_id": p.part_id, "name": p.name} for p in _music_data.parts_info],
        "slices": len(_music_data.timeline_slices),
    }
