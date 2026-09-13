# widgets/region1_list_widget.py
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidgetItem

from widgets.region_property_list_widget import RegionPropertyListWidget


class Region1ListWidget(RegionPropertyListWidget):
    """
    Region 1 (score info) property list. The only behaviour beyond the
    shared base is routing Ctrl+Tab / Ctrl+Shift+Tab to the section tab
    bar sitting above it, so a multi-section score's sections can be
    stepped through without first moving focus onto the bar - kept as its
    own file/class so Region 1 has the same one-file-per-region shape as
    Region2ListWidget/TimelineListWidget/Region5ListWidget.

    Stage 7 (PerformanceMarkingsStrategy.md section 9): the Directives list
    is appended after the plain "label: value" property rows, each carrying
    its directive_marks index via UserRole so Ctrl+N (and the Menu key/
    Shift+F10 context-menu equivalent) can toggle it without a side table.
    """

    directive_toggle_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._directive_row_count = 0

    def _region_ctrl_tab(self, forward: bool) -> bool:
        tabs = getattr(self.window(), "region_1_section_tabs", None)
        if tabs is None:
            return False
        return tabs.step(1 if forward else -1)

    def refresh_list(self, data: dict, directive_rows: List[Tuple[int, str, bool]] = ()) -> None:
        """Extends the shared base's plain property rows with the
        Directives list - `directive_rows` is (index, display text,
        surfaced) triples from MusicData.get_directive_rows(), already in
        bar order. A surfaced directive gets no visible marker here (that's
        Region 5's asterisk, stage 9); its state is read back from
        MusicData when Ctrl+N is pressed."""
        current_row = self.currentRow()

        self.clear()
        for key, value in data.items():
            self.addItem(QListWidgetItem(f"{key}: {value}"))

        self._directive_row_count = len(directive_rows)
        for index, text, _surfaced in directive_rows:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.addItem(item)

        if self.count() > 0:
            self.setCurrentRow(min(max(current_row, 0), self.count() - 1))

    def current_directive_index(self) -> Optional[int]:
        """The directive_marks index behind the focused row, or None for a
        plain property row (or an empty/absent selection)."""
        item = self.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift_f10 = key == Qt.Key.Key_F10 and bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )

        if (key == Qt.Key.Key_N and ctrl) or key == Qt.Key.Key_Menu or shift_f10:
            index = self.current_directive_index()
            if index is not None:
                self.directive_toggle_requested.emit(index)
                return

        super().keyPressEvent(event)
