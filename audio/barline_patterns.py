# audio/barline_patterns.py
"""PerformanceMarkingsStrategy.md section 10: barline sound patterns beyond
the plain single beep, plus the declarations widgets/sound_icon_dictionary_
dialog.py reads to describe them.

Same plain-module shape as audio/boundary_cue.py and audio/performance_cue.py.
Each bar-style/repeat variant - including the plain barline case - is its own
recorded one-shot sample in [preset:barline_patterns] (tools/config.ini),
rather than being synthesized from the metronome's click samples. A repeat
barline's short-short-long rhythm is baked into its own recording, so playing
one is a single note-on rather than a scheduled multi-step sequence.

Reserved on its own channel (BARLINE_PATTERN_CHANNEL) so these one-shots -
which DO cut each other off on purpose, the same as every other one-shot in
this app - never collide with an UNRELATED one-shot (the metronome click, the
boundary cue, ...) that happens to share a channel. It sits below
BOUNDARY_CUE_CHANNEL (250) in the reserved 244-255 block.
"""
from typing import Dict, List, Tuple

BARLINE_PATTERN_CHANNEL = 249
BARLINE_PATTERN_BANK = 0
BARLINE_PATTERN_PROGRAM = 7  # [preset:barline_patterns] in tools/config.ini

_VELOCITY = 127

# Gap between successive steps of a multi-step play_event_sequence call.
# Barline patterns are single-sample one-shots now, but PlaybackController.
# play_event_sequence is shared with other multi-step sequences (e.g. the
# lead-in click) that still need a step spacing.
STEP_MS = 90

# The plain barline beep (today's unchanged behaviour, suppressed under the
# metronome) - PlaybackController.play_barline_indicator's own fallback, kept
# separate from BARLINE_PATTERNS below since it isn't selected by
# pattern_for_crossing.
PLAIN_BARLINE_NOTE = 60

# One entry per strategy section 10 sound row beyond the plain beep. `note`
# is this pattern's own key in [preset:barline_patterns] - each already a
# complete recorded pattern (e.g. repeat_end_and_start's short-short-long-
# short-short), so no scheduling is needed to reproduce it.
BARLINE_PATTERNS: Dict[str, Dict] = {
    "double": {
        "note": 62,
        "meaning": "Double barline - a section division",
    },
    "heavy": {
        "note": 63,
        "meaning": "Heavy barline - an emphatic division, or the opening of a section",
    },
    "tick_or_short": {
        "note": 61,
        "meaning": "Tick or short (mensurstrich) barline",
    },
    "repeat_start": {
        "note": 64,
        "meaning": "Repeat start (forward repeat barline)",
    },
    "repeat_end": {
        "note": 65,
        "meaning": "Repeat end (backward repeat barline)",
    },
    "repeat_end_and_start": {
        "note": 66,
        "meaning": "Combined repeat end and start at one barline",
    },
}


def _event(note: int) -> Tuple[int, int, int, int, int]:
    return (BARLINE_PATTERN_CHANNEL, BARLINE_PATTERN_BANK, BARLINE_PATTERN_PROGRAM, note, _VELOCITY)


def plain_barline_event() -> Tuple[int, int, int, int, int]:
    """(channel, bank, program, pitch, velocity) for an ordinary barline -
    PlaybackController.play_barline_indicator's fallback when
    pattern_for_crossing finds no repeat/double/heavy/tick mark."""
    return _event(PLAIN_BARLINE_NOTE)


def events_for_pattern(kind: str) -> List[Tuple[int, int, int, int, int]]:
    """(channel, bank, program, pitch, velocity) for `kind`, as a
    single-element list - what PlaybackController.play_event_sequence and
    Help > Sound Icon Dictionary's Play button both sound. A list, not a bare
    tuple, so both callers can treat every catalog entry the same way
    regardless of how many steps it takes to play."""
    return [_event(BARLINE_PATTERNS[kind]["note"])]


def pattern_for_crossing(
    before_measure: int, after_measure: int, repeat_spans, ending_spans, barline_marks
) -> "str | None":
    """Which BARLINE_PATTERNS key (if any) sounds for crossing from
    before_measure to after_measure, per strategy section 10. None means the
    plain single beep (today's unchanged behaviour, suppressed under the
    metronome) is all that applies - including an ordinary bar-style, a
    dotted/dashed subdividing barline (section 2's inventory keeps those at
    "one short beep", not a distinct pattern), and no barline mark at all.

    `ending_spans` is accepted but unused: the strategy's sound table lists
    only bar-style and repeat variants - an ending's boundary is a plain
    barline underneath, and its start/end are already read in the note list
    (stage 3) - so a caller can pass MusicData.ending_spans through without
    this needing to special-case it."""
    repeat_end = any(s.end_measure == before_measure for s in repeat_spans)
    repeat_start = any(s.start_measure == after_measure for s in repeat_spans)
    if repeat_end and repeat_start:
        return "repeat_end_and_start"
    if repeat_end:
        return "repeat_end"
    if repeat_start:
        return "repeat_start"

    mark = next(
        (m for m in barline_marks if m.measure == before_measure and m.location != "left"),
        None,
    )
    if mark is None:
        mark = next(
            (m for m in barline_marks if m.measure == after_measure and m.location == "left"),
            None,
        )
    if mark is None:
        return None
    if mark.kind == "double_barline":
        return "double"
    style = mark.style.lower()
    if "heavy" in style:
        return "heavy"
    if style in ("tick", "short"):
        return "tick_or_short"
    return None
