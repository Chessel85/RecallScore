# tests/audio/test_metronome.py
"""E8/Ref 14: click_event_for_beat is the one rule both the Sequencer
(playback) and MainWindow (navigation) use to decide whether/how a beat
position clicks - pure function, tested in isolation."""
from audio.metronome import (
    METRONOME_ACCENT_NOTE,
    METRONOME_BANK,
    METRONOME_CHANNEL,
    METRONOME_CLICK_C_NOTE,
    METRONOME_CLICK_D_NOTE,
    METRONOME_OFFBEAT_NOTE,
    METRONOME_PROGRAM,
    METRONOME_VELOCITY,
    click_event_for_beat,
    click_event_for_symbol,
)


def test_beat_one_is_accented():
    channel, bank, program, pitch, velocity = click_event_for_beat(1.0)
    assert channel == METRONOME_CHANNEL
    assert bank == METRONOME_BANK
    assert program == METRONOME_PROGRAM
    assert pitch == METRONOME_ACCENT_NOTE
    assert velocity == METRONOME_VELOCITY


def test_other_whole_beats_are_not_accented():
    _, _, _, pitch, velocity = click_event_for_beat(3.0)
    assert pitch == METRONOME_OFFBEAT_NOTE, "a different sample distinguishes the accent, not velocity"
    assert velocity == METRONOME_VELOCITY


def test_non_whole_beat_position_is_not_a_click():
    assert click_event_for_beat(1.5) is None
    assert click_event_for_beat(2.25) is None


# --- click_event_for_symbol (Metronome Player tool's per-beat pattern) ---


def test_symbol_a_and_b_reuse_the_score_metronome_samples():
    assert click_event_for_symbol("A")[3] == METRONOME_ACCENT_NOTE
    assert click_event_for_symbol("b")[3] == METRONOME_OFFBEAT_NOTE, "case-insensitive"


def test_symbol_c_and_d_are_the_two_new_samples_on_the_metronome_channel():
    for sym, note in (("C", METRONOME_CLICK_C_NOTE), ("d", METRONOME_CLICK_D_NOTE)):
        channel, bank, program, pitch, velocity = click_event_for_symbol(sym)
        assert (channel, bank, program) == (METRONOME_CHANNEL, METRONOME_BANK, METRONOME_PROGRAM)
        assert pitch == note
        assert velocity == METRONOME_VELOCITY


def test_rest_and_unknown_symbols_are_not_a_click():
    assert click_event_for_symbol(".") is None
    assert click_event_for_symbol("x") is None
