# tests/audio/test_boundary_cue.py
"""Ref 2 AC4/Ref 3 AC4: boundary_cue_event() is the fixed (channel, bank,
program, pitch, velocity) tuple PlaybackController.play_boundary_cue fires
when a navigation key would step past the start or end of the timeline -
pure function, tested in isolation."""
from audio.metronome import METRONOME_CHANNEL
from audio.boundary_cue import (
    BOUNDARY_CUE_BANK,
    BOUNDARY_CUE_CHANNEL,
    BOUNDARY_CUE_NOTE,
    BOUNDARY_CUE_PROGRAM,
    BOUNDARY_CUE_VELOCITY,
    boundary_cue_event,
)
from audio.performance_cue import PERFORMANCE_CUE_CHANNEL
from audio.position_announcer import POSITION_ANNOUNCER_CHANNEL
from audio.voice_confirmation_cue import VOICE_CONTROL_CUE_CHANNEL
from audio.midi_input import LIVE_MIDI_INPUT_CHANNEL


def test_boundary_cue_event_fields():
    channel, bank, program, pitch, velocity = boundary_cue_event()
    assert channel == BOUNDARY_CUE_CHANNEL
    assert bank == BOUNDARY_CUE_BANK
    assert program == BOUNDARY_CUE_PROGRAM
    assert pitch == BOUNDARY_CUE_NOTE
    assert velocity == BOUNDARY_CUE_VELOCITY


def test_boundary_cue_channel_is_distinct_from_every_other_reserved_channel():
    assert BOUNDARY_CUE_CHANNEL not in {
        METRONOME_CHANNEL,
        POSITION_ANNOUNCER_CHANNEL,
        PERFORMANCE_CUE_CHANNEL,
        LIVE_MIDI_INPUT_CHANNEL,
        VOICE_CONTROL_CUE_CHANNEL,
    }


def test_boundary_cue_program_does_not_collide_with_the_other_project_soundfont_presets():
    """All the project-soundfont one-shots share one sfid; a distinct
    program number is what keeps program_select landing on the right sample
    (talking metronome 0, click 1, performance cue 2, voice cues 3-5)."""
    assert BOUNDARY_CUE_PROGRAM == 6
