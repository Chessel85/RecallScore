# audio/performance_cue.py
"""Ref 29: the structural change cue - "the cursor just landed on a key
signature, time signature, or immediate tempo change" (PerformanceMarkings
Strategy.md section 7). Same plain-module shape as audio/metronome.py and
audio/position_announcer.py.

Originally a generic "something in Region 5 changed" cue; stage 6 of the
performance markings plan retired that broad trigger and narrowed it to
exactly these three structural changes, since everything else that used to
fire it now has its own note-list row where the user is already reading.
Unlike a beat-position cue, this one isn't tied to a beat - it fires
whenever RegionPresenter.refresh_region_5 finds
MusicData.structural_change_labels() non-empty at the cursor's current
position (never at index 0), so performance_cue_event() takes no argument
and always returns the same event - one sound for all three kinds
(decided in review: a second dimension of sound would only add something to
learn)."""
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
