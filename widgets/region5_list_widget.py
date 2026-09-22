# widgets/region5_list_widget.py
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from models.performance_region_row import PerformanceRegionRow
from widgets.region_focus_cycle import RegionFocusCycleMixin


class Region5ListWidget(RegionFocusCycleMixin, QListWidget):
    """
    Region 5 (Ref 29, the "Performance region"): a flat list of whichever
    repeat/ending/hairpin rows are active at the cursor's current position.

    A list, not a table, for the same "NVDA reads a whole row in one
    keystroke" reasoning as Region 2. Unlike Region 2 there is no
    user-authored order to preserve across a rebuild, so refresh_list is a
    plain repopulate landing on row 0 rather than an id-based re-anchor.

    Alt+Home/Alt+End jump the timeline cursor to the focused row's span
    start/end - scoped to this region only, distinct from the global
    Ctrl+Home/Ctrl+End, which mean "first/last note of the piece" from
    anywhere. The keystroke turns into span_jump_requested rather than a
    call back into MainWindow, wired in MainWindow.connect_signals() like
    Region 2's filter_changed.
    """

    # is_start: True for Alt+Home (jump to the focused span's start),
    # False for Alt+End.
    span_jump_requested = Signal(bool)
    # Stage 9 (PerformanceMarkingsStrategy.md section 8): the focused row's
    # marking_categories id, emitted by Ctrl+N - toggles immediately, no menu.
    category_toggle_requested = Signal(str)
    # Reported: the Menu key/Shift+F10 used to fire the same immediate
    # toggle as Ctrl+N - a real keystroke shortcut, but not what "context
    # menu" means for those two keys everywhere else in the app (Region 2's
    # single-item Unlink menu, Region 4's Add/Remove scope menu). They now
    # open an actual one-item popup instead; category + anchor position, S6-
    # style like Region 2/4's own context_menu_requested.
    context_menu_requested = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        # P2: how many of the leading items are live "context" rows (Section
        # / Chord / Lyric), so update_context_rows knows which ones it may
        # relabel in place.
        self._context_row_count = 0

    def refresh_list(
        self,
        context_rows: List[PerformanceRegionRow],
        structural_rows: List[PerformanceRegionRow],
    ) -> None:
        """Clears and repopulates: the P2 context rows first, then the Ref
        29 structural rows. Both empty shows a single "None" placeholder
        (UserRole None, so Alt+Home/End no-ops on it), matching
        get_region_3_data()'s own ["None"] convention."""
        self.clear()
        self._context_row_count = len(context_rows)
        all_rows = list(context_rows) + list(structural_rows)
        if not all_rows:
            item = QListWidgetItem("None")
            item.setData(Qt.ItemDataRole.UserRole, None)
            self.addItem(item)
        else:
            for row in all_rows:
                item = QListWidgetItem(row.label)
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.addItem(item)
        if self.count() > 0:
            self.setCurrentRow(0)

    def update_context_rows(self, context_rows: List[PerformanceRegionRow]) -> bool:
        """Relabels the leading context rows in place (text + UserRole),
        never clearing or moving focus - mirrors
        RegionPresenter.refresh_region_3_labels. Returns False (caller falls
        back to a full refresh_list) when the row count changed, so a
        Section/Chord/Lyric row appearing or disappearing still rebuilds."""
        if len(context_rows) != self._context_row_count:
            return False
        for i, row in enumerate(context_rows):
            item = self.item(i)
            if item is None:
                return False
            item.setText(row.label)
            item.setData(Qt.ItemDataRole.UserRole, row)
        return True

    def current_row_data(self) -> Optional[PerformanceRegionRow]:
        """The row behind the focused item, or None (empty list or the
        placeholder), so callers never reach into currentItem() themselves."""
        item = self.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        shift_f10 = key == Qt.Key.Key_F10 and bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )

        if key == Qt.Key.Key_Home and alt:
            self.span_jump_requested.emit(True)
            return
        elif key == Qt.Key.Key_End and alt:
            self.span_jump_requested.emit(False)
            return
        elif key == Qt.Key.Key_N and ctrl:
            row = self.current_row_data()
            if row is not None and row.category is not None:
                self.category_toggle_requested.emit(row.category)
                return
        elif key == Qt.Key.Key_Menu or shift_f10:
            row = self.current_row_data()
            item = self.currentItem()
            if row is not None and row.category is not None and item is not None:
                anchor = self.visualItemRect(item).center()
                self.context_menu_requested.emit(
                    row.category, self.viewport().mapToGlobal(anchor)
                )
                return

        super().keyPressEvent(event)
