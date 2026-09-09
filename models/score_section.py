# models/score_section.py
"""One selectable section of a score.

A single MusicXML file can hold several independent pieces back to back (see
`UserPlans/MultiSectionScores.md`). The chosen architecture builds one
complete, independent `TimelineBuild` per section and keeps them all on
`MusicData`; "select a section" then means "apply that section's
`TimelineBuild`".

Every score has at least one `ScoreSection`. MIDI, Guitar Pro and Ultimate
Guitar scores - and any MusicXML file without a `<measure number>` restart -
produce exactly one, with an empty `label`, so the downstream path is
unchanged from before this feature existed.
"""
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ScoreSection:
    """`build` is a `models.timeline_build.TimelineBuild` - a full, standalone
    timeline plus its side-channel markers, exactly what `build_timeline`
    returns for a whole file. `credits` holds the per-section Region 1
    overrides (key/time/tempo taken from this section's first slice);
    populated by task 5, empty until then."""

    index: int
    label: str
    build: Any
    credits: Dict[str, str] = field(default_factory=dict)
