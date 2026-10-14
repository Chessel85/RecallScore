# tests/manual/playback_fingerprint.py
"""Fingerprint of what the desktop playback path SCHEDULES, across the whole
score corpus - the acceptance gate for moving the play plan out of
PlaybackController (RSBV task 4.1, models/play_plan.py).

For each score it runs a fixed set of play scenarios (play to end with and
without a lead-in, loop once, loop until stopped over several iterations,
each loop repeat mode, a pickup start, a tempo change, a negative Delay
Refresh offset) through the real PlaybackController and Sequencer, driven
by a virtual clock instead of QTimer. It records the resolved play run,
every count-in click, every play_from call and its arguments, every
Sequencer step with its virtual time, and every timer interval armed.

    python tests/manual/playback_fingerprint.py before.txt
    python tests/manual/playback_fingerprint.py after.txt --check before.txt

See README.md in this folder for the baseline workflow.
"""
from _corpus import prepare_environment, render, run

prepare_environment()

# Steps recorded per scenario: enough for several loop iterations of a
# few bars, without walking a whole long score note by note.
STEP_CAP = 160

SCENARIOS = [
    # (name, start ("first" | "second_bar" | "last_bar"), settings kwargs,
    #  tempo_bpm override or None, delay_ms for Delay Refresh)
    ("plain_to_end", "first", dict(), None, 0),
    ("lead_in_bar_to_end", "first", dict(lead_in_enabled=True, lead_in_bars=1), None, 0),
    ("lead_in_beats_mid", "second_bar", dict(lead_in_enabled=True, lead_in_bars=0, lead_in_beats=2), None, 0),
    ("loop1_first", "first", dict(play_mode="loop_forever", loop_length_bars=1), None, 0),
    ("loop2_lead_each", "second_bar",
     dict(play_mode="loop_forever", loop_length_bars=2, lead_in_enabled=True,
          lead_in_bars=1, loop_lead_in=True), None, 0),
    ("loop_once4_lead", "first",
     dict(play_mode="loop_once", loop_length_bars=4, lead_in_enabled=True, lead_in_bars=1), None, 0),
    ("loop3_second", "first",
     dict(play_mode="loop_forever", loop_length_bars=3, loop_repeat_mode="second"), None, 0),
    ("loop4_alternate", "first",
     dict(play_mode="loop_forever", loop_length_bars=4, loop_repeat_mode="alternate"), None, 0),
    ("loop2_last_bar", "last_bar",
     dict(play_mode="loop_forever", loop_length_bars=2, lead_in_enabled=True,
          lead_in_bars=1, lead_in_beats=1), None, 0),
    ("loop2_fast", "second_bar", dict(play_mode="loop_forever", loop_length_bars=2), 200, 0),
    ("loop2_negative_delay", "first",
     dict(play_mode="loop_forever", loop_length_bars=2, lead_in_enabled=True, lead_in_bars=1), None, -150),
    ("to_end_negative_delay", "first", dict(lead_in_enabled=True, lead_in_bars=1), None, -150),
]


class Clock:
    def __init__(self):
        self.now = 0
        self.timers = []
        self.seq = 0

    def next_due(self):
        due = [t for t in self.timers if t.running]
        if not due:
            return None
        return min(due, key=lambda t: (t.due, t.order))


class ClockTimer:
    """QTimer stand-in on a shared virtual clock: start(ms) arms it at
    now + ms, and the driver fires whichever armed timer is due first."""

    def __init__(self, clock, name, log):
        self.clock = clock
        self.name = name
        self.log = log
        self.running = False
        self.due = 0
        self.order = 0
        self._callback = None
        self.timeout = self
        clock.timers.append(self)

    def setSingleShot(self, value):
        pass

    def setTimerType(self, value):
        pass

    def connect(self, callback):
        self._callback = callback

    def start(self, ms):
        self.log.append(f"  t={self.clock.now} arm {self.name} {ms}")
        self.running = True
        self.due = self.clock.now + ms
        self.clock.seq += 1
        self.order = self.clock.seq

    def stop(self):
        self.running = False

    def isActive(self):
        return self.running

    def fire(self):
        self.running = False
        self.clock.now = max(self.clock.now, self.due)
        self._callback()


class _Session:
    def __init__(self, music_data, synth):
        self.music_data = music_data
        self.synth = synth


class _Gate:
    def __init__(self, delay_ms):
        from models.refresh_settings import RefreshSettings

        self.settings = RefreshSettings(delay_ms=delay_ms)

    def flush(self):
        pass

    def cancel(self):
        pass


def _start_index(md, where):
    measures = md.measure_numbers()
    if where == "first" or len(measures) < 2:
        return md.active_event_index
    measure = measures[1] if where == "second_bar" else measures[-1]
    first = md.first_visible_event_index_of_measure(measure)
    if first is None:
        return md.active_event_index
    nxt = md.next_visible_event_index(first)
    # The bar's second note, so a looping run's snap to the bar line shows.
    if nxt is not None and md.timeline_slices[nxt].measure == measure:
        return nxt
    return first


def _scenario(path, name, where, settings_kwargs, tempo, delay_ms, out):
    from audio.sequencer import Sequencer
    from controllers.playback_controller import PlaybackController
    from models.music_data import MusicData
    from models.play_settings import PlaySettings
    from tests.support.null_synth import NullSynth

    md = MusicData(file_path=path)
    if not md.timeline_slices:
        out.append(f"-- {name}: empty")
        return
    md.active_event_index = _start_index(md, where)
    if tempo is not None:
        md.playback_tempo_bpm = tempo
    md.metronome_enabled = True
    md.position_announcer_enabled = True

    log = []
    clock = Clock()
    synth = NullSynth()
    pc = PlaybackController(_Session(md, synth), timer=ClockTimer(clock, "play", log))
    if delay_ms:
        pc.refresh_gate = _Gate(delay_ms)
    seq = Sequencer(
        md, synth,
        timer=ClockTimer(clock, "seq", log),
        lead_timer=ClockTimer(clock, "lead", log),
        parent=pc,
    )
    pc.sequencer = seq
    seq.step_played.connect(pc._on_sequencer_step)
    seq.finished.connect(pc._on_sequencer_finished)

    real_play_from = seq.play_from

    def play_from(start_index, **kwargs):
        seed = kwargs.get("initial_jump_state")
        shown = dict(kwargs)
        if seed is not None:
            shown["initial_jump_state"] = render(seed)
        log.append(f"  t={clock.now} play_from {start_index} {render(shown)}")
        real_play_from(start_index, **kwargs)

    seq.play_from = play_from
    seq.step_played.connect(lambda i: log.append(f"  t={clock.now} step {i}"))
    seq.finished.connect(lambda: log.append(f"  t={clock.now} finished"))

    real_click = synth.play_click
    real_word = synth.play_word

    def click(*a):
        log.append(f"  t={clock.now} click {a[3]}")
        real_click(*a)

    def word(*a):
        log.append(f"  t={clock.now} word {a[3]}")
        real_word(*a)

    synth.play_click = click
    synth.play_word = word

    pc.set_play_settings(PlaySettings(**settings_kwargs))
    pc.toggle_play_stop()

    out.append(f"-- {name} cursor={md.active_event_index}")
    run_ = pc._play_run
    if run_ is not None:
        out.append(
            f"  run start={run_.start_index} end={run_.end_index} "
            f"endq={render(run_.end_quarters)} pickup={run_.is_pickup} "
            f"offset={run_.offset_ms} iter={run_.iteration_ms} pad={run_.loop_tail_pad_ms} "
            f"repeats={run_.respect_repeats} restore={run_.restore_index}"
        )
        out.append(f"  events={render(run_.events)}")
    steps = 0
    while steps < STEP_CAP:
        timer = clock.next_due()
        if timer is None:
            break
        timer.fire()
        steps += 1
        if pc._play_run is not None and pc._play_run.iteration_count >= 4:
            break
    out.extend(log)
    out.append(
        f"  end active={md.active_event_index} run={pc.is_play_run_active} "
        f"playing={seq.is_playing}"
    )
    pc.stop()
    out.append(f"  after_stop active={md.active_event_index}")


def dump_one(path, out):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    for name, where, kwargs, tempo, delay in SCENARIOS:
        try:
            _scenario(path, name, where, kwargs, tempo, delay, out)
        except Exception as e:
            out.append(f"-- {name} FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    raise SystemExit(run(__doc__.splitlines()[0], dump_one))
