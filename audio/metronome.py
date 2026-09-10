# audio/metronome.py
"""E8/Ref 14: metronome click constants and the one rule deciding whether a
beat position gets a click.

A plain module (constants + one pure function), not a class - same shape as
models/key_signatures.py and models/duration_units.py.

Both audio/sequencer.py (playback) and main_window.py (step navigation) call
click_event_for_beat(), so the two contexts click off one definition.
"""
from typing import Optional, Tuple

# Accent vs regular beat is which SAMPLE plays, not a velocity difference:
# SynthEngine loads soundfonts/recall_score_sounds.sf2 as a second soundfont
# alongside FluidR3_GM and program_selects it on METRONOME_CHANNEL.
# Synthesised clicks (a sawtooth lead, then GM Claves accented by velocity)
# were both tried and rejected as sounds.
METRONOME_CHANNEL = 255  # reserved in MusicData.RESERVED_CHANNELS so no real
                         # part lands here. The six Recall Score channels sit
                         # at the top of the 256-channel range (250-255) so
                         # parts get plain channels 0, 1, 2 ... with no gaps;
                         # the reservation is purely collision avoidance.
METRONOME_BANK = 0
METRONOME_PROGRAM = 1  # [preset:click_default] in tools/config.ini
METRONOME_ACCENT_NOTE = 60  # "accent" sample - beat 1 of every bar
METRONOME_OFFBEAT_NOTE = 61  # "offbeat" sample - every other beat
METRONOME_VELOCITY = 100

# Two extra click samples (tools/config.ini [preset:click_default] 62/63),
# used only by the Metronome Player tool's per-beat click pattern (A/B/C/D).
# click_event_for_beat above never uses these - it is the score metronome /
# lead-in / position announcer, which only ever distinguish accent vs offbeat.
METRONOME_CLICK_C_NOTE = 62
METRONOME_CLICK_D_NOTE = 63

_SYMBOL_TO_NOTE = {
    "A": METRONOME_ACCENT_NOTE,
    "B": METRONOME_OFFBEAT_NOTE,
    "C": METRONOME_CLICK_C_NOTE,
    "D": METRONOME_CLICK_D_NOTE,
}


def click_event_for_symbol(symbol) -> Optional[Tuple[int, int, int, int, int]]:
    """(channel, bank, program, pitch, velocity) for one Metronome Player
    pattern position, or None for a rest ('.') or any unknown symbol.

    Case-insensitive - the dialog normalises to upper case but callers need
    not. Same channel/soundfont as click_event_for_beat, just a wider choice
    of sample."""
    note = _SYMBOL_TO_NOTE.get(str(symbol).upper())
    if note is None:
        return None
    return METRONOME_CHANNEL, METRONOME_BANK, METRONOME_PROGRAM, note, METRONOME_VELOCITY


def click_event_for_beat(beat_position: float) -> Optional[Tuple[int, int, int, int, int]]:
    """(channel, bank, program, pitch, velocity) for a click at this beat
    position, or None if it isn't a whole beat - main beats are always whole
    numbers in the score's own ts-relative units (Ref 18), so this is the
    same "is this a beat" test everywhere it's needed.

    Duration is decided nowhere: each click zone is a one-shot, non-looping
    sample, and FluidSynth retires such a voice by itself once the sample
    data runs out. See SynthEngine.play_click.
    """
    if not float(beat_position).is_integer():
        return None
    pitch = METRONOME_ACCENT_NOTE if beat_position == 1 else METRONOME_OFFBEAT_NOTE
    return METRONOME_CHANNEL, METRONOME_BANK, METRONOME_PROGRAM, pitch, METRONOME_VELOCITY
