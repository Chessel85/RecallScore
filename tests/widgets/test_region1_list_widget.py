# tests/widgets/test_region1_list_widget.py
"""Stage 7 (PerformanceMarkingsStrategy.md section 9): the Directives list
appended after Region 1's plain property rows, and Ctrl+N/Menu-key/Shift+F10
toggling one via directive_toggle_requested."""
from PySide6.QtCore import Qt

from widgets.region1_list_widget import Region1ListWidget


def _make_widget(qtbot):
    widget = Region1ListWidget()
    qtbot.addWidget(widget)
    calls = []
    widget.directive_toggle_requested.connect(lambda index: calls.append(index))
    return widget, calls


def test_refresh_list_appends_directive_rows_after_the_property_rows(qtbot):
    widget, _calls = _make_widget(qtbot)

    widget.refresh_list(
        {"Title": "Test Score"},
        [(0, "Directive: Jauntily (measure 2)", False)],
    )

    assert widget.count() == 2
    assert widget.item(0).text() == "Title: Test Score"
    assert widget.item(1).text() == "Directive: Jauntily (measure 2)"
    assert widget.item(1).data(Qt.ItemDataRole.UserRole) == 0


def test_current_directive_index_is_none_on_a_plain_property_row(qtbot):
    widget, _calls = _make_widget(qtbot)
    widget.refresh_list(
        {"Title": "Test Score"},
        [(0, "Directive: Jauntily (measure 2)", False)],
    )
    widget.setCurrentRow(0)

    assert widget.current_directive_index() is None


def test_ctrl_n_emits_toggle_for_the_focused_directive_row(qtbot):
    widget, calls = _make_widget(qtbot)
    widget.refresh_list(
        {"Title": "Test Score"},
        [(3, "Directive: Jauntily (measure 2)", False)],
    )
    widget.setCurrentRow(1)  # the directive row

    qtbot.keyClick(widget, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)

    assert calls == [3]


def test_ctrl_n_is_a_noop_on_a_plain_property_row(qtbot):
    widget, calls = _make_widget(qtbot)
    widget.refresh_list(
        {"Title": "Test Score"},
        [(0, "Directive: Jauntily (measure 2)", False)],
    )
    widget.setCurrentRow(0)  # the property row, not the directive

    qtbot.keyClick(widget, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)

    assert calls == []


def test_menu_key_also_toggles_the_focused_directive_row(qtbot):
    widget, calls = _make_widget(qtbot)
    widget.refresh_list({}, [(5, "Directive: Jauntily (measure 2)", False)])
    widget.setCurrentRow(0)

    qtbot.keyClick(widget, Qt.Key.Key_Menu)

    assert calls == [5]


def test_shift_f10_also_toggles_the_focused_directive_row(qtbot):
    widget, calls = _make_widget(qtbot)
    widget.refresh_list({}, [(5, "Directive: Jauntily (measure 2)", False)])
    widget.setCurrentRow(0)

    qtbot.keyClick(widget, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)

    assert calls == [5]


def test_refresh_list_clamps_current_row_across_a_rebuild(qtbot):
    widget, _calls = _make_widget(qtbot)
    widget.refresh_list({"A": "1", "B": "2"}, [(0, "Directive: X (measure 1)", False)])
    widget.setCurrentRow(2)  # the directive row

    widget.refresh_list({"A": "1"}, [])  # directive gone, fewer rows overall

    assert widget.currentRow() == 0
