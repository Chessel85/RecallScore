# Architecture: detail

`CLAUDE.md` carries the module map and the invariants you must not break. This
file is the reasoning behind them. Format-specific parser detail is in
`docs/parsers.md`.

Package-per-domain layout; each module holds one class. Data flows one way:

`main.py` to `MainWindow` to `MusicXMLReader.load()` to `MusicData` to four
region views plus `SynthEngine`.

---

## `models/`

`note_data.py` (`NoteData`), `event_slice.py` (`EventSlice`),
`parts_structure.py` (`PartStructureInfo`), and `music_data.py` (`MusicData`, the
aggregate plus timeline builder).

### `MusicData`'s six collaborators

The logic lives in six classes, each built once in `__post_init__`, each holding
a back-reference to the `MusicData` it serves and **owning no score state of its
own** — so none can go stale against the score, and none needs rebuilding when a
field changes:

* **`timeline_navigator.py`** (`TimelineNavigator`) — cursor movement (Refs
  2/3/5/6): Left/Right, Ctrl+Left/Right, Home/End, typed-measure jump, and the
  per-measure first/last-visible-index lookups Region 5's span jumps and Find
  share. **Also owns the filter-dependent visibility caches** —
  `MusicData._invalidate_visibility_cache` is a delegator to
  `TimelineNavigator.invalidate_cache`.
* **`note_renderer.py`** (`NoteRenderer`) — Ref 15 AC4's attribute display
  system: Region 3's row text, Region 4's rows, and the per-voice which/order
  state. The state itself (`voice_display_attributes`, `attribute_order`) stays
  on `MusicData` because `export_config`/`apply_config` persist it; only the
  reading and mutating moved.
* **`playback_event_builder.py`** (`PlaybackEventBuilder`) — note grouping into
  `(channel, program, pitches, duration_ms[, bank])` events plus the grace-note
  side channel, quarters-to-ms conversion, and both stepping functions
  (`next_visible_event_index` and the repeat/ending/Segno/Coda/D.C./D.S./Fine-aware
  `next_playback_index`).
* **`override_manager.py`** (`OverrideManager`) — every override that mutates
  already-parsed notes in place: part name/instrument, percussion item
  name/sound, whole-piece key signature. Grouped because each is applied from
  both a dialog's OK and `apply_config`, and each is losslessly re-derivable from
  an immutable original the parser recorded (`percussion_source_key`,
  `file_key_fifths`).
* **`find_index.py`** (`FindIndex`) — the Find dialog's target catalog and
  occurrence scanner.
* **`performance_rows.py`** (`PerformanceRows`) — Ref 29's two whole-score
  read-outs: `get_performance_region_rows` (Region 5's start/end row list at the
  cursor) and `get_performance_report_lines` (the Performance Report's line
  list). Extracted (S17) because the two were the largest methods in the
  codebase, 28% of `music_data.py`. Reads spans/marks and the `_bar_beat_label`
  / `_marking_part_prefix` / `_tempo_change_at` helpers off `MusicData` live.

**`MusicData` keeps a one-line delegator for every method these took over**,
including the private ones tests drive directly (`_note_attribute_pairs`,
`_format_note_for_region_3`, `_sounding_bounds`, `_slice_is_navigable`,
`_quarters_to_ms`). That is deliberate and load-bearing: `MusicData` is replaced
wholesale on every load, so **no caller may hold its own collaborator** —
everything must keep asking `MusicData`. Put new behaviour in the collaborator
that owns it; adding a method to `MusicData` is only right if it is a delegator
or genuinely cross-cutting.

### `models/` must not import from `parsers/`

It previously did so five times, including a *private* name
(`parsers.midi_timeline_builder._spell_pitch`), and `MusicData.__post_init__`
imported all four timeline builders at module scope. Because
`TimelineBuilder`/`UgTimelineBuilder` import music21, merely importing the data
model cost **461 ms and 706 modules**; it is now **45 ms and 111 modules**, with
music21 not loaded at all. Four modules carry what used to be reached across the
boundary:

* **`models/synthetic_parts.py`** — the identifiers for parts/voices this app
  FABRICATES: `CHORDS_PART_ID`/`CHORDS_PART_NAME`/`LYRICS_PART_ID`/
  `LYRICS_PART_NAME`, `GP_CHORD_VOICE_ID`/`GP_CHORD_VOICE_NAME`,
  `STAVE_TEXT_VOICE_ID`/`STAVE_TEXT_VOICE_NAME`. These had been defined
  independently in three parser modules, every pair having to agree verbatim
  (`collapsed_part_ids` matches part_ids by string; `get_performance_report_lines`
  joins names by exact text) — the R5 bug class, latent. One definition now; the
  parser modules re-export what they already published.
* **`models/pitch_spelling.py`** — `spell_pitch` plus the two pitch-class tables.
  Both `MidiTimelineBuilder` (parse time) and `OverrideManager` (key-override
  re-spelling) need it, and it is pitch arithmetic over a fixed table, not
  parsing.
* **`models/strum_codes.py`** — UG's undocumented strum-code vocabulary: the
  **full 9-code table** (`STRUM_CODES: Dict[int, StrumSlot]`,
  `StrumSlot(stroke, effect)`) taken verbatim from UG's own front-end bundle
  (webpack module `78736`): `1/101` down/up, `2/102` down/up muted, `3/103`
  down/up accented, `201` palm mute, `202` pause, `203` real pause. The app
  previously knew only 3 codes and **mislabelled `202` (a pause, the commonest
  code in every real pattern) as "muted strum"**. `slot_words(code)` is the
  spoken form; `strumming_pattern_text(codes)` the Region 1 credit. A pure lookup
  table, same category as `models/gm_instruments.py`.
* **`parsers/timeline_builder_factory.py`** plus **`models/timeline_build.py`** —
  format dispatch moved to `parsers/` where it belongs, while `models/` keeps the
  contract. See `docs/parsers.md`.

Related small models: **`models/strum_pattern.py`** (`StrumPattern(name, bpm,
denominator, is_triplet, codes)` plus `slots_per_bar()`/`bar_count()`/
`slot_ms()`/`slot_labels()`/`slot_rows()`), **`models/beat_position_words.py`**
(`spoken_word_for_beat_position`, shared with the talking metronome and
re-exported by `audio/position_announcer.py`), and **`models/section_span.py`**
(`SectionSpan(label, start_measure, end_measure)`, published through
`models/timeline_build.py` like every other side-channel list).

---

## `audio/`

### `audio/synth_engine.py`

In-process FluidSynth. At import it prepends `<root>/bin` via
`os.add_dll_directory` plus `PATH` and pre-loads the glib/gobject/gthread/
fluidsynth DLLs with `ctypes.CDLL` before `import fluidsynth`; **that ordering is
required on Windows** and is why the module has side effects at import time.

The synth runs on the WASAPI driver at 48 kHz with a 128-frame period and 2
periods — low-latency settings chosen for Ref 9's 25 ms budget; don't raise them
without cause.

**GOTCHA: `samplerate` must be passed to the `Synth()` constructor itself**
(`fluidsynth.Synth(gain=0.7, samplerate=48000.0)`). `pyfluidsynth.Synth.__init__`
calls `new_fluid_synth(self.settings)` — the actual DSP engine creation — using
whatever `synth.sample-rate` is in the settings object at that exact moment. A
`self._fs.setting("synth.sample-rate", ...)` call made *after* construction only
updates the stored value and silently keeps rendering at pyfluidsynth's own 44100
Hz default. That mismatch (audio generated at 44100, WASAPI stream opened at
48000) speeds everything up by 48000/44100 — audible as ~147 cents sharp, i.e.
every note roughly a semitone sharp.

WASAPI **shared** mode (no exclusive-mode setting anywhere in this code) is relied
on to resample this fixed 48 kHz stream to whatever the user's device runs at —
standard OS behavior, deliberately not second-guessed with device-format
detection.

**Note-off is scheduled by one single-shot `QTimer` per sounding group**, not one
shared timer, so each part rings for its own `duration_ms` independent of the
others.

**`play_chord(events, retrigger=True)`.** The default silences everything
currently sounding first (`stop_all_notes()`), correct for discrete audition
(Ref 8 AC2 — Region 3 navigation, chord audition) where each move should present
a clean slate. `Sequencer` passes `retrigger=False` for its natural step-to-step
advance during real playback (Ref 10): with the default, a new part's attack
(e.g. Violin I entering mid-phrase) silenced *other*, unrelated parts' still-
ringing notes. `Sequencer.play_from()` and any explicit reposition still call
`stop_all_notes()` themselves, so restarting playback elsewhere does clear the
deck — only the in-run advance is non-destructive.

### Reserved channels

The synth addresses all 256 MIDI channels (`audio.synth_engine.SYNTH_MIDI_CHANNELS`,
passed to the `Synth()` constructor and mirrored by `MusicData.MAX_MIDI_CHANNELS`;
a test asserts they match). `MusicData.RESERVED_CHANNELS` keeps real instrument
parts off six of them:

| Channel (0-idx) | Owner | Pan |
|---|---|---|
| 255 | `METRONOME_CLICK_CHANNEL` — the click metronome | full right (127) |
| 254 | `POSITION_ANNOUNCER_CHANNEL` — the talking metronome | full left (0) |
| 253 | `PERFORMANCE_CUE_CHANNEL` — Region 5's change cue | centre (64) |
| 252 | `LIVE_MIDI_INPUT_CHANNEL` — live MIDI input | — |
| 251 | `VOICE_CONTROL_CUE_CHANNEL` — voice-control confirmation ding | — |
| 250 | `BOUNDARY_CUE_CHANNEL` — Region navigation boundary cue | — |

**Why 250–255, at the top of the range.** Parts take plain channels 0, 1, 2 … in
part-list order (`get_channel_for_part` — see below), so the reserved channels
have to sit above every channel a part could claim. `MAX_PARTS`
(`MAX_MIDI_CHANNELS - len(RESERVED_CHANNELS)` = 250) is exactly `min(RESERVED_CHANNELS)`,
and `ScoreSession` refuses any score with more parts than that, so a part index
can never collide with a reserved channel. A test asserts
`min(RESERVED_CHANNELS) >= MAX_PARTS` so the simplification can't silently break
if someone reserves a seventh channel low. Keeping the six separate (rather than
folding them onto one) avoids the `noteoff(channel, key)` collisions below and
preserves click-hard-right / announcer-hard-left panning.

Channel 9 (and 25, 41, …) is FluidSynth's default drum channel, but the engine
always calls `program_select` with an explicit sfont/bank/preset, which bypasses
that — so the 10th part, now on channel 9, sounds as its own instrument.

**Why a channel per sound, not a note-numbering convention.** Several presets in
`recall_score_sounds.sf2` start their note numbering at 60, so a click and a word
landing on the same beat would share a `(channel, key)` pair on one channel —
and FluidSynth's `noteoff(channel, key)` releases *every* voice matching that
pair regardless of which preset started it, so an early note-off meant for one
would silence both. A channel reservation holds systemically for any future
click/word preset pair; a numbering convention has to be remembered by hand every
time. Confirmed with the user as the deliberate choice when Ref 29's cue took the
third channel.

Pan is set **once at load time** in `_load_click_soundfont`, not per call, since
each channel is permanently dedicated and a channel's pan persists until changed.

`LIVE_MIDI_INPUT_CHANNEL` is defined as a plain literal in `models/music_data.py`
rather than imported — `models/` has never imported from `audio/`, and the other
three constants are mirrored the same way.

### `audio/metronome.py` and `soundfonts/recall_score_sounds.sf2` (Ref 14)

The click's sound is a second, small, project-authored soundfont loaded by
`SynthEngine._load_click_soundfont` alongside the main GM soundfont (its own
`sfid`, `self._click_sfid`) — not a synthesized tone or GM percussion, both of
which were tried and rejected as unsatisfying.

Built by `tools/wav_to_sf2.py` from real recorded WAV clips via a plain-text
config (`tools/config.ini`, checked into git alongside its source WAVs, e.g.
`tools/click1/`, `tools/words1/`, `tools/bells/`; `tools/example_config.ini` is
the template new presets should copy from).

**GOTCHA (`.gitignore`):** the `.sf2` is checked into git even though
`soundfonts/` is otherwise ignored. A bare `soundfonts/` line makes git treat the
whole directory as opaquely ignored and never evaluate a later per-file negation
against it, so `.gitignore` uses `soundfonts/*` (contents, not the directory) for
the `!soundfonts/recall_score_sounds.sf2` exception to take effect.

`click_event_for_beat()` returns `(channel, bank, program, pitch, velocity)` —
accent vs. regular beat is which *sample* plays (`program_select` onto the
dedicated click soundfont), not a velocity difference on one fixed voice.

**No explicit note-off scheduling.** Each click/word zone is a one-shot,
non-looping sample (`SampleModes=0`), and FluidSynth deactivates such a voice on
its own once the sample data is exhausted, *regardless of whether a note-off was
ever sent*. An earlier design read each sample's natural length from a sidecar
`recall_score_sounds.sf2.json` to schedule a `QTimer` note-off; that was
unnecessary and is gone (`tools/wav_to_sf2.py` no longer writes the sidecar).
`_stop_click()`/`_stop_announcement()` remain the deliberate-*interrupt* path,
called from `stop_all_notes()` and from `play_click`/`play_word` before a new one
starts.

### `audio/position_announcer.py` (Ref 28)

The talking metronome, on the same custom soundfont
(`talking_metronome_default` preset, bank 0/program 0, notes 60-69 =
one..seven/e/and/a per `tools/config.ini`).

`spoken_word_for_beat_position(beat_position)` splits the ts-relative beat
position into a whole part (1-7, AC3) and a fractional remainder (25/33/50/66/75%
to e/and/and/a/a, AC4); `announcement_event_for_beat()` wraps that into the same
5-tuple shape as `click_event_for_beat()`. Both `Sequencer._sound_current_step`
and `MainWindow._play_selected_region_3_notes` call it right alongside (not
instead of) the click, gated by its own independent
`MusicData.position_announcer_enabled`.

Unlike `set_metronome_enabled`, toggling this **never rebuilds
`timeline_slices`** — AC5 requires the announcer to only ever speak at positions
that already have an event and never create its own.

`SynthEngine.play_word()` is a near-duplicate of `play_click()` with its own
active-note slot (`_active_announcement`), sharing `self._click_sfid`.

### `audio/performance_cue.py` (Ref 29)

Region 5's "something changed, check it" cue: bank 0/program 2
(`[preset:performance_cue_default]`). `performance_cue_event()` returns a fixed
5-tuple, not a beat-position lookup, since the cue fires on "the active Region 5
row set changed", not on a beat grid. `play_performance_cue`/
`_stop_performance_cue` mirror `play_click`/`_stop_click` with their own
`_active_performance_cue` slot; `stop_all_notes()` calls
`_stop_performance_cue()` alongside the other two.

### `audio/strum_schedule.py`

`build_strum_schedule(slots, midi_pitches, slot_ms, note_delay_ms=20.0)` is a
**pure function** (no Qt, no timers) turning a list of `StrumSlot`s into
`(start_ms, pitch, velocity, note_duration_ms)` note-ons: a `"down"`/`"p.m."`
stroke fires low-to-high, `"up"` high-to-low, each `note_delay_ms` apart;
`"pause"`/`"real pause"` emit nothing but keep their `slot_ms` slot so timing
holds; `"mute"`/`"p.m."` are short and quiet, `"accent"` louder.

**`slot_ms` comes from the pattern's own `bpm`/`denominator`/`is_triplet`**
(`StrumPattern.slot_ms()`), not from dividing one chord's duration — the old bug
squeezed a 32-slot two-bar 16th pattern into one chord.

Used **only** by the Strumming Patterns dialog's demo
(`SynthEngine.play_strum_pattern`, a flat one-`QTimer`-per-attack wrapper tracked
in `_pending_strum_timers`, cancelled by `stop_all_notes()`).

`sound_events(synth, music_data, events, retrigger, grace_events=None)` is the
single dispatch point `PlaybackController.audition_selection` and
`Sequencer._sound_current_step` route through; it chooses between
`play_chord_with_grace` (a MusicXML grace note in the selection) and plain
`play_chord`.

### `audio/midi_input.py` and `controllers/live_midi_input_controller.py`

Play a connected MIDI keyboard live through the app's own synth. Options > Live
MIDI Input Settings... (`Ctrl+Shift+L`); `Ctrl+D` toggles on/off.

**Deliberately never layers on FluidSynth's own MIDI driver** (`Synth.start()`'s
auto-created router/driver) — that is the path `_init_engine` avoids, both for
the original MIDI-controller collision bug and its documented
`delete_fluid_midi_driver()` deadlock. Instead `audio/midi_input.py` is a
standalone `python-rtmidi` session (`MidiInputManager`, `list_input_ports()`)
handing `(status, pitch, velocity)` tuples to a plain Python callback; the
controller feeds those into the same `fluidsynth.Synth` instance via
`SynthEngine.live_note_on`/`live_note_off`/`live_all_notes_off`.

**Live-input notes are tracked separately** (`SynthEngine._live_input_active_notes`,
a bare `set` of pitches — one channel, so no tuple needed). **`stop_all_notes()`
deliberately does not touch it**: score navigation calls `stop_all_notes()` far
too often, for a purpose that has nothing to do with a note the user is
physically holding. Only `live_all_notes_off()` (explicit disable, device change,
app close) force-releases them.

**Threading.** `python-rtmidi`'s callback fires on its own internal thread.
`LiveMidiInputController._on_raw_message` does nothing but emit
`_raw_note_on`/`_raw_note_off`; both are connected with an explicit
`Qt.ConnectionType.QueuedConnection`, forcing the actual `SynthEngine` call onto
the main thread's event loop — chosen over a lock so "`SynthEngine` is only ever
touched from the main thread" stays true, rather than introducing this codebase's
first lock. `_connect()` applies instrument/volume/pan synchronously before
returning, so a queued note-on for a fresh connection can only run afterwards —
race-free by construction.

**Settings** (`models/live_midi_input_settings.py`) are **global**
(`AppSettings.live_midi_input`), not per-score — confirmed with the user: which
keyboard is plugged in and what it sounds like is the user's hardware setup, not
a property of any one piece. `device_name` is matched against `python-rtmidi`'s
enumerated port name at connect time, the only identifier available. `start()`
auto-connects to the last-used device if `enabled` and present, and degrades
silently (no popup, no exception) otherwise — a device not being plugged in is an
ordinary state, not an error.

The device combo has **no live-preview signal**, unlike instrument/volume/pan
(which mirror `MixerDialog`'s live-preview-then-commit/cancel shape) — there is
nothing to preview about a port choice until a note is played, and reconnecting
is heavier than a CC tweak. Read only via `result_settings()` after OK.

`widgets/range_spin_box.py`'s `RangeSpinBox` (Home/End/Insert convenience keys)
was extracted out of `widgets/mixer_dialog.py` so both dialogs can share it.

---

## `controllers/`

`MainWindow` was a 1,320-line class holding eleven unrelated jobs. It is now a
shell that builds widgets, owns the controllers below, and wires them in
`connect_signals()`. **Put new behaviour in the controller that owns it, not in
the window.**

* **`score_session.py`** (`ScoreSession`) — what is loaded: the `MusicData`, the
  synth, `uk_terms`, the load thread. Emits `score_loaded`. **Every controller
  reads `session.music_data` per call and never caches it**, because `MusicData`
  is replaced wholesale on each load — caching would leave a controller driving
  the previous score, a bug class that grows with each controller added.
* **`playback_controller.py`** (`PlaybackController`) — Sequencer lifecycle,
  transport, the one lead-in/looping play session, absolute tempo, boundary cue,
  chord audition, metronome/announcer toggles, mute, and the mixer. **Touches no
  widgets**: widget-derived values are passed in
  (`audition_selection(indices)`), which is what makes the transport testable
  without a window. Signals `cursor_moved(play_all)` / `status_text_changed` /
  `playback_state_changed` rather than calling the view.
* **`navigation_controller.py`** (`NavigationController`) — cursor movement only.
  Every method either moves and emits `position_changed(play_all)`, or emits
  `boundary_hit`. Deciding what that sounds like and redraws is the shell's
  wiring. Also owns the **Ref 6 typed-bar-number buffer** (`pending_digits`,
  `append_pending_digit`/`clear_pending_digits`/`commit_pending_digits`,
  `pending_digits_changed` to `RegionPresenter.show_pending_digits`). It used to
  live on `TimelineListWidget`, so the feature only worked with the Note region
  focused; it is now global — `setup_shortcuts` binds bare `0`-`9` and `Escape` as
  `WindowShortcut`s. Every cursor move clears the buffer so a later, unrelated
  `Enter` can't action a stale number.
* **`region_presenter.py`** (`RegionPresenter`) — **the only controller that
  touches widgets.** Owns the five regions, the status bar, and the refresh choke
  point (`update_timeline_views`).
* **`attribute_controller.py`**, **`focus_controller.py`**,
  **`score_persistence.py`** — Ref 15 AC4's attribute system, the region focus
  cycle / F6 panes, and the per-score `.rsc`.
* **`score_edit_controller.py`** (`ScoreEditController`) — edits to the loaded
  score's own data: the Instruments dialog's part name/instrument and
  per-percussion-item overrides, the Key Signature dialog's whole-piece override,
  and Reorder Parts. The counterpart of `PlaybackController` for score data
  rather than transport. Touches no widgets: Region 2's labels and row order go
  through `RegionPresenter.rename_part`/`rename_voice`/`reorder_parts`. Each
  apply method returns whether anything actually changed, so a dialog dismissed
  with no edits triggers no rebuild.

**GOTCHA:** `FocusController` holds the window solely for `window.focusWidget()`,
which is NOT `QApplication.focusWidget()` — the former reports focus within this
window's subtree even when the window isn't active, which the pane and
Home/End-enabling checks depend on.

**GOTCHA:** dialog *construction* stays in `MainWindow` (every dialog), because
tests monkeypatch `main_window.<DialogClass>` with a lambda matching the
constructor's signature. Controllers own the logic behind a dialog, not its
lifecycle. The pattern is uniform: read the dialog's inputs from a controller,
construct, `exec()`, hand the result straight back to that controller, restore
focus. A `_show_*_dialog` method that does more than that has logic in the wrong
place.

### One play model (Ref 12)

Preview and its separate transport are gone; `Space` (`toggle_play_stop`) is the
single play control, and there is one settings dialog.

* **Tempo is absolute and flat.** `MusicData.playback_tempo_bpm` (quarter-note
  BPM, `None` = score default) replaces the old session-only
  `playback_tempo_offset`. `effective_tempo_bpm(index)` ignores `index` —
  playback holds one steady tempo; the score's internal rall./accel./section
  changes are still *described* (Region 5, Performance Report, `tempo_changes`)
  but never sounded. The displayed number (`playback_tempo_display_bpm`) is
  denominator-relative (a quarter in 4/4, an eighth in 6/8, via
  `tempo_display_beat_unit_name_at`), clamped `MIN_TEMPO_BPM`=5 to
  `MAX_TEMPO_BPM`=300. Region 1 still shows the score's *notated* marking, so the
  two numbers can legitimately differ. `F`/`S` = `nudge_playback_tempo(+/-10)`;
  `D` = `reset_playback_tempo()`. Persisted **per-score**
  (`ScoreConfig.playback_tempo_bpm`, schema v3).
* **`PlaySettings`** (`models/play_settings.py`) — `lead_in_enabled` (master
  toggle), `lead_in_bars`/`lead_in_beats`, `loop_enabled`, `loop_length_bars`
  (cap 64), `loop_lead_in`. Global (`AppSettings.play`); `from_dict` still reads
  the old `preview` key and field names for back-compat.
* **`_PlayRun`** carries `looping: bool`. Non-looping = lead-in only: starts on
  the exact cursor, `end_index=None`, cursor follows, ends via
  `_on_sequencer_finished`. Looping: snaps to the bar line of the cursor's
  measure, fixed `loop_length_bars` window, cursor frozen, `("loop",)` restart
  timer. `toggle_play_stop` builds a `_PlayRun` when
  `loop_enabled or lead_in_enabled`, else the plain `sequencer.play_from` path.
  Neither `play_command` (voice "play") nor the plain path involve a `_PlayRun`.
* **Keybindings:** `Ctrl+L` Toggle Looping, `Ctrl+D` Live MIDI Input, `Ctrl+I`
  Toggle Lead-in, `Ctrl+Enter`/`Ctrl+Return` commit typed number as loop length,
  `Ctrl+T` a second shortcut on Play Settings... (`Ctrl+Shift+V`),
  `Enter`/`Return` commits a typed bar number only. `Alt+PageUp`/`PageDown` and
  the `loop length N` voice command act on loop length.
* `widgets/play_settings_dialog.py` replaces `preview_settings_dialog.py` plus
  `tempo_offset_dialog.py` (both deleted). The Mixer dialog's "Preview" button
  (`Alt+W`) calls `toggle_play_stop`, honouring current loop/lead-in settings.
* **Verification note:** `tests/manual/model_fingerprint.py` is *expected to
  differ* on tempo-derived fields (playback is now flat) — re-capture the
  baseline. `parser_fingerprint.py` is unchanged.

---

## Keyboard shortcuts (`UserPlans/KeyboardShortcuts.md`)

Tools > Keyboard Shortcuts opens a dialog (`widgets/keyboard_shortcuts_dialog.py`)
that rebinds any menu `QAction` plus four window-level `QShortcut`s (tempo
faster/slower/reset, play selected notes). The design follows invariant 8
("two copies of the same fact will diverge"): there is no separate table of
factory-default shortcuts anywhere in the codebase.

* **`models/shortcut_map.py`** (`ShortcutMap`, Qt-free) holds the actual logic
  on canonical `QKeySequence` PortableText strings (`"Ctrl+Shift+K"`):
  `defaults` is a snapshot handed in by the caller, `overrides` holds only the
  user's *differences* from it (`""` means "no shortcut"). `bindings()`
  resolves the two into what's actually live, so an action the user never
  touched automatically picks up a changed default in a later version instead
  of being frozen at whatever the snapshot said when the user last saved.
* **`controllers/shortcut_controller.py`** (`ShortcutController`) is the only
  place that touches Qt for this feature. At construction it walks the menu
  bar (`_build_targets`) to build one `ShortcutTarget` per rebindable
  `QAction`/`QShortcut`, then takes the defaults snapshot from
  `target.get()` **before** loading and applying `app_settings.load().shortcuts`
  — that snapshot *is* the factory-defaults table `ShortcutMap` needs, taken
  from wherever `MenuBuilder` / `MainWindow.setup_shortcuts` actually built
  those objects. It also owns `_build_reserved()`, the table of keys the
  dialog refuses to rebind because a widget's `keyPressEvent`/`event()`
  handles them directly (region-cycle Tab, the typed-bar-number family,
  list navigation, Ctrl+1-9, etc.) — each entry's comment names the file that
  owns that key. **A new hardcoded key added to a widget's `keyPressEvent`
  must be added there too**, or the dialog will silently let the user steal
  it for something else.
* Every mutation (`assign`/`clear`/`restore_defaults`) re-applies the live
  `QKeySequence`s to every target and immediately saves the override diff via
  `app_settings.set_shortcut_overrides`, the same "commit right away" pattern
  as `set_uk_terms` — there's no working copy, matching the dialog's Apply +
  Close (no Cancel) design.
* `ShortcutController` holds QActions and QShortcuts but no widgets;
  `widgets/keyboard_shortcuts_dialog.py` and `widgets/shortcut_capture_edit.py`
  (the key-combination-recording `QLineEdit`) only ever call the controller's
  public methods, so a test can hand the dialog a fake controller.

---

## `widgets/`

`region_table_widget.py` (`RegionTableWidget`, a plain property-list table used
by regions 1 and 4), `region2_list_widget.py` (`Region2ListWidget`, region 2 — a
flat navigable list, not a table, so NVDA reads a whole row's name/level/on-off
status in one Up/Down keystroke instead of needing column-by-column navigation),
`timeline_list_widget.py` (`TimelineListWidget`, region 3),
`region5_list_widget.py` (`Region5ListWidget`, region 5), and
`region2_manager.py` (`Region2HierarchyModel` / `Region2Node`, pure state — no
Qt — that both `Region2ListWidget` and its tests drive).

**Building a new dialog that pairs a reorderable list with buttons, or mixes
plain `QPushButton`s with a `QDialogButtonBox`? Read
`docs/dialog_widget_patterns.md` first** — it covers a live-NVDA-confirmed Qt
accessibility trap (`autoDefault` silently masks a button's own `&`-mnemonic as
"Enter" once focused, not reproducible in the offscreen test harness) and the
working-copy Ok/Cancel plus focus-restoration conventions
`widgets/attribute_order_dialog.py` and `widgets/part_order_dialog.py` establish.

### Tab handling

**`widgets/region_focus_cycle.py` (`RegionFocusCycleMixin`) is the single owner of
Tab/Shift+Tab** — mixed into all four `QAbstractItemView`-based region widgets,
always *before* the Qt base class in the MRO so its `event()` wins and `super()`
still reaches the widget's own. **Don't add Tab handling to a region's
`keyPressEvent`; it will not fire.**

**GOTCHA:** `QAbstractItemView` intercepts `Key_Tab`/`Key_Backtab` at the
`event()` level *before* `keyPressEvent()` is ever invoked, for a single-column
view like a `QListWidget`. Three region widgets had dead `keyPressEvent` Tab
handlers, masked because Qt's native `focusNextPrevChild()` ring (formed by widget
creation order) happened to match the desired cycle order for every transition
except wrap-around, and the old last region (a `QTableWidget`, where Tab *does*
reach `keyPressEvent`) genuinely handled its own wrap. Region 5 becoming last
exposed it.

A synthetic Shift+Tab also arrives as plain `Key_Tab` with `ShiftModifier` set,
not as `Key_Backtab` — both conventions are checked in the mixin.

**Testing note that follows:** assert the cycle *method runs*, not just where
focus lands (`test_every_region_routes_tab_through_the_region_cycle_not_qts_focus_chain`).
The two older cycle tests only checked the landing widget, so they passed for the
entire period the handlers were dead. Likewise, drive Tab through
`widget.event(...)` rather than `widget.keyPressEvent(...)` in unit tests;
calling `keyPressEvent` directly tests a path the app never takes.

### Signals, not window callbacks

`TimelineListWidget` and `Region5ListWidget` emit signals rather than calling back
into `MainWindow` through `self.window()` — matching `Region2ListWidget.filter_changed`,
so both are unit-testable with no window.

* `TimelineListWidget`: `navigate_requested(direction, by_measure)` (Left/Right/
  Home/End to `NavigationController.navigate`), `vertical_move_made` (Up/Down to
  `MainWindow.on_region_3_vertical_move`, kept in the shell as it clears the digit
  buffer *and* re-auditions), `loop_length_adjust_requested(+/-1)`
  (Alt+PageUp/PageDown), `attribute_number_requested(n)` (Ctrl+1..9).
* `Region5ListWidget`: `span_jump_requested(is_start)` (Ctrl+Home/Ctrl+End).

All wired in `connect_signals()`. Digit/`Enter`/`Escape` are **not** handled in
`TimelineListWidget` — the typed-bar jump is window-wide.
`RegionFocusCycleMixin` still uses `self.window()` for the Tab cycle — shared
focus-ring infrastructure, deliberately left as the one such call.

`Region2ListWidget` maps `O` to toggling the focused row's node (Up/Down need no
override). `Region2ListWidget.refresh_list(preferred_node_id=...)` deliberately
re-anchors the current row after a rebuild so NVDA keeps announcing the row the
user is on.

### `widgets/menu_builder.py`

`MenuBuilder` builds the whole menu bar and returns an `Actions` dataclass the
shell keeps as `self._actions`; every QAction is reached as
`self._actions.<name>` (production and tests), with no per-action aliases on the
window. `FocusController`/`ScorePersistenceController` are handed the few actions
they gate, in `setup_menu`.

**`Actions`' fields are held as attributes, never locals:** PySide can garbage-
collect a QAction's Python wrapper while the C++ object is still alive and
parented, leaving "Internal C++ object already deleted" for anything later
reaching it via `menuBar().actions()`.

### Direct-jump navigation actions

Each region has a direct-jump `QAction` in the `&Navigation` menu
(`move_to_metadata`/`move_to_parts`/`move_to_notes`/`move_to_attributes`/
`move_to_performance`) that moves focus there from anywhere in the window without
changing the timeline position. All five stay enabled regardless of current
focus, unlike `first_measure`/`last_measure` (Home/End), which
`FocusController.update_navigation_actions_enabled` greys out outside the Note
region.

Mapped to **Z/X/C/V/B** (regions 1-5). They were originally scattered letters
(I/V/N/A/P), which were hard to locate by feel; Z/X/C/V/B sit together on the
keyboard's bottom row, left-to-right in the same order as the five regions, and
don't collide with Ctrl+M/Ctrl+P/F/S/D. (`S` was the first choice for the
Metadata region but collided with the bare-`S` tempo shortcut.)

### Dialogs

* **`widgets/instrument_dialog.py`** (`InstrumentDialog`, Edit > Instruments...,
  `Ctrl+Shift+I`) — per-part display-name/GM-instrument override, for both
  MusicXML and MIDI ("piano may not always be a suitable default"). One row per
  part in a `QListWidget`; the name is free text, the instrument is picked from
  `models/gm_instruments.py`'s 128-entry table — **never a raw program number**
  (the user explicitly doesn't want program numbers surfaced) — via an editable
  `QComboBox` plus a contains-anywhere `QCompleter`. Deliberately
  editable/searchable, unlike the Key Signature dialog: plain keyboard-search
  alone isn't enough to browse 128 entries. `setInsertPolicy(NoInsert)` stops a
  typed-but-unmatched string becoming a bogus item; an unresolved edit is ignored
  at commit rather than corrupting the part's program.

  `MusicData.apply_part_overrides` mutates `parts_info` in place (already read
  live everywhere, so the program override needs no further wiring) and
  **re-syncs every affected `NoteData.part_name`** — `get_performance_report_lines`
  joins `parts_info.name` against `note.part_name` by exact text, so renaming
  only one side would silently reopen the "0 notes" bug (R5).

  Region 2's part-row label is updated in place
  (`Region2HierarchyModel.rename_part`/`Region2ListWidget.rename_part`), **never
  via `load_score_structure`** — that resets every node back to `enabled=True`,
  discarding the user's on/off toggles.
* **`widgets/key_signature_dialog.py`** (`KeySignatureDialog`, Edit > Key
  Signature..., `Ctrl+Shift+K`) — a single whole-piece key-signature override,
  persisted per file, mainly for MIDI files lacking correct key metadata.
  Originally a second control inside the Instruments dialog; split out after the
  user found renaming a part and overriding the score's key too different a pair
  of actions to share one dialog.

  One **non-editable** `QComboBox`, 31 entries (`models/key_signatures.py`'s
  `key_override_options()`: a "use the file's own key" sentinel plus all 15 major
  and 15 minor key names in fifths order) — 31 is few enough that Qt's native
  keyboard-search suffices. Picking e.g. "G major" sets the fifths and the
  major/minor display mode together, which also replaces `FIFTHS_MAP`'s ambiguous
  `"C major / A minor"`-style label.

  **`FIFTHS_MAP`'s strings spell every accidental out as a word** ("F sharp", "B
  flat"), never a symbol or letter suffix — NVDA read "Bb major" as just "b
  major", silently losing the accidental.

  `MusicData.apply_key_signature_override(fifths, mode)`: for a MIDI score,
  re-spells every note via `spell_pitch`; clearing the override (`fifths=None`)
  re-derives each note's spelling from its own `file_key_fifths` rather than a
  cached original string, so no re-parse is needed. **MusicXML and GP notes are
  never re-spelled** — their spelling comes from the file's own `<step>/<alter>`
  and never depended on key; the override there only changes what's *displayed*.
* **`models/mixer_settings.py`** / **`widgets/mixer_dialog.py`** (Edit >
  Mixer..., `Ctrl+Shift+X`) — per-instrument volume/pan (plus the click/announcer/
  cue channels) and mute.

  **The design property that matters:** `MixerSettings` stores **only explicit
  overrides**, so an empty one — the default for every score — causes
  `apply_mixer` to leave the engine exactly as it would be without the feature
  for any channel with nothing set. Don't "helpfully" default volumes to 100/pan
  to 64 and send them as overrides; that would make the no-settings case a
  different code path.

  `PlaybackController.begin_mixer_edit`/`set_mixer_volume`/`set_mixer_pan`/
  `commit_mixer_edit`/`cancel_mixer_edit` own the live-preview-then-commit/cancel
  edit session (a working-copy `MixerSettings`, discarded on Cancel).

  **`apply_mixer()` resends every mixer-controllable channel unconditionally on
  each load/attach** — an explicit override where one exists, else the real GM
  default — not just channels this score overrides. The synth is a long-lived
  singleton across file loads, so a channel left untouched silently inherited the
  *previous* score's Mixer setting (a cello at 0% survived into an unrelated score
  whose part landed on the same channel). Sending nothing only leaves the engine
  "as it would be without this feature" on the very first load, not on every later
  one.
* **Options > Reorder Parts...** (`widgets/part_order_dialog.py`) — NVDA reads
  whichever part's row Region 3 lands on first after every navigation step (always
  row 0), so for a UG import the user had no way to choose whether the chord name
  or the lyric got read first. A working-copy OK/Cancel dialog (list plus Move
  Up/Move Down, Alt+U/Alt+D); unlike `AttributeOrderDialog`, moves are staged and
  committed only on OK.

  Applying goes through `MusicData.reorder_parts` (reorders `parts_info` and
  stably re-sorts every `EventSlice.notes` list by the new part order — a live,
  render-time reorder, the same "mutable order the render layer reads" pattern
  `attribute_order` established) and `Region2ListWidget.reorder_parts` /
  `Region2HierarchyModel.reorder_roots` (in-place, **not** a
  `load_score_structure` rebuild). Persisted per-score via
  `ScoreConfig.part_order`, best-effort: an unknown part_id is ignored; a known
  one missing from the saved order keeps its relative position, appended after
  every explicitly-ordered part.

### File > Recent Files

`AppSettings.recent_files`/`add_recent_file`/`MAX_RECENT_FILES = 8` — a **global**
(not per-score) most-recent-first list, no duplicates, populated on every
successful load via `_on_score_loaded` and rebuilt into the submenu
(`_refresh_recent_files_menu`) on startup and after each change. Each item reads
`"<filename> (<folder>)"` (filename first — the name is what the user
recognises), with `&` to `&&` on the whole string so a real filename containing
one isn't eaten as a QAction mnemonic.

Gated on `os.path.exists(music_data.file_path)`, which naturally excludes a live
UG URL import's synthetic slug without special-casing `is_ug`.

**Gotcha:** the terminology-language toggle used to call
`app_settings.save(AppSettings(uk_terms=uk_terms))` — a fresh dataclass literal —
which would silently wipe `recent_files` on every UK/US switch. It is now
load-mutate-save, the same reasoning `add_recent_file` follows.

File > Open Example Score... was removed from the File menu (the user's request);
the bundled `examples/` packaging step is untouched.

---

## `main_window.py` — the shell

A 2-row, 6-column `QGridLayout` (column spans keep both rows aligned under one
shared grid despite the uneven 2-then-3 region count per row). Row 1: region 1 =
score info, region 2 = parts/staves/voices. Row 2: region 3 = note list at the
cursor, region 4 = note attributes for the *selected* notes, region 5 = the
Performance region. Window title is `"Recall Score"`, or
`"<filename> - Recall Score"` once a file is loaded. The `&Edit` menu's "Open
Local Folder" / "Clear Preferences for <filename>" / "Performance Report..." are
the extent of that menu.

Most of its methods are **one-line delegators**, plus read-only properties
(`_music_data`, `sequencer`, `synth`, `_uk_terms`, `_load_thread`,
`_last_focused_region`). That is deliberate: it is the stable API the region
widgets call through `window()` and the tests drive, so `MainWindow` is a facade
over the controllers. Adding a method here is only right if it is wiring.

**`_on_score_loaded` stays in the shell** because it is pure cross-controller
orchestration, and **its order is load-bearing**: the saved config must reach
`MusicData` before the regions render, and Region 2's per-node toggles must be in
effect before the first audition, or the opening chord includes voices the user
had switched off.

---

## `persistence/` (Phase G, Ref 27)

Qt-aware I/O only.

**The `ScoreConfig` dataclass itself lives in `models/score_config_data.py`.**
`MusicData` imports it, and importing anything from `persistence/score_config.py`
(which uses `QStandardPaths`) would have dragged the whole of Qt into `models/`,
silently breaking the "models/ stays Qt-free" invariant that
`main_window.detect_default_uk_terms()`'s placement depends on.
`persistence.score_config` re-exports `ScoreConfig`, so import sites are
unchanged; the JSON key codecs stayed in `persistence/` (spelling a tuple key in
a file is serialisation, not data shape). `test_models_package_does_not_import_qt`
guards it **in a subprocess** — the test session loads PySide6 via conftest
first, so in-process `sys.modules` proves nothing.

* **`app_settings.py`** (`AppSettings`) — a single **global** file
  (`load()`/`save()`) for preferences independent of any score.
* **`score_config.py`** (`ScoreConfig`, `path_for`/`load_for`/`save`/
  `delete_for`) — **per-file**, keyed by the music file's own basename plus
  extension only (`"Chessel Duet.mxl.rsc"`), **never by its folder**, so the user
  can move the file and the same config is found again.

Both live under `QStandardPaths.AppLocalDataLocation` (`main.py` sets
`QApplication.setApplicationName("Recall Score")`).

**`apply_config` is best-effort by construction** —
`voice_display_attributes`/`attribute_order` are filtered against the freshly-
loaded score's own known voices/attribute keys, so a saved entry with nothing
left to match is silently dropped rather than rejecting the whole config.

`MainWindow` calls `_save_current_score_config()` right before swapping in a new
file and again in `closeEvent` — not on every individual toggle.

Tests get an isolated `tmp_path`-based store via the autouse
`_isolate_persistence` fixture, same reasoning as the audio-blocking fixture:
without it, tests would read/write the real machine's `%LOCALAPPDATA%`.

### `parts_off`/`staves_off`/`voices_off` are OFF-lists, not ON-lists

Each is that node's **own** toggle state, independent of its ancestors —
deliberately NOT the ancestor-gated "effectively active" set
`get_active_voice_tuples()` computes for Ref 7's live filtering.

**Why:** switching a part off with a sub-voice still individually on, then
reloading, used to bring that sub-voice back off too, because only the flattened,
gated set was ever persisted — there was no way to tell "individually off" apart
from "merely hidden because its part is off".

`Region2HierarchyModel.get_off_node_keys()`/`apply_off_node_keys()` are the
lossless, ungated read/write of all three levels and are the real save/restore
path. `MusicData.export_config`/`apply_config` only fill in
`voice_display_attributes`/`attribute_order`/`metronome_enabled`/
`position_announcer_enabled` plus a best-effort `voices_off` of their own
(derived from `active_voice_filter`, for standalone/test use with no Region 2
widget). `MainWindow._save_current_score_config` overwrites that derived
`voices_off` and fills in `parts_off`/`staves_off` from
`region_2.model_manager.get_off_node_keys()`; `_on_score_loaded` restores them via
`apply_off_node_keys` (whose `refresh_list()` propagates the result to
`MusicData.active_voice_filter` through the same `filter_changed` signal a live
toggle uses).

---

## Timeline model

The timeline is a flat, sorted list of `EventSlice` — one entry per distinct
`(measure, offset_in_quarters)` with at least one sounding note. **Rests are
skipped, so navigation lands only on attacks.** `active_event_index` is the
cursor; `move_timeline_left/right` return `bool` (False at the boundaries).

`TimelineBuilder.build()` is a third hand-rolled `ElementTree` pass, separate
from `MusicXMLReader`. music21's stream is stored on `MusicData.score` but is
**not** the source of truth for notes — the DOM walk is, because it handles
`<backup>`/`<forward>` offsets, `<chord>` grouping, and `notations/technical`
string/fret data explicitly.

### Parser conventions (spec requirements)

* **Pickup bars** are detected by `implicit="yes"` or by measure 1's staff-1
  content summing to less than a full bar. When present, every measure number
  shifts down by one, so the pickup is measure **0** and the first full bar is
  **1**. Pickup notes get beat positions placing them at the *end* of the
  notional bar.
* **Beat positions and durations are relative to the time-signature
  denominator**, not to quarter notes. `beat_unit_quarter_len = 4.0 /
  denominator`; a quarter note is `ts_duration` 1.0 in 4/4 but 2.0 in 7/8.
  `NoteData.quarter_length` is kept separately for playback timing.
* **`notations/technical` and `notations/articulations`/`ornaments` children can
  repeat on one note** — e.g. a rasgueado marks one note with three `<pluck>`
  children (p/i/m/a). **Always read them with `.findall()`, never `.find()`** —
  `.find()` silently returns only the first match and drops the rest (a
  real-world bug caught against a live MuseScore export; fixture
  `multi_value_technical.musicxml`).

### Grace notes

`<grace>` notes carry no `<duration>`, so `_MeasureOffsetWalker.step()` never
advances `offset_divs` past one — a grace note landed at the exact same
`(measure, offset)` as the note it decorates and rendered as a phantom extra
chord tone (a real acciaccatura showing "A, B" instead of "A grace B").

`TimelineBuilder.build()` buffers one or more consecutive grace notes per
`(staff, voice)` in `pending_grace` (reset per measure, same convention as
`pending_dynamics`) and attaches them to the next non-grace note's
`NoteData.grace_notes` (a `List[GraceNote]`) instead of bucketing them as their
own slice — **a grace note never gets an `EventSlice`/row of its own.** A
trailing, unresolved grace note (untested by any real file) is flushed as an
ordinary standalone note at measure end rather than dropped.

`slash="yes"` (acciaccatura) vs. absent/`"no"` (appoggiatura) is captured on
`GraceNote.slash` but **realized identically for now** — both just ring briefly
before the main note; true appoggiatura time-stealing is unmodelled.

`_note_attribute_pairs`'s `"step"` value becomes `"A grace B"` (the main note's
step name, the literal word "grace", then the grace step names comma-joined)
whenever `grace_notes` is set — shared by Regions 3 and 4 since both read that
same pair.

**Playback:** `get_grace_note_events_for_indices`/`get_grace_note_events_at_index`
mirror `get_playback_events_for_indices` (grouped by part, `(channel, program,
pitches)`, no `duration_ms`) but are a **separate side channel**, not merged into
the main pitch list — merging is what caused the stacking.
`sound_events` routes to `SynthEngine.play_chord_with_grace` whenever
`grace_events` is non-empty; that sounds the grace note(s) immediately for
`audio/grace_note_schedule.effective_grace_duration_ms`'s clamped duration
(default 60 ms, **capped to half the shortest main note's own `duration_ms`** so
a fast tempo can't have the pre-note outlast what it decorates) via the same
one-QTimer-per-pending-attack shape as `play_strum_pattern`
(`_pending_grace_timers`, cancelled by `stop_all_notes()`), then fires the main
chord on a delay via `play_chord(..., retrigger=False)`.

MusicXML only: GP has its own native grace-note concept and MIDI has none at all
(a grace note is indistinguishable from an ordinary very short note there).

### Playback events

GM programs are **1-indexed in the model** (25 = nylon guitar, from MusicXML
`<midi-program>`) and **0-indexed on the wire** —
`get_playback_events_for_indices` does the `-1` conversion per part, so **don't
convert twice**.

Each part gets its own MIDI channel — `get_channel_for_part` returns the part's
index in `parts_info`, unmodified — so a chord spanning two parts plays both
instruments instead of collapsing onto `parts_info[0]`'s program.
`SynthEngine.play_chord` / `NullSynth.play_chord` take the resulting
`(channel, program, midi_notes, duration_ms)` groups and sound them together.

There is no skip list and no wrap: every `RESERVED_CHANNELS` entry sits at or
above `MAX_PARTS` (250), and `ScoreSession._on_loaded` refuses any score whose
`parts_info` (synthetic Chords/Lyrics parts included, since each takes a channel)
exceeds `MAX_PARTS` — emitting `load_failed` with an accessible message and
leaving the previous score open — so a part index is always a free, unreserved
channel.

**`duration_ms` is per-group, not per-slice.** Each part's duration comes from the
`max` `quarter_length` of *that part's* notes at this slice, not from
`EventSlice.quarter_length` (which is `min()` across every note from **every**
part). A slice-wide duration meant one part's short note clamped every other part
sounding at the same instant. `play_chord` schedules note-off with one
independent `QTimer` per group so this holds even across a single call with mixed
lengths.

---

## Performance markings (Ref 29)

### Where spans come from

Repeat/ending spans and barline-style points come out of
**`TimelineBuilder._scan_first_part`**, one walk of `root.find("part")` that also
produces `measure_start_quarters`, each measure's `(ts_num, ts_den, fifths)`, and
`tempo_changes`, returned together as a `_FirstPartScan`. This consolidated four
separate methods that each re-walked the same measures with their own copy of the
measure-number parse and (for three of them) their own offset walker — four
chances for the pickup/offset handling to drift apart.

**Reading from the first part only is the deliberate "structural, not per-voice"
convention** (`_detect_pickup` does the same): time signatures, tempo markings and
barlines are score-wide properties.

**Hairpins are per-part, not first-part-only.** `<direction-type>/<wedge>` is
collected in the per-part walk (`_step_wedge`, called from `_handle_direction`),
because a wedge on any staff of any part must be reported —
`examples/pachelbels-canon-in-d-string-quartet.mxl` has 154 wedges across all 6
parts, of which the old first-part-only scan saw 18.

`_PartState.open_wedges` is keyed `(staff, number)` and each value is a **stack**
(not the single most-recent-wins slot `open_direction_spans` uses): a long hairpin
with shorter ones nested inside it is a real notation concept, so a
`<wedge type="stop">` closes the innermost first. Nested pedals/dashes are not a
thing, so those stay single-slot.

A `stop` with an empty stack emits `HairpinSpan(kind="", start_known=False)` (the
kind of a bare stop is unknowable); a wedge still open when its part ends is
flushed by `_flush_open_wedges` with `end_known=False`. Both synthetic positions
exist only so containment / Ctrl+End resolve — **the `*_known` flags are what the
wording keys off** ("no start marked in the file" / "no end marked in the file").
`self.hairpin_spans` is sorted by `start_quarters_from_start` at the end of
`build()` so the multi-part collection is chronological.

Plain-text `<words>` dynamics/tempo instructions ("cresc.", "rall.") are
classified in `_handle_direction` via `models/vocabulary.py`'s
`dynamics_instruction_kind`/`tempo_instruction_label` (**narrow whole-text
allow-lists, never a substring sweep**) and emitted as point `DirectionMark`s
(`kind="dynamics_word"`/`"tempo_word"`) — the same word still stays a Stave Text
event too (per-note reading vs. score overview).

`<barline>/<repeat direction="forward"|"backward">` pairs are tracked with a
single "currently open forward repeat" slot (most-recent-wins on an unclosed
second forward — nested repeat barlines aren't a real notation concept), and
`<barline>/<ending number type="start"|"stop"|"discontinue">` is tracked per open
number. A backward repeat with no preceding forward defaults its start to measure
1 (the standard reading of an unmarked opening repeat; untested by any real file,
only by `tests/fixtures/unmatched_backward_repeat.musicxml`).

Spans populate `MusicData.repeat_spans`/`ending_spans`/`hairpin_spans` as
**side-channel outputs**, the same pattern as `tempo_changes` — **not** a
per-`EventSlice` field like `time_sig`/`key_fifths`, since spans are rare, not "in
effect at literally every slice". Repeat/ending containment is a plain
measure-number range check (barlines only occur at measure boundaries); hairpin
containment compares `EventSlice.quarters_from_start` against the span's
quarters, since a `<wedge>` can start/stop mid-measure.

`MusicData.total_measures` (from `max(measure_start_quarters.keys())`) is the
whole-score bar count — deliberately **not** derived from `timeline_slices`,
which would undercount a trailing all-rest measure.

### Region 5 rows

`MusicData.get_performance_region_rows(index=None)` resolves the target slice
(default the cursor) and returns two `PerformanceRegionRow`s per active span — a
start line and an end line, repeats then endings then hairpins, each in span-list
order. **That order is stable and load-bearing**: `MainWindow._refresh_region_5`
diffs the label list.

Row wording follows one generic `"<thing> start"`/`"<thing> end"` pattern
throughout (user-requested, not `"Start <thing>"`) — `"Repeat start: bar 2"`,
`"Ending 1 start"`, `"Crescendo start"`. Wording goes through
`vocabulary.bar_word(uk_terms)`, **never a hardcoded "bar"/"measure" literal** —
that is a dialect choice, not a fixed pick.

**Hairpin rows state the full range** so one row read alone conveys it —
`"Crescendo start: bar 1 beat 3, to bar 2 beat 2"` — with each endpoint via
`_bar_beat_label` (beat suffix only when not on the downbeat). An unmatched wedge
gets a single row: `"Diminuendo start: bar 23, no end marked in the file"` (or the
mirror; `kind==""` reads as "Hairpin"). Hairpin rows are part-name-prefixed only
when more than one part has a hairpin (`MusicData._marking_part_prefix`).
Repeat/ending rows never name a beat, since barlines occur only at measure
boundaries by construction.

**Jump targets.** `slice_index_at_or_after_quarters(quarters)` and
`last_visible_event_index_of_measure(measure)` resolve Ctrl+Home/Ctrl+End. A
hairpin row's `jump_target_quarters` is set (a wedge can start/stop mid-measure)
so it uses the quarters lookup; a repeat/ending row's is `None`, resolved via the
measure lookup instead — Ctrl+Home uses `first_visible_event_index_of_measure`,
Ctrl+End uses `last_visible_event_index_of_measure` (the user's decision: "the end
of it" means the *last* sounding note of the end bar, not the first).

**One-shot rows.** A time-signature or immediate/point tempo change landing
exactly on the resolved slice emits a single row — no start/end pair. It compares
`EventSlice.time_sig` and the raw `_tempo_change_at(index)` tuple (**not** the
divided display float, to avoid a float-precision false positive, and
deliberately **not** `effective_tempo_bpm`/`playback_tempo_display_bpm`, which
reflect the user's absolute playback-tempo setting and would make changing it look
like a score change) against the immediately preceding slice in whichever list the
resolved slice came from. **Never fires at index 0** — the opening signature/tempo
is already in Region 1 and the status bar every load. It reuses hairpins'
`jump_target_quarters` mechanism as-is; both Ctrl+Home/Ctrl+End resolve to the
row's own position, a harmless no-op.

Accelerando/ritardando (a span, like a hairpin) is explicitly out of scope —
nothing parses it yet, and it needs its own investigation into how the user's
scores actually encode it.

### The refresh choke point and the audio cue

`MainWindow._refresh_region_5` is hooked into `_update_timeline_views`
(unconditional of `play_all`) rather than scattered across every navigation
method — every path that moves `active_event_index` already funnels through
there. It diffs the new row-label list against
`self._last_performance_row_labels` and skips the rebuild when unchanged, so
Region 5's focus/selection isn't reset on every step while the cursor stays
inside the same span(s).

**GOTCHA:** that sentinel must start as `None`, not `[]`. Starting at `[]` made
the very first render (an empty opening position, whose rows are also `[]`)
compare equal and get silently skipped, leaving Region 5 with no items at all
rather than its documented "None" placeholder row.

**Ordering is load-bearing:** `_update_timeline_views` calls
`_play_selected_region_3_notes()` (when `play_all`) **before** `_refresh_region_5()`.
`_play_selected_region_3_notes` calls `play_chord(events)` with the default
`retrigger=True`, which calls `stop_all_notes()` first — with the cue fired first,
that `stop_all_notes()` landed a fraction of a second later and cut the
just-started cue off. Playback never hit this because `_on_sequencer_step` calls
`_update_timeline_views(play_all=False)`. Sound the notes first, then fire the cue
on its own untouched reserved channel.

### Performance Report

`MusicData.get_performance_report_lines()` (Edit > Performance Report...,
`widgets/performance_report_dialog.py`) is a separate, read-only, whole-score
summary. It reuses `get_region_1_data()` **wholesale**, not cherry-picked keys —
`credits_dict`'s keys come from each file's own `<credit-type>` text and aren't
guaranteed to match a fixed name like "Title". It counts notes per instrument
from `_real_timeline_slices` (**the whole score, ignoring the current Region 2
filter** — the report describes the piece, not the current filtered view).

Its **Dynamics** section is one chronological list merging hairpins (part-prefixed),
plain-text `dynamics_word` point marks, and point `<dynamics>` marks; an unmatched
hairpin carries the same "no start/end marked in the file" wording. A
dashed/bracket line drawn under a "cresc." is reported **separately** under
`Dashed lines:` / `Bracket lines:` **as written** — two things in the file, two
lines.

**No jump-to-location navigation from the report** — an explicit scope cut from
the user, unlike Region 5's own Ctrl+Home/Ctrl+End.

### The helper-driven shape (S7 / S17)

Both methods now live in **`models/performance_rows.py`** (`PerformanceRows`, a
`MusicData` collaborator — S17), reached through one-line delegators. They read
everything (`section_spans`/`repeat_spans`/`hairpin_spans`/`direction_marks`/…
and the `_bar_beat_label` / `_marking_part_prefix` / `_tempo_change_at` /
`get_region_1_data` helpers) off `self.data`.

`get_performance_region_rows` was ~380 lines of ~17 near-identical
`for span/mark ... if it matches: rows.append(...)` blocks, and
`get_performance_report_lines` a second ~210-line method over the same data. Both
are now driven by small nested helpers, with the genuinely irregular cases left as
explicit branches:

* Region rows: `_pair(spans, contained, start_label, end_label, *,
  jump_quarters=False)` covers the section/repeat/ending/dashed-line start+end
  blocks; `_point(marks, label, *, kind=None, jump="slice"|"measure"|"mark")`
  covers the ~12 one-shot point rows. The hairpin 3-way completeness branch is
  one label decision building a short `(label, jump_measure, jump_quarters)`
  list, then a single append loop; the key/time/tempo diff stays explicit code.
* The nested `_dir_prefix` no longer rebuilds `direction_spans + direction_marks`
  per call inside a loop over `direction_spans` (quadratic in shape) —
  `_dir_kind_pids` (a `kind -> [part_id]` dict) is built once.
* Report: `_tally(header, items, line_fn, *, omit_if_empty=False)` is the "count
  line then one line per item" shape; `omit_if_empty` reproduces the sections
  hand-written with an `if items:` guard (Sections, Rehearsal marks, Tempo
  instructions). The Dynamics (merged/sorted) and Pedal (two-list count) sections
  stay explicit.

**Row/line order is unchanged and still load-bearing.**

---

## Selection-driven regions

Region 3 is `ExtendedSelection` and defaults to selecting every note in the
current slice (`Ctrl+A` reselects all). **Regions 4 and audio follow the
selection, not the slice:** `get_region_4_data_for_indices(indices)` and
`get_midi_notes_for_indices(indices)` take Region 3's selected rows.

`RegionPresenter.update_timeline_views(play_all=...)` blocks Region 3's signals
during a rebuild to avoid audition storms, then fires playback once.

`get_region_3_data()` and all three indices-taking accessors read through
`MusicData._visible_notes()` first, which filters the current slice's notes by
`active_voice_filter` — the `(part_id, staff, voice)` set Region 2 maintains (Ref
7) — so **a selected row index always means the same note in Region 3, Region 4
and playback** even when some notes are hidden. Keep view code reading through
these accessors rather than reaching into `timeline_slices`.

### The `setCurrentRow` gotcha

After any Region 3 rebuild that calls `selectAll()`, also call
`region_3.setCurrentRow(0, QItemSelectionModel.SelectionFlag.NoUpdate)`
**outside** the `blockSignals` window.

`selectAll()` marks rows selected but deliberately leaves the view's own
"current" item untouched, and Qt's accessibility bridge needs a definite current
item to tell NVDA which note to announce — with several notes selected NVDA still
gets a selection-changed announcement, but with exactly one note there was nothing
pointing at it.

**The explicit `NoUpdate` flag is required.** The plain one-arg
`setCurrentRow(0)` was believed to default to `NoUpdate` and leave `selectAll()`'s
selection alone, but in this PySide6 version it doesn't: it collapses the
selection down to just row 0, silently turning "moving onto a chord sounds every
note in it" into "only the first note sounds". Always pass the flag explicitly.

### The attribute system (Ref 15 AC4)

Region 3's row text and Region 4's rows both go through an attribute system
beyond the bare note name, split into a WHICH half and an ORDER half.

**WHICH:** `voice_display_attributes` (keyed by `(part_id, staff, voice)`) is
which optional keys (`string`, `fret`, `dynamic`, `articulation`, `fingering`,
`pluck`, ...) are switched on per voice — defaulting to just `{"step"}`.
`_note_attribute_pairs(note)` returns only the keys that note actually has a
value for, so a key renders **only when it is both toggled on for that voice and
present on the note**; absence isn't a bug, it's the mechanism.
`set_display_attribute(key, scope, notes, add)` fans a toggle out across
`"voice"/"stave"/"part"/"score"` scope, driven by Region 4's context menu.

**ORDER:** `MusicData.attribute_order` is the live, mutable, per-instance
rendering order both `_format_note_for_region_3` and `_region_4_rows` iterate.
`DISPLAY_ATTRIBUTE_ORDER` is only the fixed *default* every fresh `MusicData`
starts from, **not what actually renders**. `move_attribute_order(key, up,
within=...)` reorders it; `attribute_keys_for_voices(voice_tuples)` scans the
whole score (not just the current slice) for which keys are relevant to a scope.

`attribute_order`, unlike `uk_terms`, is **per-score** — persisted via
`persistence/score_config.py` and restored in `_on_score_loaded` through
`apply_config`; a fresh `MusicData` with no saved config falls back to
`DISPLAY_ATTRIBUTE_ORDER`.

Options > Reorder Attributes... (`widgets/attribute_order_dialog.py`) is the UI:
scoped to whichever part/staff/voice is selected in Region 2, Move Up/Move Down
(Alt+U/Alt+D) move the selected attribute live. It deliberately doesn't duplicate
the add/remove menu.

**Adding a new optional per-note attribute needs no UI work at all** — append it
to `DISPLAY_ATTRIBUTE_ORDER` and `_note_attribute_pairs`, and the toggle menu,
scope fan-out, ordering, and omit-if-absent rendering all pick it up
automatically.

---

## Comprehensive Find (P0-P6)

Navigation > Find... (`Ctrl+F`, `widgets/find_dialog.py`; Alt+Right/Alt+Left step
next/previous from anywhere in the window via `NavigationController`).

**Governing principle: anything in the score that is not a plain note, a rest or
a lyric is findable** — and that is structural, not a list we keep extending. Two
mechanisms:

* **Attribute target** — a per-note fact. A new `Optional[str]` field on
  `NoteData`, populated in the parser, emitted from
  `NoteRenderer.note_attribute_pairs`, appended to `DISPLAY_ATTRIBUTE_ORDER`.
  Find, Region 3/4 rendering, the toggle menu, Reorder Attributes and `.rsc`
  persistence pick it up for free. Keys: `tie`, `slur`, `tuplet`, `fermata`,
  `arpeggio` (chord notes only), `accidental` (cautionary/editorial only),
  `technique`, `glissando`, `grace`, `other_notation`, `chord_symbol`,
  `chord_diagram`. New fields default `None`, so the MIDI/GP/UG builders are
  unaffected except where they opt in (GP's `tied`/`slide` fill
  `tie`/`glissando`).
* **Marking target** — a structural fact not attached to a timeline note. A model
  in `models/`, populated in `TimelineBuilder`, published through
  `models/timeline_build.py`, a `MARKING_KINDS` entry plus a branch in
  `FindIndex.candidate_indices_for_target`, and a Region 5 row plus Performance
  Report line. Kinds: `DirectionSpan`/`DirectionMark` (pedal, octave-shift,
  rehearsal, dashed/bracket lines, `other_direction` catch-all), `BarlineMark`
  (double/other, **never** the final `light-heavy`), `ClefChangeMark`,
  `MeasureStyleMark`. These lists default empty in `TimelineBuild`, so
  non-MusicXML formats show none of them.

**Value-level Find.** `FindTarget` carries an optional `value`. For the keys in
`find_target.VALUE_EXPANDED_KEYS` (an explicit allow-list — `articulation`,
`technique`, `dynamic`, `accidental`, `tie`, `slur`, `glissando`, `tuplet`,
`chord symbol`, `other notation`) the dialog offers an "any" row plus one row per
distinct value found; every other key stays a single "any" row however many
values it holds. **Comma-joined multi-value keys are matched by membership over
the split list, never `==`.** The occurrence cache is keyed `(key, value)` and
dropped by `invalidate_cache()` from `MusicData._invalidate_visibility_cache`.

**Occurrence counts.** Every dialog row ends with `"N occurrences"` /
`"1 occurrence"` (`find_target.occurrence_label`). A count is
`len(sorted_candidate_indices(target))` — timeline *positions*, so a chord of
three staccato notes counts once — computed via the cached path in
`available_targets_with_counts()`, not a second scan. **Attribute counts respect
the Region 2 voice filter; marking counts don't** (markings are structural, like
Region 5). Documented in the user guide 5.7.

**Two catch-alls are the completeness guarantee.** `_read_notations` keeps a
`_RECOGNISED_NOTATION_TAGS` frozenset; any other `<notations>` child becomes
`other_notation` = `tag.replace("-", " ")`. `_handle_direction` does the same via
`_RECOGNISED_DIRECTION_TYPE_TAGS` to an `other_direction` `DirectionMark`. Both
are presence-filtered, so a score with none shows nothing extra; both are covered
by tests feeding an invented element name.

**Not made audible** (standing decision, unchanged): ties, arpeggios, ornaments,
pedal and octave shift stay label-only; `<octave-shift>` does not transpose
playback. See Known gaps in `CLAUDE.md`.

**Instrument transposition is the exception** — `<attributes>/<transpose>` for a
B♭ trumpet, F horn, double bass at `<octave-change>-1`, … *is* applied, but only
to `midi_pitch` (playback + Region 4's `midi` row). `step_name`/`octave` and all
region text stay as written, so the note list shows what is on the player's part
while the MIDI sounds in concert pitch with it. See `docs/parsers.md` →
Transposing instruments.
