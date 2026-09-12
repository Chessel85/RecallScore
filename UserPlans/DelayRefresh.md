# Plan: Delay Refresh (screen-reader pacing for playback)

Implementation plan for Sonnet. Read `CLAUDE.md` and `docs/architecture.md`
before starting. Work through the tasks in order; each is separately testable
and separately committable. **Two live-testing checkpoints are marked below —
stop at each and hand back to the user before carrying on.** Docs come last,
after both checkpoints pass.

## Why this exists (the user's own words)

> This feature is to allow the screen reader to announce the note name before
> it is heard. Or to allow the user to remove any conflict between hearing a
> note and the screen reader.

That single sentence settles every design question below. The point is not
"delay a redraw"; it is to move the screen reader's speech and the sounding
note apart in time, in either direction:

* **Refresh off** — the regions and status bar do not change at all while
  playback runs, so NVDA says nothing. Text catches up on pause or stop.
* **Negative delay** (down to −1 s) — the text refreshes *ahead* of the music,
  so NVDA announces "F sharp" and *then* the note sounds. The music is what
  moves: playback is held back by that amount, including on initial play.
* **Positive delay** (up to +1 s) — the text refreshes *after* the note has
  sounded, so the note is heard clean and the announcement follows it.

Accessibility is the product (see `CLAUDE.md`), and this is a pure
accessibility feature. When a judgement call comes up that this plan does not
cover, decide it by asking which option keeps speech and sound from colliding.

## Where it plugs in

Three facts about the existing code shape the whole design. Verify each still
holds before you start; if any has moved, stop and say so rather than adapting
around it.

1. Every region/status refresh funnels through two signals wired in
   `main_window.py:510-518`:
   `playback.cursor_moved` → `presenter.update_timeline_views` (Regions 3/4/5
   plus the status bar), and `playback.playback_state_changed` →
   `presenter.update_playback_status_field`. Manual navigation reaches the same
   presenter method by a *separate* path (`navigation.position_changed`) — that
   path must stay ungated. Only playback is ever delayed.
2. During playback the emitter is `PlaybackController._on_sequencer_step`
   (`controllers/playback_controller.py:1050`), which sets
   `music_data.active_event_index = index` and then emits `cursor_moved`.
3. `Sequencer._sound_current_step` (`audio/sequencer.py:188-239`) sounds the
   notes, then the metronome click, then the position announcer, and **only
   then** emits `step_played`. That ordering is what makes a negative delay
   cheap to implement.

## The chosen architecture — and why

**A positive delay holds the *text* back. A negative delay holds the *music*
back.** Two small deferrals, each one timer, neither duplicating the
sequencer's schedule.

The rejected alternative was to keep one clock and compute a lookahead — at
each step, work out the gap to the next step and refresh the text
`gap − delay` ms later. That needs the sequencer to expose its next index and
its `_delay_ms_to` result, it is only approximate when a note is shorter than
the lead, and it leaves the metronome click and the spoken position announcer
travelling with the *text* rather than with the music, which is backwards.
Holding the audio back inside `_sound_current_step` shifts notes, click and
announcer together as one stream, and gives "the music is delayed on initial
play" for free rather than as a special case.

Two consequences to keep in mind while implementing:

* The lag applies to `music_data.active_event_index`, not just to the widget
  text. Region 3's rows are derived from that index, so delaying only the
  redraw would paint the wrong row. Any pending cursor move is **flushed** on
  pause, on stop, and on manual navigation.
* The Playing/Paused/Stopped status field keeps updating live, always. It
  changes only at transport events, so it cannot babble, and suppressing it
  would make pausing silent to a screen reader — the opposite of the point.

---

## Task 1 — `models/refresh_settings.py` (new)

stdlib-only and Qt-free like every other `models/` module (guarded by
`test_models_package_does_not_import_qt`). Model it on
`models/play_settings.py`.

```python
MIN_REFRESH_DELAY_MS = -1000
MAX_REFRESH_DELAY_MS = 1000

@dataclass
class RefreshSettings:
    refresh_during_playback: bool = True
    delay_ms: int = 0
```

With `from_dict(data)` (tolerating `None` and junk, as `PlaySettings.from_dict`
does) and `copy()`. Clamp `delay_ms` into the range on construction — a
hand-edited settings file must not be able to hold playback back by a minute.

Milliseconds in the model, seconds in the dialog. The JSON stays integral and
the timer arithmetic needs no rounding.

Defaults are today's behaviour exactly: refresh on, no delay. A user who never
opens the dialog must notice nothing.

### Test

`tests/models/test_refresh_settings.py` — defaults, clamping at both ends,
`from_dict(None)`, `from_dict` with a string where a number belongs.

---

## Task 2 — `persistence/app_settings.py`

Add `refresh: RefreshSettings = field(default_factory=RefreshSettings)` to
`AppSettings`, read it in `load()` via `RefreshSettings.from_dict(data.get("refresh"))`,
and add `set_refresh_settings(settings)` following the **load-mutate-save**
pattern the file already documents at length — constructing a fresh
`AppSettings` here would silently wipe `uk_terms` and the Recent Files list.

Global, not per-score, for the same reason `play` and `tuner` are: this is a
property of how the user hears things, not of the piece.

Extend the docstring paragraph that explains why `play` is global to mention
`refresh` alongside it.

---

## Task 3 — `controllers/refresh_delay_controller.py` (new)

The gate. It owns the settings and sits between `playback.cursor_moved` and
`presenter.update_timeline_views`. **It touches no widgets** (invariant 6 —
`RegionPresenter` is the only controller allowed to).

```
class RefreshDelayController(QObject):
    refresh_requested = Signal(bool)   # play_all, forwarded from cursor_moved
```

Constructor takes `session` and an injectable `timer=None` (build a single-shot
`QTimer` when absent), exactly as `PlaybackController.__init__` does — tests
must drive this without the clock.

State: `_settings: RefreshSettings`, `_pending_index: Optional[int]`.

Methods:

* `set_settings(settings)` — stores a copy, and `flush()`es first so changing
  the setting mid-playback cannot strand a pending refresh.
* `settings` property — read-only copy, for the dialog and for persistence.
* `set_refresh_during_playback(enabled) -> bool` — the Ctrl+H toggle's entry
  point. Returns the new state so the caller can announce it.
* `handle_cursor_moved(index, play_all, is_playing)` — the whole decision:
  * not playing, **or** refresh on with `delay_ms <= 0` → apply immediately
    (set `active_event_index`, emit `refresh_requested`). This is today's path
    and must stay byte-for-byte equivalent in effect.
  * refresh **off** → record `_pending_index`, emit nothing.
  * refresh on, `delay_ms > 0` → record `_pending_index`, start the timer for
    `delay_ms`; on timeout apply.
  * A negative `delay_ms` needs nothing here — the music is what moves
    (Task 6), so the text is already early relative to what is heard.
* `flush()` — apply `_pending_index` now, stop the timer, clear the pending
  state. No-op when nothing is pending.
* `cancel()` — stop the timer and drop `_pending_index` without applying it.

Applying means: `self.session.music_data.active_event_index = index` then
`self.refresh_requested.emit(play_all)`. Guard on `music_data` being falsy, as
every other controller does.

### Test — `tests/test_refresh_delay_controller.py`

Drive it with a fake timer (copy the pattern from the existing playback tests).

* refresh on, delay 0, playing → emits synchronously, cursor moves.
* not playing → emits synchronously regardless of the settings (manual
  navigation is never gated).
* refresh off, playing → no emission, cursor unchanged; then `flush()` emits
  once with the last index seen.
* refresh on, delay 250 ms → nothing until the timer fires, then one emission.
* two steps inside one delay window → the *later* index wins, one emission
  (the pending slot is a slot, not a queue).
* `cancel()` then `flush()` → nothing emitted.

---

## Task 4 — wire the gate into `PlaybackController` and `MainWindow`

In `controllers/playback_controller.py`:

* `_on_sequencer_step` stops writing `active_event_index` and emitting
  directly. Keep its two existing early-return guards (the `update_cursor` /
  `looping_run` test) unchanged — they decide *whether* this step tracks at all,
  which is separate from *when* it lands. Hand the index to the gate instead.
  The cleanest seam without giving `PlaybackController` a reference to another
  controller: keep emitting `cursor_moved`, but emit it with the index, and let
  `MainWindow` route that signal into the gate. Add a second signal
  `playback_cursor_stepped = Signal(int, bool)` rather than changing
  `cursor_moved`'s signature — `cursor_moved` is emitted from six other places
  (stop, finish, loop restart) that must stay immediate and ungated.
* `toggle_pause_resume` and `pause_command` call the gate's `flush()` before
  emitting `playback_state_changed`, so pausing lands the text on the true
  position. The docstring at line 1052 already *claims* pause refreshes the
  regions "for free"; with a gate in place that is only true because of this
  call — update the comment to say so.
* `stop()`, `attach_score()` and `detach_score()` call `cancel()`.
* Add an `is_paused` property (a thin read of `self.sequencer`, `False` when the
  sequencer is `None`) — Task 8 needs it.

Since `PlaybackController` must not know about `RefreshDelayController`, give
it a plain optional collaborator slot set by `MainWindow`
(`self.refresh_gate = None`, with every call site guarded), rather than an
import. Follow whichever of the two the existing code already does for a
similar pairing if you find one.

In `main_window.py` `connect_signals()`:

```
self.playback.playback_cursor_stepped.connect(self.refresh_gate.handle_cursor_moved)
self.refresh_gate.refresh_requested.connect(self.presenter.update_timeline_views)
```

`navigation.position_changed` and the other `cursor_moved` emissions keep their
direct connection to the presenter. Also flush the gate on manual navigation so
a keypress mid-playback cannot leave a stale pending index behind it.

### Test

Extend `tests/test_main_window_playback.py` (or wherever the transport tests
live) with an end-to-end: with refresh off, stepping the sequencer leaves
Region 3's row text unchanged; pausing updates it to the stepped position.
Use `tests/support/null_synth.py` — no real engine, per the harness invariants.

---

## Task 5 — the Ctrl+H toggle

`Ctrl+H` is **free** (verified across the whole codebase, and it is not in
`docs/keystrokes.md`).

In `widgets/menu_builder.py`, in `_playback_menu`, just below
`a.play_settings`:

```python
a.refresh_on_playback = self._action(
    "Toggle Refres&h on Playback", self.slots.toggle_refresh_on_playback,
    QKeySequence("Ctrl+H"), checkable=True,
    status_tip="Update the regions and status bar while playback runs",
)
```

Checkable, so a screen reader announces its state on focus — the same pattern
as Toggle Lead-in and Toggle Metronome. Mnemonic on `h`: `P`, `t`, `y`, `i`,
`R`, `u`, `o`, `x` are already taken in that menu, so check the whole menu
before settling on a letter (this menu has a documented history of mnemonic
collisions being fixed one at a time and drifting into the next one).

`MainWindow.toggle_refresh_on_playback()` is wiring: flip the gate's setting,
persist through `app_settings.set_refresh_settings`, keep the action's checked
state in sync, and speak the new state aloud — Ctrl+H is pressed with focus in
the Note region, so the menu tick and the status bar are both invisible to the
user at that moment.

Add `RegionPresenter.announce_refresh_on_playback(enabled)` alongside
`announce_play_mode` (`controllers/region_presenter.py:241`), using
`accessible_announcer.announce`. Wording: `"Refresh on playback on."` /
`"Refresh on playback off."` Keep it short — the user hears the CLI and the app
through NVDA, and a long phrase here is heard on every press.

Also set the action's initial checked state from the loaded settings at
startup, and re-sync it whenever the dialog (Task 7) is accepted. **Do not
store the flag in two places** (invariant 8) — the gate's `RefreshSettings` is
the single source; the action's tick is a view of it.

---

## Task 6 — the negative delay, in `audio/sequencer.py`

This is the half that needs ears, not assertions. Keep it small.

Add `lead_offset_ms: int = 0` as sequencer state, set through `play_from`
(a new keyword argument, defaulting to 0) so an existing caller is unchanged.

In `_sound_current_step`, when `lead_offset_ms == 0`, the body stays **exactly
as it is today** — the synchronous path must not gain a timer hop, both for the
25 ms audition budget and so the fingerprint harnesses see no change. When it
is non-zero:

1. Emit `step_played` first.
2. Defer the audio block — `sound_events(...)`, the metronome click, the
   position announcer — into a single-shot timer of `lead_offset_ms`.

Everything after `step_played.emit` (the `next_playback_index` call, the
retrigger bookkeeping, the measure budget, the timer start) stays on the
original clock. The run's schedule is untouched; the whole audio stream just
sits `lead_offset_ms` later. Note-offs are scheduled by `SynthEngine` relative
to when a note actually starts, so a uniform shift is safe.

The deferral timer must be injectable alongside the existing one, and both
`pause()` and `stop()` must stop it **before** `stop_all_notes()` — otherwise a
pause lands in the gap and the note fires into the silence a moment later.

In `controllers/playback_controller.py`, derive
`lead_offset_ms = max(0, -settings.delay_ms)` from the gate's settings and:

* pass it to every `sequencer.play_from(...)` call on the play path;
* subtract it from the lead-in total in `_start_play_iteration`, so a count-in
  runs straight into the first note instead of leaving an audible gap after the
  last click;
* add it to `loop_tail_pad_ms`, so a loop restart does not clip the shifted
  tail of the last note.

### Test

`tests/audio/test_sequencer.py`:

* with an offset set, `step_played` fires with **no** synth call yet; after the
  injected timer fires, the notes, click and announcer have all sounded
  (`null_synth` records them).
* `pause()` and `stop()` during the gap → nothing ever sounds for that step.
* offset 0 → the synth is called synchronously inside `_sound_current_step`,
  proving the default path did not gain a hop.

---

## ⛔ Checkpoint A — live test before going further

Stop here and hand back to the user. Everything that can be judged by ear is
now in place, and the remaining work (dialog, docs) is cosmetic around it.
Nothing below this line is worth doing if the feel is wrong.

Ask the user to try, with a score loaded and NVDA running:

1. Ctrl+H off, then Space. Does NVDA stay quiet through the whole run? Does the
   text land on the right position when Ctrl+Space pauses, and back at the start
   when Space stops?
2. Ctrl+H on again — is everything exactly as it was before this feature?
3. A negative delay, once Task 7's dialog exists — but if the dialog is not
   built yet, hard-code `RefreshSettings(delay_ms=-400)` at the startup wiring
   for one run and ask whether the note name is heard cleanly *before* the note.
   That is the single question this whole feature exists to answer.

Expect −400 ms or so to be the interesting region; NVDA takes real time to
start speaking. If ±1 s turns out to be the wrong range, that is a one-line
change in Task 1 and much cheaper to make now than after the docs are written.

---

## Task 7 — `widgets/delay_refresh_dialog.py` (new)

Read `docs/dialog_widget_patterns.md` first. Model it on
`widgets/play_settings_dialog.py`, which is the closest existing dialog — a
pure view that edits a working copy and hands it back, with a `QLabel` +
`setBuddy` for every control.

* `QCheckBox` "&Refresh text on playback".
* `QDoubleSpinBox`, buddy label "Refresh &delay (seconds):", range −1.00 to
  1.00, single step 0.05, two decimals, suffix `" seconds"`. Seconds here,
  milliseconds in the model — convert at the boundary, in this class.
* `_update_enabled_states()` greys the spin box out when the tickbox is clear,
  wired to `toggled` and called once in `__init__` — the same shape
  `PlaySettingsDialog` uses for its lead-in spins.
* `showEvent` defers focus with `QTimer.singleShot(0, ...)` to **the tickbox** —
  the literal first widget in tab order. Do not "helpfully" focus the spin box
  instead; the user has been explicit about this, twice.
* `refresh_settings()` returns a `RefreshSettings`. Clamping is the model's
  job, not the dialog's.

Menu entry in `_playback_menu`, below the Ctrl+H toggle:

```python
a.delay_refresh = self._action(
    "&Delay Refresh...", self.slots._show_delay_refresh_dialog,
    QKeySequence("Ctrl+Shift+D"),
    status_tip="Set whether and when the regions refresh during playback",
)
```

`Ctrl+Shift+D` is free (verified). Dialog *construction* stays in `MainWindow`
(tests monkeypatch `main_window.DelayRefreshDialog`); on accept, push the
settings into the gate, persist them, and re-sync the Ctrl+H action's tick.

### Test — `tests/widgets/test_delay_refresh_dialog.py`

Spin box disabled when the tickbox is clear and enabled when set; seconds →
milliseconds round-trip including a negative value; the dialog opens with the
settings it was given.

Plus, in `tests/test_main_window_menus.py`: both actions exist with the right
sequences, and the toggle is checkable.

---

## Task 8 — Escape stops a paused playback

Requested alongside the rest: while playback is paused, Escape reverts to
stopped.

Escape is **already bound** at `main_window.py:360` to
`navigation.clear_pending_digits`. Do **not** add a second `QShortcut` for it —
two `WindowShortcut`s on one sequence are ambiguous and neither fires (the file
says so at length about Space). Replace the existing lambda with a router:

```python
def _on_escape(self):
    """Escape means "cancel the thing in progress". While playback is
    paused that is the pause itself; otherwise it is a half-typed bar
    number."""
    if self.playback.is_paused:
        self.playback.stop()
    else:
        self.navigation.clear_pending_digits()
```

Paused-and-mid-typed-number is not reachable in practice (typing a digit jumps
the cursor), so the ordering above needs no further thought.

In `controllers/shortcut_controller.py`, the Escape reservation (line ~103)
currently reads "type a bar number or loop length". That string is what the
Keyboard Shortcuts dialog shows the user, so amend it — but Escape is shared
with the Enter/Return/digit family in one `add(...)` call, so **split Escape
into its own `add()`** with its own reason rather than rewording the group:
`"cancel a typed bar number, or stop a paused playback"`.

### Test

In `tests/test_main_window_navigation.py` (which already exercises Escape at
line 486): paused → Escape stops; not paused → Escape clears the digit buffer
and does not touch the transport.

---

## ⛔ Checkpoint B — full live test

Hand back again. The feature is complete; only docs remain. Run the full suite
first (`.venv\Scripts\python.exe -m pytest`) and report the result honestly,
then ask the user to exercise:

* the dialog, with a screen reader, tabbing through every control in order;
* the tickbox disabling the spin box;
* Ctrl+H mid-playback (not just while stopped);
* Escape while paused, and Escape with a half-typed bar number;
* a negative delay with a lead-in enabled, checking the count-in still runs
  straight into the first note;
* a negative delay with "loop until stopped", checking the last note is not
  clipped at the restart.

This feature changes `parsers/`-adjacent nothing, so the fingerprint harnesses
are not the gate here — but if any `models/` file was touched beyond the new
one, run `tests/manual/model_fingerprint.py --check` per `CLAUDE.md`.

---

## Task 9 — docs, last

Only after both checkpoints pass.

* `docs/architecture.md` — the new controller, where the gate sits in the
  signal chain, and the "positive delays text, negative delays music" decision
  with its reasoning.
* `docs/keystrokes.md` — Ctrl+H, Ctrl+Shift+D, and Escape's new meaning. Then
  regenerate `docs/keystrokes.html` with the exact pandoc command in
  `docs/packaging.md:112`.
* `docs/release_notes.md` — one entry, in the existing voice.
* **Do not touch `docs/user_guide.md` or `user_guide.html`.** The user asks for
  those explicitly when they want them.
* `wishlist.txt` is the user's own file — never author its content.
