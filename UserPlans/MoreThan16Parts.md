# Plan: scores with more than 16 parts

Read `CLAUDE.md` and `docs/architecture.md` ("Reserved channels", and the
per-part channel section near `get_channel_for_part`) before starting. Tasks
are in order; each is separately testable and separately committable.

## What was found (2026-09-10)

* The limit is ours, not FluidSynth's. pyfluidsynth's `Synth()` constructor
  defaults to `channels=256` (it sets `synth.midi-channels`), so the engine
  has been running 256 channels all along. Verified with a standalone probe
  (no audio driver): `program_select` + `noteon` succeed on channels 15, 16,
  40 and 255 (channel 255 reports preset "Violin"); channel 256 returns -1.
* What caps it at 16 is our own code: every channel argument in
  `audio/synth_engine.py` is masked with `& 0x0F` (12 sites), and
  `MusicData.MAX_MIDI_CHANNELS = 16`.
* Six channels are reserved, not three: 4 boundary cue, 5 voice-control
  ding, 6 live MIDI input, 7 performance cue, 8 position announcer, 9 click.
  So only 10 parts get a channel of their own today.
* Part 11 onwards silently wraps (`idx % len(usable_channels)`) and shares a
  channel with an earlier part: shared Mixer volume/pan, and
  `noteoff(channel, key)` cutting off the other part's note at the same
  pitch. There is no refusal today, just subtly wrong playback.
* Nothing sends MIDI out (python-rtmidi is input-only), so nothing else is
  tied to channels 0-15. Mixer settings and `.rsc` files are keyed by
  part_id / fixed string keys, never channel numbers, so no saved file
  changes meaning.
* Multi-section scores share one `parts_info`, so the part count is
  file-wide.

## Decisions (from the user)

1. One engine, lift the cap. No second FluidSynth engine: it would mean
   a second audio stream and added latency risk against the 25 ms budget
   (Ref 9), for no gain.
2. Keep the six Recall Score channels separate (merging them would bring
   back the `noteoff(channel, key)` collisions and lose click-right /
   announcer-left panning), but move them to the top of the range, 250-255,
   so parts get plain channels 0, 1, 2 ... with no gaps.
3. A file with more parts than fit (250) is refused with an accessible
   message; the previous score stays open.
4. Polyphony (256 simultaneous voices): live-test first, raise only if
   dropouts are heard.

---

## Task 1 - Let SynthEngine use all 256 channels (`audio/`)

* In `audio/synth_engine.py` add `SYNTH_MIDI_CHANNELS = 256` and pass it
  explicitly: `fluidsynth.Synth(gain=0.7, samplerate=48000.0,
  channels=SYNTH_MIDI_CHANNELS)`. It is the current default, but relying on
  a library default for a load-bearing value is how invariant 13 happened;
  it must be a constructor argument for the same reason samplerate is.
* Remove every `& 0x0F` mask (`set_program`, `set_channel_volume`,
  `set_channel_pan`, the five `play_*` cue methods, `play_chord`,
  `play_chord_with_grace`, `play_strum_pattern`). An out-of-range channel is
  already harmless: FluidSynth returns -1 and does nothing.
* No behaviour change yet: every channel in use is still below 16.
* Tests: a test that `SYNTH_MIDI_CHANNELS == MusicData.MAX_MIDI_CHANNELS`
  (after Task 2). This is the usual guard for a fact duplicated between
  `audio/` and `models/`, since models may not import audio.

## Task 2 - Move the reserved channels to 250-255 (`audio/`, `models/`)

* New values, in both the owning `audio/` module and `MusicData`'s mirror:
  click 255, position announcer 254, performance cue 253, live MIDI input
  252, voice-control ding 251, boundary cue 250.
* `MusicData.MAX_MIDI_CHANNELS = 256`, and a new
  `MAX_PARTS = MAX_MIDI_CHANNELS - len(RESERVED_CHANNELS)` (250).
* `get_channel_for_part` becomes "the part's index in `parts_info`": every
  reserved channel now sits above `MAX_PARTS`, and Task 3 guarantees no
  score exceeds it. Drop the wrap and the per-call usable-channel list
  (along with the class-scope comprehension note in its docstring). Add a
  test that `min(RESERVED_CHANNELS) >= MAX_PARTS`, so the simplification
  can't silently break if someone reserves a seventh channel low.
* Channel 9 now carries an ordinary part (the 10th). FluidSynth marks
  channel 9 (and 25, 41, ...) as a drum channel by default. We always use
  `program_select` with an explicit sfont/bank/preset, which should bypass
  that, but verify with the same kind of probe used above:
  `program_select(9, sfid, 0, 40)` then `channel_info(9)` should report
  Violin, and a rendered note should sound as one. If it doesn't, set
  `synth.drums-channel.active` to 0 in the constructor.
* Update the comments that list the old numbers ("(8)", "(7)" ...) in
  `audio/boundary_cue.py`, `performance_cue.py`,
  `voice_confirmation_cue.py`, `position_announcer.py`, `metronome.py`,
  `midi_input.py` and the block above `RESERVED_CHANNELS`.
* Tests to update: `tests/models/test_music_data.py`
  `test_get_channel_for_part_skips_...` (P5 is now channel 4, P11 is 10, no
  wrap; replace the wrap assertion with one using `MAX_PARTS` parts), and
  the comment at `tests/test_main_window_score_edit.py:113`. The existing
  "cue channels are all distinct" tests in `tests/audio/` should pass
  unchanged.
* Acceptance gate: run `tests/manual/model_fingerprint.py --check` against a
  pre-change baseline. The only diffs allowed are `chan=` values on parts of
  scores with more than four parts. Anything else is a regression.

## Task 3 - Refuse a score with too many parts (`controllers/`)

* In `ScoreSession._on_loaded`: if `len(music_data.parts_info) >
  MusicData.MAX_PARTS`, emit `load_failed` with the message and return
  without assigning `self.music_data`. Both file loads and Ultimate Guitar
  imports pass through here, so one check covers both.
* Message (shown by the existing `_show_load_error` QMessageBox, which takes
  focus and is read by NVDA): "This score has N parts. Recall Score can play
  at most 250, so it cannot be opened."
* Count every `parts_info` entry, including the synthetic Chords/Lyrics
  parts, since each one takes a channel.
* Existing behaviour of the failure path, confirmed: the previous score stays
  loaded, and the file is not added to Recent Files (that only happens in
  `_on_score_loaded`).
* Tests: a MusicData with `MAX_PARTS + 1` parts_info entries fires
  `load_failed` with that text and leaves `session.music_data` unchanged;
  one with exactly `MAX_PARTS` loads normally.

## Task 4 - Docs

* `docs/architecture.md` "Reserved channels": the table is already stale (it
  says four channels). Rewrite it with all six at 250-255, and say why they
  sit above the parts.
* `docs/architecture.md` per-part channel paragraph (around line 792):
  channel = parts_info index; the 250-part limit and where it's enforced.
* Check `docs/parsers.md:440` (percussion channel wording) still reads
  right.

## Task 5 - Live test (user)

* Put the 16-part MusicXML file in `files/` (the fingerprint harness then
  covers it too). Open it and check:
  * every part sounds as its own instrument, in audition and Preview;
  * Mixer volume/pan on parts 11-16 affect only that part;
  * click still hard right, announcer still hard left, performance cue,
    boundary cue, voice-control ding and live MIDI keyboard all still sound;
  * the 10th part (now on channel 9) sounds as its instrument, not drums.
* Polyphony: listen for notes dropping out in dense passages during
  Preview. If heard, raise `synth.polyphony` to 512 as a constructor keyword
  in `SynthEngine._init_engine` (it must be set before the synth is created,
  like samplerate), then re-test. Audition latency is not expected to
  change: the engine already ran 256 channels before this work.

## Out of scope / future

* MIDI export (not yet built, Ref 25) will need its own mapping from our
  channel numbers to a file's 16 channels per port. Don't let that future
  feature reintroduce masking in the engine.
