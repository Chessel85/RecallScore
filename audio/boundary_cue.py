# audio/boundary_cue.py
"""Ref 2 AC4/Ref 3 AC4: the short sound played INSTEAD of moving when a
navigation key would step past the start or end of the active timeline.

Same plain-module shape as audio/performance_cue.py. A recorded one-shot
sample (tools/bells/bump.wav) routed through the small project-authored
soundfont, the same path the click / position announcer / performance cue
already use.
"""
from typing import Tuple

# Sixth reserved channel, alongside METRONOME_CLICK_CHANNEL (9),
# POSITION_ANNOUNCER_CHANNEL (8), PERFORMANCE_CUE_CHANNEL (7),
# LIVE_MIDI_INPUT_CHANNEL (6) and VOICE_CONTROL_CUE_CHANNEL (5), for the
# reason spelled out in position_announcer.py: FluidSynth releases a ringing
# one-shot by channel+key, not by preset, so unrelated sounds sharing a
# channel can cut each other off. MusicData.BOUNDARY_CUE_CHANNEL duplicates
# this value (models/ doesn't import audio/).
BOUNDARY_CUE_CHANNEL = 4
BOUNDARY_CUE_BANK = 0
BOUNDARY_CUE_PROGRAM = 6  # [preset:boundary_cue] in tools/config.ini
BOUNDARY_CUE_NOTE = 60
# Full MIDI velocity - a one-shot UI cue has no expressive reason to hold
# back, and SF2's default velocity curve measurably quietens anything below
# max (same note as the voice-control cues).
BOUNDARY_CUE_VELOCITY = 127


def boundary_cue_event() -> Tuple[int, int, int, int, int]:
    """(channel, bank, program, pitch, velocity) for the boundary cue - one
    generic sound for both the start and the end of the timeline."""
    return (
        BOUNDARY_CUE_CHANNEL,
        BOUNDARY_CUE_BANK,
        BOUNDARY_CUE_PROGRAM,
        BOUNDARY_CUE_NOTE,
        BOUNDARY_CUE_VELOCITY,
    )
