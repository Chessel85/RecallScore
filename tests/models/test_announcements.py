"""models/announcements.py: the spoken wording both the desktop and the web
version use. The strings are the desktop's, live-tested with NVDA - a change
here is heard by every user, so the tests pin them exactly."""
from models import announcements
from models.performance_indicator_mode import (
    PERFORMANCE_INDICATOR_ALWAYS_ON,
    PERFORMANCE_INDICATOR_OFF,
    PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING,
)


def test_measure_change_follows_terminology():
    assert announcements.measure_change(6, uk_terms=False) == "Measure 6."
    assert announcements.measure_change(6, uk_terms=True) == "Bar 6."


def test_loop_length_singular_and_plural():
    assert announcements.loop_length(1, uk_terms=True) == "Loop length 1 bar."
    assert announcements.loop_length(4, uk_terms=False) == "Loop length 4 measures."
    assert announcements.loop_length_status(2, uk_terms=True) == "Loop length: 2 bars"


def test_attribute_by_number_is_one_based_and_bounded():
    rows = [("step", "step", "C"), ("octave", "octave", "4")]
    assert announcements.attribute_by_number(rows, 2) == "octave: 4"
    assert announcements.attribute_by_number(rows, 0) is None
    assert announcements.attribute_by_number(rows, 3) is None


def test_mode_phrases_fall_back_to_the_default():
    assert announcements.play_mode("loop_once") == "Play mode: play loop once."
    assert announcements.play_mode("bogus") == "Play mode: play to end."
    assert announcements.loop_repeat_mode("bogus") == announcements.loop_repeat_mode("first")
    assert announcements.performance_indicator_mode(PERFORMANCE_INDICATOR_ALWAYS_ON) == (
        "Performance indicator always on."
    )
    assert announcements.performance_indicator_mode(
        PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING
    ) == "Performance indicator on except when playing."
    assert announcements.performance_indicator_mode("bogus") == (
        announcements.performance_indicator_mode(PERFORMANCE_INDICATOR_OFF)
    )


def test_toggles_and_status_fields():
    assert announcements.refresh_on_playback(True) == "Region refresh on."
    assert announcements.staves_collapsed(False) == "Staves uncollapsed"
    assert announcements.metronome_status(True) == "Metronome: On"
    assert announcements.position_announcer_status(False) == "Position Announcer: Off"
    assert announcements.pending_digits("12", uk_terms=False) == "Go to measure: 12"
