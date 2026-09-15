# models/key_change_mark.py
from dataclasses import dataclass


@dataclass
class KeyChangeMark:
    """PerformanceMarkingsImplementationPlanV2.md stage 10 rule 2: a part's
    own <attributes>/<key>/<fifths> changing partway through the piece,
    tracked per PART (not first-part-only, unlike measure_ts_fifths) so a
    mismatch between parts can be detected. Populated by TimelineBuilder.
    _handle_attributes as a side effect of build(); the part's FIRST key is
    never a change (_PartState.attributes_seen).

    is_score_level is resolved once, after every part has been walked
    (TimelineBuilder._resolve_key_time_levels): True for the MAJORITY value
    at that measure ("score when every part writes the same thing at that
    bar" - strategy section 3.3 rule 2 - reduces to majority-wins so one
    stray part doesn't spoil the row for every part that genuinely agrees
    with each other), False for every mark in the minority (one row per
    differing part).

    "Agrees" compares fifths - previous_fifths (the CHANGE), not the new
    fifths value itself - a transposing part's written key signature is
    permanently offset from a concert-pitch part's (a real orchestral score
    with clarinets/horns/etc. proves this: at one genuine, single, whole-
    orchestra key change every part reported a DIFFERENT new fifths value,
    each instrument's own transposition baked in), but a shared modulation
    shifts every part's own fifths by the SAME delta regardless of that
    fixed per-instrument offset.
    """

    part_id: str
    fifths: int
    previous_fifths: int
    measure: int
    beat_position: float
    quarters_from_start: float
    is_score_level: bool = False
