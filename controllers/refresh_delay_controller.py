# controllers/refresh_delay_controller.py
"""The Delay Refresh gate: sits between PlaybackController's per-step cursor
signal and RegionPresenter.update_timeline_views, deciding WHEN a playback
cursor move actually reaches the regions/status bar - see
UserPlans/DelayRefresh.md for the feature's reasoning.

Touches no widgets (invariant 6 - RegionPresenter is the only controller
allowed to). Manual navigation (navigation.position_changed) never passes
through here - it stays connected directly to the presenter so it is never
gated.

Only positive delays and "refresh off" live here. A negative delay instead
holds the MUSIC back (audio/sequencer.py's lead_offset_ms) so the text is
already early relative to what is heard - this controller has nothing to do
in that case.
"""
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from models.refresh_settings import RefreshSettings


class RefreshDelayController(QObject):
    """refresh_requested(play_all) - forwarded from cursor_moved once a
    pending cursor move is actually applied (immediately, or after the
    configured delay)."""

    refresh_requested = Signal(bool)

    def __init__(self, session, timer=None, parent=None):
        super().__init__(parent)
        self.session = session
        self._settings = RefreshSettings()
        self._pending_index: Optional[int] = None
        self._pending_play_all: bool = False
        # timer: injectable like PlaybackController's/Sequencer's, so tests
        # can drive the delay without waiting on the clock.
        if timer is None:
            timer = QTimer(self)
        self._timer = timer
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer)

    @property
    def music_data(self):
        return self.session.music_data

    @property
    def settings(self) -> RefreshSettings:
        """A read-only copy, for the dialog and for persistence."""
        return self._settings.copy()

    def set_settings(self, settings: RefreshSettings) -> None:
        """Flushes first so changing the setting mid-playback cannot strand
        a pending refresh under the old settings."""
        self.flush()
        self._settings = settings.copy()

    def set_refresh_during_playback(self, enabled: bool) -> bool:
        """The Ctrl+H toggle's entry point. Returns the new state so the
        caller can announce it."""
        settings = self._settings.copy()
        settings.refresh_during_playback = enabled
        self.set_settings(settings)
        return self._settings.refresh_during_playback

    def handle_cursor_moved(self, index: int, play_all: bool, is_playing: bool) -> None:
        """The whole decision:
        * not playing, or refresh on with delay_ms <= 0 -> apply immediately
          (today's path, unchanged in effect).
        * refresh off -> record the index, emit nothing until flush().
        * refresh on, delay_ms > 0 -> record the index, start the timer;
          apply on timeout. A later step inside the same window overwrites
          the pending index - it's a slot, not a queue.
        A negative delay_ms needs nothing here - the music is what moves.
        """
        if not is_playing or (
            self._settings.refresh_during_playback and self._settings.delay_ms <= 0
        ):
            self._apply(index, play_all)
            return

        self._pending_index = index
        self._pending_play_all = play_all
        if self._settings.refresh_during_playback and self._settings.delay_ms > 0:
            self._timer.start(self._settings.delay_ms)

    def flush(self) -> None:
        """Applies any pending index now. No-op when nothing is pending."""
        if self._pending_index is None:
            return
        self._timer.stop()
        index = self._pending_index
        play_all = self._pending_play_all
        self._pending_index = None
        self._apply(index, play_all)

    def cancel(self) -> None:
        """Stops the timer and drops any pending index without applying
        it."""
        self._timer.stop()
        self._pending_index = None

    def _on_timer(self) -> None:
        index = self._pending_index
        play_all = self._pending_play_all
        self._pending_index = None
        if index is not None:
            self._apply(index, play_all)

    def _apply(self, index: int, play_all: bool) -> None:
        if not self.music_data:
            return
        self.music_data.active_event_index = index
        self.refresh_requested.emit(play_all)
