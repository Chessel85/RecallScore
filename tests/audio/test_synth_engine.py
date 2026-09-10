# tests/audio/test_synth_engine.py
"""SynthEngine note bookkeeping, exercised without a real engine.

Instances are built with object.__new__ and their state set by hand, rather
than constructed normally: SynthEngine.__init__ opens WASAPI, which the
autouse guard in conftest deliberately blocks (D-7). What's under test here
is the pure bookkeeping around _active_notes, so a recording stand-in for
self._fs is all the engine that's needed.
"""
from PySide6.QtCore import QObject

from audio.synth_engine import SynthEngine


class _RecordingFluidSynth:
    def __init__(self):
        self.note_offs = []
        self.note_ons = []
        self.program_selects = []
        self.ccs = []

    def noteoff(self, channel, note):
        self.note_offs.append((channel, note))

    def noteon(self, channel, note, velocity):
        self.note_ons.append((channel, note, velocity))

    def program_select(self, channel, sfid, bank, program):
        self.program_selects.append((channel, sfid, bank, program))

    def cc(self, channel, ctrl, value):
        self.ccs.append((channel, ctrl, value))


def _engine():
    # __init__ is skipped (it opens WASAPI), but SynthEngine is a QObject now
    # and QTimer(self) needs the C++ half initialised, so run QObject.__init__.
    engine = SynthEngine.__new__(SynthEngine)
    QObject.__init__(engine)
    engine._fs = _RecordingFluidSynth()
    engine._sfid = 1
    engine._active_notes = []
    engine._group_off_timers = []
    engine._pending_strum_timers = []
    engine._pending_grace_timers = []
    engine._active_click = None
    engine._active_announcement = None
    engine._active_performance_cue = None
    engine._active_voice_confirmation_cue = None
    engine._active_boundary_cue = None
    engine._live_input_active_notes = set()
    return engine


def test_expiring_group_does_not_silence_another_group_holding_the_same_note():
    """R16: two voices of one part sounding a unison land on that part's
    single channel at the same pitch, so (channel, note) legitimately appears
    in _active_notes twice - once per group, each with its own duration and
    its own timer.

    _stop_group used to release the first matching entry, so the shorter
    voice's expiry sent noteoff for a pitch the longer voice was still
    holding: the note stopped early and a stale entry was left behind for
    stop_all_notes to release a second time. This is the same class of bug
    play_chord already carries two scars from (one group's timing clobbering
    another's), one level further down.
    """
    engine = _engine()
    short_group = [(0, 60)]
    long_group = [(0, 60)]
    engine._active_notes.extend(short_group + long_group)

    engine._stop_group(short_group, timer=None)

    assert engine._fs.note_offs == [], "the other group is still holding this note"
    assert engine._active_notes == [(0, 60)], "only this group's claim is released"

    engine._stop_group(long_group, timer=None)

    assert engine._fs.note_offs == [(0, 60)], "last claim released -> note actually stops"
    assert engine._active_notes == []


def test_expiring_group_releases_notes_no_other_group_holds():
    """The ordinary case: distinct pitches stop as soon as their own group
    expires, with no reference counting getting in the way."""
    engine = _engine()
    group = [(0, 60), (0, 64)]
    engine._active_notes.extend(group)

    engine._stop_group(group, timer=None)

    assert sorted(engine._fs.note_offs) == [(0, 60), (0, 64)]
    assert engine._active_notes == []


def _demo_slots(*specs):
    from models.strum_codes import StrumSlot

    return [StrumSlot(stroke, effect) for stroke, effect in specs]


def test_play_strum_pattern_schedules_one_pending_timer_per_stroke_event(qtbot):
    """Setup/wiring only, mirroring this file's own convention of testing
    bookkeeping without letting a real QTimer actually fire: confirms
    play_strum_pattern creates exactly as many _pending_strum_timers as
    build_strum_schedule would return events for the same inputs, and that
    nothing sounds synchronously."""
    from audio.strum_schedule import build_strum_schedule

    engine = _engine()
    slots = _demo_slots(("down", "none"), ("pause", "none"), ("up", "none"))
    pitches = [48, 55]
    expected = build_strum_schedule(slots, pitches, slot_ms=100.0)

    engine.play_strum_pattern(0, None, pitches, slots, slot_ms=100.0)

    assert len(engine._pending_strum_timers) == len(expected)
    assert engine._fs.note_ons == [], "nothing should sound synchronously - every stroke is scheduled"
    for timer in engine._pending_strum_timers:
        assert timer.isActive()
    for timer in engine._pending_strum_timers:
        timer.stop()  # tidy up so no timer outlives the test


def test_play_strum_pattern_pins_the_program_before_scheduling(qtbot):
    engine = _engine()
    engine.play_strum_pattern(2, 24, [48], _demo_slots(("down", "none")), slot_ms=100.0)

    assert engine._fs.program_selects == [(2, 1, 0, 24)]
    for timer in engine._pending_strum_timers:
        timer.stop()


def test_stop_all_notes_cancels_pending_strum_timers(qtbot):
    """The class of bug _group_off_timers already exists to prevent, one
    level earlier: a previous demo's still-pending future strokes must
    not fire midway through a new one."""
    engine = _engine()
    engine.play_strum_pattern(
        0, None, [48, 55], _demo_slots(("down", "none"), ("up", "none")), slot_ms=100.0
    )
    pending = list(engine._pending_strum_timers)
    assert pending, "should have scheduled something to cancel"

    engine.stop_all_notes()

    assert engine._pending_strum_timers == []
    for timer in pending:
        assert not timer.isActive(), "a cancelled timer must not still be pending"


def test_fire_strum_note_sounds_the_note_and_removes_itself_from_pending(qtbot):
    """Direct call, same convention _stop_group's own tests use above -
    exercises the bookkeeping without waiting for a real QTimer to fire."""
    engine = _engine()
    stand_in_timer = object()
    engine._pending_strum_timers.append(stand_in_timer)

    engine._fire_strum_note(channel=3, pitch=60, velocity=90, duration_ms=250.0, timer=stand_in_timer)

    assert engine._fs.note_ons == [(3, 60, 90)]
    assert (3, 60) in engine._active_notes
    assert stand_in_timer not in engine._pending_strum_timers
    for timer in engine._group_off_timers:
        timer.stop()  # tidy up the note-off timer this scheduled


def test_live_note_on_off_track_pitches_only_on_the_live_channel():
    from audio.midi_input import LIVE_MIDI_INPUT_CHANNEL

    engine = _engine()
    engine.live_note_on(60, 90)
    engine.live_note_on(64, 80)

    assert engine._fs.note_ons == [(LIVE_MIDI_INPUT_CHANNEL, 60, 90), (LIVE_MIDI_INPUT_CHANNEL, 64, 80)]
    assert engine._live_input_active_notes == {60, 64}

    engine.live_note_off(60)

    assert engine._fs.note_offs == [(LIVE_MIDI_INPUT_CHANNEL, 60)]
    assert engine._live_input_active_notes == {64}


def test_stop_all_notes_does_not_touch_live_input_notes():
    """The whole point of live_input_active_notes being tracked separately
    from _active_notes: moving the score cursor (which calls
    stop_all_notes() via play_chord's retrigger, or directly) must not cut
    off a note the user is physically holding on a connected keyboard."""
    engine = _engine()
    engine.live_note_on(60, 90)
    engine._active_notes.append((0, 67))  # an ordinary score note also sounding

    engine.stop_all_notes()

    from audio.midi_input import LIVE_MIDI_INPUT_CHANNEL
    assert (LIVE_MIDI_INPUT_CHANNEL, 60) not in engine._fs.note_offs
    assert engine._live_input_active_notes == {60}, "the live note must still be tracked as held"
    assert engine._active_notes == [], "the ordinary score note is still cleared as normal"


def test_live_all_notes_off_force_releases_every_held_note():
    from audio.midi_input import LIVE_MIDI_INPUT_CHANNEL

    engine = _engine()
    engine.live_note_on(60, 90)
    engine.live_note_on(64, 80)

    engine.live_all_notes_off()

    assert sorted(engine._fs.note_offs) == [(LIVE_MIDI_INPUT_CHANNEL, 60), (LIVE_MIDI_INPUT_CHANNEL, 64)]
    assert engine._live_input_active_notes == set()


def test_synth_midi_channels_constant_is_256():
    """MoreThan16Parts Task 1: the synth is created with all 256 MIDI
    channels, and that number is an explicit constant, not a library
    default. Task 2 adds the cross-check that this equals
    MusicData.MAX_MIDI_CHANNELS (the fact is duplicated across audio/ and
    models/, which may not import each other)."""
    from audio.synth_engine import SYNTH_MIDI_CHANNELS

    assert SYNTH_MIDI_CHANNELS == 256


def test_channel_arguments_reach_the_engine_unmasked_above_15():
    """MoreThan16Parts Task 1: every `& 0x0F` mask is gone, so a part
    assigned a channel >= 16 addresses that channel rather than silently
    wrapping into 0-15 and colliding with another part. An out-of-range
    channel is harmless - FluidSynth returns -1 and does nothing."""
    engine = _engine()
    engine._click_sfid = 2

    engine.set_program(40, program=24, bank=0)
    engine.set_channel_volume(37, 100)
    engine.set_channel_pan(200, 0)
    engine.play_chord([(41, 24, [60])], duration_ms=0)
    engine.play_click(250, 0, 0, 60, 100)

    assert engine._fs.program_selects[0][0] == 40
    assert (37, engine.VOLUME_CC, 100) in engine._fs.ccs
    assert (200, engine.PAN_CC, 0) in engine._fs.ccs
    assert (41, 60, 90) in engine._fs.note_ons
    assert engine._active_click == (250, 60)
    for timer in engine._group_off_timers:
        timer.stop()


def test_stopping_a_group_is_safe_with_no_engine():
    """A build with no FluidSynth available (missing DLLs/soundfont) still
    runs every playback call as a no-op - the timer bookkeeping must be
    cleaned up regardless."""
    engine = _engine()
    engine._fs = None
    timer = object()
    engine._group_off_timers.append(timer)

    engine._stop_group([(0, 60)], timer=timer)

    assert engine._group_off_timers == []
