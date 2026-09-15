# models/wavy_line_span.py
from dataclasses import dataclass


@dataclass
class WavyLineSpan:
    """A trill line crossing one or more barlines (<barline>/<wavy-line>),
    PerformanceMarkingsImplementationPlanV2.md stage 10 (inventory.csv:
    "Barline", "Length", "Low priority"). Barline-level like the fermata/
    segno/coda barline items, so it is scanned from the FIRST part only
    (structural, not per-voice - the same convention as repeat/ending spans)
    and rendered as one bare score-level range row via the SAME start/end-
    measure mechanism as RepeatSpan/EndingSpan."""

    start_measure: int
    end_measure: int
