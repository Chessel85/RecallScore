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
    NavigationController does that for Left/Right/Home/End/Find, and the
    slot wired to vertical_move_made for an in-slice Up/Down here.
    """

    # (direction, by_measure): direction is "left"/"right"/"home"/"end";
    # by_measure (Ctrl held) is only meaningful for left/right.
    navigate_requested = Signal(str, bool)
    # An in-slice Up/Down finished (selection already collapsed here) - the
    # slot re-auditions the note without position cues and clears any
    # half-typed bar number.
    vertical_move_made = Signal()
    # Alt+PageUp / Alt+PageDown: +1 / -1 to the loop length in bars.
    loop_length_adjust_requested = Signal(int)
    # Ctrl+1..9: speak Region 4's Nth attribute row without moving focus.
    attribute_number_requested = Signal(int)

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)

        if key == Qt.Key.Key_PageUp and alt:
            # Alt avoids QListWidget's own native PageUp (move the current
            # row up a page) - bare PageUp/PageDown would collide with that
            # the same way bare Up/Down would collide with chord-selection
            # handling below, so this is deliberately not bound plain.
            self.loop_length_adjust_requested.emit(1)
            return
        elif key == Qt.Key.Key_PageDown and alt:
            self.loop_length_adjust_requested.emit(-1)
            return
        elif ctrl and Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            # Quick attribute lookup: speaks Region 4's Nth row without
            # moving focus off Region 3 - see RegionPresenter.
            # announce_attribute_by_number, which silently no-ops if N
            # exceeds the currently displayed attribute list.
            self.attribute_number_requested.emit(key - Qt.Key.Key_0)
            return

        if key == Qt.Key.Key_Left:
            self.navigate_requested.emit("left", ctrl)
        elif key == Qt.Key.Key_Right:
            self.navigate_requested.emit("right", ctrl)
        elif key == Qt.Key.Key_Home:
            self.navigate_requested.emit("home", False)
        elif key == Qt.Key.Key_End:
            self.navigate_requested.emit("end", False)
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
