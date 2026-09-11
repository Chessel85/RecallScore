# audio/performance_cue.py
"""Ref 29: the Performance region's "something changed, check Region 5" cue.
Same plain-module shape as audio/metronome.py and audio/position_announcer.py.

Unlike those two, this cue isn't tied to a beat position - it fires when
RegionPresenter.refresh_region_5 sees the active row set change, plus one
narrow exception (MusicData.is_at_beginning_repeat_target) where it re-fires
on an unchanged row set - so performance_cue_event() takes no argument and
always returns the same event.
"""
from typing import Tuple

# One of the six reserved channels, alongside METRONOME_CHANNEL (255) and
# POSITION_ANNOUNCER_CHANNEL (254), for the reason spelled out in
# position_announcer.py: FluidSynth releases a ringing one-shot by
# channel+key, not by preset, so unrelated sounds sharing a channel can cut
# each other off. The six sit at the top of the 256-channel range (250-255)
# so parts get plain channels 0, 1, 2 ... with no gaps.
# MusicData.PERFORMANCE_CUE_CHANNEL duplicates this value (models/ doesn't
# import audio/).
PERFORMANCE_CUE_CHANNEL = 253
PERFORMANCE_CUE_BANK = 0
PERFORMANCE_CUE_PROGRAM = 2  # [preset:performance_cue_default]
PERFORMANCE_CUE_NOTE = 60
PERFORMANCE_CUE_VELOCITY = 100


def performance_cue_event() -> Tuple[int, int, int, int, int]:
    """(channel, bank, program, pitch, velocity) for the change cue - one
    generic sound, not a per-marker-type one (the user's explicit choice)."""
    return (
        PERFORMANCE_CUE_CHANNEL,
        PERFORMANCE_CUE_BANK,
        PERFORMANCE_CUE_PROGRAM,
        PERFORMANCE_CUE_NOTE,
        PERFORMANCE_CUE_VELOCITY,
    )
