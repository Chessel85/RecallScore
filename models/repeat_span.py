# models/repeat_span.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class RepeatSpan:
    """Ref 29: one forward-repeat/backward-repeat barline pair
    (<barline>/<repeat direction="forward"|"backward">), in measure numbers.
    Populated by TimelineBuilder._repeat_and_ending_spans as a side effect
    of build(), the same pattern as TempoChange/tempo_changes.

    Stage 7 (MusicXMLMarkingInventory.md priority list #7): `times`, from the
    backward repeat's own `times="N"` attribute - "play N times" surfaced in
    the Region 5 row text (models/marking_labels.repeat_times_suffix). None
    means the file didn't write one - the ordinary "play twice" reading,
    which gets no suffix at all (invariant 14 reports only what is written).
    `after_jump`, from `after-jump="yes"` - the repeat applies only after a
    da capo/dal segno jump has landed. Parsed and stored but not yet wired
    into playback stepping; that is a behaviour change out of scope for this
    stage's additive-only parser work."""

    start_measure: int
    end_measure: int
    times: Optional[int] = None
    after_jump: bool = False
