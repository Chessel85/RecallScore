# tests/widgets/test_link_parts_dialog.py
"""Pure widget-state tests for LinkPartsDialog (stage 9) - like
InstrumentDialog/PartOrderDialog, it never touches MusicData itself (it
works on a copy of the groups via models/part_links.py's plain functions),
so it can be driven directly with no MainWindow/score involved."""
from PySide6.QtCore import Qt

from widgets.link_parts_dialog import LinkPartsDialog

ROWS = [
    ("P1", "Violin", None),
    ("P2", "Viola", None),
    ("P3", "Cello", None),
]


def _select(dialog, *rows):
    dialog.part_list.clearSelection()
    for row in rows:
        dialog.part_list.item(row).setSelected(True)
    dialog.part_list.setCurrentRow(rows[-1])


def test_populates_one_bare_row_per_part_when_nothing_is_linked(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, groups=[])
    qtbot.addWidget(dialog)

    assert [dialog.part_list.item(i).text() for i in range(3)] == ["Violin", "Viola", "Cello"]


def test_populates_group_prefixed_rows_from_existing_groups(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, groups=[["P1", "P2"]])
    qtbot.addWidget(dialog)

    assert [dialog.part_list.item(i).text() for i in range(3)] == [
        "1. Violin", "1. Viola", "Cello",
    ]


def test_link_button_enabled_only_with_two_or_more_unlinked_rows_selected(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, groups=[])
    qtbot.addWidget(dialog)

    _select(dialog, 0)
    assert dialog.link_button.isEnabled() is False

    _select(dialog, 0, 1)
    assert dialog.link_button.isEnabled() is True


def test_link_button_disabled_when_a_selected_row_is_already_linked(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, groups=[["P1", "P2"]])
    qtbot.addWidget(dialog)

    _select(dialog, 0, 2)  # P1 (linked) + P3 (unlinked)
    assert dialog.link_button.isEnabled() is False


def test_unlink_button_enabled_only_on_a_linked_current_row(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, groups=[["P1", "P2"]])
    qtbot.addWidget(dialog)

    dialog.part_list.setCurrentRow(2)  # Cello, unlinked
    assert dialog.unlink_button.isEnabled() is False

    dialog.part_list.setCurrentRow(0)  # Violin, linked
    assert dialog.unlink_button.isEnabled() is True


def test_link_updates_row_texts_and_group_and_keeps_focus_in_the_list(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, groups=[])
    qtbot.addWidget(dialog)

    _select(dialog, 0, 1)
    dialog._link()

    assert [dialog.part_list.item(i).text() for i in range(3)] == [
        "1. Violin", "1. Viola", "Cello",
    ]
    assert dialog.part_link_groups() == [["P1", "P2"]]


def test_unlink_dissolves_a_pair_and_updates_row_texts(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, groups=[["P1", "P2"]])
    qtbot.addWidget(dialog)

    dialog.part_list.setCurrentRow(0)
    dialog._unlink()

    assert [dialog.part_list.item(i).text() for i in range(3)] == ["Violin", "Viola", "Cello"]
    assert dialog.part_link_groups() == []


def test_unlink_keeps_the_current_row_on_the_same_part(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, groups=[["P1", "P2"]])
    qtbot.addWidget(dialog)

    dialog.part_list.setCurrentRow(0)
    dialog._unlink()

    assert dialog.part_list.currentItem().data(Qt.ItemDataRole.UserRole) == "P1"


def test_initial_part_id_selects_that_row(qtbot):
    dialog = LinkPartsDialog(rows=ROWS, groups=[], initial_part_id="P3")
    qtbot.addWidget(dialog)

    assert dialog.part_list.currentItem().data(Qt.ItemDataRole.UserRole) == "P3"
