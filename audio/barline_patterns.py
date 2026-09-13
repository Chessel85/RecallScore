# audio/barline_patterns.py
"""PerformanceMarkingsStrategy.md section 10: barline sound patterns beyond
the plain single beep, plus the declarations widgets/sound_icon_dictionary_
dialog.py reads to describe them.

Same plain-module shape as audio/boundary_cue.py and audio/performance_cue.py.
A one-shot-sample technique already loaded into the project soundfont via
audio/metronome.py's [preset:click_default] preset is reused rather than
adding a new sample: a "long" step is the beat-1 accent sample, a "short"
step the offbeat sample, and "heavy" is the same accent sample pitched an
octave down - FluidSynth pitches a sample by MIDI note number, so a "lower
beep" needs no new asset.

Reserved on its own channel (BARLINE_PATTERN_CHANNEL) so a multi-step
pattern's own successive noteons - which DO cut each other off on purpose,
one beep's release giving way to the next exactly like every other one-shot
in this app - never collide with an UNRELATED one-shot (the metronome click,
the boundary cue, ...) that happens to share a channel. It sits below
BOUNDARY_CUE_CHANNEL (250) in the reserved 244-255 block.
"""
from typing import Dict, List, NamedTuple, Optional, Tuple

from audio.metronome import (
    METRONOME_ACCENT_NOTE,
    METRONOME_BANK,
    METRONOME_OFFBEAT_NOTE,
    METRONOME_PROGRAM,
)

BARLINE_PATTERN_CHANNEL = 249
BARLINE_PATTERN_BANK = METRONOME_BANK
BARLINE_PATTERN_PROGRAM = METRONOME_PROGRAM

_LONG_NOTE = METRONOME_ACCENT_NOTE
_SHORT_NOTE = METRONOME_OFFBEAT_NOTE
_HEAVY_NOTE = METRONOME_ACCENT_NOTE - 12  # same sample, an octave down
_VELOCITY = 100
_SOFT_VELOCITY = 70

# Gap between successive steps of a multi-step pattern. The longest pattern
# (repeat_end_and_start, 5 steps) is comfortably inside a fast Left/Right
# repeat at this spacing (strategy section 10).
STEP_MS = 90


class BarlineStep(NamedTuple):
    pitch: int
    velocity: int


def _step(pitch: int, velocity: int = _VELOCITY) -> BarlineStep:
    return BarlineStep(pitch, velocity)


# One entry per strategy section 10 sound row beyond the plain beep, which
# keeps its own pre-existing code path (PlaybackController.
# play_barline_indicator's click_event_for_beat call) unchanged by this
# stage - it is the one row the strategy calls "today's behaviour".
#
# The repeat mnemonic: the short beeps are the repeat dots, and they sit on
# the side of the long beep that the repeated music is on, exactly as the
# notation prints them - so a repeat START (forward - the repeated music
# comes AFTER it) is long-then-short-short, and a repeat END (backward - the
# repeated music came BEFORE it) is short-short-then-long.
BARLINE_PATTERNS: Dict[str, Dict] = {
    "double": {
        "steps": [_step(_SHORT_NOTE), _step(_SHORT_NOTE)],
        "meaning": "Double barline - a section division",
    },
    "heavy": {
        "steps": [_step(_HEAVY_NOTE)],
        "meaning": "Heavy barline - an emphatic division, or the opening of a section",
    },
    "tick_or_short": {
        "steps": [_step(_SHORT_NOTE, _SOFT_VELOCITY)],
        "meaning": "Tick or short (mensurstrich) barline",
    },
    "repeat_start": {
        "steps": [_step(_LONG_NOTE), _step(_SHORT_NOTE), _step(_SHORT_NOTE)],
        "meaning": "Repeat start (forward repeat barline)",
    },
    "repeat_end": {
        "steps": [_step(_SHORT_NOTE), _step(_SHORT_NOTE), _step(_LONG_NOTE)],
        "meaning": "Repeat end (backward repeat barline)",
    },
    "repeat_end_and_start": {
        "steps": [
            _step(_SHORT_NOTE), _step(_SHORT_NOTE), _step(_LONG_NOTE),
            _step(_SHORT_NOTE), _step(_SHORT_NOTE),
        ],
        "meaning": "Combined repeat end and start at one barline",
    },
}


def events_for_pattern(kind: str) -> List[Tuple[int, int, int, int, int]]:
    """(channel, bank, program, pitch, velocity) per step of `kind`, in
    playback order - what PlaybackController schedules STEP_MS apart
    through SynthEngine.play_click."""
    steps = BARLINE_PATTERNS[kind]["steps"]
    return [
        (BARLINE_PATTERN_CHANNEL, BARLINE_PATTERN_BANK, BARLINE_PATTERN_PROGRAM, s.pitch, s.velocity)
        for s in steps
    ]


def pattern_for_crossing(
    before_measure: int, after_measure: int, repeat_spans, ending_spans, barline_marks
) -> Optional[str]:
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
