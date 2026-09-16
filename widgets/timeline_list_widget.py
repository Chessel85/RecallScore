# timeline_list_widget.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget

from widgets.region_focus_cycle import RegionFocusCycleMixin


class TimelineListWidget(RegionFocusCycleMixin, QListWidget):
    """
    Region 3 list widget handling custom timeline traversal (Left/Right)
    and single-note selection collapsing (Up/Down).

    It reaches nothing back in MainWindow: every keystroke it handles turns
    into one of the signals below, wired to a controller in
    MainWindow.connect_signals() the same way Region 2's filter_changed is.
    That keeps the widget unit-testable without a window.

    Typing a bar number then Enter (Ref 6) is NOT handled here - it is
    global: main_window.py's window-wide digit shortcuts feed
    NavigationController, Enter commits the typed bar number (via
    audition_phrase), Ctrl+Enter commits it as the loop length, and Escape
    cancels. Any cursor move cancels a half-typed number -
    NavigationController does that for Left/Right/Find, and the slot wired
    to vertical_move_made for an in-slice Up/Down here.

    Home/End are NOT handled here either - they fall through to
    QListWidget's own native top/bottom-row behaviour. "First/last note of
    the piece" is Ctrl+Home/Ctrl+End, a global menu action (Navigation menu)
    that doesn't move focus, not a Region-3-only keystroke - see
    MainWindow._navigation_menu_first_measure/_last_measure. Likewise
    Ctrl+Left/Ctrl+Right (move by bar) is a global action now, not handled
    here.

    Alt+PageUp/Alt+PageDown (loop length) and Ctrl+1..9 (speak Region 4's
    Nth attribute row) are ALSO not handled here - both are global
    `MainWindow.setup_shortcuts` QShortcuts now (see MainWindow.
    increase_loop_length/decrease_loop_length and RegionPresenter.
    announce_attribute_by_number), since neither one is really a Region-3
    position move.
    """

    # direction is "left"/"right" - note-by-note stepping only. By-measure
    # and first/last-of-piece jumps are global menu actions now (see the
    # class docstring), not routed through this signal.
    navigate_requested = Signal(str)
    # An in-slice Up/Down finished (selection already collapsed here) - the
    # slot re-auditions the note without position cues and clears any
    # half-typed bar number.
    vertical_move_made = Signal()

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        if key == Qt.Key.Key_Left and not ctrl:
            self.navigate_requested.emit("left")
        elif key == Qt.Key.Key_Right and not ctrl:
            self.navigate_requested.emit("right")
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            # Qt's ExtendedSelection arrow handling collapses a multi-row
            # selection only as a side effect of the current row CHANGING.
            # At a boundary (Up on the top row of a selected chord) there is
            # nowhere to move, so it no-ops and leaves the whole chord
            # selected. Re-collapsing unconditionally is harmless when the
            # native handling already did it, and fixes the boundary case.
            super().keyPressEvent(event)
            current = self.currentItem()
            if current is not None:
                self.clearSelection()
                current.setSelected(True)
            self.vertical_move_made.emit()
        # Tab/Shift+Tab are handled in RegionFocusCycleMixin.event() -
        # QAbstractItemView never lets them reach keyPressEvent here.
        else:
            super().keyPressEvent(event)
