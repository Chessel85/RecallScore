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
    _press(widget, Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier)
    _press(widget, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
    _press(widget, Qt.Key.Key_Home)
    _press(widget, Qt.Key.Key_End)

    assert calls == [
        ("left", False),
        ("right", False),
        ("left", True),
        ("right", True),
        ("home", False),
        ("end", False),
    ]


def test_alt_pageup_pagedown_emit_loop_length_adjust(qtbot):
    widget = TimelineListWidget()
    qtbot.addWidget(widget)
    calls = _spy(widget.loop_length_adjust_requested)

    _press(widget, Qt.Key.Key_PageUp, Qt.KeyboardModifier.AltModifier)
    _press(widget, Qt.Key.Key_PageDown, Qt.KeyboardModifier.AltModifier)

    assert calls == [(1,), (-1,)]


def test_ctrl_digit_emits_attribute_number_requested(qtbot):
    widget = TimelineListWidget()
    qtbot.addWidget(widget)
    calls = _spy(widget.attribute_number_requested)

    _press(widget, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)

    assert calls == [(3,)]


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
