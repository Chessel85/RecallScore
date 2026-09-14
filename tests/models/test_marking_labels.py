# tests/models/test_marking_labels.py
"""Stage 4 of the PI tweaks plan: the "end of bar" wording in
models/marking_labels.py, unit-tested in isolation from any timeline."""
from models import marking_labels


def test_bar_beat_label_on_the_downbeat():
    assert marking_labels.bar_beat_label("bar", 12, 1, beats_in_bar=4) == "bar 12"


def test_bar_beat_label_mid_bar():
    assert marking_labels.bar_beat_label("bar", 12, 4.5, beats_in_bar=4) == "bar 12 beat 4.5"


def test_bar_beat_label_past_the_end_of_a_4_4_bar():
    assert marking_labels.bar_beat_label("bar", 12, 5, beats_in_bar=4) == "end of bar 12"


def test_bar_beat_label_past_the_end_of_a_3_4_bar():
    assert marking_labels.bar_beat_label("bar", 12, 4, beats_in_bar=3) == "end of bar 12"


def test_bar_beat_label_past_the_end_of_a_6_8_bar():
    assert marking_labels.bar_beat_label("bar", 12, 7, beats_in_bar=6) == "end of bar 12"


def test_bar_beat_label_without_beats_in_bar_never_says_end_of():
    # A caller that has no time signature to hand (beats_in_bar=None) keeps
    # today's behaviour rather than guessing.
    assert marking_labels.bar_beat_label("bar", 12, 5) == "bar 12 beat 5"


def test_bar_beat_label_does_not_capitalise_end():
    assert marking_labels.bar_beat_label("bar", 12, 5, beats_in_bar=4).startswith("end of")


def test_range_label_crossing_a_barline_to_the_end_of_the_bar():
    label = marking_labels.range_label(
        "bar", 3, 2, 12, 5, start_beats_in_bar=4, end_beats_in_bar=4
    )
    assert label == "bar 3 beat 2 to end of bar 12"


def test_range_label_crossing_a_barline_without_beats_in_bar_unchanged():
    label = marking_labels.range_label("bar", 3, 2, 12, 5)
    assert label == "bar 3 beat 2 to bar 12 beat 5"


def test_range_label_same_bar_ending_at_the_barline():
    label = marking_labels.range_label(
        "bar", 12, 2, 12, 5, start_beats_in_bar=4, end_beats_in_bar=4
    )
    assert label == "bar 12 beat 2 to end of bar 12"


def test_range_label_same_bar_mid_bar_unaffected():
    label = marking_labels.range_label(
        "bar", 12, 2, 12, 3, start_beats_in_bar=4, end_beats_in_bar=4
    )
    assert label == "bar 12 beat 2 to beat 3"


def test_range_label_both_ends_on_downbeats_still_bars_n_to_m():
    label = marking_labels.range_label(
        "bar", 3, 1, 12, 1, start_beats_in_bar=4, end_beats_in_bar=4
    )
    assert label == "bars 3 to 12"
