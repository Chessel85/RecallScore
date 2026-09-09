# controllers/navigation_controller.py
from typing import Optional

from PySide6.QtCore import QObject, Signal

from models.find_target import FindTarget


class NavigationController(QObject):
    """Moving the timeline cursor: Left/Right, Ctrl+Left/Right, Home/End,
    a typed bar number, Region 5's span jumps, and Find (widgets/
    find_dialog.py).

    Every method either moves and emits position_changed(play_all), or fails
    to move and emits boundary_hit. Deciding what a move sounds like and
    what it redraws is deliberately NOT this class's job - MainWindow wires
    those two signals - which is what keeps navigation free of both widgets
    and the synth.
    """

    position_changed = Signal(bool, bool)  # play_all, announce_measure
    boundary_hit = Signal()
    # Options > Bar Line Indicator (Ctrl+B): emitted when a plain Left/Right
    # step (arrow key or the "forward"/"back" voice command, both of which
    # land on timeline_left/right) actually moves AND the measure number
    # changes - i.e. a bar line was crossed. Emitted AFTER position_changed
    # so PlaybackController.play_barline_indicator's beep isn't cut off by
    # the destination note's own retrigger=True audition. The by-measure
    # jumps (Ctrl+Left/Right) deliberately don't emit it - they always cross
    # a bar line and already announce the new bar number.
    barline_crossed = Signal()
    # Ref 6: the digits typed so far towards a bar number, emitted on every
    # change so RegionPresenter can show "Go to measure: 12" in the status
    # bar. Empty string once committed or cancelled.
    pending_digits_changed = Signal(str)

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        # Ref 6: digits build up here as they are typed (from any region or
        # the status bar - main_window.py's window-wide digit shortcuts feed
        # this), and are jumped to on Enter. Any cursor move or Escape
        # cancels a half-typed number so a later, unrelated Enter can't
        # action a stale one.
        self.pending_digits: str = ""
        # The FindTarget last armed by the Find dialog's OK (Ctrl+F) -
        # what Alt+Right/Alt+Left (find_next/find_previous) cycle through.
        # None until Find has been used at least once this session; a
        # reload doesn't clear it, since the target is just a plain
        # (category, key) tag, not a reference into the old score - if the
        # new score has no matching occurrences, find_occurrence simply
        # returns None and the cue is the ordinary boundary_hit.
        self.current_find_target: Optional[FindTarget] = None
        # Set by MainWindow after RegionPresenter is constructed (same
        # deferred wiring as VoiceControlController.presenter - the presenter
        # doesn't exist yet when this controller is built). Only
        # select_section needs it: a section switch redraws Region 1 and
        # resets Region 5's diff state as well as moving the cursor, more
        # than the position_changed signal alone conveys.
        self.presenter = None

    @property
    def music_data(self):
        return self.session.music_data

    def _moved(self, ok: bool, announce_measure: bool = False) -> None:
        if ok:
            self.position_changed.emit(True, announce_measure)
        else:
            self.boundary_hit.emit()

    # --- typed bar number (Ref 6) -----------------------------------------

    def append_pending_digit(self, ch: str) -> None:
        self.pending_digits += ch
        self.pending_digits_changed.emit(self.pending_digits)

    def clear_pending_digits(self) -> None:
        """Cancel a half-typed bar number. A cheap no-op when nothing is
        pending, so movement methods can call it unconditionally."""
        if self.pending_digits:
            self.pending_digits = ""
            self.pending_digits_changed.emit("")

    def commit_pending_digits(self) -> bool:
        """Enter: if a bar number is pending, jump to it and return True;
        otherwise return False so the caller falls through to Preview."""
        if not self.pending_digits:
            return False
        digits = self.pending_digits
        self.pending_digits = ""
        self.pending_digits_changed.emit("")
        self.to_typed_measure(digits)
        return True

    def _current_measure(self) -> Optional[int]:
        slice_ = self.music_data.get_current_slice() if self.music_data else None
        return slice_.measure if slice_ is not None else None

    def navigate(self, direction: str, by_measure: bool = False) -> None:
        """Dispatch a Note-region arrow-key move. Region 3
        (TimelineListWidget) emits navigate_requested(direction, by_measure)
        and MainWindow.connect_signals routes it straight here, so the
        widget itself stays window-free. `direction` is
        "left"/"right"/"home"/"end"; `by_measure` (Ctrl held) applies only
        to left/right."""
        if direction == "left":
            self.measure_left() if by_measure else self.timeline_left()
        elif direction == "right":
            self.measure_right() if by_measure else self.timeline_right()
        elif direction == "home":
            self.timeline_home()
        elif direction == "end":
            self.timeline_end()

    def timeline_left(self) -> None:
        self.clear_pending_digits()
        if not self.music_data:
            return
        before = self._current_measure()
        moved = self.music_data.move_timeline_left()
        self._moved(moved)
        after = self._current_measure()
        if moved and before is not None and after is not None and before != after:
            self.barline_crossed.emit()

    def timeline_right(self) -> None:
        self.clear_pending_digits()
        if not self.music_data:
            return
        before = self._current_measure()
        moved = self.music_data.move_timeline_right()
        self._moved(moved)
        after = self._current_measure()
        if moved and before is not None and after is not None and before != after:
            self.barline_crossed.emit()

    def measure_left(self) -> None:
        self.clear_pending_digits()
        if not self.music_data:
            return
        self._moved(self.music_data.move_timeline_left_by_measure(), announce_measure=True)

    def measure_right(self) -> None:
        self.clear_pending_digits()
        if not self.music_data:
            return
        self._moved(self.music_data.move_timeline_right_by_measure(), announce_measure=True)

    def timeline_home(self) -> None:
        """Home (Ref 5). Unlike Left/Right this jumps to a known limit, so it
        never represents crossing a boundary and never cues one."""
        self.clear_pending_digits()
        if not self.music_data:
            return
        self.music_data.move_timeline_home()
        self.position_changed.emit(True, True)

    def timeline_end(self) -> None:
        """End (Ref 5) - see timeline_home."""
        self.clear_pending_digits()
        if not self.music_data:
            return
        self.music_data.move_timeline_end()
        self.position_changed.emit(True, True)

    def to_typed_measure(self, digits: str) -> None:
        """Ref 6: Enter with pending digits jumps to that bar's first active
        event; an unknown bar sounds the boundary cue and doesn't move."""
        if not self.music_data:
            return
        self._moved(self.music_data.jump_to_measure(int(digits)), announce_measure=True)

    def jump_to_span(self, row, is_start: bool) -> None:
        """Region 5's Ctrl+Home/Ctrl+End (Ref 29). `row` is the focused
        PerformanceRegionRow, passed in rather than read off the widget.

        A hairpin row carries jump_target_quarters, because a wedge can
        start or stop mid-measure; a repeat/ending row has None and resolves
        by measure, barlines falling only at measure boundaries. Ctrl+End on
        one of those lands on the LAST sounding note of the end bar (the
        user's decision) - the app's only "last event in a measure" target.
        """
        self.clear_pending_digits()
        if not self.music_data or row is None:
            return

        if row.jump_target_quarters is not None:
            index = self.music_data.slice_index_at_or_after_quarters(row.jump_target_quarters)
        elif is_start:
            index = self.music_data.first_visible_event_index_of_measure(row.jump_target_measure)
        else:
            index = self.music_data.last_visible_event_index_of_measure(row.jump_target_measure)

        if index is None:
            self.boundary_hit.emit()
            return

        self.music_data.active_event_index = index
        self.position_changed.emit(True, False)

    def next_section(self) -> None:
        """Ctrl+Alt+Right (P2): jump to the first bar of the next song
        section after the cursor. A positional jump like Home/End, so it
        cues the boundary at the last section rather than wrapping (unlike
        Find). A no-op boundary cue on a score with no sections."""
        self._step_section(direction=1)

    def previous_section(self) -> None:
        """Ctrl+Alt+Left counterpart of next_section."""
        self._step_section(direction=-1)

    def _step_section(self, direction: int) -> None:
        self.clear_pending_digits()
        data = self.music_data
        if not data or not data.section_spans:
            self.boundary_hit.emit()
            return
        starts = sorted(
            i for i in (
                data.first_visible_event_index_of_measure(s.start_measure)
                for s in data.section_spans
            )
            if i is not None
        )
        if not starts:
            self.boundary_hit.emit()
            return
        current = data.active_event_index
        if direction > 0:
            target = next((i for i in starts if i > current), None)
        else:
            target = next((i for i in reversed(starts) if i < current), None)
        if target is None:
            self.boundary_hit.emit()
            return
        data.active_event_index = target
        self.position_changed.emit(True, False)

    # --- score sections (multi-section MusicXML) -------------------------
    #
    # A "section" here is one of N independent pieces packed into a single
    # file (UserPlans/MultiSectionScores.md) - distinct from the P2 "song
    # section" jumps above. Selecting one swaps MusicData's live
    # TimelineBuild so every other region behaves as if that section were
    # the whole file.

    def select_section(self, index: int, announce: bool = True) -> bool:
        """Make section `index` active. Returns True when it actually
        changed, False for an out-of-range or unchanged index.

        Doesn't emit position_changed: a section switch also rebuilds
        Region 1 and drops Region 5's cross-section diff state, so it
        drives RegionPresenter directly (via the injected reference) rather
        than through the ordinary move signal.

        `announce` is False when the switch came from Region 1's tab bar,
        which NVDA already voices ("Exercise 2, tab, 2 of 2") - a second
        QAccessible announcement would just double up (the same trap noted
        in RegionPresenter.update_timeline_views). It stays True for the
        menu / any programmatic caller, where nothing else speaks."""
        self.clear_pending_digits()
        data = self.music_data
        if data is None or not data.set_active_section(index):
            return False
        if self.presenter is not None:
            # Reset FIRST: Region 5 must not be diffed against the previous
            # section's rows, or its "None" placeholder fails to render.
            self.presenter.reset_performance_labels()
            self.presenter.refresh_region_1()
            # Regions 3/4/5, the status bar and the landing-note audition
            # all go through the normal move path.
            self.presenter.update_timeline_views(play_all=True)
            if announce:
                self.presenter.announce_section_change()
        return True

    def step_section(self, delta: int) -> bool:
        """Left/Right on the Region 1 section row: move `delta` sections
        from the active one, clamped at the ends (no wrap - matches a
        QTabBar's own arrows and Ref 6's boundary behaviour). Sounds the
        boundary cue on a no-op at an end."""
        data = self.music_data
        if data is None:
            return False
        target = data.active_section_index + delta
        if not (0 <= target < len(data.sections)):
            self.boundary_hit.emit()
            return False
        return self.select_section(target)

    def arm_find_target(self, target: FindTarget) -> None:
        """Called by MainWindow on the Find dialog's OK, before the initial
        jump - stores what Alt+Right/Alt+Left will cycle through next."""
        self.current_find_target = target

    def find_next(self) -> None:
        """Alt+Right, and the Find dialog's own OK (arm then jump forward
        from wherever the cursor already is). A no-op boundary cue, same as
        an unresolved Region 5 jump, when nothing is armed yet or the
        target has no occurrences."""
        self._find(direction=1)

    def find_previous(self) -> None:
        """Alt+Left counterpart of find_next."""
        self._find(direction=-1)

    def _find(self, direction: int) -> None:
        self.clear_pending_digits()
        if not self.music_data or self.current_find_target is None:
            self.boundary_hit.emit()
            return
        from_index = self.music_data.active_event_index
        index = self.music_data.find_occurrence(self.current_find_target, from_index, direction)
        if index is None:
            self.boundary_hit.emit()
            return

        # find_occurrence always returns either the nearest occurrence
        # strictly ahead/behind from_index, or - when none remains in that
        # direction - wraps to the first/last occurrence overall. Reported:
        # that wrap was silent, indistinguishable from an ordinary short
        # hop. Since a genuine (non-wrapped) hit is always strictly ahead/
        # behind from_index by construction, landing anywhere else can only
        # mean a wrap occurred.
        wrapped = index <= from_index if direction > 0 else index >= from_index

        self.music_data.active_event_index = index
        # Move (and sound the destination note) first, boundary cue after -
        # the reverse order would have the note's own retrigger=True
        # silence the cue almost immediately, the same bug already fixed
        # for Region 5's own change cue (see MainWindow._update_timeline_
        # views's ordering comment).
        self.position_changed.emit(True, False)
        if wrapped:
            self.boundary_hit.emit()
