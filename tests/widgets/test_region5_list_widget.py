# tests/widgets/test_region5_list_widget.py
"""S6: Region5ListWidget emits span_jump_requested instead of calling
MainWindow.jump_to_performance_span_* through self.window()."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from models.performance_region_row import PerformanceRegionRow
from widgets.region5_list_widget import Region5ListWidget


def _press(widget, key, modifiers=Qt.KeyboardModifier.NoModifier):
    widget.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers))


def test_alt_home_end_emit_span_jump_requested(qtbot):
    widget = Region5ListWidget()
    qtbot.addWidget(widget)
    calls = []
    widget.span_jump_requested.connect(calls.append)

    _press(widget, Qt.Key.Key_Home, Qt.KeyboardModifier.AltModifier)
    _press(widget, Qt.Key.Key_End, Qt.KeyboardModifier.AltModifier)

    assert calls == [True, False]


def test_plain_home_end_do_not_emit(qtbot):
    widget = Region5ListWidget()
    qtbot.addWidget(widget)
    calls = []
    widget.span_jump_requested.connect(calls.append)

    _press(widget, Qt.Key.Key_Home)
    _press(widget, Qt.Key.Key_End)

    assert calls == []


# --- Stage 9 (PerformanceMarkingsStrategy.md section 8): Ctrl+N/Menu key/
# Shift+F10 toggle the focused row's marking category -------------------


def _widget_on_row(qtbot, category):
    widget = Region5ListWidget()
    qtbot.addWidget(widget)
    widget.refresh_list([], [PerformanceRegionRow(label="* Repeat measures 1 to 8", jump_target_measure=1, category=category)])
    calls = []
    widget.category_toggle_requested.connect(calls.append)
    return widget, calls


def test_ctrl_n_emits_toggle_for_the_focused_rows_category(qtbot):
    widget, calls = _widget_on_row(qtbot, "repeats_endings")

    _press(widget, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)

    assert calls == ["repeats_endings"]


def test_menu_key_and_shift_f10_also_toggle(qtbot):
    widget, calls = _widget_on_row(qtbot, "repeats_endings")

    _press(widget, Qt.Key.Key_Menu)
    _press(widget, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)

    assert calls == ["repeats_endings", "repeats_endings"]


def test_ctrl_n_is_a_noop_on_a_row_with_no_category(qtbot):
    widget, calls = _widget_on_row(qtbot, None)

    _press(widget, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)

    assert calls == []


def test_ctrl_n_is_a_noop_on_the_none_placeholder(qtbot):
    widget = Region5ListWidget()
    qtbot.addWidget(widget)
    widget.refresh_list([], [])  # "None" placeholder, UserRole None
    calls = []
    widget.category_toggle_requested.connect(calls.append)

    _press(widget, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)

    assert calls == []
