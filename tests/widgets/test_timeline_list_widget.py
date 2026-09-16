# tests/widgets/test_timeline_list_widget.py
"""S6: TimelineListWidget emits signals instead of calling back into
MainWindow through self.window(), so its key handling can be exercised with
no window at all."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QListWidgetItem

from widgets.timeline_list_widget import TimelineListWidget


def _press(widget, key, modifiers=Qt.KeyboardModifier.NoModifier):
    widget.keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers)
    )


def _spy(signal):
    calls = []
    signal.connect(lambda *args: calls.append(args))
    return calls


def test_arrow_keys_emit_navigate_requested(qtbot):
    widget = TimelineListWidget()
    qtbot.addWidget(widget)
    calls = _spy(widget.navigate_requested)

    _press(widget, Qt.Key.Key_Left)
    _press(widget, Qt.Key.Key_Right)

    assert calls == [("left",), ("right",)]


def test_ctrl_left_right_do_not_emit_navigate_requested(qtbot):
    """Ctrl+Left/Ctrl+Right are now the global "move by bar" menu action,
    not a Region-3 signal - this widget no longer interprets them at all."""
    widget = TimelineListWidget()
    qtbot.addWidget(widget)
    calls = _spy(widget.navigate_requested)

    _press(widget, Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier)
    _press(widget, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)

    assert calls == []


def test_home_end_reach_native_list_behaviour(qtbot):
    """Bare Home/End no longer emit navigate_requested - they fall through to
    QListWidget's own top/bottom-row behaviour."""
    widget = TimelineListWidget()
    qtbot.addWidget(widget)
    for text in ("C", "E", "G"):
        widget.addItem(QListWidgetItem(text))
    widget.setCurrentRow(1)
    calls = _spy(widget.navigate_requested)

    _press(widget, Qt.Key.Key_End)
    assert calls == []
    assert widget.currentRow() == 2

    _press(widget, Qt.Key.Key_Home)
    assert calls == []
    assert widget.currentRow() == 0


def test_widget_no_longer_defines_loop_length_or_attribute_number_signals(qtbot):
    """Alt+PageUp/PageDown and Ctrl+1..9 are global MainWindow.setup_shortcuts
    QShortcuts now (see tests/test_main_window_playback.py and
    tests/test_main_window_navigation.py) - this widget doesn't interpret
    them at all any more."""
    widget = TimelineListWidget()
    qtbot.addWidget(widget)

    assert not hasattr(widget, "loop_length_adjust_requested")
    assert not hasattr(widget, "attribute_number_requested")


def test_up_down_collapse_selection_and_emit_vertical_move_made(qtbot):
    widget = TimelineListWidget()
    qtbot.addWidget(widget)
    for text in ("C", "E", "G"):
        widget.addItem(QListWidgetItem(text))
    widget.selectAll()
    widget.setCurrentRow(0)
    calls = _spy(widget.vertical_move_made)

    _press(widget, Qt.Key.Key_Down)

    assert calls == [()]
    assert [i.row() for i in widget.selectedIndexes()] == [widget.currentRow()]
    assert len(widget.selectedIndexes()) == 1
