# controllers/playback_controller.py
from typing import Any, List, Optional, Tuple

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from audio.barline_patterns import STEP_MS
from audio.navigation_cues import barline_indicator_events, count_in_cues, position_cues
from audio.free_metronome import free_metronome_beat
from audio import boundary_cue as _boundary_cue
from audio.boundary_cue import boundary_cue_event
from audio.sequencer import Sequencer
from audio.strum_schedule import sound_events
from models import announcements, mixer_settings
from models.mixer_settings import MixerEdit
from models import play_plan
from models.play_plan import PlayRun
from models.play_settings import (
    PLAY_MODE_LOOP_FOREVER,
    PLAY_MODE_TO_END,
    PlaySettings,
)


# The play session's plan lives in models/play_plan.py, shared with the web
# version; the old private name stays for the tests and comments using it.
_PlayRun = PlayRun


class PlaybackController(QObject):
    """Everything that makes sound, and the transport state around it:
    Sequencer lifecycle, play/pause/stop, the lead-in/looping play session,
    absolute tempo, chord audition, the boundary cue, and the metronome/
    announcer toggles.

    Touches no widgets. Where a widget-derived value is needed it is passed
    in - audition_selection(indices) rather than reading Region 3's
    selection - which is what keeps the transport logic testable without a
    window.

    Signals rather than direct calls into the view, so the refresh ordering
    stays owned by MainWindow (see its _on_cursor_moved):
      cursor_moved(play_all)   - the timeline position changed
      status_text_changed()    - the whole status bar needs rebuilding
      playback_state_changed() - only the Playing/Paused/Stopped field
      playback_cursor_stepped(index, play_all) - one Sequencer step, en
        route to the Delay Refresh gate (see refresh_gate below) rather
        than straight to the regions - unlike cursor_moved, which stays
        immediate and ungated everywhere else it's emitted (stop, finish,
        loop restart).
    """

    cursor_moved = Signal(bool)
    status_text_changed = Signal()
    playback_state_changed = Signal()
    playback_cursor_stepped = Signal(int, bool)

    # Boundary cue (Ref 2 AC4/Ref 3 AC4): a short sound played INSTEAD of
    # moving, deliberately unlike anything in the score so it isn't mistaken
    # for one. Was a low GM contrabass note; now a recorded one-shot sample
    # (tools/bells/bump.wav) on its own reserved channel, routed through the
    # project soundfont like the click / announcer / performance cue -
    # see audio/boundary_cue.py.
    BOUNDARY_CUE_CHANNEL = _boundary_cue.BOUNDARY_CUE_CHANNEL

    def __init__(self, session, timer=None, parent=None):
        super().__init__(parent)
        self.session = session
        # One Sequencer per loaded score - it holds a reference to that
        # score's MusicData, so it is recreated in attach_score().
        self.sequencer: Optional[Sequencer] = None
        # Groundwork for wishlist #7 (mute): consulted before anything
        # sounds. False throughout today, so every path is unchanged.
        self._muted = False
        # Mixer dialog edit session (begin/set/commit/cancel_mixer_edit
        # below) - None outside of an open dialog.
        self._mixer_edit: Optional[MixerEdit] = None
        # Play Settings (Space/Playback > Play Settings): lead-in and
        # looping. Per-score - they live on music_data.play_settings (see
        # the play_settings property below); this slot only holds them
        # while no score is loaded.
        self._unloaded_play_settings = PlaySettings()
        self._play_run: Optional[_PlayRun] = None
        # Delay Refresh gate (controllers/refresh_delay_controller.py): a
        # plain optional collaborator slot, not an import - this controller
        # must not know the gate's type, only that it has flush()/cancel().
        # Set by MainWindow after both are constructed; every call site
        # below guards it being None (unit tests build a PlaybackController
        # with no gate at all).
        self.refresh_gate = None
        # timer: injectable like Sequencer's, so tests can drive the
        # count-in and the loop without waiting on the clock.
        if timer is None:
            timer = QTimer(self)
            # See Sequencer.__init__'s own comment - the same fast-tempo
            # drift applies to the count-in/loop-restart chain here.
            timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._play_timer = timer
        self._play_timer.setSingleShot(True)
        self._play_timer.timeout.connect(self._on_play_timer)

        # Play Metronome (Ctrl+Alt+Space): a free-running click track at the
        # current playback tempo that never moves the timeline - for playing
        # along by ear. Independent of the Ctrl+M score metronome (which
        # only clicks as the cursor steps over a beat during real playback)
        # and of the transport. One chained single-shot timer, re-armed each
        # beat so an F/S/D tempo change takes effect on the very next click.
        self._play_metronome_timer = QTimer(self)
        self._play_metronome_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._play_metronome_timer.setSingleShot(True)
        self._play_metronome_timer.timeout.connect(self._sound_play_metronome_beat)
        self._play_metronome_beat = 1

    @property
    def music_data(self):
        return self.session.music_data

    @property
    def play_settings(self) -> PlaySettings:
        """The current score's Play Settings, read per call (MusicData is
        replaced wholesale on every load, so this never caches it). No score
        loaded -> a placeholder holding PlaySettings' defaults."""
        music_data = self.music_data
        if music_data is None:
            return self._unloaded_play_settings
        return music_data.play_settings

    @play_settings.setter
    def play_settings(self, settings: PlaySettings) -> None:
        music_data = self.music_data
        if music_data is None:
            self._unloaded_play_settings = settings
        else:
            music_data.play_settings = settings

    @property
    def synth(self):
        return self.session.synth

    @property
    def muted(self) -> bool:
        return self._muted

    @property
    def _lead_offset_ms(self) -> int:
        """Delay Refresh's negative-delay half (UserPlans/DelayRefresh.md):
        a negative RefreshSettings.delay_ms holds the MUSIC back by that
        many ms rather than the gate holding the text back - see
        audio/sequencer.py's own lead_offset_ms. 0 with no gate wired
        (unit tests that build a bare PlaybackController) or with a
        zero/positive delay, where the gate handles it instead."""
        if self.refresh_gate is None:
            return 0
        return max(0, -self.refresh_gate.settings.delay_ms)

    @property
    def is_playback_active(self) -> bool:
        """Playing, paused, or in a play run's count-in or loop gap."""
        sequencer = self.sequencer
        playing = sequencer is not None and (sequencer.is_playing or sequencer.is_paused)
        return playing or self._play_run is not None

    @property
    def is_paused(self) -> bool:
        """Task 8 (Escape stops a paused playback): a thin read of the
        Sequencer, False when there is none (no score loaded, or between
        loads)."""
        return self.sequencer is not None and self.sequencer.is_paused

    def attach_score(self, music_data) -> None:
        """Called on every load: stop whatever the previous score was doing,
        build that score's own Sequencer, and push the score's own saved
        mixer state (music_data.mixer - already populated by apply_config()
        before this runs, see main_window.py's _on_score_loaded)."""
        self.cancel_play_run()
        self.stop_play_metronome()
        if self.refresh_gate is not None:
            self.refresh_gate.cancel()
        if self.sequencer is not None:
            self.sequencer.stop()
        self.sequencer = Sequencer(music_data, self.synth, parent=self)
        self.sequencer.step_played.connect(self._on_sequencer_step)
        self.sequencer.finished.connect(self._on_sequencer_finished)
        self.apply_mixer(music_data.mixer)

    def detach_score(self) -> None:
        """File > Close: the inverse of attach_score. Silence anything
        sounding or scheduled and drop the score's Sequencer, so the
        controller is back to its pre-load state. The synth stays alive
        (it is a process-long singleton), so an explicit stop_all_notes()
        is needed here where closeEvent can rely on synth.close()."""
        self.cancel_play_run()
        self.stop_play_metronome()
        if self.refresh_gate is not None:
            self.refresh_gate.cancel()
        if self.sequencer is not None:
            self.sequencer.stop()
        self.sequencer = None
        self._muted = False
        self.synth.stop_all_notes()

    def apply_mixer(self, mixer) -> None:
        """Wishlist #4: push a score's saved volume/pan onto every mixer
        channel - the override where there is one, else the real default
        (mixer_settings.channel_levels says why every channel is resent)."""
        if mixer is None or not self.music_data:
            return
        self._muted = mixer.muted
        self._send_levels(mixer_settings.channel_levels(self.music_data, mixer))

    def _send_levels(self, levels) -> None:
        for channel, volume, pan in levels:
            self.synth.set_channel_volume(channel, volume)
            self.synth.set_channel_pan(channel, pan)

    # --- mixer dialog (wishlist #4) -----------------------------------
    # The rows, the edit session and the levels are models/mixer_settings.py's
    # (shared with the web version); this only sends them to the synth.

    def begin_mixer_edit(self) -> List[Tuple[str, str, int, int]]:
        """Opens a Mixer dialog edit session and returns (key, label,
        volume_percent, pan_percent) per row for MixerDialog to display
        (MixerEdit.rows)."""
        if not self.music_data:
            return []
        self._mixer_edit = MixerEdit(self.music_data.mixer)
        return self._mixer_edit.rows(self.music_data)

    def set_mixer_volume(self, key: str, percent: int) -> None:
        """Live preview: pushed to the synth immediately, and recorded on
        the edit's working copy - music_data.mixer itself isn't touched
        until commit_mixer_edit (OK)."""
        if self._mixer_edit is None:
            return
        level = self._mixer_edit.set_volume(self.music_data, key, percent)
        if level is not None:
            self.synth.set_channel_volume(*level)

    def set_mixer_pan(self, key: str, percent: int) -> None:
        """Pan counterpart of set_mixer_volume - same live-preview shape."""
        if self._mixer_edit is None:
            return
        level = self._mixer_edit.set_pan(self.music_data, key, percent)
        if level is not None:
            self.synth.set_channel_pan(*level)

    def commit_mixer_edit(self) -> None:
        """OK: the working copy becomes the score's real mixer - already
        live on the synth, so there is nothing further to send."""
        if self.music_data and self._mixer_edit is not None:
            self._mixer_edit.commit(self.music_data)
        self._mixer_edit = None

    def cancel_mixer_edit(self) -> None:
        """Cancel: put the synth back exactly as it was before the dialog
        opened. music_data.mixer is left untouched throughout."""
        if self.music_data and self._mixer_edit is not None:
            self._send_levels(self._mixer_edit.revert_levels(self.music_data))
        self._mixer_edit = None

    def end_mixer_edit(self, accepted: bool) -> None:
        """S5: close out a mixer edit session - commit or revert, then
        silence anything the dialog's own Preview button (Alt+W) left
        running.

        `is_play_run_active` as well as the Sequencer's own flags: a play
        run can have a count-in or a loop pending that `is_playing`/
        `is_paused` cannot see, so checking the Sequencer alone would leave
        it running after the dialog closed.
        """
        if accepted:
            self.commit_mixer_edit()
        else:
            self.cancel_mixer_edit()
        sequencer_running = self.sequencer is not None and (
            self.sequencer.is_playing or self.sequencer.is_paused
        )
        if self.is_play_run_active or sequencer_running:
            self.stop()

    # --- transport ---------------------------------------------------

    def toggle_play_stop(self) -> None:
        """Space (Ref 10): the single play control. Not playing -> start from
        the cursor (looping the loop-length window when looping is on, else
        playing to the end and stopping); playing -> stop, silence and
        revert; paused -> resume. Space owns both starting and resuming;
        Ctrl+Space only pauses.

        From the last note it sounds the boundary cue instead of playing:
        there is nothing ahead to play, the same "can't go further" signal
        Left/Right give."""
        if not self.music_data or self.sequencer is None:
            return
        if self.is_play_metronome_running:
            # Space is the "stop everything sounding" key - a running
            # free-metronome click track is what it stops here, the same as
            # it would stop real playback.
            self.stop_play_metronome()
            return
        if self._play_run is not None:
            # A play run may be mid-count-in with nothing sounding yet, which
            # is_playing cannot see - without this, Space would start a
            # second, overlapping run underneath the count-in.
            self.stop()
            return
        if self.sequencer.is_paused:
            self.sequencer.resume()
            self.playback_state_changed.emit()
            return
        if self.sequencer.is_playing:
            self.stop()
            return

        self._start_from_cursor()

    def _start_from_cursor(self) -> None:
        """Start playback from the current cursor, honouring loop/lead-in
        settings. The single start path shared by Space (toggle_play_stop)
        and voice "play" (play_command); assumes nothing is currently
        playing, paused or mid play-run - callers apply their own guards."""
        start_index = self.music_data.active_event_index
        if self.music_data.next_visible_event_index(start_index) is None:
            self.play_boundary_cue()
            return

        if self.play_settings.loop_enabled or self.play_settings.lead_in_enabled:
            run = self._build_play_run(looping=self.play_settings.loop_enabled)
            if run is None:
                return
            self._play_run = run
            self._start_play_iteration(with_lead_in=run.settings.has_lead_in())
        else:
            self.sequencer.play_from(
                start_index, update_cursor=True, lead_offset_ms=self._lead_offset_ms
            )
            self.playback_state_changed.emit()

    def play_command(self) -> None:
        """Hands-free voice control's directional "play" (Ref 19): resumes
        if paused, starts from the cursor if stopped, no-ops if already
        playing. Unlike toggle_play_stop, never stops what's already
        running - a spoken "play" heard while music is already playing
        should not silence it, the way pressing Space a second time
        deliberately does."""
        if not self.music_data or self.sequencer is None:
            return
        self.stop_play_metronome()
        if self._play_run is not None:
            self.stop()
        if self.sequencer.is_paused:
            self.sequencer.resume()
            self.playback_state_changed.emit()
        elif not self.sequencer.is_playing:
            self._start_from_cursor()

    def pause_command(self) -> None:
        """Hands-free voice control's directional "pause" (Ref 19): pauses
        if playing, no-ops otherwise - never resumes, unlike a spoken "pause"
        heard while already paused, which should just stay paused. Body is
        identical to toggle_pause_resume today, kept as its own named method
        since the two commands mean different things even where they
        currently coincide."""
        if self.sequencer is None:
            return
        if self.sequencer.is_playing:
            self.sequencer.pause()
            if self.refresh_gate is not None:
                self.refresh_gate.flush()
            self.playback_state_changed.emit()

    def toggle_pause_resume(self) -> None:
        """Ctrl+Space (Ref 10 AC3): pauses only. Resuming is Space's job -
        having both resume collides and leaves users pressing Space twice.

        flush()es the Delay Refresh gate before announcing the pause: with a
        positive delay in effect, a pending cursor move may still be sitting
        in the gate rather than applied to the regions yet - without this,
        "pause refreshes the regions" (see _on_sequencer_step's docstring)
        would land on a stale position that hasn't caught up yet."""
        if self.sequencer is None:
            return
        if self.sequencer.is_playing:
            self.sequencer.pause()
            if self.refresh_gate is not None:
                self.refresh_gate.flush()
            self.playback_state_changed.emit()

    def revert_pause_on_move(self) -> None:
        """Called by NavigationController on every real cursor move (never
        on a boundary_hit no-op, and never for Region 3's Up/Down note
        browsing, which isn't a navigate_requested move at all).

        A paused playback resuming from where it was paused only makes
        sense if the cursor is still sitting there. Once the user has moved
        - by any means - that position is stale, so this drops straight to
        Stopped rather than leaving Space poised to jump back to the old
        paused note. Deliberately NOT the ordinary stop(): that syncs
        active_event_index from the Sequencer's own reverted position
        (Ref 10 AC5), which would stomp the navigation move that just
        landed. Silencing/resetting the Sequencer only, leaving
        active_event_index exactly where navigation put it, is what makes
        the next Space behave like an ordinary stopped-state start."""
        if self.sequencer is None or not self.sequencer.is_paused:
            return
        self.cancel_play_run()
        self.sequencer.stop()
        self.playback_state_changed.emit()

    def stop(self) -> None:
        """Stops whatever is running before anything new starts. Only a
        cursor-tracking run syncs active_event_index and the regions back
        afterwards - a looping run never moved the cursor - but the status
        field always updates.

        Cancelling the play session first is what makes Space stop a
        count-in that has not sounded a note yet."""
        # A looping run tracks the playing position in Region 3 as it runs
        # (_on_sequencer_step) but leaves the Sequencer's own update_cursor
        # False, so stopping it must put the cursor back to where the loop
        # was started from - captured before cancel_play_run() drops the run.
        looping_restore_index = None
        if self._play_run is not None and self._play_run.looping:
            looping_restore_index = self._play_run.restore_index
        self.cancel_play_run()
        self.stop_play_metronome()
        if self.refresh_gate is not None:
            self.refresh_gate.cancel()
        if self.sequencer is None:
            return
        was_tracking_cursor = self.sequencer.update_cursor
        self.sequencer.stop()
        # current_index is None on a Sequencer that has never been played
        # from - which stopping a preview during its count-in reaches, since
        # nothing has started the Sequencer yet. Syncing the cursor to it
        # would set active_event_index to None and break every later read.
        if was_tracking_cursor and self.music_data and self.sequencer.current_index is not None:
            self.music_data.active_event_index = self.sequencer.current_index
            self.cursor_moved.emit(False)
        elif looping_restore_index is not None and self.music_data:
            self.music_data.active_event_index = looping_restore_index
            self.cursor_moved.emit(False)
        else:
            self.playback_state_changed.emit()

    def phrase_end_index(self, current_measure: int, start_index: int, bars: int = 2) -> int:
        """See models/play_plan.py's phrase_end_index."""
        return play_plan.phrase_end_index(self.music_data, current_measure, start_index, bars)

    # --- play session ----------------------------------------------------

    @property
    def is_play_run_active(self) -> bool:
        """True from the first tick of the count-in until the play run stops
        - the check callers need instead of sequencer.is_playing, which is
        False during the lead-in and between loop repeats."""
        return self._play_run is not None

    def set_play_settings(self, settings: PlaySettings) -> None:
        """Applied to the NEXT play run: a running session keeps its own
        snapshot, so accepting the dialog can't change what a loop is doing
        half way through."""
        self.play_settings = settings.copy()

    def adjust_loop_length_bars(self, delta: int) -> None:
        """Alt+PageUp/PageDown in the Note region: lengthen/shorten the loop
        window by one bar per press. Alt avoids the native PageUp/PageDown
        paging QListWidget already gives Region 3 - the same reason Ctrl is
        used for measure-at-a-time Left/Right there.

        Applies to the NEXT play run, exactly like the dialog's OK - a
        running loop keeps its own already-started snapshot. Clamped to
        [MIN_LOOP_LENGTH_BARS, MAX_LOOP_LENGTH_BARS] by PlaySettings."""
        self.play_settings = self.play_settings.with_loop_length_bars(
            self.play_settings.loop_length_bars + delta
        )
        self.status_text_changed.emit()

    def set_loop_length_bars(self, bars: int) -> None:
        """Typed Ctrl+Enter buffer / the voice command "loop length N" (Ref
        19) - sets the loop length directly, unlike adjust_loop_length_bars'
        relative +/-1 nudge. Clamped by PlaySettings itself, same as every
        other entry point (the dialog, Alt+PageUp/PageDown). Stored on the
        score, so it is saved with the .rsc like every other entry point."""
        self.play_settings = self.play_settings.with_loop_length_bars(bars)
        self.status_text_changed.emit()

    def cycle_play_mode(self) -> str:
        """Ctrl+L: rotate the play mode "play to end" -> "play loop once" ->
        "play loop until stopped" -> "play to end". Returns the new mode.
        Replaces the old toggle_loop (a plain loop on/off)."""
        return self.set_play_mode(self.play_settings.next_play_mode())

    def set_play_mode(self, mode: str) -> str:
        """The deterministic target for cycle_play_mode and the Play
        Settings dialog. Stored per score and refreshes the status bar; an
        unknown value coerces to "play to end" in PlaySettings.__post_init__.
        Returns the mode actually stored."""
        self.play_settings = self.play_settings.with_play_mode(mode)
        self.status_text_changed.emit()
        return self.play_settings.play_mode

    def toggle_lead_in(self) -> bool:
        """Ctrl+I. Returns the new state, like cycle_play_mode."""
        return self.set_lead_in_enabled(not self.play_settings.lead_in_enabled)

    def set_loop_enabled(self, enabled: bool) -> bool:
        """The deterministic on/off target the voice "looping on/off"
        commands still use (Ref 19). Maps onto the three-way play mode: on
        -> "play loop until stopped", off -> "play to end". Returns the
        resulting loop_enabled bool."""
        self.set_play_mode(PLAY_MODE_LOOP_FOREVER if enabled else PLAY_MODE_TO_END)
        return self.play_settings.loop_enabled

    def set_lead_in_enabled(self, enabled: bool) -> bool:
        """Counterpart of set_loop_enabled for "lead in on/off"."""
        self.play_settings = self.play_settings.with_lead_in_enabled(enabled)
        self.status_text_changed.emit()
        return self.play_settings.lead_in_enabled

    def set_loop_repeat_mode(self, mode: str) -> str:
        """"Repeat handling while looping" - how a repeat barline clipped by
        the loop window is read (see models/play_settings.py's
        LOOP_REPEAT_MODES). Per score, like loop_enabled; an unknown value
        coerces to "first" in PlaySettings.__post_init__. Returns the mode
        actually stored."""
        self.play_settings = self.play_settings.with_loop_repeat_mode(mode)
        self.status_text_changed.emit()
        return self.play_settings.loop_repeat_mode

    def cycle_loop_repeat_mode(self) -> str:
        """Ctrl+R: rotate first -> second -> alternate -> first."""
        return self.set_loop_repeat_mode(self.play_settings.next_loop_repeat_mode())

    def _build_play_run(self, looping: bool) -> Optional[PlayRun]:
        """See models/play_plan.py's build_play_run."""
        return play_plan.build_play_run(self.music_data, self.play_settings, looping)

    def _refresh_play_span(self, run: PlayRun) -> None:
        """See models/play_plan.py's refresh_play_span."""
        play_plan.refresh_play_span(self.music_data, run)

    def _loop_seed_jump_state(self, mode: str, iteration_count: int):
        """See models/play_plan.py's loop_seed_jump_state."""
        return play_plan.loop_seed_jump_state(self.music_data, mode, iteration_count)

    def _start_play_iteration(self, with_lead_in: bool) -> None:
        """Plan one iteration (models/play_plan.py's plan_iteration: the
        span at the current tempo, count-in clicks, the moment the notes
        start), then walk it with the chained timer."""
        run = self._play_run
        if run is None or not self.music_data:
            return
        play_plan.plan_iteration(self.music_data, run, with_lead_in, self._lead_offset_ms)
        if with_lead_in:
            # Nothing sounds for a whole count-in, so the status field is
            # the only sign Enter was heard at all - update it now rather
            # than at the first note.
            self.playback_state_changed.emit()
        self._advance_play()

    def _advance_play(self) -> None:
        """Fire every event due at the current position, then arm the timer
        for the next one. Events due at 0 fire synchronously, so a preview
        with no lead-in still starts sounding within the keypress that asked
        for it, exactly as it did before this feature existed."""
        run = self._play_run
        if run is None:
            return
        while run.event_index < len(run.events):
            due_ms, action = run.events[run.event_index]
            if due_ms > run.elapsed_ms:
                self._play_timer.start(due_ms - run.elapsed_ms)
                return
            run.event_index += 1
            self._fire_play_event(action)
            # A loop repeat rebuilds run.events and re-arms the timer from
            # scratch, and a stop drops the session entirely - either way
            # this walk is finished with the schedule it was reading.
            if self._play_run is not run or run.event_index == 0:
                return
        # Nothing further scheduled: a non-looping preview is now just the
        # Sequencer running to its own end, which ends the session (see
        # _on_sequencer_finished).

    def _on_play_timer(self) -> None:
        run = self._play_run
        if run is None:
            return
        run.elapsed_ms = run.events[run.event_index][0]
        self._advance_play()

    def _fire_play_event(self, action: Tuple[Any, ...]) -> None:
        run = self._play_run
        if run is None or not self.music_data:
            return
        kind = action[0]
        if kind == "count":
            self._sound_count_in_beat(action[1])
        elif kind == "play":
            run.playing = True
            if self.sequencer is not None:
                start_index, kwargs = play_plan.play_from_arguments(run, self._lead_offset_ms)
                self.sequencer.play_from(start_index, **kwargs)
            self.playback_state_changed.emit()
        elif kind == "loop":
            # Advance the iteration counter BEFORE the next iteration is
            # built, so "alternate" mode's _loop_seed_jump_state (called
            # from _start_play_iteration -> _refresh_play_span) sees the new
            # count.
            run.iteration_count += 1
            self._start_play_iteration(with_lead_in=play_plan.restart_with_lead_in(run))

    def _sound_count_in_beat(self, beat_position: float) -> None:
        """One beat of the count-in. The click always sounds during a
        lead-in (the lead-in tickbox IS "play the count-in click"; there is
        no silent-numbers-only count-in any more), independent of the Ctrl+M
        metronome toggle. The spoken beat number follows Ctrl+P - the user's
        decision: with the announcer on, hearing "three, four" is the
        clearest signal of where the downbeat lands. Muting (wishlist #7)
        silences both without changing the timing."""
        if self._muted or not self.music_data:
            return
        click, announcement = count_in_cues(self.music_data, beat_position)
        if click is not None:
            self.synth.play_click(*click)
        if announcement is not None:
            self.synth.play_word(*announcement)

    def cancel_play_run(self) -> None:
        """Drop the session and its pending schedule. Silencing and stopping
        the Sequencer stays with the callers that need it - stop() and
        attach_score both do that themselves."""
        self._play_timer.stop()
        self._play_run = None

    def _on_sequencer_step(self, index: int) -> None:
        """Ref 10 AC4: a cursor-tracking run moves active_event_index and
        refreshes the regions as it goes - though WHEN that actually lands
        is now the Delay Refresh gate's call (controllers/
        refresh_delay_controller.py), not this method's: it only hands the
        index off via playback_cursor_stepped, which MainWindow routes into
        the gate. That is what makes "pause refreshes the regions" true for
        free (see toggle_pause_resume/pause_command's flush()) - the gate
        already has the live position throughout, not just at the moment of
        pausing.

        A looping run also tracks here even though the Sequencer's own
        update_cursor is False for it (so the Sequencer's stop/finish
        reversion can't move the cursor): the Note region should follow the
        loop just as it follows a plain lead-in run. stop() puts the cursor
        back to the loop's start (run.restore_index) afterwards."""
        if self.sequencer is None or not self.music_data:
            return
        looping_run = self._play_run is not None and self._play_run.looping
        if not self.sequencer.update_cursor and not looping_run:
            return
        self.playback_cursor_stepped.emit(index, False)

    def _on_sequencer_finished(self) -> None:
        """A run ending on its own flips is_playing without anyone calling
        stop(). The Sequencer reverts to the original start position when
        that happens (AC5's "stopping reverts" applies to reaching the end
        too - the user's decision), so a cursor-tracking run must sync the
        regions to that reverted position exactly as stop() does, rather
        than leaving them on the last note.

        A non-looping play run (lead-in only) AND a "loop once" run both end
        for good here. A "loop until stopped" run does NOT end - it restarts
        the next iteration off THIS signal (plus loop_tail_pad_ms), which is
        the whole point: `finished` fires only once every chained Sequencer
        step has actually run and the last note's ring-out has been waited
        out, so any accumulated per-step timer drift is already absorbed and
        the restart can't land early and clip the last note."""
        run = self._play_run
        # "loop once" (looping window, but loop_forever False) terminates
        # like a lead-in run - and, having tracked the Note region through
        # the single pass with update_cursor False, it restores the cursor
        # to where the loop started, exactly as stop() does for a stopped
        # "loop until stopped" run.
        ends_now = run is not None and play_plan.ends_when_notes_finish(run)
        loop_once_restore = (
            run.restore_index if (ends_now and run is not None and run.looping) else None
        )
        if ends_now:
            self.cancel_play_run()
        if self.sequencer.update_cursor and self.music_data:
            self.music_data.active_event_index = self.sequencer.current_index
            self.cursor_moved.emit(False)
        elif loop_once_restore is not None and self.music_data:
            self.music_data.active_event_index = loop_once_restore
            self.cursor_moved.emit(False)
        elif run is not None and run.looping and not ends_now and self.music_data:
            # "loop until stopped", between iterations: snap the Note region
            # back to the loop's start so it matches what the next iteration
            # is about to sound rather than sitting on the last note through
            # the bar-line gap, then arm the restart. loop_tail_pad_ms is 0
            # in the common case, so _advance_play fires ("loop",)
            # synchronously and the next iteration starts right here.
            self.music_data.active_event_index = run.start_index
            self.cursor_moved.emit(False)
            self.playback_state_changed.emit()
            # Arm the restart through _play_timer (never synchronously from
            # inside this `finished` slot): _on_play_timer -> _advance_play
            # fires the ("loop",) event, which rebuilds the next iteration.
            # A 0ms pad still defers to the next event-loop turn, keeping the
            # Sequencer out of a re-entrant play_from.
            run.events = play_plan.loop_restart_events(run)
            run.event_index = 0
            run.elapsed_ms = 0
            self._play_timer.start(max(0, run.loop_tail_pad_ms))
            return
        self.playback_state_changed.emit()

    # --- tempo -------------------------------------------------------

    def tempo_faster(self) -> None:
        """F (Ref 12 AC3): +10 on the absolute playback tempo (in
        time-signature-denominator beats), clamped to the 5-300 bounds.
        Does not move the timeline or re-audition."""
        if not self.music_data:
            return
        self.music_data.nudge_playback_tempo(10)
        self.status_text_changed.emit()

    def tempo_slower(self) -> None:
        """S (Ref 12 AC3): -10 on the absolute playback tempo."""
        if not self.music_data:
            return
        self.music_data.nudge_playback_tempo(-10)
        self.status_text_changed.emit()

    def tempo_reset(self) -> None:
        """D (Ref 12 AC4): reset playback tempo to the score's own tempo."""
        if not self.music_data:
            return
        self.music_data.reset_playback_tempo()
        self.status_text_changed.emit()

    def set_playback_tempo(self, display_bpm: float) -> None:
        """The Play Settings dialog's absolute tempo field. display_bpm is
        in the time-signature denominator beat at the cursor; MusicData
        clamps and converts to its stored quarter-note BPM."""
        if not self.music_data:
            return
        self.music_data.set_playback_tempo_display_bpm(display_bpm)
        self.status_text_changed.emit()

    # --- toggles -----------------------------------------------------

    def toggle_metronome(self) -> bool:
        """Ctrl+M (Ref 14). Returns the new state so the caller can keep the
        menu action checked in sync."""
        if not self.music_data:
            return False
        self.music_data.toggle_metronome()
        self.status_text_changed.emit()
        return self.music_data.metronome_enabled

    def toggle_position_announcer(self) -> bool:
        """Ctrl+P (Ref 28): mirrors toggle_metronome, but needs no timeline
        rebuild (see MusicData.position_announcer_enabled)."""
        if not self.music_data:
            return False
        self.music_data.toggle_position_announcer()
        self.status_text_changed.emit()
        return self.music_data.position_announcer_enabled

    def toggle_bar_line_indicator(self) -> bool:
        """Ctrl+B: mirrors toggle_position_announcer - per-score (saved in
        the .rsc), needs no timeline rebuild. Returns the new state so the
        caller can keep the menu action checked in sync and speak it aloud."""
        if not self.music_data:
            return False
        self.music_data.toggle_bar_line_indicator()
        return self.music_data.bar_line_indicator_enabled

    def play_barline_indicator(
        self, before_measure: Optional[int] = None, after_measure: Optional[int] = None
    ) -> None:
        """Options > Bar Line Indicator: a beep (or, per
        PerformanceMarkingsStrategy.md section 10, a short pattern of them)
        fired when a plain Left/Right step (arrow key or the "forward"/
        "back" voice command) crosses a bar line, so a screen-reader user
        hears bar boundaries - and what kind of barline they are - while
        arrowing through notes.

        before_measure/after_measure (NavigationController.barline_crossed)
        identify WHICH barline was crossed, so a repeat/double/heavy/tick
        barline sounds its own pattern (_play_barline_pattern) instead of
        the plain beep below. Only the plain beep is suppressed while the
        Ctrl+M metronome is on - it already accents beat 1 of every bar, so
        a second beep at the same instant there is just noise; the section
        10 patterns sound regardless, since the metronome tells you about
        beats and nothing about barline meaning. Independent of the position
        announcer, which stays audible alongside either.

        before_measure/after_measure are normalised to (min, max) before
        pattern_for_crossing looks them up - a barline is the same barline
        whichever direction it is crossed from, so Left across a repeat end
        must sound the same pattern as Right did. That decision is
        audio/navigation_cues.barline_indicator_events, shared with the web.

        Sounds AFTER the destination note's own audition, never before: both
        the plain beep and a pattern are on BARLINE_PATTERN_CHANNEL, which
        stop_all_notes() releases, and the note audition's retrigger=True
        calls stop_all_notes() - firing either first would have it cut off
        almost immediately (the same ordering constraint as the Region 5
        change cue and the Find wrap boundary cue). barline_crossed is
        emitted after position_changed for exactly this reason, so nothing
        extra is needed here."""
        if not self.music_data or self._muted:
            return
        # The first step fires right away (preserving the audition-then-cue
        # ordering above); any later ones go through play_event_sequence.
        self.play_event_sequence(
            barline_indicator_events(self.music_data, before_measure, after_measure)
        )

    def play_event_sequence(self, events) -> None:
        """Sounds one or more (channel, bank, program, pitch, velocity)
        steps STEP_MS apart via SynthEngine.play_click - shared by the
        barline patterns above and Help > Sound Icon Dictionary's Play
        button (widgets/sound_icon_dictionary_dialog.py), so a demo play
        sounds exactly like the real thing. The first step fires
        immediately; each later step is scheduled via QTimer.singleShot
        rather than a persistent QTimer - a sequence is short and
        self-contained, so there is nothing to cancel between plays."""
        for i, event in enumerate(events):
            if i == 0:
                self.synth.play_click(*event)
            else:
                QTimer.singleShot(i * STEP_MS, lambda e=event: self.synth.play_click(*e))

    # --- play metronome (Alt+Space) --------------------------------------

    @property
    def is_play_metronome_running(self) -> bool:
        return self._play_metronome_timer.isActive()

    def toggle_play_metronome(self) -> bool:
        """Ctrl+Alt+Space: start/stop a free-running metronome click. It
        sounds at the current playback tempo (F/S/D adjustments included)
        and the time signature at the cursor, never moves the timeline, and
        is separate from the Ctrl+M score metronome. Returns the new on/off
        state.

        Refused while playback is going (playing, paused or counting in):
        it is a quick way to get a click on its own, and a click with the
        music is Ctrl+M's job (the user's decision, 2026-10-14)."""
        if self.is_play_metronome_running:
            self.stop_play_metronome()
            return False
        if not self.music_data or self.is_playback_active:
            return False
        self._play_metronome_beat = 1
        self._sound_play_metronome_beat()
        return True

    def stop_play_metronome(self) -> None:
        self._play_metronome_timer.stop()

    def _sound_play_metronome_beat(self) -> None:
        """Sound the current beat's click and arm the timer for the next.
        Tempo and time signature are re-read every beat, so a tempo change
        or a cursor move to a differently-metred bar is picked up on the
        next click rather than needing a restart."""
        if not self.music_data:
            self._play_metronome_timer.stop()
            return
        click, self._play_metronome_beat, beat_ms = free_metronome_beat(
            self.music_data, self._play_metronome_beat
        )
        if not self._muted and click is not None:
            self.synth.play_click(*click)
        self._play_metronome_timer.start(beat_ms)

    # --- sounding ----------------------------------------------------

    def play_boundary_cue(self) -> None:
        """Sounds INSTEAD of moving, when a navigation key would go past a
        boundary of the active timeline (Ref 2 AC4/Ref 3 AC4)."""
        if self._muted:
            return
        self.synth.play_boundary_cue(*boundary_cue_event())

    def audition_selection(
        self, selected_indices: List[int], with_position_cues: bool = True
    ) -> None:
        """Sound the given Region 3 rows, plus the click and spoken position
        if they are on. Indices are passed in rather than read off the
        widget, so this stays widget-free.

        `with_position_cues=False` sounds only the notes: an Up/Down move
        within the current slice (e.g. stepping through a chord's notes)
        stays on the same timeline position and beat, so re-firing the
        metronome click and the spoken beat position there is just noise -
        those cues belong to real timeline movement (arrow / Ctrl+arrow /
        Alt+arrow / go-to-bar), which always passes the default True."""
        if not self.music_data or self._muted:
            return

        note_indices = self.music_data.note_indices_from_selection(selected_indices)
        events = self.music_data.get_playback_events_for_indices(note_indices)
        grace_events = self.music_data.get_grace_note_events_for_indices(note_indices)

        # sound_events (audio/strum_schedule.py) routes a selection with a
        # MusicXML grace note through play_chord_with_grace, else falls
        # straight through to the unchanged play_chord path used by every
        # format (UG chords included - per-chord strumming was removed) -
        # each group still carries its own duration, so no slice-wide
        # duration_ms is needed here.
        sound_events(self.synth, self.music_data, events, retrigger=True, grace_events=grace_events)

        if not with_position_cues:
            return

        # Ref 14 AC3 / Ref 28 AC1/AC2: both fire even with no events at all
        # (a metronome-only beat marker), which is why they aren't folded
        # into `if events`, and independently of each other.
        click, word = position_cues(self.music_data)
        if click is not None:
            self.synth.play_click(*click)
        if word is not None:
            self.synth.play_word(*word)

    # --- status text -------------------------------------------------

    def status_fields(self) -> List[str]:
        """The three status-bar fields describing playback state, appended
        after MusicData's own position/key/time/tempo fields."""
        return [
            self.playback_status_text(),
            self.metronome_status_text(),
            self.position_announcer_status_text(),
            self.loop_length_status_text(),
        ]

    def playback_status_text(self) -> str:
        """Playing/Paused/Stopped from the Sequencer - deliberately not a
        MusicData concern, describing UI state rather than the score.

        A play run reports its own phase first: during the count-in nothing
        is sounding yet and the Sequencer would say "Stopped", which reads
        as "Space did nothing". Looping is called out because it is the one
        state that will not end on its own."""
        return announcements.playback_status(
            self._play_run,
            paused=self.sequencer is not None and self.sequencer.is_paused,
            playing=self.sequencer is not None and self.sequencer.is_playing,
        )

    def metronome_status_text(self) -> str:
        """Ref 14: On/Off, since there is otherwise no way to check the
        metronome without listening for a click."""
        return announcements.metronome_status(bool(self.music_data and self.music_data.metronome_enabled))

    def position_announcer_status_text(self) -> str:
        """Ref 28: same discoverability reasoning as the metronome field."""
        return announcements.position_announcer_status(
            bool(self.music_data and self.music_data.position_announcer_enabled)
        )

    def loop_length_status_text(self) -> str:
        """Alt+PageUp/PageDown (adjust_loop_length_bars) and the typed
        Ctrl+Enter buffer have no visible control to read the current value
        off, unlike a spin box in the dialog - so the count is shown here
        the same way the metronome/announcer toggles are."""
        uk_terms = self.session.uk_terms if self.session else True  # "bar"
        return announcements.loop_length_status(self.play_settings.loop_length_bars, uk_terms)
