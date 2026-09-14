# tests/test_bar_line_indicator.py
"""Options > Bar Line Indicator (Ctrl+B): a high metronome beep when a plain
Left/Right step crosses a bar line, so bar boundaries are audible while
arrowing through notes.
"""
import pytest

from audio.barline_patterns import BARLINE_PATTERN_CHANNEL, BARLINE_PATTERNS, PLAIN_BARLINE_NOTE
from models.barline_mark import BarlineMark
from models.repeat_span import RepeatSpan
from tests.support.main_window_helpers import load_and_wait
from widgets import accessible_announcer


def test_off_by_default_no_beep_on_crossing(window, qtbot, null_synth, many_measures_score):
    load_and_wait(window, qtbot, many_measures_score)
    null_synth.clicks.clear()

    window.navigation.timeline_right()  # each bar is one note - this crosses a bar line

    assert null_synth.clicks == []


def test_beeps_when_a_plain_step_crosses_a_bar_line(
    window, qtbot, null_synth, many_measures_score
):
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    null_synth.clicks.clear()

    window.navigation.timeline_right()

    assert len(null_synth.clicks) == 1
    click = null_synth.clicks[0]
    assert click["pitch"] == PLAIN_BARLINE_NOTE
    assert click["channel"] == BARLINE_PATTERN_CHANNEL


def test_no_beep_when_the_step_stays_inside_one_bar(
    window, qtbot, null_synth, minimal_score
):
    # minimal_score is four quarter notes in a single 4/4 bar.
    load_and_wait(window, qtbot, minimal_score)
    window.toggle_bar_line_indicator()
    null_synth.clicks.clear()

    window.navigation.timeline_right()

    assert null_synth.clicks == []


def test_no_beep_at_a_boundary_where_the_cursor_does_not_move(
    window, qtbot, null_synth, many_measures_score
):
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    null_synth.clicks.clear()

    window.navigation.timeline_left()  # already on the first note - can't move

    assert null_synth.clicks == []


def test_has_no_effect_while_the_metronome_is_on(
    window, qtbot, null_synth, many_measures_score
):
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    window.toggle_metronome()
    null_synth.clicks.clear()

    window.navigation.timeline_right()

    # Only the ordinary per-step audition click - the indicator adds nothing.
    assert len(null_synth.clicks) == 1


def test_still_beeps_while_only_the_position_announcer_is_on(
    window, qtbot, null_synth, many_measures_score
):
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    window.toggle_position_announcer()
    null_synth.clicks.clear()

    window.navigation.timeline_right()

    assert [c["pitch"] for c in null_synth.clicks] == [PLAIN_BARLINE_NOTE]


def test_ctrl_b_toggles_menu_state_and_announces(
    window, qtbot, monkeypatch, many_measures_score
):
    load_and_wait(window, qtbot, many_measures_score)
    spoken = []
    monkeypatch.setattr(accessible_announcer, "announce", lambda w, m: spoken.append(m))

    assert window._actions.bar_line_indicator.isChecked() is False

    window.toggle_bar_line_indicator()
    assert window._actions.bar_line_indicator.isChecked() is True
    assert window._music_data.bar_line_indicator_enabled is True
    assert spoken == ["Bar line indicator on"]

    window.toggle_bar_line_indicator()
    assert window._actions.bar_line_indicator.isChecked() is False
    assert window._music_data.bar_line_indicator_enabled is False
    assert spoken == ["Bar line indicator on", "Bar line indicator off"]


def test_the_beep_fires_after_the_destination_note_audition(
    window, qtbot, monkeypatch, null_synth, many_measures_score
):
    """The beep is on BARLINE_PATTERN_CHANNEL, which stop_all_notes()
    releases, and the note audition calls stop_all_notes() - so the beep
    must be emitted after the audition, not before."""
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    calls = []
    real_play_chord = null_synth.play_chord
    real_play_click = null_synth.play_click
    monkeypatch.setattr(
        null_synth, "play_chord",
        lambda *a, **k: (calls.append("note"), real_play_chord(*a, **k))[1],
    )
    monkeypatch.setattr(
        null_synth, "play_click",
        lambda *a, **k: (calls.append("click"), real_play_click(*a, **k))[1],
    )

    window.navigation.timeline_right()

    assert "note" in calls and "click" in calls
    assert calls.index("click") > calls.index("note")


def test_saved_per_score_in_the_rsc_and_restored_on_reload(
    window, qtbot, many_measures_score
):
    from persistence import score_config

    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    window._save_current_score_config()

    saved = score_config.load_for(many_measures_score)
    assert saved is not None
    assert saved.bar_line_indicator_enabled is True

    load_and_wait(window, qtbot, many_measures_score)
    assert window._music_data.bar_line_indicator_enabled is True
    assert window._actions.bar_line_indicator.isChecked() is True


def test_repeat_start_pattern_sounds_on_the_bar_line_pattern_channel(
    window, qtbot, null_synth, many_measures_score
):
    """PerformanceMarkingsImplementationPlan.md stage 4: a repeat start
    barline gets its own recorded one-shot on its own reserved channel, not
    the plain barline beep."""
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    window._music_data.repeat_spans = [RepeatSpan(start_measure=2, end_measure=12)]
    window._music_data.active_event_index = 0  # bar 1, about to step into bar 2
    null_synth.clicks.clear()

    window.navigation.timeline_right()
    qtbot.wait(200)

    assert len(null_synth.clicks) == 1  # repeat_start's own recorded pattern
    assert all(c["channel"] == BARLINE_PATTERN_CHANNEL for c in null_synth.clicks)


def test_repeat_pattern_sounds_even_while_the_metronome_is_running(
    window, qtbot, null_synth, many_measures_score
):
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    window.toggle_metronome()
    window._music_data.repeat_spans = [RepeatSpan(start_measure=2, end_measure=12)]
    window._music_data.active_event_index = 0
    null_synth.clicks.clear()

    window.navigation.timeline_right()
    qtbot.wait(200)

    pattern_clicks = [c for c in null_synth.clicks if c["channel"] == BARLINE_PATTERN_CHANNEL]
    assert len(pattern_clicks) == 1


def test_plain_barline_beep_is_unaffected_by_stage_4(
    window, qtbot, null_synth, many_measures_score
):
    """No repeat/double/heavy/tick mark at this boundary: the plain beep
    still plays, now on its own recorded sample."""
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    null_synth.clicks.clear()

    window.navigation.timeline_right()
    qtbot.wait(200)

    assert len(null_synth.clicks) == 1
    assert null_synth.clicks[0]["channel"] == BARLINE_PATTERN_CHANNEL
    assert null_synth.clicks[0]["pitch"] == PLAIN_BARLINE_NOTE


@pytest.mark.parametrize(
    "setup, expected_note",
    [
        (
            lambda md: setattr(md, "repeat_spans", [RepeatSpan(start_measure=5, end_measure=8)])
            or setattr(md, "barline_marks", []),
            BARLINE_PATTERNS["repeat_start"]["note"],
        ),
        (
            lambda md: setattr(md, "repeat_spans", [RepeatSpan(start_measure=1, end_measure=4)])
            or setattr(md, "barline_marks", []),
            BARLINE_PATTERNS["repeat_end"]["note"],
        ),
        (
            lambda md: setattr(
                md, "repeat_spans",
                [RepeatSpan(start_measure=1, end_measure=4), RepeatSpan(start_measure=5, end_measure=8)],
            ) or setattr(md, "barline_marks", []),
            BARLINE_PATTERNS["repeat_end_and_start"]["note"],
        ),
        (
            lambda md: setattr(md, "repeat_spans", []) or setattr(
                md, "barline_marks",
                [BarlineMark(kind="double_barline", style="double", measure=4, location="right")],
            ),
            BARLINE_PATTERNS["double"]["note"],
        ),
        (
            lambda md: setattr(md, "repeat_spans", []) or setattr(
                md, "barline_marks",
                [BarlineMark(kind="other_barline", style="heavy", measure=4, location="right")],
            ),
            BARLINE_PATTERNS["heavy"]["note"],
        ),
        (
            lambda md: setattr(md, "repeat_spans", []) or setattr(
                md, "barline_marks",
                [BarlineMark(kind="other_barline", style="tick", measure=4, location="right")],
            ),
            BARLINE_PATTERNS["tick_or_short"]["note"],
        ),
    ],
    ids=["repeat_start", "repeat_end", "repeat_end_and_start", "double", "heavy", "tick"],
)
def test_pattern_sounds_the_same_note_whichever_direction_the_barline_is_crossed(
    window, qtbot, null_synth, many_measures_score, setup, expected_note
):
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    setup(window._music_data)

    null_synth.clicks.clear()
    window.playback.play_barline_indicator(4, 5)
    rightward_note = null_synth.clicks[-1]["pitch"]

    null_synth.clicks.clear()
    window.playback.play_barline_indicator(5, 4)
    leftward_note = null_synth.clicks[-1]["pitch"]

    assert rightward_note == leftward_note == expected_note


def test_leftward_crossing_of_a_plain_barline_still_plays_the_plain_beep(
    window, qtbot, null_synth, many_measures_score
):
    load_and_wait(window, qtbot, many_measures_score)
    window.toggle_bar_line_indicator()
    null_synth.clicks.clear()

    window.playback.play_barline_indicator(5, 4)

    assert len(null_synth.clicks) == 1
    assert null_synth.clicks[0]["pitch"] == PLAIN_BARLINE_NOTE
    assert null_synth.clicks[0]["channel"] == BARLINE_PATTERN_CHANNEL


def test_defaults_off_and_is_per_score_not_carried_between_scores(
    window, qtbot, many_measures_score, minimal_score
):
    load_and_wait(window, qtbot, many_measures_score)
    assert window._music_data.bar_line_indicator_enabled is False  # default off
    window.toggle_bar_line_indicator()
    assert window._music_data.bar_line_indicator_enabled is True

    # A different score with no saved .rsc starts off, not carried over.
    load_and_wait(window, qtbot, minimal_score)
    assert window._music_data.bar_line_indicator_enabled is False
    assert window._actions.bar_line_indicator.isChecked() is False
