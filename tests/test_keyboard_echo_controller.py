# tests/test_keyboard_echo_controller.py
"""KeyboardEchoController (F12 tutorial mode) - the `window` fixture (a real
MainWindow) since it reads live QAction shortcuts off ShortcutController,
same reasoning as test_shortcut_controller.py. eventFilter is called
directly with hand-built QKeyEvents (test_shortcut_capture_edit.py's own
pattern) rather than routed through the real Qt application event loop."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from widgets import accessible_announcer


def _key_event(key, modifiers=Qt.KeyboardModifier.NoModifier, event_type=QEvent.Type.KeyPress):
    return QKeyEvent(event_type, key, modifiers)


def _spoken(monkeypatch):
    spoken = []
    monkeypatch.setattr(accessible_announcer, "announce", lambda w, m: spoken.append(m))
    return spoken


def test_triggering_the_action_enters_echo_mode_and_announces_it(window, monkeypatch):
    spoken = _spoken(monkeypatch)

    window._actions.keyboard_echo_mode.trigger()

    assert window.keyboard_echo.is_active()
    assert window._actions.keyboard_echo_mode.isChecked()
    assert spoken and "echo mode" in spoken[-1].lower()


def test_a_bound_key_is_announced_by_name_instead_of_firing(window, monkeypatch):
    spoken = _spoken(monkeypatch)
    window.keyboard_echo.toggle()  # enter
    spoken.clear()

    event = _key_event(Qt.Key.Key_Space)
    consumed = window.keyboard_echo.eventFilter(window, event)

    assert consumed is True
    assert spoken == ["Play/Stop"]


def test_a_reserved_non_action_key_is_announced_by_its_reason(window, monkeypatch):
    spoken = _spoken(monkeypatch)
    window.keyboard_echo.toggle()  # enter
    spoken.clear()

    event = _key_event(Qt.Key.Key_Tab)
    window.keyboard_echo.eventFilter(window, event)

    assert spoken == ["Used to move between regions."]


def test_an_unbound_key_says_nothing_is_assigned(window, monkeypatch):
    spoken = _spoken(monkeypatch)
    window.keyboard_echo.toggle()  # enter
    spoken.clear()

    event = _key_event(Qt.Key.Key_J)
    window.keyboard_echo.eventFilter(window, event)

    assert spoken == ["Nothing assigned to this key."]


def test_f12_exits_instead_of_being_echoed(window, monkeypatch):
    spoken = _spoken(monkeypatch)
    window.keyboard_echo.toggle()  # enter
    spoken.clear()

    event = _key_event(Qt.Key.Key_F12)
    window.keyboard_echo.eventFilter(window, event)

    assert not window.keyboard_echo.is_active()
    assert not window._actions.keyboard_echo_mode.isChecked()
    assert spoken == ["Keyboard echo mode off."]


def test_shortcut_override_events_are_swallowed_without_announcing(window, monkeypatch):
    spoken = _spoken(monkeypatch)
    window.keyboard_echo.toggle()  # enter
    spoken.clear()

    event = _key_event(Qt.Key.Key_Space, event_type=QEvent.Type.ShortcutOverride)
    consumed = window.keyboard_echo.eventFilter(window, event)

    assert consumed is True
    assert event.isAccepted()
    assert spoken == []
