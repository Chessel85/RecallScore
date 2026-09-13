# tests/audio/test_barline_patterns.py
"""PerformanceMarkingsImplementationPlan.md stage 4: barline sound pattern
selection (strategy section 10)."""
from audio.barline_patterns import (
    BARLINE_PATTERN_CHANNEL,
    BARLINE_PATTERNS,
    events_for_pattern,
    pattern_for_crossing,
)
from models.barline_mark import BarlineMark
from models.ending_span import EndingSpan
from models.repeat_span import RepeatSpan


def test_repeat_start_pattern_crossing_into_the_opening_bar():
    spans = [RepeatSpan(start_measure=5, end_measure=8)]
    assert pattern_for_crossing(4, 5, spans, [], []) == "repeat_start"


def test_repeat_end_pattern_crossing_out_of_the_closing_bar():
    spans = [RepeatSpan(start_measure=5, end_measure=8)]
    assert pattern_for_crossing(8, 9, spans, [], []) == "repeat_end"


def test_combined_end_and_start_when_both_land_on_the_same_barline():
    spans = [RepeatSpan(start_measure=1, end_measure=4), RepeatSpan(start_measure=5, end_measure=8)]
    assert pattern_for_crossing(4, 5, spans, [], []) == "repeat_end_and_start"


def test_double_barline_pattern():
    marks = [BarlineMark(kind="double_barline", style="double", measure=4, location="right")]
    assert pattern_for_crossing(4, 5, [], [], marks) == "double"


def test_heavy_barline_pattern_for_every_heavy_style():
    for style in ("heavy", "heavy light", "heavy heavy"):
        marks = [BarlineMark(kind="other_barline", style=style, measure=4, location="right")]
        assert pattern_for_crossing(4, 5, [], [], marks) == "heavy"


def test_tick_and_short_barline_pattern():
    for style in ("tick", "short"):
        marks = [BarlineMark(kind="other_barline", style=style, measure=4, location="right")]
        assert pattern_for_crossing(4, 5, [], [], marks) == "tick_or_short"


def test_dotted_and_dashed_fall_back_to_the_plain_beep():
    """Section 2's inventory keeps a dotted/dashed subdividing barline at
    "one short beep" - the same as an ordinary barline, not a distinct
    pattern."""
    for style in ("dotted", "dashed"):
        marks = [BarlineMark(kind="other_barline", style=style, measure=4, location="right")]
        assert pattern_for_crossing(4, 5, [], [], marks) is None


def test_ordinary_barline_with_no_mark_at_all_falls_back_to_the_plain_beep():
    assert pattern_for_crossing(4, 5, [], [], []) is None


def test_ending_boundary_is_not_a_pattern_of_its_own():
    spans = [EndingSpan(number=1, start_measure=5, end_measure=8)]
    assert pattern_for_crossing(4, 5, [], spans, []) is None


def test_events_for_pattern_share_the_reserved_channel_and_match_declared_steps():
    for kind, spec in BARLINE_PATTERNS.items():
        events = events_for_pattern(kind)
        assert len(events) == len(spec["steps"])
        for event, step in zip(events, spec["steps"]):
            assert event[0] == BARLINE_PATTERN_CHANNEL
            assert event[3] == step.pitch
            assert event[4] == step.velocity


def test_longest_pattern_is_the_combined_repeat_barline():
    assert max(BARLINE_PATTERNS, key=lambda k: len(BARLINE_PATTERNS[k]["steps"])) == "repeat_end_and_start"
