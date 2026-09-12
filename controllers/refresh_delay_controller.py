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

The settings themselves live on MusicData (music_data.refresh_settings), not
on this controller - per-score, like mixer/metronome_enabled (invariant 8:
never write the same fact in two places). This controller reads/writes that
field directly rather than caching its own copy, so a freshly loaded score's
defaults (or its saved .rsc choice, via apply_config) take effect with no
separate seeding step here."""
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
        """A read-only copy of the current score's settings, for the dialog
        and for the Ctrl+H toggle. No score loaded yet -> RefreshSettings'
        own defaults (ticked, no delay)."""
        music_data = self.music_data
        if music_data is None:
            return RefreshSettings()
        return music_data.refresh_settings.copy()

    def set_settings(self, settings: RefreshSettings) -> None:
        """Flushes first so changing the setting mid-playback cannot strand
        a pending refresh under the old settings. A no-op (beyond the flush)
        when no score is loaded - there is nowhere to store the setting."""
        self.flush()
        music_data = self.music_data
        if music_data is not None:
            music_data.refresh_settings = settings.copy()

    def set_refresh_during_playback(self, enabled: bool) -> bool:
        """The Ctrl+H toggle's entry point. Returns the new state so the
        caller can announce it."""
        settings = self.settings
        settings.refresh_during_playback = enabled
        self.set_settings(settings)
        return self.settings.refresh_during_playback

    def handle_cursor_moved(self, index: int, play_all: bool, is_playing: bool = True) -> None:
        """The whole decision:
        * not playing, or refresh on with delay_ms <= 0 -> apply immediately
          (today's path, unchanged in effect).
        * refresh off -> record the index, emit nothing until flush().
        * refresh on, delay_ms > 0 -> record the index, start the timer;
          apply on timeout. A later step inside the same window overwrites
          the pending index - it's a slot, not a queue.
        A negative delay_ms needs nothing here - the music is what moves.

        is_playing defaults to True: PlaybackController.playback_cursor_stepped
        (this method's usual signal source) only ever fires while a run is
        actually stepping through the score, so MainWindow connects the
        two-arg signal straight to this three-arg slot and lets the default
        stand in for "yes, playing".
        """
        settings = self.settings
        if not is_playing or (
            settings.refresh_during_playback and settings.delay_ms <= 0
        ):
            self._apply(index, play_all)
            return

        self._pending_index = index
        self._pending_play_all = play_all
        if settings.refresh_during_playback and settings.delay_ms > 0:
            # Only arm when idle. Restarting on every step - QTimer.start()
            # on an already-running timer resets its countdown - starved
            # the refresh entirely during continuous playback: any step
            # inside the window kept pushing the deadline out, so the timer
            # never actually fired until a gap longer than delay_ms opened
            # up (live-tested: at +1s, the note list never refreshed while
            # notes kept arriving faster than that). Leaving the first
            # timer to run its course means it fires delay_ms after the
            # window opened, applying whatever index is pending at that
            # point - still "a slot, not a queue", just one that actually
            # drains.
            if not self._timer.isActive():
                self._timer.start(settings.delay_ms)

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
