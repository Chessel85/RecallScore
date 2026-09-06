# tests/models/test_metronome_pattern.py
"""Pure pattern helpers for the Metronome Player tool - Qt-free, tested in
isolation like models/strum_pattern.py's own helpers."""
from models.metronome_pattern import (
    default_pattern,
    normalise_pattern,
    pattern_length_matches,
    snap_time_signature,
)


def test_default_pattern_accents_beat_one():
    assert default_pattern(4) == "ABBB"
    assert default_pattern(7) == "ABBBBBB"
    assert default_pattern(1) == "A"


def test_default_pattern_clamps_below_one():
    assert default_pattern(0) == "A"
    assert default_pattern(-3) == "A"


def test_normalise_pattern_strips_whitespace_and_upper_cases():
    assert normalise_pattern(" a.b ") == "A.B"
    assert normalise_pattern("a b\tc\nd") == "ABCD"


def test_pattern_length_matches_counts_positions():
    assert pattern_length_matches("ABBCDDD", 7) is True
    assert pattern_length_matches("ABBB", 5) is False
    assert pattern_length_matches(" a . b ", 3) is True


def test_snap_time_signature_clamps_numerator_and_snaps_denominator():
    assert snap_time_signature(15, 2) == (12, 2)
    assert snap_time_signature(4, 3) == (4, 4)
    assert snap_time_signature(0, 8) == (1, 8)
    assert snap_time_signature(3, 4) == (3, 4)
