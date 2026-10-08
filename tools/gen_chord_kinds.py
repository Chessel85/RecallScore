#!/usr/bin/env python
"""gen_chord_kinds.py - write models/chord_kinds.py, the chord-symbol table
that lets the app resolve a MusicXML <harmony> without music21 (RSBV 1.4).

Standalone like every script in tools/: no imports from the app. Unlike the
others it needs music21 (a third-party library, already in the venv),
because the table IS music21's answer for every input the MusicXML reader
can ask about, captured once:

    every root spelling (C to B, alter -2 to +2)
    x every kind music21 knows (its chord types, their aliases, MusicXML's
      "other" and "none")
    x no bass, or any of the 35 bass spellings

music21's voicing is not root-plus-intervals (it realises a figured bass,
bumps octaves, detects inversions and pulls the chord into a fixed range,
with quirks such as unsorted and repeated pitches), so the table stores its
pitch lists verbatim rather than a port of the algorithm. The label needs no
table: it is always root + a fixed suffix per kind + "/bass" when a bass is
given and differs from the root. This script asserts that rule, and the two
fallbacks models/chord_kinds.py relies on, for every entry before writing.

Usage (from the repo root; the full sweep takes a few minutes):

    .venv\\Scripts\\python.exe tools/gen_chord_kinds.py           # write the file
    .venv\\Scripts\\python.exe tools/gen_chord_kinds.py --check   # fail if it would change

Run --check after upgrading music21. tests/models/test_chord_kinds.py
(slow) compares the committed table against music21 too.
"""
import argparse
import base64
import sys
import textwrap
import zlib
from pathlib import Path

from music21 import __version__ as MUSIC21_VERSION
from music21 import harmony

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "models" / "chord_kinds.py"

STEPS = "CDEFGAB"
ALTERS = (-2, -1, 0, 1, 2)
ACCIDENTALS = {-2: "--", -1: "-", 0: "", 1: "#", 2: "##"}
FALLBACK_KIND = "other"
# Kinds that aren't in music21's list but must behave like FALLBACK_KIND
# (checked over the whole grid): any unrecognised string, including
# music21's own abbreviations, which it doesn't accept as a kind.
UNKNOWN_KIND_SAMPLES = ("foo", "Major", "maj7")

SPELLINGS = [step + ACCIDENTALS[alter] for step in STEPS for alter in ALTERS]


def all_kinds() -> list:
    kinds = list(harmony.CHORD_TYPES)
    for alias in harmony.CHORD_ALIASES:
        if alias not in kinds:
            kinds.append(alias)
    for musicxml_only in (FALLBACK_KIND, "none"):
        if musicxml_only not in kinds:
            kinds.append(musicxml_only)
    return kinds


def music21_chord(root, kind, bass=None):
    kwargs = {"root": root, "kind": kind}
    if bass:
        kwargs["bass"] = bass
    cs = harmony.ChordSymbol(**kwargs)
    return [p.midi for p in cs.pitches], cs.figure


def kind_grid(kind):
    """Every (root, bass) entry for one kind, roots outer, bass inner
    (None first) - the order models/chord_kinds.py indexes by - plus the
    kind's label suffix. Asserts the label rule as it goes."""
    entries = []
    suffix = None
    for root in SPELLINGS:
        for bass in [None] + SPELLINGS:
            pitches, figure = music21_chord(root, kind, bass)
            if not pitches or not all(0 <= p <= 127 for p in pitches):
                raise SystemExit(f"unexpected pitches {pitches} for {root} {kind} {bass}")
            if bass is None and suffix is None:
                suffix = figure[len(root):]
            expected = root + suffix + (f"/{bass}" if bass and bass != root else "")
            if figure != expected:
                raise SystemExit(f"label rule broken: {root} {kind} {bass} -> {figure!r}, expected {expected!r}")
            entries.append(pitches)
    return entries, suffix


def check_fallbacks(grids):
    """The two music21 behaviours models/chord_kinds.py reproduces without
    tabling them: an unknown kind acts as FALLBACK_KIND, and the bare
    ChordSymbol(root=...) (_resolve_harmony's retry when the bass is
    unreadable) is the "pedal" row's no-bass entry, labelled root+"pedal"."""
    for kind in UNKNOWN_KIND_SAMPLES:
        assert kind not in grids, kind
        entries, suffix = kind_grid(kind)
        if entries != grids[FALLBACK_KIND][0] or suffix != grids[FALLBACK_KIND][1]:
            raise SystemExit(f"unknown kind {kind!r} does not behave like {FALLBACK_KIND!r}")
    pedal_entries, _ = grids["pedal"]
    for r_index, root in enumerate(SPELLINGS):
        cs = harmony.ChordSymbol(root=root)
        pitches, figure = [p.midi for p in cs.pitches], cs.figure
        if pitches != pedal_entries[r_index * (len(SPELLINGS) + 1)] or figure != root + "pedal":
            raise SystemExit(f"bare ChordSymbol(root={root!r}) is not the pedal row: {pitches} {figure!r}")


def pack(entries) -> str:
    raw = bytearray()
    for pitches in entries:
        raw.append(len(pitches))
        raw.extend(pitches)
    return base64.b64encode(zlib.compress(bytes(raw), 9)).decode("ascii")


def render(grids) -> str:
    lines = [
        "# models/chord_kinds.py",
        f"# GENERATED by tools/gen_chord_kinds.py from music21 {MUSIC21_VERSION}. Do not edit;",
        "# rerun the generator instead.",
        '"""MusicXML <harmony> root/kind/bass -> (MIDI pitches, label), exactly as',
        "music21.harmony.ChordSymbol(root=..., kind=..., bass=...) answers, without",
        "music21 (RSBV 1.4: the browser version has none, and desktop no longer",
        "needs it for chords).",
        "",
        "The pitch lists are music21's own voicing, captured for every root",
        "spelling (alter -2 to +2), every kind music21 knows and every bass, so",
        "order and duplicates are kept as music21 gives them. The label is root +",
        "KIND_SUFFIX[kind] + \"/bass\" when a bass differs from the root. Pure",
        "stdlib; Qt-free and parsers-free like the rest of models/.",
        '"""',
        "import base64",
        "import zlib",
        "from typing import Dict, List, Optional, Tuple",
        "",
        f'MUSIC21_VERSION = "{MUSIC21_VERSION}"',
        "",
        "_STEPS = \"CDEFGAB\"",
        "_ACCIDENTALS = {-2: \"--\", -1: \"-\", 0: \"\", 1: \"#\", 2: \"##\"}",
        f'FALLBACK_KIND = "{FALLBACK_KIND}"',
        "",
        "KIND_SUFFIX: Dict[str, str] = {",
    ]
    for kind, (_, suffix) in grids.items():
        lines.append(f"    {kind!r}: {suffix!r},")
    lines += ["}", "", "_PACKED: Dict[str, str] = {"]
    for kind, (entries, _) in grids.items():
        lines.append(f"    {kind!r}: (")
        for chunk in textwrap.wrap(pack(entries), 72):
            lines.append(f'        "{chunk}"')
        lines.append("    ),")
    lines += ["}", ""]
    lines.append(_LOOKUP_CODE)
    return "\n".join(lines)


_LOOKUP_CODE = '''
_decoded: Dict[str, List[Tuple[int, ...]]] = {}


def _entries(kind: str) -> List[Tuple[int, ...]]:
    entries = _decoded.get(kind)
    if entries is None:
        raw = zlib.decompress(base64.b64decode(_PACKED[kind]))
        entries = []
        i = 0
        while i < len(raw):
            n = raw[i]
            entries.append(tuple(raw[i + 1:i + 1 + n]))
            i += 1 + n
        _decoded[kind] = entries
    return entries


def _spelling(step: str, alter: int) -> Optional[Tuple[int, str]]:
    """(index among the 35 spellings, music21 name) or None for a step
    that isn't a note letter. An alter outside -2..2 reads as natural."""
    step = step.strip().upper()
    if len(step) != 1 or step not in _STEPS:
        return None
    if alter not in _ACCIDENTALS:
        alter = 0
    return _STEPS.index(step) * 5 + alter + 2, step + _ACCIDENTALS[alter]


def chord_symbol(
    root_step: str,
    root_alter: int,
    kind: str,
    bass_step: Optional[str] = None,
    bass_alter: int = 0,
) -> Tuple[List[int], str]:
    """(pitches, label) for a chord symbol, as music21 gives them. An
    unknown kind is music21's FALLBACK_KIND (the root alone). An
    unreadable root gives ([], ""); an unreadable bass gives music21's
    bare ChordSymbol(root=...) answer, the root alone labelled "pedal"."""
    root = _spelling(root_step, root_alter)
    if root is None:
        return [], ""
    root_index, root_name = root
    if kind not in _PACKED:
        kind = FALLBACK_KIND
    row = root_index * 36
    if bass_step is None:
        return list(_entries(kind)[row]), root_name + KIND_SUFFIX[kind]
    bass = _spelling(bass_step, bass_alter)
    if bass is None:
        return list(_entries("pedal")[row]), root_name + "pedal"
    bass_index, bass_name = bass
    label = root_name + KIND_SUFFIX[kind]
    if bass_name != root_name:
        label += "/" + bass_name
    return list(_entries(kind)[row + 1 + bass_index]), label
'''


def build() -> str:
    grids = {}
    for kind in all_kinds():
        grids[kind] = kind_grid(kind)
        print(f"  {kind}", file=sys.stderr)
    check_fallbacks(grids)
    return render(grids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="regenerate in memory and fail if models/chord_kinds.py differs")
    args = parser.parse_args()
    text = build()
    if args.check:
        current = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""
        if current != text:
            print(f"{OUT_PATH} is out of date; rerun without --check", file=sys.stderr)
            return 1
        print("MATCH")
        return 0
    OUT_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
