"""Spike 1 Python half: import the shared code, parse a score, and time a
navigation step the way the real bridge would serve one key press.

Everything returned to JavaScript is a JSON string, the same rule the real
web/py/rsbv_api.py will follow (JavaScript never holds Python objects).
"""
import json
import time

_md = None


def import_shared():
    start = time.perf_counter()
    import parsers.musicXML_reader  # noqa: F401  (the MusicXML path's whole tree)
    import music21

    return json.dumps({
        "import_ms": (time.perf_counter() - start) * 1000,
        "music21_stub": bool(getattr(music21, "RSBV_STUB", False)),
    })


def parse(path):
    """Load one score and report sizes and a sample of every region."""
    global _md
    from parsers.musicXML_reader import MusicXMLReader

    start = time.perf_counter()
    _md = MusicXMLReader(path).load()
    load_ms = (time.perf_counter() - start) * 1000

    return json.dumps({
        "load_ms": load_ms,
        "slices": len(_md.timeline_slices),
        "parts": len(_md.parts_info),
        "region1": _md.get_region_1_data(),
        "region3": _md.get_region_3_data(),
        "status": _md.get_status_bar_fields(),
    })


def step():
    """One Right Arrow: move, then render what Regions 3 and 6 would show.
    Returns {"moved": bool, "region3": [...], "status": [...]}."""
    moved = _md.move_timeline_right()
    return json.dumps({
        "moved": moved,
        "region3": _md.get_region_3_data(),
        "status": _md.get_status_bar_fields(),
    })


def home():
    _md.move_timeline_home()
