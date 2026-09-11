# tests/widgets/test_shortcut_capture_edit.py
"""ShortcutCaptureEdit (UserPlans/KeyboardShortcuts.md) - a QLineEdit that
records one key combination instead of typed text. Pure widget-state tests,
no MainWindow/score involved (like test_metronome_player_dialog)."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QPushButton, QWidget

from widgets.shortcut_capture_edit import ShortcutCaptureEdit


def _edit(qtbot):
    edit = ShortcutCaptureEdit()
    qtbot.addWidget(edit)
    edit.show()
    qtbot.waitExposed(edit)
    return edit


def _key_event(key, modifiers=Qt.KeyboardModifier.NoModifier, event_type=QEvent.Type.KeyPress):
    return QKeyEvent(event_type, key, modifiers)


def test_ctrl_shift_k_is_recorded(qtbot):
    edit = _edit(qtbot)
    edit.setFocus()
    qtbot.keyClick(edit, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert edit.sequence() == "Ctrl+Shift+K"


def test_a_modifier_only_press_records_nothing(qtbot):
    edit = _edit(qtbot)
    edit.setFocus()
    qtbot.keyClick(edit, Qt.Key.Key_Control)
    assert edit.sequence() == ""


def test_tab_does_not_record_and_leaves_the_event_ignored(qtbot):
    edit = _edit(qtbot)
    event = _key_event(Qt.Key.Key_Tab)
    edit.keyPressEvent(event)
    assert edit.sequence() == ""
    assert not event.isAccepted()


def test_escape_does_not_record_and_leaves_the_event_ignored(qtbot):
    edit = _edit(qtbot)
    event = _key_event(Qt.Key.Key_Escape)
    edit.keyPressEvent(event)
    assert edit.sequence() == ""
    assert not event.isAccepted()


def test_return_does_not_record_and_leaves_the_event_ignored(qtbot):
    edit = _edit(qtbot)
    event = _key_event(Qt.Key.Key_Return)
    edit.keyPressEvent(event)
    assert edit.sequence() == ""
    assert not event.isAccepted()


def test_backspace_clears_a_recorded_sequence(qtbot):
    edit = _edit(qtbot)
    edit.setFocus()
    qtbot.keyClick(edit, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    assert edit.sequence() != ""

    qtbot.keyClick(edit, Qt.Key.Key_Backspace)
    assert edit.sequence() == ""
    assert edit.text() == ""


def test_alt_a_is_recorded_rather_than_triggering_a_sibling_apply_button(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    edit = ShortcutCaptureEdit(parent)
    button = QPushButton("&Apply", parent)
    clicks = []
    button.clicked.connect(lambda: clicks.append(True))
    parent.show()
    qtbot.waitExposed(parent)
    edit.setFocus()

    qtbot.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.AltModifier)

    assert edit.sequence() == "Alt+A"
    assert clicks == []


def test_numpad_keys_drop_the_keypad_modifier(qtbot):
    edit = _edit(qtbot)
    edit.setFocus()
    qtbot.keyClick(
        edit, Qt.Key.Key_5,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.KeypadModifier,
    )
    assert edit.sequence() == "Ctrl+5"
