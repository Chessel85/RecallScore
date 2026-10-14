# tests/models/test_play_plan.py
"""models/play_plan.py: the Qt-free play plan shared by the desktop and the
web version (RSBV 4.1). The plan is checked against what the desktop
Sequencer actually schedules, so the web's scheduler, which walks the same
plan, keeps the desktop's timing. The whole-corpus gate is
tests/manual/playback_fingerprint.py."""
from audio.sequencer import Sequencer
from models import play_plan
from models.play_settings import PlaySettings
from tests.support.fake_timer import FakeTimer


def _desktop_steps(md, null_synth, start_index, **play_from_kwargs):
    """Every (time_ms, index) the desktop Sequencer sounds, and when it
    finishes."""
    timer = FakeTimer()
    seq = Sequencer(md, null_synth, timer=timer)
    sounded = []
    finished = []
    seq.step_played.connect(lambda i: sounded.append(i))
    seq.finished.connect(lambda: finished.append(True))
    seq.play_from(start_index, **play_from_kwargs)
    while timer.running and not finished:
        timer.fire()
    times = [0]
    for ms in timer.scheduled_ms:
        times.append(times[-1] + ms)
    return list(zip(times, sounded)), times[-1]


def _plan_steps(md, start_index, horizon_ms, **walker_kwargs):
    """The same run walked chunk by chunk, as the web scheduler will."""
    walker = play_plan.StepWalker(md, start_index, **walker_kwargs)
    steps = []
    base = 0
    index, retrigger = start_index, False
    while True:
        chunk = play_plan.step_chunk(walker, index, retrigger, horizon_ms)
        steps.extend((base + offset, i) for offset, i, _ in chunk.steps)
        base += chunk.next_offset_ms
        if chunk.next_index is None:
            return steps, base
        index, retrigger = chunk.next_index, chunk.next_retrigger


def test_step_chunks_match_the_desktop_sequencer_through_repeats_and_a_dc(
    timeline, null_synth, repeat_ending_then_dc_al_coda_score
):
    md = timeline(repeat_ending_then_dc_al_coda_score)

    desktop, desktop_end = _desktop_steps(md, null_synth, 0)

    for horizon in (1, 700, 2500, 10 ** 9):
        assert _plan_steps(md, 0, horizon) == (desktop, desktop_end)


def test_step_chunks_match_the_desktop_sequencer_on_a_real_score(
    timeline, null_synth, score_bourree_full
):
    md = timeline(score_bourree_full)
    md.playback_tempo_bpm = 160

    desktop, desktop_end = _desktop_steps(md, null_synth, 0)

    assert _plan_steps(md, 0, 1000) == (desktop, desktop_end)


def test_a_budgeted_loop_iteration_matches_the_desktop_and_its_span(
    timeline, null_synth, repeat_ending_then_dc_al_coda_score
):
    """Loop length 4 from bar 1, mode "first": m1, m2, m3, then the repeat
    back to m2 - four bar entries, ending on m2's bar line (8 quarters)."""
    md = timeline(repeat_ending_then_dc_al_coda_score)
    md.active_event_index = 0
    run = play_plan.build_play_run(
        md, PlaySettings(play_mode="loop_forever", loop_length_bars=4), looping=True
    )
    start, kwargs = play_plan.play_from_arguments(run)
    assert kwargs["measure_budget"] == 4 and kwargs["end_index"] is None

    desktop, desktop_end = _desktop_steps(md, null_synth, start, **kwargs)
    walker_kwargs = {
        k: kwargs[k] for k in ("end_index", "jump_lower_bound", "initial_jump_state", "measure_budget")
    }
    planned, planned_end = _plan_steps(md, start, 1500, **walker_kwargs)

    assert (planned, planned_end) == (desktop, desktop_end)
    indices, span_ms, end_quarters = md.simulate_loop_iteration(start, 4, None)
    assert [i for _, i in planned] == indices
    assert end_quarters == run.end_quarters == 8.0
    assert run.iteration_ms == span_ms == 8000
    assert planned_end + run.loop_tail_pad_ms >= run.iteration_ms - 1


def test_lead_in_ahead_of_a_pickup_counts_through_a_whole_bar(timeline, score_bourree_full):
    md = timeline(score_bourree_full)
    md.active_event_index = 0
    run = play_plan.build_play_run(
        md,
        PlaySettings(lead_in_enabled=True, lead_in_bars=1, play_mode="loop_forever", loop_length_bars=1),
        looping=True,
    )
    assert run.is_pickup is True and run.offset_ms == 0

    play_plan.plan_iteration(md, run, with_lead_in=True)

    counts = [action[1] for _, action in run.events if action[0] == "count"]
    assert counts == [1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0]
    beat_ms = 60000.0 / md.effective_tempo_bpm(0)
    play_at = next(offset for offset, action in run.events if action[0] == "play")
    last_count = max(offset for offset, action in run.events if action[0] == "count")
    assert abs(play_at - (last_count + beat_ms)) <= 1
    assert run.playing is False


def test_a_lead_in_only_run_starts_on_the_cursor_and_follows_it(timeline, many_measures_score):
    md = timeline(many_measures_score)
    md.jump_to_measure(3)
    run = play_plan.build_play_run(md, PlaySettings(lead_in_enabled=True), looping=False)

    assert run.start_index == md.active_event_index and run.end_index is None
    assert play_plan.play_from_arguments(run, 40) == (
        run.start_index, {"update_cursor": True, "lead_offset_ms": 40}
    )
    assert play_plan.ends_when_notes_finish(run) is True


def test_a_negative_refresh_delay_pulls_the_first_note_forward_by_that_much(
    timeline, many_measures_score
):
    md = timeline(many_measures_score)
    run = play_plan.build_play_run(md, PlaySettings(lead_in_enabled=True), looping=False)

    plain = play_plan.iteration_events(md, run, True)
    offset = play_plan.iteration_events(md, run, True, lead_offset_ms=150)

    assert plain[-1] == (plain[-1][0], ("play",))
    assert offset[-1][0] == plain[-1][0] - 150
    assert offset[:-1] == plain[:-1]


def test_a_loop_until_stopped_restart_continues_without_stopping_notes(
    timeline, many_measures_score
):
    md = timeline(many_measures_score)
    md.jump_to_measure(3)
    run = play_plan.build_play_run(
        md, PlaySettings(play_mode="loop_forever", loop_length_bars=2), looping=True
    )
    assert play_plan.ends_when_notes_finish(run) is False
    assert play_plan.play_from_arguments(run)[1]["stop_previous"] is True

    run.iteration_count = 1

    assert play_plan.loop_restart_events(run) == [(run.loop_tail_pad_ms, ("loop",))]
    _, kwargs = play_plan.play_from_arguments(run)
    assert kwargs["stop_previous"] is False
    assert kwargs["jump_lower_bound"] == run.start_index


def test_a_repeat_with_a_lead_in_each_time_stops_notes_and_counts_again(
    timeline, many_measures_score
):
    md = timeline(many_measures_score)
    run = play_plan.build_play_run(
        md,
        PlaySettings(play_mode="loop_forever", lead_in_enabled=True, loop_lead_in=True),
        looping=True,
    )
    run.iteration_count = 1

    assert play_plan.restart_with_lead_in(run) is True
    assert play_plan.play_from_arguments(run)[1]["stop_previous"] is True


def test_alternate_mode_switches_the_seed_every_iteration(
    timeline, repeat_ending_then_dc_al_coda_score
):
    md = timeline(repeat_ending_then_dc_al_coda_score)

    first = play_plan.loop_seed_jump_state(md, "alternate", 0)
    second = play_plan.loop_seed_jump_state(md, "alternate", 1)

    assert first is None
    assert second == play_plan.loop_seed_jump_state(md, "second", 5)
    assert second.repeats_taken == set(range(len(md.repeat_spans)))


def test_a_loop_reaching_past_the_end_stops_at_the_last_sounding_note(
    timeline, many_measures_score
):
    md = timeline(many_measures_score)
    last_measure = md.measure_numbers()[-1]
    start = md.first_visible_event_index_of_measure(last_measure)

    assert play_plan.phrase_end_index(md, last_measure, start, bars=4) == md.last_sounding_event_index()


def test_the_walker_never_mutates_the_seed_it_was_given(
    timeline, repeat_ending_then_dc_al_coda_score
):
    md = timeline(repeat_ending_then_dc_al_coda_score)
    seed = play_plan.loop_seed_jump_state(md, "second", 0)
    before = seed.copy()

    _plan_steps(md, 0, 1000, initial_jump_state=seed, measure_budget=8)

    assert seed == before


# --- PlayTimeline: the whole run, as the web scheduler plans it -------------

import pytest  # noqa: E402

from controllers.playback_controller import PlaybackController  # noqa: E402
from models.play_plan import PlayTimeline  # noqa: E402
from tests.support.virtual_clock import VirtualClock  # noqa: E402


class _Session:
    def __init__(self, music_data, synth):
        self.music_data = music_data
        self.synth = synth


def _desktop_timeline(md, null_synth, settings, limit):
    """What the desktop does, on a virtual clock: (ms, "count", beat),
    (ms, "step", index) and (ms, "finished", None) when the notes finish."""
    clock = VirtualClock()
    pc = PlaybackController(_Session(md, null_synth), timer=clock.timer())
    seq = Sequencer(md, null_synth, timer=clock.timer(), lead_timer=clock.timer(), parent=pc)
    pc.sequencer = seq
    seq.step_played.connect(pc._on_sequencer_step)
    seq.finished.connect(pc._on_sequencer_finished)
    log = []
    count_in = pc._sound_count_in_beat
    pc._sound_count_in_beat = lambda beat: (log.append((clock.now, "count", beat)), count_in(beat))
    seq.step_played.connect(lambda i: log.append((clock.now, "step", i)))
    seq.finished.connect(lambda: log.append((clock.now, "finished", None)))
    pc.set_play_settings(settings)
    pc.toggle_play_stop()
    clock.run(5000, until=lambda: len(log) >= limit)
    pc.stop()
    return log[:limit]


def _timeline(md, settings, limit, chunk_ms=900):
    timeline = PlayTimeline(md, settings)
    out = []
    until = 0
    while len(out) < limit and not timeline.finished:
        until += chunk_ms
        for entry in timeline.plan(until):
            kind = {"count": "count", "step": "step"}.get(entry.kind, "finished")
            detail = entry.beat if kind == "count" else entry.index if kind == "step" else None
            out.append((entry.at_ms, kind, detail))
    return out[:limit]


SCENARIOS = {
    "plain": PlaySettings(),
    "lead_in_to_end": PlaySettings(lead_in_enabled=True, lead_in_bars=1, lead_in_beats=1),
    "loop2_lead_in_each": PlaySettings(
        play_mode="loop_forever", loop_length_bars=2, lead_in_enabled=True, loop_lead_in=True
    ),
    "loop1": PlaySettings(play_mode="loop_forever", loop_length_bars=1),
    "loop_once3": PlaySettings(play_mode="loop_once", loop_length_bars=3, lead_in_enabled=True),
    "loop4_alternate": PlaySettings(play_mode="loop_forever", loop_length_bars=4, loop_repeat_mode="alternate"),
    "loop3_second": PlaySettings(play_mode="loop_forever", loop_length_bars=3, loop_repeat_mode="second"),
}


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
@pytest.mark.parametrize(
    "score, measure",
    [
        ("many_measures_score", 3),
        ("repeat_ending_then_dc_al_coda_score", None),
        ("score_bourree_full", None),
        ("score_bourree_full", 9),
    ],
)
def test_the_timeline_matches_the_desktop(timeline, null_synth, request, score, measure, scenario):
    md = timeline(request.getfixturevalue(score))
    if measure is not None:
        assert md.jump_to_measure(measure)
    md.metronome_enabled = True
    settings = SCENARIOS[scenario]

    desktop = _desktop_timeline(md, null_synth, settings, limit=120)
    md.active_event_index = 0 if measure is None else md.first_visible_event_index_of_measure(measure)
    if measure is not None:
        md.jump_to_measure(measure)
    planned = _timeline(md, settings, limit=len(desktop))

    assert planned == desktop


def test_a_resume_sounds_the_paused_step_again_and_carries_on(
    timeline, repeat_ending_then_dc_al_coda_score
):
    md = timeline(repeat_ending_then_dc_al_coda_score)
    whole = [e for e in PlayTimeline(md, PlaySettings()).plan(10 ** 9) if e.kind == "step"]

    paused = PlayTimeline(md, PlaySettings())
    heard = [e for e in paused.plan(10 ** 9) if e.kind == "step"]
    at = heard[4]
    assert paused.can_pause_at(at.seq)
    paused.resume_from(at.seq)
    after = [e for e in paused.plan(10 ** 9) if e.kind == "step"]

    assert after[0].at_ms == 0 and after[0].stop is True and after[0].index == at.index
    assert [e.index for e in after] == [e.index for e in whole[4:]]
    assert [e.at_ms - after[0].at_ms for e in after] == [e.at_ms - whole[4].at_ms for e in whole[4:]]


def test_the_timeline_ends_by_putting_the_cursor_back(timeline, many_measures_score):
    md = timeline(many_measures_score)
    md.jump_to_measure(3)
    start = md.active_event_index

    entries = PlayTimeline(md, PlaySettings(lead_in_enabled=True)).plan(10 ** 9)

    assert entries[-1].kind == "end" and entries[-1].index == start
    assert not PlayTimeline(md, PlaySettings()).can_pause_at(0)
