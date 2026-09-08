# parsers/file_signature.py
"""Fail-fast checks run before a score load starts.

The load pipeline dispatches purely on the filename extension
(workers/score_load_worker.py). That means a MIDI file renamed to .xml, or a
text file named .gp, is handed to the wrong reader and - historically -
produced a silent, empty score rather than an error. `precheck` closes that:
it confirms the file exists, is non-empty and readable, then sniffs its first
bytes and refuses when they do not match the reader the extension selects.

Everything here is stdlib and byte-level, so it behaves identically on
Windows and macOS. `looks_like` tolerates a UTF-8 BOM and leading whitespace
before an XML declaration.
"""
import os
import zipfile

from models.score_formats import SIGNATURE_EXPECTATIONS
from parsers.score_load_error import ScoreLoadError

_HEAD_BYTES = 512
_UTF8_BOM = b"\xef\xbb\xbf"

# extension -> (expected kind from looks_like, human label for messages).
# S4: the list itself lives in models/score_formats.py so adding a format is
# a one-file edit. models.score_formats is pure stdlib, so this module stays
# dependency-light and identical across Windows/macOS.
_EXPECTED = SIGNATURE_EXPECTATIONS


def looks_like(file_path: str) -> str:
    """A coarse content kind: "midi", "zip", "xml", "ug-json" or "unknown".

    "zip" is only returned for a structurally valid archive (a truncated file
    that merely starts with the ZIP magic is "unknown"), so a half-downloaded
    .mxl/.gp is caught here rather than deep inside a reader.
    """
    try:
        with open(file_path, "rb") as f:
            head = f.read(_HEAD_BYTES)
    except OSError:
        return "unknown"

    if head[:4] == b"MThd":
        return "midi"
    if head[:2] == b"PK":
        return "zip" if zipfile.is_zipfile(file_path) else "unknown"

    stripped = head[3:] if head[:3] == _UTF8_BOM else head
    stripped = stripped.lstrip()
    if stripped[:1] == b"<":
        return "xml"
    if stripped[:1] == b"{":
        return "ug-json"
    return "unknown"


def _mismatch_message(label: str, want_kind: str, got_kind: str) -> str:
    if want_kind == "zip" and got_kind == "xml":
        return (
            f"This file is named like a {label} file but contains plain XML "
            "text. It may be misnamed."
        )
    if want_kind == "xml" and got_kind == "zip":
        target = ".mscz" if label == "MuseScore" else ".mxl"
        return (
            f"This looks like a compressed {label} file. Rename it to "
            f"{target} and try again."
        )
    if want_kind == "midi":
        return (
            "This file is named like a MIDI file but does not contain MIDI "
            "data. It may be misnamed or corrupt."
        )
    return (
        f"This does not look like a valid {label} file. It may be corrupt or "
        "the wrong type of file."
    )


def verify(file_path: str) -> None:
    """Raise ScoreLoadError when the file's contents do not match the reader
    its extension selects. An unrecognised extension is left alone -
    MusicXMLReader is the pipeline's catch-all and will report its own
    failure."""
    ext = os.path.splitext(file_path)[1].lower()
    expected = _EXPECTED.get(ext)
    if expected is None:
        return
    want_kind, label = expected
    got_kind = looks_like(file_path)
    if got_kind == want_kind:
        return
    # T10: a .mxl is normally a zip container, but plain MusicXML text
    # misnamed .mxl is still perfectly readable - read_musicxml_root()
    # dispatches on the real container type, not the extension. Let it
    # through rather than tell a screen-reader user to rename the file.
    if ext == ".mxl" and got_kind == "xml":
        return
    raise ScoreLoadError(_mismatch_message(label, want_kind, got_kind))


def precheck(file_path: str) -> None:
    """Synchronous fail-fast gate for a local score file. Raises
    ScoreLoadError with a spoken-friendly message; returns None if the file
    is worth handing to a reader. Not for URL imports (no local file)."""
    name = os.path.basename(file_path) or file_path
    if not os.path.isfile(file_path):
        raise ScoreLoadError(f"File not found: {name}")
    try:
        size = os.path.getsize(file_path)
    except OSError as e:
        raise ScoreLoadError(
            "This file could not be read. It may be locked by another program.",
            cause=e,
        )
    if size == 0:
        raise ScoreLoadError("This file is empty.")
    try:
        with open(file_path, "rb") as f:
            f.read(1)
    except OSError as e:
        raise ScoreLoadError(
            "This file could not be opened for reading. It may be locked by "
            "another program, or you may not have permission to read it.",
            cause=e,
        )
    verify(file_path)
