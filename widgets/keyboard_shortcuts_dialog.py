# widgets/keyboard_shortcuts_dialog.py
"""Tools > Keyboard Shortcuts... (UserPlans/KeyboardShortcuts.md).

Pure view: only calls the ShortcutController methods passed into __init__
(so a test can pass a fake), never imports models/ or persistence/. Apply
and Restore Defaults commit right away through the controller - there's no
working copy and no Cancel, matching the plan's Apply + Close design.
"""
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from widgets.accessible_announcer import announce
from widgets.form_helpers import add_buddy_row
from widgets.shortcut_capture_edit import ShortcutCaptureEdit

_NAME_ROLE = Qt.ItemDataRole.UserRole + 1


class KeyboardShortcutsDialog(QDialog):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Keyboard Shortcuts")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.filter_edit = QLineEdit(self)
        add_buddy_row(form, "&Filter:", self.filter_edit, self.filter_edit)
        self.filter_edit.textChanged.connect(self._apply_filter)

        self.action_list = QListWidget(self)
        add_buddy_row(form, "Action &list:", self.action_list, self.action_list)
        self.action_list.currentRowChanged.connect(self._on_current_row_changed)

        self.current_shortcut_edit = QLineEdit(self)
        self.current_shortcut_edit.setReadOnly(True)
        form.addRow("Current shortcut:", self.current_shortcut_edit)

        self.new_shortcut_edit = ShortcutCaptureEdit(self)
        add_buddy_row(form, "&New shortcut:", self.new_shortcut_edit, self.new_shortcut_edit)
        self.new_shortcut_edit.sequence_changed.connect(self._on_capture_changed)

        self.apply_button = QPushButton("&Apply", self)
        self.apply_button.clicked.connect(self._apply)
        layout.addWidget(self.apply_button)

        self.remove_button = QPushButton("&Remove Shortcut", self)
        self.remove_button.setAutoDefault(False)
        self.remove_button.clicked.connect(self._remove)
        layout.addWidget(self.remove_button)

        self.restore_button = QPushButton("Restore &Defaults...", self)
        self.restore_button.setAutoDefault(False)
        self.restore_button.clicked.connect(self._restore_defaults)
        layout.addWidget(self.restore_button)

        self.close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.close_box.rejected.connect(self.reject)
        layout.addWidget(self.close_box)

        self.apply_button.setDefault(True)

        self._populate()
        self._update_button_states()

    # --- population / filter -------------------------------------------

    def _row_text(self, action_id: str, name: str) -> str:
        shortcut = self._controller.display_text(action_id)
        return f"{self._category_of(action_id)}: {name}, {shortcut or 'no shortcut'}"

    def _category_of(self, action_id: str) -> str:
        for t in self._controller.targets():
            if t.id == action_id:
                return t.category
        return ""

    def _populate(self) -> None:
        self._needle = ""
        self._rebuild_list()

    def _rebuild_list(self, preferred_id=None) -> None:
        """Rebuilds the list from scratch containing only rows matching
        self._needle. Filtered-out rows must not exist in the widget at all
        - Qt's own Home/End (and, live, NVDA's object navigation) reach past
        a merely-hidden QListWidgetItem straight to row 0, so setHidden()
        alone left a "filtered out but still keyboard/screen-reader
        reachable" row (2026-09-11 live NVDA testing)."""
        self.action_list.clear()
        selected_row = -1
        ordered = sorted(
            self._controller.targets(), key=lambda t: (t.category + t.name()).lower()
        )
        for t in ordered:
            name = t.name()
            if self._needle and (
                self._needle not in t.category.lower()
                and self._needle not in name.lower()
            ):
                continue
            item = QListWidgetItem(self._row_text(t.id, name))
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            item.setData(_NAME_ROLE, name)
            self.action_list.addItem(item)
            if t.id == preferred_id:
                selected_row = self.action_list.count() - 1
        if self.action_list.count():
            self.action_list.setCurrentRow(selected_row if selected_row >= 0 else 0)
        self._on_current_row_changed(self.action_list.currentRow())

    def _apply_filter(self, text: str) -> None:
        preferred_id = self._current_action_id()
        self._needle = text.strip().lower()
        self._rebuild_list(preferred_id)

    # --- current row / capture -------------------------------------------

    def _current_action_id(self):
        item = self.action_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _on_current_row_changed(self, row: int) -> None:
        action_id = self._current_action_id()
        shortcut = self._controller.display_text(action_id) if action_id else ""
        self.current_shortcut_edit.setText(shortcut or "None")
        self.new_shortcut_edit.clear_sequence()
        self._update_button_states()

    def _on_capture_changed(self, portable: str) -> None:
        if portable:
            announce(self, self.new_shortcut_edit.text())
        self._update_button_states()

    def _update_button_states(self) -> None:
        action_id = self._current_action_id()
        self.apply_button.setEnabled(
            action_id is not None and bool(self.new_shortcut_edit.sequence())
        )
        self.remove_button.setEnabled(
            action_id is not None and bool(self._controller.display_text(action_id))
        )

    def _refresh_row(self, action_id: str) -> None:
        for row in range(self.action_list.count()):
            item = self.action_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == action_id:
                name = item.data(_NAME_ROLE)
                item.setText(self._row_text(action_id, name))
                return

    def _name_of(self, action_id: str) -> str:
        for t in self._controller.targets():
            if t.id == action_id:
                return t.name()
        return action_id

    # --- button actions ----------------------------------------------------

    def _apply(self) -> None:
        action_id = self._current_action_id()
        if action_id is None:
            return
        seq = self.new_shortcut_edit.sequence()
        if not seq:
            return
        name = self._name_of(action_id)

        if self._controller.owner_of(seq) == action_id:
            announce(self, f"{name} already uses {self.new_shortcut_edit.text()}")
            return

        reason = self._controller.reserved_reason(seq)
        if reason is not None:
            QMessageBox.warning(
                self,
                "Keyboard Shortcuts",
                f"{self.new_shortcut_edit.text()} can't be assigned: it is "
                f"used to {reason}.",
            )
            return

        other = self._controller.owner_of(seq)
        if other is not None:
            other_name = self._name_of(other)
            answer = QMessageBox.question(
                self,
                "Keyboard Shortcuts",
                f"{self.new_shortcut_edit.text()} is already assigned to "
                f"{other_name}. Assign it to {name} instead? {other_name} "
                f"will then have no shortcut.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        displaced = self._controller.assign(action_id, seq)
        self._refresh_row(action_id)
        if displaced is not None:
            self._refresh_row(displaced)
        self.new_shortcut_edit.clear_sequence()
        self.current_shortcut_edit.setText(self._controller.display_text(action_id) or "None")
        self._update_button_states()

    def _remove(self) -> None:
        action_id = self._current_action_id()
        if action_id is None:
            return
        name = self._name_of(action_id)
        self._controller.clear(action_id)
        self._refresh_row(action_id)
        self.current_shortcut_edit.setText("None")
        self._update_button_states()
        announce(self, f"{name} has no shortcut")

    def _restore_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            "Keyboard Shortcuts",
            "Restore every keyboard shortcut to its default? All your "
            "changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._controller.restore_defaults()
        for row in range(self.action_list.count()):
            item = self.action_list.item(row)
            action_id = item.data(Qt.ItemDataRole.UserRole)
            self._refresh_row(action_id)
        self._on_current_row_changed(self.action_list.currentRow())
        announce(self, "Default shortcuts restored")

    # --- focus ---------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.filter_edit.setFocus)
