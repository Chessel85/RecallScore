# tests/widgets/test_link_parts_dialog.py
"""Pure widget-state tests for LinkPartsDialog (stage 9, redesigned
2026-09-16) - like InstrumentDialog/PartOrderDialog, it never touches
MusicData itself (main_window.py applies checked_part_ids() through
score_edit.link_new_group), so it can be driven directly with no
MainWindow/score involved. `rows` is only ever unlinked parts now - the
caller (ScoreEditController.link_dialog_rows) is responsible for omitting
anyone already in a group."""
from PySide6.QtCore import Qt

from widgets.link_parts_dialog import LinkPartsDialog

ROWS = [
    ("P1", "Violin"),
    ("P2", "Viola"),
    ("P3", "Cello"),
]


def _check(dialog, *rows):
    for row in rows:
        dialog.part_list.item(row).setCheckState(Qt.CheckState.Checked)


def test_populates_one_unchecked_row_per_part(qtbot):
    dialog = LinkPartsDialog(rows=ROWS)
    qtbot.addWidget(dialog)

    assert [dialog.part_list.item(i).text() for i in range(3)] == ["Violin", "Viola", "Cello"]
    assert all(
        dialog.part_list.item(i).checkState() == Qt.CheckState.Unchecked for i in range(3)
    )


def test_ok_disabled_until_two_or_more_rows_are_checked(qtbot):
    dialog = LinkPartsDialog(rows=ROWS)
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False

    _check(dialog, 0)
    assert dialog._ok_button.isEnabled() is False

    _check(dialog, 1)
    assert dialog._ok_button.isEnabled() is True


def test_unchecking_back_below_two_disables_ok(qtbot):
    dialog = LinkPartsDialog(rows=ROWS)
    qtbot.addWidget(dialog)

    _check(dialog, 0, 1)
    assert dialog._ok_button.isEnabled() is True

    dialog.part_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert dialog._ok_button.isEnabled() is False


def test_checked_part_ids_returns_only_checked_rows_in_list_order(qtbot):
    dialog = LinkPartsDialog(rows=ROWS)
    qtbot.addWidget(dialog)

    _check(dialog, 0, 2)
    assert dialog.checked_part_ids() == ["P1", "P3"]


def test_initial_part_id_selects_that_row(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, initial_part_id="P3")
    qtbot.addWidget(dialog)

    assert dialog.part_list.currentItem().data(Qt.ItemDataRole.UserRole) == "P3"
