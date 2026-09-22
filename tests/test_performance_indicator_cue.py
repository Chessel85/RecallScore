# tests/test_performance_indicator_cue.py
"""Options > Performance Indicator (Ctrl+C cycles it): the "ding" that fires
when the cursor arrives on a row Region 3's note list marks as a MarkingRow -
see UserPlans/PerformanceIndicatorCue.md and RegionPresenter.
update_timeline_views's `fire =` gate.
"""
from PySide6.QtCore import Qt

from models.performance_indicator_mode import (
    PERFORMANCE_INDICATOR_ALWAYS_ON,
    PERFORMANCE_INDICATOR_OFF,
    PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING,
)
from tests.support.main_window_helpers import load_and_wait, no_lead_in
from widgets import accessible_announcer


def _enable_structural_changes(window):
    """A time/key/tempo change's note-list row is category
    "structural_changes" - off by default (marking_categories_off starts as
    every category, see main_window._on_score_loaded), so the cue's other
    gate (Ctrl+N) needs turning on before any test here can see a
    MarkingRow to fire on."""
    window.presenter.toggle_marking_category_in_note_list("structural_changes")


def _move_into_the_time_signature_change(qtbot, window):
    # ts_change_score: 4/4 (bar 1, 4 slices) -> 6/8 (bar 2) -> 4/4 (bar 3) -
    # four Right presses land on the first slice of bar 2.
    for _ in range(4):
        qtbot.keyClick(window.region_3, Qt.Key.Key_Right)


def test_off_never_fires(window, qtbot, null_synth, ts_change_score):
    load_and_wait(window, qtbot, ts_change_score)
    _enable_structural_changes(window)
    assert window.presenter.performance_indicator_mode == PERFORMANCE_INDICATOR_OFF
    null_synth.performance_cues.clear()

    _move_into_the_time_signature_change(qtbot, window)

    assert null_synth.performance_cues == []


def test_on_except_when_playing_fires_on_navigation(window, qtbot, null_synth, ts_change_score):
    load_and_wait(window, qtbot, ts_change_score)
    _enable_structural_changes(window)
    window.presenter.performance_indicator_mode = PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING
    null_synth.performance_cues.clear()

    _move_into_the_time_signature_change(qtbot, window)

    assert len(null_synth.performance_cues) == 1


def test_on_except_when_playing_does_not_fire_on_a_simulated_playback_step(
    window, qtbot, null_synth, ts_change_score
):
    load_and_wait(window, qtbot, ts_change_score)
    _enable_structural_changes(window)
    window.presenter.performance_indicator_mode = PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING
    window._music_data.active_event_index = 3  # first slice of bar 2 (the change)
    null_synth.performance_cues.clear()
    # Fake a real play run in progress (PlaybackController.is_play_run_active)
    # without spinning up actual playback machinery.
    window.presenter._is_playing = lambda: True

    window.presenter.update_timeline_views(play_all=False)

    assert null_synth.performance_cues == []


def test_always_on_fires_on_navigation_and_on_a_simulated_playback_step(
    window, qtbot, null_synth, ts_change_score
):
    load_and_wait(window, qtbot, ts_change_score)
    _enable_structural_changes(window)
    window.presenter.performance_indicator_mode = PERFORMANCE_INDICATOR_ALWAYS_ON
    null_synth.performance_cues.clear()

    _move_into_the_time_signature_change(qtbot, window)

    assert len(null_synth.performance_cues) == 1

    null_synth.performance_cues.clear()
    window.presenter._is_playing = lambda: True

    window.presenter.update_timeline_views(play_all=False)

    assert len(null_synth.performance_cues) == 1


def test_a_same_position_refresh_never_fires_regardless_of_mode(
    window, qtbot, null_synth, ts_change_score
):
    """A Region 2 filter toggle (or any other play_all=False refresh) at the
    SAME cursor position, with no real play run active, is neither a manual
    navigation move nor a playback step - it must stay silent even in
    Always-on."""
    load_and_wait(window, qtbot, ts_change_score)
    _enable_structural_changes(window)
    window.presenter.performance_indicator_mode = PERFORMANCE_INDICATOR_ALWAYS_ON
    _move_into_the_time_signature_change(qtbot, window)
    null_synth.performance_cues.clear()

    window.presenter.update_timeline_views(play_all=False)  # no real play run

    assert null_synth.performance_cues == []


def test_always_on_fires_during_a_real_play_run_with_no_lead_in_or_looping(
    window, qtbot, null_synth, repeats_and_endings_score
):
    """Regression test (live-reported): MainWindow's own is_playing lambda,
    not just RegionPresenter's fire= gate in isolation. is_play_run_active
    alone is False for an entire plain "play to end" run when both lead-in
    and looping are off - _start_from_cursor only builds a _PlayRun (what
    is_play_run_active checks) when either is on, otherwise it calls
    sequencer.play_from() directly. MainWindow must combine is_play_run_
    active with sequencer.is_playing (same reasoning as PlaybackController.
    end_mixer_edit) so Always-on still fires on a real step in this,
    the most common playback shape."""
    load_and_wait(window, qtbot, repeats_and_endings_score)
    no_lead_in(window)
    window.presenter.toggle_marking_category_in_note_list("repeats_endings")
    window.presenter.performance_indicator_mode = PERFORMANCE_INDICATOR_ALWAYS_ON

    window.toggle_play_stop()  # a real play run, no lead-in, no loop
    assert window.playback.is_play_run_active is False  # the gap this test guards
    null_synth.performance_cues.clear()

    # The exact signal a real Sequencer step sends, landing on measure 2
    # (index 1) where the repeat opens.
    window.playback.playback_cursor_stepped.emit(1, False)

    assert len(null_synth.performance_cues) == 1
    window.toggle_play_stop()  # stop, so no timer keeps running into the next test


def test_ctrl_c_cycles_and_announces(window, qtbot, monkeypatch, minimal_score):
    load_and_wait(window, qtbot, minimal_score)
    spoken = []
    monkeypatch.setattr(accessible_announcer, "announce", lambda w, m: spoken.append(m))
    assert window.presenter.performance_indicator_mode == PERFORMANCE_INDICATOR_OFF

    window.cycle_performance_indicator_mode()
    assert window.presenter.performance_indicator_mode == PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING

    window.cycle_performance_indicator_mode()
    assert window.presenter.performance_indicator_mode == PERFORMANCE_INDICATOR_ALWAYS_ON

    window.cycle_performance_indicator_mode()
    assert window.presenter.performance_indicator_mode == PERFORMANCE_INDICATOR_OFF

    assert spoken == [
        "Performance indicator on except when playing.",
        "Performance indicator always on.",
        "Performance indicator off.",
    ]


def test_submenu_checked_item_follows_the_cycle(window, qtbot, minimal_score):
    load_and_wait(window, qtbot, minimal_score)
    a = window._actions
    assert a.performance_indicator_off.isChecked() is True
    assert a.performance_indicator_on_except_when_playing.isChecked() is False
    assert a.performance_indicator_always_on.isChecked() is False

    window.cycle_performance_indicator_mode()

    assert a.performance_indicator_off.isChecked() is False
    assert a.performance_indicator_on_except_when_playing.isChecked() is True
    assert a.performance_indicator_always_on.isChecked() is False

    window.cycle_performance_indicator_mode()

    assert a.performance_indicator_off.isChecked() is False
    assert a.performance_indicator_on_except_when_playing.isChecked() is False
    assert a.performance_indicator_always_on.isChecked() is True
