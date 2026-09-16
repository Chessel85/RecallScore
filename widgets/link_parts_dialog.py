# widgets/link_parts_dialog.py
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from widgets.list_focus_helper import focus_list_and_reannounce_current_row


class LinkPartsDialog(QDialog):
    """Parts > Link Parts... (PerformanceMarkingsImplementationPlanV2.md
    stage 9 / PITweaksImplementationPlan.md item 1) - marks two or more
    parts as "the same music" so each shows the others' performance
    markings in the note list (models/marking_rows.py's borrowed rows).

    Redesigned (user-requested, 2026-09-16): this dialog now only ever
    CREATES one new group. It used to be a working-copy dialog handling
    both linking and unlinking with an ExtendedSelection list (Ctrl+Click/
    Ctrl+Space to build a non-contiguous selection) - live-tested and
    reported unusable, NVDA does not reliably announce that kind of list's
    per-item selected state. Each row here is instead a checkable item
    (plain Space toggles it, and NVDA announces "checked"/"not checked" on
    every row reliably) and the dialog carries only OK/Cancel: OK links
    every checked part into one new group, Cancel discards.

    `rows` therefore only ever lists currently UNLINKED parts - a part
    already in a group can't join another (models/part_links.py), so
    main_window.py's caller omits it rather than showing a checkbox here
    that OK would have to silently refuse. Dissolving an existing group is
    a separate action now, reached from Region 2's own context menu.

    initial_part_id, same idea as PartOrderDialog's, opens the list on
    whichever part Region 2's current selection belongs to (a no-op if
    that part is already linked and therefore not in `rows` at all)."""

    def __init__(
        self,
        parent=None,
        rows: Optional[List[Tuple[str, str]]] = None,
        initial_part_id: Optional[str] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Link Parts")

        rows = rows or []
        label = QLabel("&Parts:", self)
        self.part_list = QListWidget(self)
        label.setBuddy(self.part_list)
        for part_id, name in rows:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, part_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.part_list.addItem(item)
        self._select_initial_row(initial_part_id)
        self.part_list.itemChanged.connect(self._update_ok_enabled)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._update_ok_enabled()

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(self.part_list)
        layout.addWidget(buttons)

    def _select_initial_row(self, initial_part_id: Optional[str]) -> None:
        if self.part_list.count() == 0:
            return
        if initial_part_id is not None:
            for row in range(self.part_list.count()):
                if self.part_list.item(row).data(Qt.ItemDataRole.UserRole) == initial_part_id:
                    self.part_list.setCurrentRow(row)
                    return
        self.part_list.setCurrentRow(0)

    def _update_ok_enabled(self, *_args) -> None:
        self._ok_button.setEnabled(len(self.checked_part_ids()) >= 2)

    def checked_part_ids(self) -> List[str]:
        return [
            self.part_list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.part_list.count())
            if self.part_list.item(row).checkState() == Qt.CheckState.Checked
        ]

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: focus_list_and_reannounce_current_row(self.part_list))
