# tests/widgets/test_region5_list_widget.py
"""S6: Region5ListWidget emits span_jump_requested instead of calling
MainWindow.jump_to_performance_span_* through self.window()."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from widgets.region5_list_widget import Region5ListWidget


def _press(widget, key, modifiers=Qt.KeyboardModifier.NoModifier):
    widget.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers))


def test_ctrl_home_end_emit_span_jump_requested(qtbot):
    widget = Region5ListWidget()
    qtbot.addWidget(widget)
    calls = []
    widget.span_jump_requested.connect(calls.append)

    _press(widget, Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier)
    _press(widget, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)

    assert calls == [True, False]


def test_plain_home_end_do_not_emit(qtbot):
    widget = Region5ListWidget()
    qtbot.addWidget(widget)
    calls = []
    widget.span_jump_requested.connect(calls.append)

    _press(widget, Qt.Key.Key_Home)
    _press(widget, Qt.Key.Key_End)

    assert calls == []
