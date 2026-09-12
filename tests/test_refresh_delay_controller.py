# tests/test_refresh_delay_controller.py
from types import SimpleNamespace

from controllers.refresh_delay_controller import RefreshDelayController
from models.refresh_settings import RefreshSettings
from tests.support.fake_timer import FakeTimer


def _make_session():
    music_data = SimpleNamespace(active_event_index=None)
    return SimpleNamespace(music_data=music_data)


def _make_controller():
    session = _make_session()
    timer = FakeTimer()
    controller = RefreshDelayController(session, timer=timer)
    return controller, session, timer


def test_refresh_on_delay_zero_playing_emits_synchronously():
    controller, session, timer = _make_controller()
    emitted = []
    controller.refresh_requested.connect(emitted.append)

    controller.handle_cursor_moved(5, False, True)

    assert session.music_data.active_event_index == 5
    assert emitted == [False]
    assert timer.running is False


def test_not_playing_emits_synchronously_regardless_of_settings():
    controller, session, timer = _make_controller()
    controller.set_settings(RefreshSettings(refresh_during_playback=False))
    emitted = []
    controller.refresh_requested.connect(emitted.append)

    controller.handle_cursor_moved(3, True, False)

    assert session.music_data.active_event_index == 3
    assert emitted == [True]


def test_refresh_off_while_playing_holds_until_flush():
    controller, session, timer = _make_controller()
    controller.set_settings(RefreshSettings(refresh_during_playback=False))
    emitted = []
    controller.refresh_requested.connect(emitted.append)

    controller.handle_cursor_moved(1, False, True)
    controller.handle_cursor_moved(2, False, True)

    assert emitted == []
    assert session.music_data.active_event_index is None

    controller.flush()

    assert emitted == [False]
    assert session.music_data.active_event_index == 2


def test_flush_with_nothing_pending_is_a_noop():
    controller, session, timer = _make_controller()
    emitted = []
    controller.refresh_requested.connect(emitted.append)

    controller.flush()

    assert emitted == []


def test_positive_delay_waits_for_the_timer():
    controller, session, timer = _make_controller()
    controller.set_settings(RefreshSettings(delay_ms=250))
    emitted = []
    controller.refresh_requested.connect(emitted.append)

    controller.handle_cursor_moved(7, False, True)

    assert emitted == []
    assert session.music_data.active_event_index is None
    assert timer.scheduled_ms[-1] == 250

    timer.fire()

    assert emitted == [False]
    assert session.music_data.active_event_index == 7


def test_two_steps_inside_one_delay_window_only_the_later_index_wins():
    controller, session, timer = _make_controller()
    controller.set_settings(RefreshSettings(delay_ms=250))
    emitted = []
    controller.refresh_requested.connect(emitted.append)

    controller.handle_cursor_moved(1, False, True)
    controller.handle_cursor_moved(2, False, True)

    timer.fire()

    assert emitted == [False]
    assert session.music_data.active_event_index == 2


def test_cancel_then_flush_emits_nothing():
    controller, session, timer = _make_controller()
    controller.set_settings(RefreshSettings(delay_ms=250))
    emitted = []
    controller.refresh_requested.connect(emitted.append)

    controller.handle_cursor_moved(9, False, True)
    controller.cancel()
    controller.flush()

    assert emitted == []
    assert session.music_data.active_event_index is None


def test_set_settings_flushes_a_pending_refresh_first():
    controller, session, timer = _make_controller()
    controller.set_settings(RefreshSettings(refresh_during_playback=False))
    emitted = []
    controller.refresh_requested.connect(emitted.append)

    controller.handle_cursor_moved(4, False, True)
    assert emitted == []

    controller.set_settings(RefreshSettings())

    assert emitted == [False]
    assert session.music_data.active_event_index == 4


def test_set_refresh_during_playback_returns_new_state():
    controller, _, _ = _make_controller()

    assert controller.set_refresh_during_playback(False) is False
    assert controller.settings.refresh_during_playback is False

    assert controller.set_refresh_during_playback(True) is True
    assert controller.settings.refresh_during_playback is True
