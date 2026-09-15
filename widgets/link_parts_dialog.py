# widgets/link_parts_dialog.py
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from models.part_links import link_group_number, link_parts, unlink_part
from widgets.accessible_announcer import announce
from widgets.list_focus_helper import focus_list_and_reannounce_current_row


class LinkPartsDialog(QDialog):
    """Parts > Link Parts... (PerformanceMarkingsImplementationPlanV2.md
    stage 9 / PITweaksImplementationPlan.md item 1) - marks two or more
    parts as "the same music" so each shows the others' performance
    markings in the note list (models/marking_rows.py's borrowed rows).

    A working-copy dialog like PartOrderDialog/AttributeOrderDialog: Link
    and Unlink both mutate this dialog's own copy of the groups (via
    models/part_links.py's plain rule functions - the SAME code
    MusicData.link_parts/unlink_part run live, so the dialog can never
    accept something the model would refuse) and only reach the window
    through part_link_groups() after exec() returns Accepted. Cancel,
    Escape or the close box discards every change. Pure view: this class
    never touches MusicData.

    initial_part_id, same idea as PartOrderDialog's, opens the list on
    whichever part Region 2's current selection belongs to."""

    def __init__(
        self,
        parent=None,
        rows: Optional[List[Tuple[str, str, Optional[int]]]] = None,
        groups: Optional[List[List[str]]] = None,
        initial_part_id: Optional[str] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Link Parts")

        self._known_part_ids = [part_id for part_id, _name, _group in (rows or [])]
        self._names = {part_id: name for part_id, name, _group in (rows or [])}
        self._groups: List[List[str]] = [list(g) for g in (groups or [])]

        label = QLabel("&Parts:", self)
        self.part_list = QListWidget(self)
        self.part_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        label.setBuddy(self.part_list)
        self._populate()
        self._select_initial_row(initial_part_id)
        self.part_list.itemSelectionChanged.connect(self._update_button_state)

        self.link_button = QPushButton("&Link", self)
        self.link_button.setAutoDefault(False)
        self.link_button.clicked.connect(self._link)
        self.unlink_button = QPushButton("&Unlink", self)
        self.unlink_button.setAutoDefault(False)
        self.unlink_button.clicked.connect(self._unlink)
        self._update_button_state()

        button_row = QHBoxLayout()
        button_row.addWidget(self.link_button)
        button_row.addWidget(self.unlink_button)

        # autoDefault=False above, same live-tested reasoning as every other
        # list+buttons dialog here (docs/dialog_widget_patterns.md): a
        # focused autoDefault button silently masks its own mnemonic to
        # NVDA. Space still activates Link/Unlink; Enter on either now
        # triggers OK instead.
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(self.part_list)
        layout.addLayout(button_row)
        layout.addWidget(buttons)

    def _row_text(self, part_id: str) -> str:
        group = link_group_number(self._groups, part_id)
        name = self._names.get(part_id, part_id)
        return f"{group}. {name}" if group is not None else name

    def _populate(self) -> None:
        self.part_list.clear()
        for part_id in self._known_part_ids:
            item = QListWidgetItem(self._row_text(part_id))
            item.setData(Qt.ItemDataRole.UserRole, part_id)
            self.part_list.addItem(item)

    def _select_initial_row(self, initial_part_id: Optional[str]) -> None:
        if self.part_list.count() == 0:
            return
        if initial_part_id is not None:
            for row in range(self.part_list.count()):
                if self.part_list.item(row).data(Qt.ItemDataRole.UserRole) == initial_part_id:
                    self.part_list.setCurrentRow(row)
                    return
        self.part_list.setCurrentRow(0)

    def _selected_part_ids(self) -> List[str]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.part_list.selectedItems()]

    def _update_button_state(self) -> None:
        selected = self._selected_part_ids()
        self.link_button.setEnabled(
            len(selected) >= 2
            and all(link_group_number(self._groups, pid) is None for pid in selected)
        )
        current_item = self.part_list.currentItem()
        current_part_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        self.unlink_button.setEnabled(
            current_part_id is not None
            and link_group_number(self._groups, current_part_id) is not None
        )

    def _refresh_row_texts(self) -> None:
        for row in range(self.part_list.count()):
            item = self.part_list.item(row)
            part_id = item.data(Qt.ItemDataRole.UserRole)
            item.setText(self._row_text(part_id))

    def _link(self) -> None:
        selected = self._selected_part_ids()
        if not link_parts(self._groups, self._known_part_ids, selected):
            announce(self, "Could not link these parts")
            return
        self._refresh_row_texts()
        self._update_button_state()

    def _unlink(self) -> None:
        current_item = self.part_list.currentItem()
        part_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        if part_id is None or not unlink_part(self._groups, part_id):
            announce(self, "This part is not linked")
            return
        self._refresh_row_texts()
        self._update_button_state()

    def part_link_groups(self) -> List[List[str]]:
        """The working-copy groups after any Link/Unlink, only meaningful
        once exec() has returned Accepted."""
        return [list(g) for g in self._groups]

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: focus_list_and_reannounce_current_row(self.part_list))
