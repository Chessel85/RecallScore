# widgets/attribute_order_dialog.py
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from widgets.list_focus_helper import focus_list_and_reannounce_current_row


def _row_text(label: str, elevated: bool, hidden_state: str) -> str:
    """Ref 15 AC4 Attribute Management: "*" prefixes a row elevated
    anywhere in the dialog's own part (any of the four add/remove scopes -
    "the level" doesn't matter, per the user), and a hidden row carries a
    suffix distinguishing the two tiers - "(hidden)" for hidden-for-this-
    part, "(hidden for all)" for hidden-for-the-whole-score. Both are
    independent flags on the same row, so both can appear together."""
    text = f"*{label}" if elevated else label
    if hidden_state == "all":
        return f"{text} (hidden for all)"
    if hidden_state == "part":
        return f"{text} (hidden)"
    return text


class AttributeOrderDialog(QDialog):
    """Options > Attribute Management... (F2/Attribute Management,
    Ref 15 AC4) - reorders and hides a single part's own attribute_order,
    always scoped to whichever part Region 2's current node belongs to
    (never stave or voice - user decision, UserPlans/hideAttributes.md).

    A working-copy OK/Cancel dialog, like widgets/part_order_dialog.py, for
    the ORDER half only: moves are staged in this dialog's own list and
    MainWindow reads ordered_keys() after exec() returns Accepted to commit
    the result via MusicData.set_attribute_order_within_part - Cancel (or
    Escape, or the window close box) discards them untouched. Pure view
    like every other dialog here: this class never touches MusicData
    itself.

    Add/&Remove... (WHICH) and &Hide/Hide for &All (the new hidden-ness
    tiers) are both, like each other, IMMEDIATE-APPLY rather than staged -
    a different feature to F2's ordering, following the same pattern
    Add/Remove already established. hide_requested/hide_for_all_requested
    carry only the attribute_key; AttributeController decides the actual
    toggle direction (hide vs unhide) by reading MusicData's live state, and
    calls set_row_state back on this dialog to update just that row's text
    in place on success - no rebuild, no disturbed selection.

    Same focus-on-show reasoning as GotoMeasureDialog: setFocus() before the
    native window exists never reaches NVDA, so it's deferred to showEvent.
    Uses focus_list_and_reannounce_current_row (widgets/list_focus_helper.py)
    rather than a bare setFocus() - see that helper's docstring for why a
    bare setFocus() alone leaves NVDA reading whatever had focus before the
    dialog opened until the user manually moves Up/Down once.

    initial_attribute_key (user-requested follow-up) pre-selects a row -
    normally the attribute Region 4's current/last-selected row carries -
    so the list opens on that attribute instead of nothing. See
    _select_initial_row for the fallback-to-first-row cases."""

    # attribute_key of the row the button was clicked for - MainWindow
    # builds and shows the actual scope menu (AttributeController.
    # show_order_menu), since its content depends on live MusicData state
    # this dialog has no access to.
    add_remove_requested = Signal(str)
    # Hide/Unhide (per-part) and Hide for All/Unhide for All - see class
    # docstring. Both carry only the attribute_key; the caller resolves
    # which direction to apply from live model state.
    hide_requested = Signal(str)
    hide_for_all_requested = Signal(str)

    def __init__(self, parent=None, rows: Optional[List[Tuple[str, str, bool, str]]] = None,
                 scope_description: str = "", initial_attribute_key: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Attribute Management")

        label = QLabel(f"Attribute order for {scope_description}:", self)
        self.attribute_list = QListWidget(self)
        label.setBuddy(self.attribute_list)
        self._row_meta: Dict[str, Tuple[str, bool, str]] = {}
        self._populate(rows or [])
        self._select_initial_row(initial_attribute_key)
        self.attribute_list.currentRowChanged.connect(self._update_button_state)

        self.up_button = QPushButton("Move &Up", self)
        self.up_button.setAutoDefault(False)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button = QPushButton("Move &Down", self)
        self.down_button.setAutoDefault(False)
        self.down_button.clicked.connect(lambda: self._move(1))
        self.add_remove_button = QPushButton("Add/&Remove...", self)
        self.add_remove_button.setAutoDefault(False)
        self.add_remove_button.clicked.connect(self._request_add_remove)
        self.hide_button = QPushButton("&Hide", self)
        self.hide_button.setAutoDefault(False)
        self.hide_button.clicked.connect(self._request_hide)
        self.hide_for_all_button = QPushButton("Hide for &All", self)
        self.hide_for_all_button.setAutoDefault(False)
        self.hide_for_all_button.clicked.connect(self._request_hide_for_all)
        self._update_button_state()

        button_row = QHBoxLayout()
        button_row.addWidget(self.up_button)
        button_row.addWidget(self.down_button)
        button_row.addWidget(self.add_remove_button)
        button_row.addWidget(self.hide_button)
        button_row.addWidget(self.hide_for_all_button)

        # autoDefault=False above, live-tested and load-bearing: autoDefault
        # isn't just "is this the dialog's default button" - Qt dynamically
        # HANDS default status to whichever autoDefault button currently has
        # keyboard focus (that's what "auto" means), and a screen reader's
        # accessible "keyboard shortcut" text for a button is generated from
        # that same live default-button flag - so an autoDefault button
        # reports "Enter" the moment it's tabbed to, silently replacing its
        # own mnemonic. Confirmed live with NVDA; not reproducible
        # offscreen, since the offscreen platform never gives a widget real
        # OS focus. Disabling autoDefault keeps every plain button here from
        # ever taking default status, so their mnemonics always announce
        # correctly and Ok stays the sole default - the trade-off (an
        # explicit, confirmed user choice) is that Enter no longer performs
        # the action itself while one of these buttons is focused; Space
        # still does, and Enter now behaves like it would on any other
        # non-default button in a standard dialog (triggers Ok instead).
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(self.attribute_list)
        layout.addLayout(button_row)
        layout.addWidget(buttons)

    def _populate(self, rows: List[Tuple[str, str, bool, str]]):
        self.attribute_list.clear()
        self._row_meta = {}
        for attribute_key, attribute_label, elevated, hidden_state in rows:
            self._row_meta[attribute_key] = (attribute_label, elevated, hidden_state)
            item = QListWidgetItem(_row_text(attribute_label, elevated, hidden_state))
            item.setData(Qt.ItemDataRole.UserRole, attribute_key)
            self.attribute_list.addItem(item)

    def _select_initial_row(self, initial_attribute_key: Optional[str]) -> None:
        """Opens the list with initial_attribute_key's row already current
        - normally whichever attribute Region 4 last had selected, so the
        dialog picks up where the user was rather than always landing on
        row 0. Falls back to the first row when that key wasn't passed, or
        isn't among the attributes in this dialog's own scope (e.g. Region 2
        is scoped to a different voice than Region 4's selection came from)."""
        if self.attribute_list.count() == 0:
            return
        if initial_attribute_key is not None:
            for row in range(self.attribute_list.count()):
                if self.attribute_list.item(row).data(Qt.ItemDataRole.UserRole) == initial_attribute_key:
                    self.attribute_list.setCurrentRow(row)
                    return
        self.attribute_list.setCurrentRow(0)

    def _current_meta(self, current_row: int) -> Tuple[str, bool, str]:
        if current_row < 0:
            return ("", False, "visible")
        attribute_key = self.attribute_list.item(current_row).data(Qt.ItemDataRole.UserRole)
        return self._row_meta.get(attribute_key, ("", False, "visible"))

    def _update_button_state(self, current_row: Optional[int] = None):
        if current_row is None:
            current_row = self.attribute_list.currentRow()
        self.up_button.setEnabled(current_row > 0)
        self.down_button.setEnabled(0 <= current_row < self.attribute_list.count() - 1)
        self.add_remove_button.setEnabled(current_row >= 0)

        has_selection = current_row >= 0
        _label, _elevated, hidden_state = self._current_meta(current_row)

        self.hide_button.setText("Un&hide" if hidden_state == "part" else "&Hide")
        # Disabled outright (not just refused-with-message) when the row is
        # already hidden for all - redundant rather than an error, unlike
        # the elevated-while-hiding case below, which stays enabled and
        # explains itself with a message instead.
        self.hide_button.setEnabled(has_selection and hidden_state != "all")

        self.hide_for_all_button.setText(
            "Unhide for &All" if hidden_state == "all" else "Hide for &All"
        )
        self.hide_for_all_button.setEnabled(has_selection)

    def _move(self, delta: int):
        row = self.attribute_list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if not (0 <= new_row < self.attribute_list.count()):
            return
        item = self.attribute_list.takeItem(row)
        self.attribute_list.insertItem(new_row, item)
        self.attribute_list.setCurrentRow(new_row)

    def _request_add_remove(self):
        item = self.attribute_list.currentItem()
        if item is None:
            return
        attribute_key = item.data(Qt.ItemDataRole.UserRole)
        self.add_remove_requested.emit(attribute_key)

    def _request_hide(self):
        item = self.attribute_list.currentItem()
        if item is None:
            return
        attribute_key = item.data(Qt.ItemDataRole.UserRole)
        self.hide_requested.emit(attribute_key)

    def _request_hide_for_all(self):
        item = self.attribute_list.currentItem()
        if item is None:
            return
        attribute_key = item.data(Qt.ItemDataRole.UserRole)
        self.hide_for_all_requested.emit(attribute_key)

    def set_row_state(self, attribute_key: str, elevated: bool, hidden_state: str) -> None:
        """Called by AttributeController after a successful Hide/Unhide (per
        -part or for-all) toggle - updates just that row's text in place,
        immediate-apply like Add/Remove, without rebuilding the list or
        disturbing the current row/selection. A no-op if `attribute_key`
        isn't a row here (shouldn't happen - the dialog only ever requests a
        toggle for one of its own rows)."""
        meta = self._row_meta.get(attribute_key)
        if meta is None:
            return
        label = meta[0]
        self._row_meta[attribute_key] = (label, elevated, hidden_state)
        for row in range(self.attribute_list.count()):
            item = self.attribute_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == attribute_key:
                item.setText(_row_text(label, elevated, hidden_state))
                break
        self._update_button_state()

    def ordered_keys(self) -> List[str]:
        """The attribute_key order after any staged moves, only meaningful
        once exec() has returned Accepted."""
        return [
            self.attribute_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.attribute_list.count())
        ]

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: focus_list_and_reannounce_current_row(self.attribute_list))
