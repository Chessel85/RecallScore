# widgets/performance_report_dialog.py
from typing import List, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from models.report_row import ReportRow
from widgets.list_focus_helper import focus_tree_and_reannounce_current_row


class PerformanceReportDialog(QDialog):
    """Ref 29: Edit > Performance Report... - a read-only, whole-score
    overview (title/composer/tempo/key/time-sig, part note counts,
    anacrusis, bar count, and every marking family's summary), built once
    from MusicData.get_performance_report_rows() and displayed as a tree.

    PITweaksImplementationPlan.md stage 6 / PerformanceMarkingsImplementation
    PlanV2.md stage 8: the flat-list and no-jump-navigation shape of the
    first iteration were scope cuts, not permanent decisions, and are
    reversed here - a QTreeWidget lets NVDA read a header's expanded state
    and a detail row's level natively, and Enter on a positioned row jumps
    the timeline cursor to it (MainWindow._show_performance_report_dialog).

    Level-0 rows (headers, the preamble) are top-level items, all collapsed
    by default; each level-1 row is a child of the most recent level-0 row.
    Each item carries its own ReportRow via setData(0, UserRole, ...), so
    itemActivated can read jump_quarters/jump_measure/jump_index/part_id
    straight off it rather than re-parsing the row's text (invariant 8).
    Activating a header (or any row with no jump target - Sections,
    Repeated sections, Endings, the preamble) does nothing beyond Qt's own
    expand/collapse; the dialog only accept()s and sets chosen_row for a
    row that actually has somewhere to jump.
    """

    def __init__(self, parent=None, rows: List[ReportRow] = None):
        super().__init__(parent)
        self.setWindowTitle("Performance Report")
        self.chosen_row: Optional[ReportRow] = None

        label = QLabel("Performance report:", self)
        self.report_tree = QTreeWidget(self)
        self.report_tree.setHeaderHidden(True)
        label.setBuddy(self.report_tree)

        current_header_item: Optional[QTreeWidgetItem] = None
        for row in rows or []:
            item = QTreeWidgetItem([row.text])
            item.setData(0, Qt.ItemDataRole.UserRole, row)
            if row.level == 0:
                self.report_tree.addTopLevelItem(item)
                current_header_item = item
            elif current_header_item is not None:
                current_header_item.addChild(item)
            else:
                # No header has been seen yet - shouldn't happen given
                # get_performance_report_rows' own build order, but a
                # detail row with nowhere to nest is still shown rather
                # than silently dropped.
                self.report_tree.addTopLevelItem(item)
        self.report_tree.collapseAll()
        if self.report_tree.topLevelItemCount() > 0:
            self.report_tree.setCurrentItem(self.report_tree.topLevelItem(0))
        self.report_tree.itemActivated.connect(self._on_item_activated)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(self.report_tree)
        layout.addWidget(close_buttons)

    def _on_item_activated(self, item: QTreeWidgetItem, column: int) -> None:
        row = item.data(0, Qt.ItemDataRole.UserRole)
        if row is not None and row.has_jump_target():
            self.chosen_row = row
            self.accept()

    def showEvent(self, event):
        """Same deferred-focus idiom as GotoMeasureDialog/AttributeOrderDialog
        - setFocus() before the native window exists never reaches NVDA."""
        super().showEvent(event)
        QTimer.singleShot(0, lambda: focus_tree_and_reannounce_current_row(self.report_tree))
