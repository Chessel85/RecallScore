"""Spike-only stand-in for music21 (RSBV Phase 0, spike 1).

parsers/timeline_builder.py and parsers/ug_timeline_builder.py import
music21.harmony at module scope, and parsers/musicXML_reader.py imports
music21 and names its classes in annotations. Phase 1 makes those imports
function-local; until then this stub lets the shared code import in
Pyodide without the real (heavy) package.

Every entry point raises, so the code takes its existing no-music21 paths:
MusicXMLReader.load() falls back to its ElementTree extractors, and
chord-symbol resolution returns the root name with no pitches.
"""


class _Unavailable:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("music21 is not installed (RSBV spike stub)")


class _Namespace:
    def __init__(self, **members):
        self.__dict__.update(members)


def _unavailable(*args, **kwargs):
    raise RuntimeError("music21 is not installed (RSBV spike stub)")


converter = _Namespace(parse=_unavailable, parseData=_unavailable)
stream = _Namespace(Score=_Unavailable)
duration = _Namespace(Duration=_Unavailable)
tempo = _Namespace(MetronomeMark=_Unavailable)
key = _Namespace(KeySignature=_Unavailable, Key=_Unavailable)
meter = _Namespace(TimeSignature=_Unavailable)
harmony = _Namespace(ChordSymbol=_Unavailable)

RSBV_STUB = True
