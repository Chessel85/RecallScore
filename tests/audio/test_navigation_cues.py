"""audio/navigation_cues.py: the shared decisions behind a move's app sounds,
used by the desktop PlaybackController and the web bridge alike."""
from types import SimpleNamespace

from audio.barline_patterns import events_for_pattern, plain_barline_event
from audio.metronome import click_event_for_beat
from audio.navigation_cues import barline_indicator_events, position_cues
from audio.position_announcer import announcement_event_for_beat
from models.repeat_span import RepeatSpan


def _data(beat=1.0, metronome=False, announcer=False, indicator=True, repeats=()):
    current = None if beat is None else SimpleNamespace(beat_position=beat)
    return SimpleNamespace(
        get_current_slice=lambda: current,
        metronome_enabled=metronome,
        position_announcer_enabled=announcer,
        bar_line_indicator_enabled=indicator,
        repeat_spans=list(repeats), ending_spans=[], barline_marks=[],
    )


def test_position_cues_are_off_until_switched_on():
    assert position_cues(_data()) == (None, None)


def test_position_cues_follow_the_beat():
    click, word = position_cues(_data(beat=1.0, metronome=True, announcer=True))
    assert click == click_event_for_beat(1.0)
    assert word == announcement_event_for_beat(1.0)


def test_no_click_off_the_beat_but_still_a_word():
    click, word = position_cues(_data(beat=1.5, metronome=True, announcer=True))
    assert click is None
    assert word == announcement_event_for_beat(1.5)


def test_no_slice_no_cues():
    assert position_cues(_data(beat=None, metronome=True, announcer=True)) == (None, None)


def test_indicator_off_is_silent():
    assert barline_indicator_events(_data(indicator=False), 1, 2) == []


def test_plain_bar_line_beeps_unless_the_metronome_is_on():
    assert barline_indicator_events(_data(), 1, 2) == [plain_barline_event()]
    assert barline_indicator_events(_data(metronome=True), 1, 2) == []


def test_a_repeat_sounds_its_pattern_from_either_side_even_with_the_metronome():
    data = _data(metronome=True, repeats=[RepeatSpan(start_measure=5, end_measure=8)])
    assert barline_indicator_events(data, 4, 5) == events_for_pattern("repeat_start")
    assert barline_indicator_events(data, 5, 4) == events_for_pattern("repeat_start")
