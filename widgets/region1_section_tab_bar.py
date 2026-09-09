# widgets/region1_section_tab_bar.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTabBar

from widgets.region_focus_cycle import RegionFocusCycleMixin


class Region1SectionTabBar(RegionFocusCycleMixin, QTabBar):
    """The section switcher sitting above Region 1's property list, shown
    only for a multi-section MusicXML score (UserPlans/MultiSectionScores.md
    - one file holding several independent pieces).

    One tab per section, labelled with the section labels ("Exercise 1",
    "Exercise 2"). A QTabBar is the control that already means "one of N
    views of the same information", and NVDA reports it natively -
    "Exercise 1, tab, 1 of 2" - with Left/Right switching, so there is no
    invented key convention and no explanatory row for the user to read
    past. Its own arrows stop at the ends rather than wrapping, which
    matches Ref 6's boundary behaviour at the ends of the timeline.

    Mixed with RegionFocusCycleMixin BEFORE QTabBar (see
    widgets/region_focus_cycle.py) so Tab/Shift+Tab step the region focus
    cycle - invariant 7's single owner of that keystroke - rather than
    being swallowed here, exactly as the region list widgets already do.
    FocusController treats this bar as an extra focus stop just ahead of
    Region 1's list while it is visible.
    """

    section_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        # NVDA reads the focused widget's accessible name; the caption QLabel
        # above is not in the tab order, so name the bar itself.
        self.setAccessibleName("Score section")
        self.setDrawBase(False)
        self.setVisible(False)
        self.currentChanged.connect(self._on_current_changed)

    def set_sections(self, labels, current_index: int) -> None:
        """Rebuild the tabs from `labels` and select `current_index`.

        currentChanged fires while setCurrentIndex runs here; on load that
        would re-enter NavigationController.select_section and reset the
        cursor a second time (plan task 5d), so the rebuild runs with
        signals blocked. Hidden entirely for fewer than two sections, so an
        ordinary file's Region 1 looks and behaves exactly as before - same
        rows, same single focus target.
        """
        blocked = self.blockSignals(True)
        try:
            while self.count():
                self.removeTab(0)
            for label in labels:
                self.addTab(label)
            if labels:
                self.setCurrentIndex(max(0, min(current_index, len(labels) - 1)))
        finally:
            self.blockSignals(blocked)
        self.setVisible(len(labels) >= 2)

    def step(self, delta: int) -> bool:
        """Move `delta` tabs from the current one, clamped at the ends - no
        wrap, matching this bar's own Left/Right arrows and Ref 6's boundary
        behaviour. Returns True when the bar is showing (so the keystroke is
        consumed even on a boundary no-op), False when hidden so the caller
        lets Ctrl+Tab fall through to the region cycle."""
        if self.isHidden() or self.count() < 2:
            return False
        target = max(0, min(self.currentIndex() + delta, self.count() - 1))
        if target != self.currentIndex():
            self.setCurrentIndex(target)
        return True

    def _region_ctrl_tab(self, forward: bool) -> bool:
        return self.step(1 if forward else -1)

    def _on_current_changed(self, index: int) -> None:
        if index >= 0:
            self.section_selected.emit(index)
