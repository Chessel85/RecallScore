# tests/parsers/test_file_signature.py
"""Unit tests for the fail-fast load gate (parsers/file_signature.py)."""
import zipfile

import pytest

from parsers.file_signature import looks_like, precheck, verify
from parsers.score_load_error import ScoreLoadError

MTHD = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0" + b"MTrk\x00\x00\x00\x04\x00\xff\x2f\x00"


def _real_zip(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("hello.txt", "hi")


# --- looks_like -----------------------------------------------------------

def test_looks_like_midi(tmp_path):
    p = tmp_path / "x.mid"
    p.write_bytes(MTHD)
    assert looks_like(str(p)) == "midi"


def test_looks_like_zip_requires_valid_archive(tmp_path):
    good = tmp_path / "x.mxl"
    _real_zip(good)
    assert looks_like(str(good)) == "zip"

    truncated = tmp_path / "y.mxl"
    truncated.write_bytes(b"PK\x03\x04" + b"\x00" * 40)
    assert looks_like(str(truncated)) == "unknown"


def test_looks_like_xml_tolerates_bom_and_whitespace(tmp_path):
    p = tmp_path / "x.musicxml"
    p.write_bytes(b"\xef\xbb\xbf  \r\n<?xml version='1.0'?><score-partwise/>")
    assert looks_like(str(p)) == "xml"


def test_looks_like_json(tmp_path):
    p = tmp_path / "x.ug"
    p.write_text('\n  {"format": "recall_score_ug_import"}', encoding="utf-8")
    assert looks_like(str(p)) == "ug-json"


def test_looks_like_unknown_for_plain_text(tmp_path):
    p = tmp_path / "x.gp"
    p.write_text("just some notes I wrote down", encoding="utf-8")
    assert looks_like(str(p)) == "unknown"


# --- verify -------------------------------------------------------------

def test_verify_accepts_matching_types(tmp_path):
    midi = tmp_path / "a.mid"
    midi.write_bytes(MTHD)
    verify(str(midi))  # no raise

    mxl = tmp_path / "b.mxl"
    _real_zip(mxl)
    verify(str(mxl))

    xml = tmp_path / "c.xml"
    xml.write_bytes(b"<?xml version='1.0'?><score-partwise/>")
    verify(str(xml))


def test_verify_rejects_midi_named_xml(tmp_path):
    p = tmp_path / "song.xml"
    p.write_bytes(MTHD)
    with pytest.raises(ScoreLoadError, match="MusicXML"):
        verify(str(p))


def test_verify_rejects_plain_xml_named_mxl(tmp_path):
    p = tmp_path / "song.mxl"
    p.write_bytes(b"<?xml version='1.0'?><score-partwise/>")
    with pytest.raises(ScoreLoadError, match="Rename it to .xml"):
        verify(str(p))


def test_verify_rejects_zip_named_xml(tmp_path):
    p = tmp_path / "song.xml"
    _real_zip(p)
    with pytest.raises(ScoreLoadError, match="compressed"):
        verify(str(p))


def test_verify_rejects_text_named_gp(tmp_path):
    p = tmp_path / "song.gp"
    p.write_text("not a guitar pro file", encoding="utf-8")
    with pytest.raises(ScoreLoadError, match="Guitar Pro"):
        verify(str(p))


def test_verify_ignores_unknown_extension(tmp_path):
    p = tmp_path / "song.txt"
    p.write_text("whatever", encoding="utf-8")
    verify(str(p))  # no raise - MusicXMLReader is the catch-all


# --- precheck ---------------------------------------------------------

def test_precheck_missing_file(tmp_path):
    with pytest.raises(ScoreLoadError, match="not found"):
        precheck(str(tmp_path / "nope.mxl"))


def test_precheck_empty_file(tmp_path):
    p = tmp_path / "empty.mxl"
    p.write_bytes(b"")
    with pytest.raises(ScoreLoadError, match="empty"):
        precheck(str(p))


def test_precheck_passes_a_good_file(tmp_path):
    p = tmp_path / "ok.mxl"
    _real_zip(p)
    precheck(str(p))  # no raise


def test_precheck_runs_signature_check(tmp_path):
    p = tmp_path / "song.mid"
    p.write_text("this is not midi", encoding="utf-8")
    with pytest.raises(ScoreLoadError, match="MIDI"):
        precheck(str(p))
