# tests/widgets/test_performance_report_dialog.py
"""Stage 8 (PITweaksImplementationPlan.md stage 6 / PerformanceMarkings
ImplementationPlanV2.md stage 8): PerformanceReportDialog as a navigable
tree. Like KeySignatureDialog, this never touches MusicData itself - it
just renders whatever ReportRows it's handed - so it's driven directly
with no MainWindow/score involved."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from models.report_row import ReportRow
from widgets.performance_report_dialog import PerformanceReportDialog

_ROWS = [
    ReportRow(text="Title: Test Piece", level=0),
    ReportRow(text="Parts: 1", level=0),
    ReportRow(text="Test Part: 4 notes", level=1, part_id="P1"),
    ReportRow(text="Pedal marks: 1", level=0),
    ReportRow(text="Pedal: Measure 1 to Measure 2", level=1, jump_quarters=0.0),
    ReportRow(text="Sections: 1", level=0),
    ReportRow(text="Verse 1: Measure 1 to Measure 4", level=1),
]


def test_tree_shape_headers_top_level_details_are_children(qtbot):
    dialog = PerformanceReportDialog(rows=_ROWS)
    qtbot.addWidget(dialog)

    tree = dialog.report_tree
    assert tree.topLevelItemCount() == 4  # Title, Parts, Pedal marks, Sections
    assert tree.topLevelItem(0).text(0) == "Title: Test Piece"
    parts_item = tree.topLevelItem(1)
    assert parts_item.text(0) == "Parts: 1"
    assert parts_item.childCount() == 1
    assert parts_item.child(0).text(0) == "Test Part: 4 notes"


def test_tree_is_collapsed_by_default(qtbot):
    dialog = PerformanceReportDialog(rows=_ROWS)
    qtbot.addWidget(dialog)

    for i in range(dialog.report_tree.topLevelItemCount()):
        assert not dialog.report_tree.topLevelItem(i).isExpanded()


def test_activating_a_header_does_not_close_the_dialog(qtbot):
    dialog = PerformanceReportDialog(rows=_ROWS)
    qtbot.addWidget(dialog)

    closed = []
    dialog.accepted.connect(lambda: closed.append(True))
    dialog._on_item_activated(dialog.report_tree.topLevelItem(1), 0)  # "Parts: 1"

    assert closed == []
    assert dialog.chosen_row is None


def test_activating_a_range_only_row_does_not_close_the_dialog(qtbot):
    """Sections/Repeated sections/Endings/preamble rows carry no jump
    target at all (section 6.1's table) - Enter on one is a no-op."""
    dialog = PerformanceReportDialog(rows=_ROWS)
    qtbot.addWidget(dialog)
    sections_item = dialog.report_tree.topLevelItem(3)
    verse_item = sections_item.child(0)

    dialog._on_item_activated(verse_item, 0)

    assert dialog.chosen_row is None


def test_activating_a_positioned_row_accepts_with_chosen_row_set(qtbot):
    dialog = PerformanceReportDialog(rows=_ROWS)
    qtbot.addWidget(dialog)
    pedal_item = dialog.report_tree.topLevelItem(2).child(0)  # "Pedal: ..."

    accepted = []
    dialog.accepted.connect(lambda: accepted.append(True))
    dialog._on_item_activated(pedal_item, 0)

    assert accepted == [True]
    assert dialog.chosen_row is not None
    assert dialog.chosen_row.text == "Pedal: Measure 1 to Measure 2"


def test_activating_a_part_row_accepts_with_its_part_id(qtbot):
    dialog = PerformanceReportDialog(rows=_ROWS)
    qtbot.addWidget(dialog)
    part_item = dialog.report_tree.topLevelItem(1).child(0)

    dialog._on_item_activated(part_item, 0)

    assert dialog.chosen_row is not None
    assert dialog.chosen_row.part_id == "P1"
