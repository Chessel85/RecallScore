# models/score_formats.py
"""S4: the one place that lists the score file formats Recall Score opens.

The extension lists used to be repeated across four unrelated files that had
to agree verbatim - the R5 "two independent copies must not drift" bug class
the project has been bitten by twice (see CLAUDE.md):

  * models/music_data.py         - is_midi / is_gp / is_ug family checks
  * workers/score_load_worker.py  - which reader class handles the file
  * parsers/file_signature.py     - expected byte signature per extension
  * main_window.py                - File > Open dialog filters

All four now read from here. .mscz/.mscx in particular used to be in three
of them and absent from MusicData; it is one entry now.

Pure stdlib so models/ stays a leaf - no Qt, no music21, no parsers/ import,
so `MusicData(file_path=...)` (the ~1ms ElementTree path timeline tests use)
is unaffected.
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class ScoreFormat:
    """One openable format family."""

    key: str
    """Stable family id: "musicxml", "musescore", "midi", "gp" or "ug".
    MusicData.is_midi/is_gp/is_ug and score_load_worker's reader dispatch key
    off this, never a raw extension literal."""
    extensions: Tuple[str, ...]
    """Lower-case, dot-prefixed. The first is the canonical one."""
    dialog_label: str
    """File > Open filter group name ("MIDI Files")."""
    requires_external_tool: bool = False
    """True for a format Recall Score can only open via a separate installed
    program (MuseScore's CLI converts .mscz/.mscx). main_window keeps such a
    format out of every File > Open filter until that tool is actually found;
    every other format is always offered."""


# Order is the File > Open filter order, and is asserted by
# tests/test_main_window_menus.py - keep musicxml first, musescore second.
SCORE_FORMATS: Tuple[ScoreFormat, ...] = (
    ScoreFormat("musicxml", (".xml", ".musicxml", ".mxl"), "MusicXML Files"),
    ScoreFormat(
        "musescore", (".mscz", ".mscx"), "MuseScore Files",
        requires_external_tool=True,
    ),
    ScoreFormat("midi", (".mid", ".midi"), "MIDI Files"),
    ScoreFormat("gp", (".gp",), "Guitar Pro Files"),
    ScoreFormat("ug", (".ug",), "Recall Score UG Import Files"),
)

_FAMILY_BY_EXT: Dict[str, str] = {
    ext: fmt.key for fmt in SCORE_FORMATS for ext in fmt.extensions
}


def family_for_path(file_path: str) -> Optional[str]:
    """The ScoreFormat.key for this path's extension, or None for an
    unrecognised one (MusicXMLReader is the load pipeline's catch-all, so an
    unknown extension is handled, not rejected here)."""
    return _FAMILY_BY_EXT.get(os.path.splitext(file_path)[1].lower())


# Per-EXTENSION expected content signature for parsers.file_signature: the
# string parsers.file_signature.looks_like() must return, plus the human
# label used in a mismatch message. This is genuinely per-extension, not
# per-format - .mxl is a zip while .xml/.musicxml are plain text, and .mscz
# is a zip while .mscx is plain text - and .mxl carries its own label
# ("compressed MusicXML") so _mismatch_message can offer a .mxl-specific
# hint. Kept here so adding a format still means editing one file.
SIGNATURE_EXPECTATIONS: Dict[str, Tuple[str, str]] = {
    ".mid": ("midi", "MIDI"),
    ".midi": ("midi", "MIDI"),
    ".gp": ("zip", "Guitar Pro"),
    ".mscz": ("zip", "MuseScore"),
    ".mscx": ("xml", "MuseScore"),
    ".ug": ("ug-json", "Recall Score Ultimate Guitar import"),
    ".xml": ("xml", "MusicXML"),
    ".musicxml": ("xml", "MusicXML"),
    ".mxl": ("zip", "compressed MusicXML"),
}
