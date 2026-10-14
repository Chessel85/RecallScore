# models/play_plan.py
"""The play plan: where a play run starts and ends, what each iteration of
it schedules (count-in clicks, the moment the notes start), how a loop
repeat is seeded, and the step-to-step timing of the notes themselves.

Qt-free and timer-free, so the desktop and the web version run one copy of
the logic (RSBV task 4.1). The desktop's PlaybackController and Sequencer
walk what this hands back with QTimers; the web's scheduler walks the same
plan on the AudioContext clock. Nothing here sounds anything: a step is an
index, and what sounds at it (notes, grace notes, click, spoken beat) stays
with the caller's shared event builders.

Moved, not rewritten, out of controllers/playback_controller.py
(_PlayRun, _build_play_run, _refresh_play_span, _loop_seed_jump_state,
phrase_end_index and the schedule half of _start_play_iteration) and
audio/sequencer.py (the jump-aware stepping, the measure budget and
_delay_ms_to). The comments that explain each live-tested fix came with
the code. Gate: tests/manual/playback_fingerprint.py.
"""
from dataclasses import dataclass, field
from typing import Any, List, NamedTuple, Optional, Tuple

from models.lead_in import build_lead_in_schedule
from models.play_settings import PlaySettings
from models.playback_jump_state import PlaybackJumpState

# (offset_ms within the iteration, action) - action is ("count", beat
# position) for a count-in click, ("play",) for the moment the notes start,
# or ("loop",) for a loop restart.
PlanEvent = Tuple[int, Tuple[Any, ...]]


@dataclass
class PlayRun:
    """One play session that needs more than a bare Sequencer run - i.e.
    one with a lead-in count-in and/or looping. The resolved span, the
    settings snapshot taken when it started, and the schedule of the
    iteration currently running.

    The session outlives the Sequencer run inside it - it also covers the
    lead-in before any note sounds and the wait to the bar line before a
    loop repeats, neither of which the Sequencer knows about. That is why
    the "stop what's running" test is is_play_run_active and not
    sequencer.is_playing.
    """

    settings: PlaySettings
    # True for a looping run (fixed N-bar window, cursor frozen); False for
    # a lead-in-then-play-to-the-end run (cursor follows, ends on its own).
    looping: bool
    start_index: int
    # None for a non-looping run - it plays to the end of the score.
    end_index: Optional[int]
    end_quarters: float
    # True when start_index falls in a pickup bar (Ref 17): a count-in ahead
    # of it must keep counting past the requested lead-in to also complete
    # the pickup's own bar - see iteration_events.
    is_pickup: bool
    # Silence between the bar line and the first note, for a previewed bar
    # that opens with a rest - kept so a repeat stays in time rather than
    # sliding forward by that gap. 0 for a pickup (its real content starts
    # at the piece's own start, not after some silence) - used as-is for a
    # LOOP repeat with no lead-in of its own; a lead-in ahead of a pickup
    # computes its own play_gap_ms instead (iteration_events).
    offset_ms: int
    # Bar line to bar line: what one loop iteration lasts. Still computed
    # (F/S/D tempo tracking, tests), but a "loop until stopped" run no
    # longer schedules its restart off this as a standalone wall-clock
    # timer - see loop_tail_pad_ms and PlaybackController.
    # _on_sequencer_finished.
    iteration_ms: int
    # "loop until stopped" only: the restart is driven by the Sequencer's
    # own `finished` signal (which fires only once every chained step has
    # actually run and the last note's ring-out has been waited out), NOT
    # by a monolithic timer armed a whole iteration ahead - that timer
    # raced the Sequencer's chained per-step timers and, at a slow tempo
    # with many steps (heavy per-step region-refresh work between each
    # timer re-arm), drifted early enough to clip the last note (reported,
    # etude 2 bar 3, loop length 3, 44 bpm). loop_tail_pad_ms is the only
    # wait left: the gap between that last note's ring-out and the bar line
    # when the iteration's final bar ends in rests. 0 when the last note
    # itself rings to (or past) the bar line, so the restart is immediate.
    loop_tail_pad_ms: int = 0
    # Looping only: the active_event_index to restore when the run stops.
    # A looping run tracks the playing position in Region 3 as it goes, the
    # same as a non-looping run - but the Sequencer's own update_cursor is
    # left False, so its stop/finish reversion never touches the cursor;
    # the controller moves it per step and puts it back here on stop().
    restore_index: Optional[int] = None
    # (offset_ms within the iteration, action) in time order, walked by one
    # chained single-shot timer - the same "reschedule a step at a time so
    # cancelling is one stop()" shape as audio/sequencer.py.
    events: List[PlanEvent] = field(default_factory=list)
    event_index: int = 0
    elapsed_ms: int = 0
    playing: bool = False
    # Looping on a MusicXML score that actually carries repeat barlines:
    # the iteration follows repeats/endings under a bar-count budget rather
    # than a linear end_index window (see build_play_run /
    # simulate_loop_iteration). False for every other run - MIDI/GP/UG and
    # repeat-less MusicXML keep the exact linear code path unchanged.
    respect_repeats: bool = False
    # How many times the ("loop",) restart has fired - drives "alternate"
    # mode's per-iteration seed choice (loop_seed_jump_state).
    iteration_count: int = 0
    # The seed handed to Sequencer.play_from for THIS iteration, recomputed
    # per iteration in refresh_play_span. None = a fresh first play-through.
    seed_jump_state: Optional[PlaybackJumpState] = None


def phrase_end_index(music_data, current_measure: int, start_index: int, bars: int = 2) -> int:
    """Through the end of the (bars-1)th measure after this one, or the
    last sounding event if the piece ends first - bounded so a loop
    can't run on into trailing rest-only padding, and so a loop length
    reaching past the end of the piece simply ends there."""
    last_sounding = music_data.last_sounding_event_index()
    end_index = last_sounding if last_sounding is not None else music_data.last_event_index()

    measures = music_data.measure_numbers()
    pos = measures.index(current_measure)
    bars = max(1, int(bars))
    if pos + bars < len(measures):
        measure_after_last = measures[pos + bars]
        candidate_end = music_data.first_event_index_of_measure(measure_after_last) - 1
        if candidate_end >= start_index:
            end_index = min(end_index, candidate_end)
    return end_index


def build_play_run(music_data, settings: PlaySettings, looping: bool) -> Optional[PlayRun]:
    """Resolve where the play run starts and (for a looping run) ends,
    in both index and real-time terms. Returns None when there is
    nothing to play. Takes its own copy of settings, so a running
    session keeps its snapshot whatever the dialog does later.

    A looping run snaps its start to the bar line of the cursor's
    measure and runs a fixed loop_length_bars window; a non-looping run
    (lead-in only) starts on the exact cursor and plays to the end."""
    current = music_data.get_current_slice()
    if current is None:
        return None

    settings = settings.copy()

    if not looping:
        start_index = music_data.active_event_index
        start_slice = music_data.timeline_slices[start_index]
        start_bar = music_data.bar_bounds_quarters(start_index)
        is_pickup = bool(start_bar and start_bar[0] < 0)
        run = PlayRun(
            settings=settings,
            looping=False,
            start_index=start_index,
            end_index=None,
            end_quarters=start_slice.quarters_from_start,
            is_pickup=is_pickup,
            offset_ms=0,
            iteration_ms=0,
        )
        refresh_play_span(music_data, run)
        return run

    start_index = music_data.first_visible_event_index_of_measure(current.measure)
    if start_index is None:
        return None

    end_index = phrase_end_index(music_data, current.measure, start_index, settings.loop_length_bars)

    # The loop repeats on the BAR LINE after the last looped bar, not
    # when the last note stops ringing: a bar ending in rests would
    # otherwise restart early and out of time, which is useless to play
    # along to. bar_bounds_quarters derives that from the slice itself
    # (see MusicData). A loop length running past the end of the piece
    # is already clamped by phrase_end_index, so the last bar of the
    # piece becomes the end of the loop.
    start_slice = music_data.timeline_slices[start_index]
    start_bar = music_data.bar_bounds_quarters(start_index)
    end_bar = music_data.bar_bounds_quarters(end_index)
    # A pickup bar's (Ref 17) NOTIONAL start is before the piece begins,
    # so its unclamped bar start comes back negative - that is the
    # signal is_pickup keys off. The matching clamp lives in
    # refresh_play_span, which needs it to derive offset_ms and
    # recomputes it per loop iteration.
    is_pickup = bool(start_bar and start_bar[0] < 0)
    end_quarters = end_bar[1] if end_bar else start_slice.quarters_from_start

    # Only MusicXML scores that actually carry repeat barlines take the
    # repeat-aware looped path; everything else (MIDI/GP/UG always have
    # an empty repeat_spans, as does a repeat-less MusicXML score) keeps
    # the linear end_index window verbatim, so fingerprints and every
    # existing loop stay unchanged. When respected, there is no linear
    # end_index - a backward repeat can send the iteration to a bar
    # before the window - so it is None and refresh_play_span derives
    # end_quarters/iteration_ms from simulate_loop_iteration instead.
    respect_repeats = bool(music_data.repeat_spans)

    run = PlayRun(
        settings=settings,
        looping=True,
        start_index=start_index,
        end_index=None if respect_repeats else end_index,
        end_quarters=end_quarters,
        is_pickup=is_pickup,
        offset_ms=0,
        iteration_ms=0,
        restore_index=music_data.active_event_index,
        respect_repeats=respect_repeats,
    )
    refresh_play_span(music_data, run)
    return run


def refresh_play_span(music_data, run: PlayRun) -> None:
    """(Re)computes offset_ms/iteration_ms/loop_tail_pad_ms from the
    CURRENT tempo - called both when a run is first built and at the top of
    every plan_iteration call (including a loop repeat), so an F/S/D tempo
    change made while already looping is reflected in the very next
    loop-restart's timing rather than replaying a stale span computed at
    whatever tempo was in force when play started. Reported live: speeding
    up ~40bpm while a repeat-containing passage was already looping left
    the loop-restart (and the lead-in count-in it schedules) drifting out
    of time - iteration_events' own bpm (used for the count-in clicks) was
    already re-derived per iteration, but iteration_ms/offset_ms - the
    loop-restart's own timing - were computed once and never touched again.

    A non-looping run starts on the exact cursor and has no bar-line
    gap or loop iteration of its own - the pickup count-in padding in
    iteration_events handles the one case (a pickup) where a gap after the
    count-in is still wanted."""
    if not run.looping:
        run.offset_ms = 0
        run.iteration_ms = 0
        return
    start_slice = music_data.timeline_slices[run.start_index]
    start_bar = music_data.bar_bounds_quarters(run.start_index)
    # Clamped at 0 for a pickup bar, whose NOTIONAL start is before the
    # piece begins - see is_pickup/build_play_run's own comment.
    bar_start_quarters = max(0.0, start_bar[0]) if start_bar else start_slice.quarters_from_start
    lead_quarters = max(0.0, start_slice.quarters_from_start - bar_start_quarters)
    bpm = music_data.effective_tempo_bpm(run.start_index)
    run.offset_ms = int(round(lead_quarters * 60000.0 / float(bpm)))
    if run.respect_repeats:
        # A backward repeat can send this iteration to a bar BEFORE the
        # window, so there is no linear end_index to time against;
        # simulate_loop_iteration walks the repeat-aware path under a
        # bar-count budget and returns its real elapsed span and the
        # bar line the ("loop",) restart fires on. The seed selects
        # which play-through of a clipped repeat is looped - recomputed
        # here per iteration so "alternate" gets the right length each
        # time and an F/S/D tempo change lands on the next restart.
        run.seed_jump_state = loop_seed_jump_state(
            music_data, run.settings.loop_repeat_mode, run.iteration_count
        )
        iter_indices, span_ms, end_quarters = music_data.simulate_loop_iteration(
            run.start_index, run.settings.loop_length_bars, run.seed_jump_state
        )
        run.end_quarters = end_quarters
        last_index = iter_indices[-1] if iter_indices else run.start_index
    else:
        # Jump-aware, not span_ms_to_quarters's flat walk - a repeat
        # fully inside the preview window makes the real Sequencer run
        # take longer than a naive linear walk would predict, and this
        # drives the loop-restart timing (iteration_ms), so it must know
        # about it too or a contained repeat gets truncated mid-replay.
        span_ms = music_data.playback_span_ms(run.start_index, run.end_index, run.end_quarters)
        last_measure = music_data.timeline_slices[run.end_index].measure
        last_index = music_data.last_visible_event_index_of_measure(last_measure)
        if last_index is None:
            last_index = run.end_index
    run.iteration_ms = run.offset_ms + span_ms

    # The one wait the Sequencer's own `finished` signal does NOT already
    # cover: when the iteration's last note is shorter than the run to
    # the bar line (final bar ends in rests), the loop must still restart
    # on the bar line, not when that note stops ringing. Mirrors
    # playback_event_builder._tail_ms exactly (max(bar_line, ring_out)),
    # minus the ring_out the Sequencer waits out itself - so 0 whenever
    # the last note rings to or past the bar line.
    last_slice = music_data.timeline_slices[last_index]
    bar_line_ms = int(
        max(0.0, run.end_quarters - last_slice.quarters_from_start) * 60000.0 / float(bpm)
    )
    ring_out_ms = music_data.get_ring_out_ms_for_index(last_index)
    # Delay Refresh's negative-delay half (UserPlans/DelayRefresh.md):
    # deliberately NOT padded by lead_offset_ms here. The Sequencer
    # defers the iteration's last note's audio, so at this natural
    # restart time it may still legitimately be ringing - but the fix
    # for that is play_from_arguments' stop_previous=False on the restart
    # (let it ring out on its own, same as an ordinary retrigger=False
    # advance), not delaying the restart itself. An earlier version
    # added lead_offset_ms here instead, which shifted the next
    # iteration's own internal clock late by that much, stretching its
    # first beat by lead_offset_ms at every loop seam (reported live).
    run.loop_tail_pad_ms = max(0, bar_line_ms - ring_out_ms)


def loop_seed_jump_state(music_data, mode: str, iteration_count: int) -> Optional[PlaybackJumpState]:
    """The PlaybackJumpState a looped iteration is seeded with, per the
    "Repeat handling while looping" mode (models/play_settings.py's
    LOOP_REPEAT_MODES):

      first     - None (a fresh run): the clipped repeat is taken once
                  and its first-time ending played; once a loop window
                  is long enough that the repeat's target lies inside
                  it, this reproduces normal repeat playback for free.
      second    - pre-marked as if one full pass already happened: every
                  repeat consumed, every first-time ending skipped, so
                  the iteration runs linearly through the second
                  play-through (first-time endings skipped, final
                  endings played).
      alternate - the "first" seed on an even iteration_count, the
                  "second" seed on an odd one.

    The "first-time ending" is the one whose measure range spans a
    repeat's backward barline - the exact condition
    PlaybackEventBuilder._jump_from_measure_end uses to mark an ending
    skipped when a real repeat retake happens, so a long-window "second"
    loop and a normal second pass agree on which endings vanish.
    """
    if not music_data:
        return None
    if mode == "alternate":
        mode = "first" if iteration_count % 2 == 0 else "second"
    if mode != "second":
        return None
    repeats = music_data.repeat_spans
    endings = music_data.ending_spans
    endings_to_skip = {
        j
        for rs in repeats
        for j, es in enumerate(endings)
        if es.start_measure <= rs.end_measure <= es.end_measure
    }
    return PlaybackJumpState(
        repeats_taken=set(range(len(repeats))),
        endings_to_skip=endings_to_skip,
        jump_taken=True,
    )


def iteration_events(music_data, run: PlayRun, with_lead_in: bool, lead_offset_ms: int = 0) -> List[PlanEvent]:
    """One iteration's schedule, in time order: the count-in clicks (when
    with_lead_in) and the ("play",) moment the notes start. Reads the
    run's current offset_ms, so call refresh_play_span first (plan_iteration
    does both)."""
    start_slice = music_data.timeline_slices[run.start_index]
    ts_num, ts_den = start_slice.time_sig
    # Re-derived per iteration, so an F/S/D tempo change during a loop
    # takes effect from the next repeat rather than never.
    bpm = music_data.effective_tempo_bpm(run.start_index)

    events: List[PlanEvent] = []
    lead_in_ms = 0
    # The silent gap between the last count-in click and the note
    # itself. Ordinarily that is just run.offset_ms (the bar-line-to-
    # first-note gap, 0 for a pickup - see build_play_run). A pickup
    # gets a different value here: see the pickup padding below.
    play_gap_ms = run.offset_ms
    if with_lead_in:
        lead_in_beats = run.settings.lead_in_beats
        if run.is_pickup:
            # Reported from real practice use: a pickup's own notated
            # beat position (e.g. beat 4 of a 4/4 bar) is not where the
            # requested lead-in should end - counting only "1, 2, 3, 4"
            # and landing exactly on the pickup's own beat leaves the
            # anacrusis itself uncounted. The user's ask: play the
            # requested lead-in in full, THEN keep counting through
            # whatever beats are needed to complete the anacrusis into a
            # whole bar, so the pickup sounds exactly where a real beat
            # 1 would follow - e.g. one bar of lead-in ahead of a
            # one-beat pickup in 4/4 counts "1, 2, 3, 4, 1, 2, 3", not
            # "4, 1, 2, 3". The count-in's own anchor (start_beat_position,
            # below) already lands the LAST click one beat before the
            # pickup's real notated position, so padding total_beats
            # with the pickup's own missing whole beats is all that is
            # needed - build_lead_in_schedule's backward-counting keeps
            # every click correctly numbered.
            #
            # A pickup that starts mid-beat (e.g. a beat 2.5 anacrusis -
            # 1.5 beats of real content in 4/4) leaves a fractional
            # leftover after the last WHOLE beat is counted - clicks
            # only ever land on whole beats (audio/metronome.py's
            # click_event_for_beat), so that remainder is a silent wait
            # after the count-in rather than another click.
            gap_beats = max(0.0, start_slice.beat_position - 1.0)
            whole_gap_beats = int(gap_beats + 1e-6)
            fractional_beats = max(0.0, gap_beats - whole_gap_beats)
            lead_in_beats += whole_gap_beats
            beat_ms = (4.0 / float(ts_den or 4)) * 60000.0 / bpm
            play_gap_ms = int(round(fractional_beats * beat_ms))
        clicks, lead_in_ms = build_lead_in_schedule(
            run.settings.lead_in_bars,
            lead_in_beats,
            ts_num,
            ts_den,
            bpm,
            start_beat_position=start_slice.beat_position,
        )
        events.extend((offset, ("count", beat)) for offset, beat in clicks)

    # Delay Refresh's negative-delay half (UserPlans/DelayRefresh.md):
    # the Sequencer itself defers each step's actual audio by
    # lead_offset_ms (audio/sequencer.py), so without this subtraction
    # the count-in's last click would be followed by play_gap_ms of
    # silence AND THEN another lead_offset_ms before the first note -
    # an audible double gap. Subtracting it here means the ("play",)
    # event (and so the Sequencer's own deferred audio for the first
    # step) lands exactly play_gap_ms after the count-in, same as
    # before this feature existed.
    events.append((max(0, lead_in_ms + play_gap_ms - lead_offset_ms), ("play",)))
    # No ("loop",) event is scheduled here, for EITHER loop mode. "loop
    # once" ends when the notes finish; "loop until stopped" restarts from
    # there too (loop_restart_events), anchored to the notes' real progress
    # so per-step timer drift can't accumulate into an early restart that
    # clips the last note (reported: etude 2, bar 3, loop length 3, 44 bpm).
    return sorted(events, key=lambda event: event[0])


def plan_iteration(music_data, run: PlayRun, with_lead_in: bool, lead_offset_ms: int = 0) -> None:
    """Start an iteration of the run: refresh its span at the current
    tempo, then load its schedule into run.events from the top. A count-in
    puts the run back in its lead-in phase (run.playing False), which the
    status field reports as Lead-in - true on a loop repeat too."""
    refresh_play_span(music_data, run)
    if with_lead_in:
        run.playing = False
    run.events = iteration_events(music_data, run, with_lead_in, lead_offset_ms)
    run.event_index = 0
    run.elapsed_ms = 0


def restart_with_lead_in(run: PlayRun) -> bool:
    """Whether a loop repeat counts in again ("lead-in on every repeat")."""
    return run.settings.loop_lead_in and run.settings.has_lead_in()


def ends_when_notes_finish(run: PlayRun) -> bool:
    """A lead-in-only run and a "loop once" run end for good when their
    notes finish; a "loop until stopped" run restarts instead."""
    return not run.looping or not run.settings.loop_forever


def loop_restart_events(run: PlayRun) -> List[PlanEvent]:
    """"Loop until stopped", once an iteration's notes have finished: the
    restart, after the wait to the bar line (0 when the last note rang to
    it). Advance run.iteration_count when it fires, BEFORE planning the
    next iteration, so "alternate" mode's seed sees the new count."""
    return [(max(0, run.loop_tail_pad_ms), ("loop",))]


def play_from_arguments(run: PlayRun, lead_offset_ms: int = 0) -> Tuple[int, dict]:
    """(start_index, keyword arguments) for Sequencer.play_from when the
    run's ("play",) event fires - the same window and stepping rules the
    web scheduler hands to StepWalker."""
    # A "loop until stopped" restart past the first iteration, with no
    # per-iteration lead-in of its own, is a NATURAL continuation - the
    # previous iteration's own deferred last note may legitimately still
    # be ringing at this (unpadded, natural) restart moment.
    # stop_previous=False lets it finish on its own rather than being cut
    # off, and - just as importantly - keeps THIS run's own internal clock
    # starting exactly on the natural schedule, so its first beat isn't
    # stretched by lead_offset_ms (both reported live; see play_from's own
    # docstring and loop_tail_pad_ms's).
    continuous_restart = (
        run.looping
        and run.iteration_count > 0
        and not restart_with_lead_in(run)
    )
    if run.looping and run.respect_repeats:
        # No linear end_index - the iteration follows repeats/endings and
        # stops on a bar-count budget, and jump_lower_bound=0 lets a
        # backward repeat land before the window. The seed picks which
        # play-through of a clipped repeat this iteration loops.
        return run.start_index, dict(
            end_index=None,
            update_cursor=False,
            jump_lower_bound=0,
            initial_jump_state=run.seed_jump_state,
            measure_budget=run.settings.loop_length_bars,
            lead_offset_ms=lead_offset_ms,
            stop_previous=not continuous_restart,
        )
    if run.looping:
        return run.start_index, dict(
            end_index=run.end_index,
            update_cursor=False,
            jump_lower_bound=run.start_index,
            lead_offset_ms=lead_offset_ms,
            stop_previous=not continuous_restart,
        )
    # Lead-in only: play to the end of the score, cursor following,
    # ending on its own when the notes finish.
    return run.start_index, dict(update_cursor=True, lead_offset_ms=lead_offset_ms)


# --- note stepping -------------------------------------------------------

class NextStep(NamedTuple):
    """What follows a step that has just sounded. index None means the run
    is over: wait_ms is then the last note's ring-out, after which it has
    finished. Otherwise wait_ms is the time to the next step, and retrigger
    says whether that step was reached by a jump (see StepWalker.advance)."""

    index: Optional[int]
    wait_ms: int
    retrigger: bool


class StepWalker:
    """The per-run stepping state of a Sequencer run: repeat/ending/Segno/
    Coda/D.C./D.S./Fine progress (MusicData.next_playback_index), the
    optional linear end_index and jump lower bound, and the looped
    respect-repeats bar budget. advance() answers "what comes after this
    step, and when" from the CURRENT tempo, so a tempo change takes effect
    on the very next step and nothing is precomputed.

    The caller keeps the index it is on and passes it in, rather than the
    walker owning it: the desktop's resume re-sounds the paused step and
    asks again from there."""

    def __init__(
        self,
        music_data,
        start_index: int,
        end_index: Optional[int] = None,
        jump_lower_bound: int = 0,
        initial_jump_state: Optional[PlaybackJumpState] = None,
        measure_budget: Optional[int] = None,
    ):
        self.music_data = music_data
        self.end_index = end_index
        self.jump_lower_bound = jump_lower_bound
        # initial_jump_state SEEDS the run's repeat/ending progress (a COPY
        # is taken, so the caller's template - the loop's per-iteration
        # seed - is never mutated).
        self.jump_state = (
            initial_jump_state.copy() if initial_jump_state is not None else PlaybackJumpState()
        )
        # Looping only (the respect-repeats path): stop the run once it has
        # entered this many DISTINCT bars, rather than at a fixed linear
        # end_index - the only way to express "play bars 7, 8 then jump
        # back to 1, 2, 3, 4", where bars 7-8 sit after bar 4 in index
        # order. None for every non-looping run and for a looping run on a
        # score with no repeat barlines (which keeps the linear end_index
        # path). A backward jump into an earlier bar counts as a new bar
        # entry.
        self.measure_budget = measure_budget
        self._measures_entered = 1
        self._budget_measure = None
        if measure_budget is not None and 0 <= start_index < len(music_data.timeline_slices):
            self._budget_measure = music_data.timeline_slices[start_index].measure

    def snapshot(self) -> tuple:
        """The stepping state as it is now, for restore(): the web takes one
        before each step so a resume can carry on from the paused step even
        though its lookahead has already walked past it."""
        return (self.jump_state.copy(), self._measures_entered, self._budget_measure)

    def restore(self, snapshot: tuple) -> None:
        jump_state, self._measures_entered, self._budget_measure = snapshot
        self.jump_state = jump_state.copy()

    def advance(self, index: int) -> NextStep:
        """The step after `index`, which has just sounded."""
        md = self.music_data
        next_index = md.next_playback_index(
            index, self.jump_state, self.end_index, self.jump_lower_bound
        )
        # Whether next_index was reached by a jump (see PlaybackJumpState.
        # last_step_was_jump) rather than a natural forward advance - a jump
        # is a reposition, so the step it lands on must retrigger.
        jumped = self.jump_state.last_step_was_jump

        # Measure-budget stop (looped respect-repeats path): if the next
        # step would enter a bar this iteration hasn't been in yet and that
        # would exceed the budget, end the iteration here instead. A
        # backward jump counts as a new bar entry, which is what lets
        # "7, 8, 1, 2, 3, 4" be six bars.
        if next_index is not None and self.measure_budget is not None:
            next_measure = md.timeline_slices[next_index].measure
            if next_measure != self._budget_measure:
                if self._measures_entered + 1 > self.measure_budget:
                    next_index = None
                else:
                    self._measures_entered += 1
                    self._budget_measure = next_measure
        if next_index is None:
            return NextStep(None, md.get_ring_out_ms_for_index(index), jumped)
        return NextStep(next_index, self._delay_ms(index, next_index, jumped), jumped)

    def _delay_ms(self, index: int, next_index: int, jumped: bool) -> int:
        """Uses the tempo at the CURRENT step, not the next one: a marking
        at next_index takes effect on arrival, so the time taken to get
        there is governed by the tempo in force beforehand (Ref 12)."""
        md = self.music_data
        if jumped:
            # The departing note rings its own natural duration before the
            # jump; the raw quarters delta below has no real-time meaning
            # for a jump, which can move EITHER backward (a repeat/D.C./D.S.
            # retake, delta <= 0 - the plain formula would collapse to the
            # 1 ms floor) OR forward over unplayed content (an ending-skip/
            # To Coda redirect, delta > 0 - the plain formula would wrongly
            # compute a real-time pause for content that's never actually
            # sounding).
            #
            # get_ring_out_ms_for_index, not the slice-wide-minimum
            # get_duration_ms_for_index - reported live (bach-bourree-tab at
            # 160bpm, metronome-only): the repeat's departing note was
            # taken about half a beat early. That slice had a shorter note
            # in one voice/part alongside the real melody note's longer
            # one; the slice-wide MIN let the shorter voice's duration
            # govern the jump, silencing the melody note before ITS OWN
            # duration had actually finished - the exact "duration_ms is
            # per-group, not per-slice" bug class (see
            # get_playback_events_for_indices' own docstring).
            return md.get_ring_out_ms_for_index(index)
        current_slice = md.timeline_slices[index]
        next_slice = md.timeline_slices[next_index]
        delta_quarters = next_slice.quarters_from_start - current_slice.quarters_from_start
        bpm = md.effective_tempo_bpm(index)
        return max(1, int(delta_quarters * 60000.0 / bpm))


class StepChunk(NamedTuple):
    """A stretch of steps for a lookahead scheduler. steps holds (offset_ms
    from the chunk's first step, index, retrigger). The chunk stops at the
    first step due at or after horizon_ms, which becomes the next chunk's
    first step: next_index, sounding next_offset_ms after this chunk's
    first, with next_retrigger. next_index None means the run is over:
    the last note has rung out next_offset_ms after the chunk began."""

    steps: List[Tuple[int, int, bool]]
    next_index: Optional[int]
    next_offset_ms: int
    next_retrigger: bool


def step_chunk(walker: StepWalker, index: int, retrigger: bool, horizon_ms: int) -> StepChunk:
    """Steps from `index` (sounding at offset 0) up to horizon_ms, for the
    web's lookahead scheduler. The tempo is read as each step is planned,
    so a tempo change lands at the next chunk, never mid-plan. The first
    step is always included, so every chunk makes progress."""
    steps: List[Tuple[int, int, bool]] = []
    offset = 0
    while True:
        steps.append((offset, index, retrigger))
        nxt = walker.advance(index)
        offset += nxt.wait_ms
        if nxt.index is None:
            return StepChunk(steps, None, offset, False)
        index, retrigger = nxt.index, nxt.retrigger
        if offset >= horizon_ms:
            return StepChunk(steps, index, offset, retrigger)


# --- the whole run as one timeline (the web scheduler) ----------------------

class TimelineEntry(NamedTuple):
    """One moment of a play timeline, at_ms after playback started.

    kind "count"   a count-in beat (beat is its position)
         "step"    a note step: sound timeline slice `index`. stop means
                   silence everything first (the start of a run, play_from's
                   stop_previous); retrigger means the step was reached by a
                   jump, so its notes silence everything first (SynthEngine's
                   retrigger, which only acts when the step has notes)
         "restart" a "loop until stopped" iteration has finished: the cursor
                   goes back to `index`, the loop's start, while the next
                   iteration is planned
         "end"     the run is over; the cursor goes back to `index`
    seq numbers the entries of one timeline, for pausing."""

    at_ms: int
    kind: str
    index: Optional[int]
    beat: Optional[float]
    stop: bool
    retrigger: bool
    seq: int


class PlayTimeline:
    """A whole play run as a stream of timed entries, planned a chunk at a
    time: PlaybackController's transport sequencing (count-in, notes, loop
    restart off the notes finishing, then the bar line pad) walked on a
    virtual clock instead of QTimers, for a lookahead scheduler.

    Started the way Space starts playback from the cursor: a lead-in or a
    loop builds a PlayRun, anything else is a plain run from the cursor to
    the end. The caller checks first that there is a next note (else the
    boundary cue). The tempo is read as each entry is planned, so a change
    lands at the next chunk. No lead-in offset: the web has no Delay
    Refresh."""

    # Steps a pause can still land on; older ones are dropped.
    _SNAPSHOTS_KEPT = 256

    def __init__(self, music_data, settings: PlaySettings):
        self.music_data = music_data
        self.start_index = music_data.active_event_index
        self.run: Optional[PlayRun] = None
        self._seq = 0
        self._buffered: Optional[TimelineEntry] = None
        self._snapshots = {}
        self._walker: Optional[StepWalker] = None
        self._step_index = 0
        self._step_at = 0
        self._step_stop = True
        self._step_retrigger = False
        self._finish_at = 0
        self._event_base = 0
        self._state = "done"
        if settings.loop_enabled or settings.lead_in_enabled:
            self.run = build_play_run(music_data, settings, looping=settings.loop_enabled)
            if self.run is not None:
                plan_iteration(music_data, self.run, self.run.settings.has_lead_in())
                self._state = "events"
        else:
            self._begin_steps(self.start_index, 0, StepWalker(music_data, self.start_index), True)

    @property
    def restore_index(self) -> int:
        """Where the cursor goes when the run stops or ends (Ref 10 AC5):
        a looping run's restore_index, else where the notes started."""
        if self.run is not None and self.run.looping:
            return self.run.restore_index
        if self.run is not None:
            return self.run.start_index
        return self.start_index

    @property
    def finished(self) -> bool:
        return self._state == "done" and self._buffered is None

    def plan(self, until_ms: int) -> List[TimelineEntry]:
        """Every entry due before until_ms not handed out yet, in time
        order. The first entry at or after until_ms is held back for the
        next call."""
        out: List[TimelineEntry] = []
        while True:
            entry = self._buffered if self._buffered is not None else self._next_entry()
            self._buffered = None
            if entry is None:
                return out
            if entry.at_ms >= until_ms:
                self._buffered = entry
                return out
            out.append(entry)

    def can_pause_at(self, seq: int) -> bool:
        """Pause only once the notes are under way (the desktop's Sequencer
        is playing): `seq`, the last entry heard, must be a step."""
        return seq in self._snapshots

    def step_index_at(self, seq: int) -> int:
        """The timeline index step `seq` sounds (one can_pause_at allows)."""
        return self._snapshots[seq][0]

    def resume_from(self, seq: int) -> None:
        """Carry on from step `seq` (the one heard when paused): it sounds
        again at time 0 of a fresh timeline, as Sequencer.resume does, with
        the stepping state it had then."""
        index, snapshot = self._snapshots[seq]
        self._walker.restore(snapshot)
        self._snapshots.clear()
        self._buffered = None
        self._begin_steps(index, 0, self._walker, True)

    def _entry(self, at_ms, kind, index=None, beat=None, stop=False, retrigger=False) -> TimelineEntry:
        self._seq += 1
        return TimelineEntry(int(at_ms), kind, index, beat, stop, retrigger, self._seq)

    def _begin_steps(self, index, at_ms, walker, stop):
        self._walker = walker
        self._step_index = index
        self._step_at = at_ms
        self._step_stop = stop
        self._step_retrigger = False
        self._state = "steps"

    def _next_entry(self) -> Optional[TimelineEntry]:
        while True:
            if self._state == "events":
                entry = self._next_run_event()
            elif self._state == "steps":
                return self._next_step()
            elif self._state == "finished":
                return self._finish()
            else:
                return None
            if entry is not None:
                return entry

    def _next_run_event(self) -> Optional[TimelineEntry]:
        """The iteration's count-in clicks, then ("play",) starts the notes
        with play_from_arguments' window (the Sequencer's play_from)."""
        run = self.run
        offset, action = run.events[run.event_index]
        run.event_index += 1
        at = self._event_base + offset
        if action[0] == "count":
            return self._entry(at, "count", beat=action[1])
        run.playing = True
        start, kwargs = play_from_arguments(run)
        walker = StepWalker(
            self.music_data,
            start,
            end_index=kwargs.get("end_index"),
            jump_lower_bound=kwargs.get("jump_lower_bound", 0),
            initial_jump_state=kwargs.get("initial_jump_state"),
            measure_budget=kwargs.get("measure_budget"),
        )
        self._begin_steps(start, at, walker, kwargs.get("stop_previous", True))
        return None

    def _next_step(self) -> TimelineEntry:
        index = self._step_index
        entry = self._entry(
            self._step_at, "step", index=index, stop=self._step_stop, retrigger=self._step_retrigger
        )
        self._snapshots[entry.seq] = (index, self._walker.snapshot())
        if len(self._snapshots) > self._SNAPSHOTS_KEPT:
            del self._snapshots[next(iter(self._snapshots))]
        nxt = self._walker.advance(index)
        if nxt.index is None:
            # The last note rings out, then the run finishes.
            self._finish_at = self._step_at + nxt.wait_ms
            self._state = "finished"
        else:
            self._step_index = nxt.index
            self._step_at += nxt.wait_ms
            self._step_stop = False
            self._step_retrigger = nxt.retrigger
        return entry

    def _finish(self) -> TimelineEntry:
        run = self.run
        if run is None or ends_when_notes_finish(run):
            self._state = "done"
            return self._entry(self._finish_at, "end", index=self.restore_index)
        # "loop until stopped": the cursor goes back to the loop's start
        # while the bar line pad runs, then the next iteration (counted
        # first, so "alternate" mode's seed sees the new count).
        restart = self._entry(self._finish_at, "restart", index=run.start_index)
        pad = loop_restart_events(run)[0][0]
        run.iteration_count += 1
        plan_iteration(self.music_data, run, restart_with_lead_in(run))
        self._event_base = self._finish_at + pad
        self._state = "events"
        return restart
