# Performance Indicator cue (Ctrl+C)

Reintroduces the "ding" that used to play whenever performance information
was reached, dropped 2026-09-13 when markings moved into the note list
(commit `e4cfa80`, "Stage 6 of the performance markings plan: structural
changes and the cue"). This is a plan for review, not yet implemented -
see the Open questions section before I start.

## What exists today (background, since this surprised the user)

`audio/performance_cue.py` still exists and still fires - but its trigger
was narrowed by `e4cfa80` to exactly three things: the cursor landing on a
key signature, time signature, or immediate tempo change
(`MusicData.structural_change_labels()` / `has_key_or_time_change_at()`),
checked in `RegionPresenter.refresh_region_5`. It never fires during
playback (see "Why `play_all` alone can't gate this" below) and never fired
for anything else - hairpins, repeats, dynamics, etc. - since those got
their own note-list rows instead. That's why the user hasn't heard it: it's
alive but rare.

## The new feature

Options > **Performance Indicator**, a submenu of three mutually exclusive,
checkable items (same `QActionGroup`-exclusive pattern as the existing
Options > Terminology (UK/US) submenu):

* **Off** - never dings.
* **On except when playing** - dings on arrow/Ctrl-arrow/Go-to-measure
  navigation, not during Play.
* **Always on** - dings during playback too.

Plus a separate, ordinary (non-checkable) Options menu action, **Cycle
Performance Indicator**, shortcut **Ctrl+C** (confirmed unused - not in
`menu_builder.py`, not in `ShortcutController._build_reserved`), which
rotates Off -> On except when playing -> Always on -> Off, updates the
submenu's checked item, and speaks the new state aloud (`accessible_
announcer`, since triggering a bare shortcut doesn't get Qt's native
checkable-menu-item announcement - same reasoning as `toggle_bar_line_
indicator`'s comment). This mirrors "Cycle Play Mode" (Ctrl+L) and "Cycle
Loop Repeat Handling" (Ctrl+R), which are exactly this shape (a fast
keystroke cycling N states with speech) but as flat menu items with no
submenu, because 2-3 states didn't seem to need one. A submenu is new for
a cycle-only setting in this app - flagged as an open question below rather
than silently deciding it.

## What counts as "arriving at a performance indicator"

The literal old trigger ("Region 5's row set changed") doesn't fit any more
- most of what used to only be in Region 5 is now a `MarkingRow` in Region
3's own note list (`models/region3_row.py`), which is where the user is
already reading. The natural modern equivalent:

**Fires whenever the rows `MusicData.get_region_3_rows()` returns for the
new cursor position include at least one `MarkingRow`** (as opposed to only
`NoteRow`s). This one check *replaces* the old narrow structural-change
trigger completely, by user decision (2026-09-22) - they are now the same
mechanism, not two that happen to overlap:

* The old cue-firing code in `refresh_region_5` (`if allow_cue and (md.
  structural_change_labels() or md.has_key_or_time_change_at())`) is
  deleted outright, along with the now-unused `allow_cue` parameter -
  nothing reads `structural_change_labels()`/`has_key_or_time_change_at()`
  for sound any more (only the note-list row and Region 5's own one-shot
  row still do, unchanged). There is exactly one place in the codebase
  that decides whether the performance-indicator sound plays.
* Every marking - including a key/time/tempo change - dings under exactly
  the same two gates: **Ctrl+N** (that marking's category must be on in
  the note list - `structural_changes` included, no exemption) and
  **Ctrl+C** (Performance Indicator must be Always-on, or On-except-when-
  playing outside of playback). Turning "Structural changes" off in the
  note list now silences its ding too, by design - confirmed with the
  user rather than assumed.

## Why `play_all` alone can't gate "On except when playing" / "Always on"

`play_all` (threaded through `position_changed`, `update_timeline_views`,
`refresh_region_5`'s retiring `allow_cue`) is `True` only for a genuine
manual navigation move. It's `False` for THREE different situations that
all currently look identical through that one bool:

1. A real playback step (`PlaybackController` emits `playback_cursor_
   stepped(index, False)`).
2. A non-navigation refresh at the SAME cursor position - Region 2 filter
   toggle, Ctrl+N category toggle, Key Signature override, Reorder/Link
   Parts (all in `score_edit_controller.py` / `region_presenter.py`,
   all calling `update_timeline_views(play_all=False)`).
3. (same bucket as 2) - nothing moved, so nothing was "arrived at".

"On except when playing" only needs `play_all is True` (that already
excludes both playback AND non-navigation refreshes - exactly today's
`allow_cue` semantics, just broadened to any marking). But "Always on"
needs to fire during playback (case 1) while staying silent for cases 2/3,
and `play_all` can't tell those apart on its own.

Fix: inject an `is_playing: Callable[[], bool]` into `RegionPresenter`
(same dependency-injection style as the existing `_playback_status_fields`
callable), wired from `main_window.py` to `self.playback.is_play_run_active`
(already exists, `playback_controller.py:616` - "True from the first tick
of the count-in until the play run stops"). Then:

```
fire = mode != OFF and any(isinstance(r, MarkingRow) for r in rows) and (
    play_all or (mode == ALWAYS_ON and is_playing())
)
```

Placed in `update_timeline_views` right after the `rows = self.music_data.
get_region_3_rows()` loop (that method already builds `rows`; `refresh_
region_5` doesn't), after the `if play_all: audition_requested.emit()`
line - preserving the existing "notes sound before the cue" ordering
requirement for manual navigation. During playback there's no audition-
cutoff risk (the Sequencer's own retrigger=False chord doesn't collide with
the cue's channel), so firing unconditionally-after is safe there too.

Same sound is reused (per your answer) - `audio/performance_cue.py`,
channel 253, no new constants needed there.

## Persistence

Global, in `persistence/app_settings.py` (per your answer) - a new
`performance_indicator_mode: str` field (values `"off"` / `"on_except_
when_playing"` / `"always_on"`), following the exact `show_engraving_
details_enabled` pattern: loaded once, a `set_performance_indicator_mode()`
setter, invalid/missing values fall back to the default. Constants
(`PERFORMANCE_INDICATOR_OFF` etc., a tuple of valid values, `DEFAULT_
PERFORMANCE_INDICATOR_MODE`) live in a new small stdlib-only module -
`models/performance_indicator_mode.py` - mirroring how `models/play_
settings.py` defines `PLAY_MODES`/`DEFAULT_PLAY_MODE` (`models/` stays
Qt-free; this needs no dataclass, just the three string constants + a
`cycle(mode) -> str` helper).

`RegionPresenter` owns the live value (it's the only reader), seeded from
`app_settings.load()` in `__init__` alongside where it could reasonably
also read `show_engraving_details_enabled` today (that one currently lives
on `MusicData` instead, for reasons specific to that toggle - not
following that path here since this setting never needs to change what a
score's own rows say, only whether a sound plays).

## Decisions (resolved 2026-09-22)

1. **Default value: Off.** Confirmed - matches every other optional audio
   toggle in this app, even though it's a real (accepted) regression from
   today's unconditional narrow structural-change cue.
2. **Submenu + separate Ctrl+C cycle action: confirmed, build both.**
   Reasoning given: there's no dialog for this setting, so Ctrl+C is how
   it actually gets changed day to day; the submenu exists so the three
   options can be browsed and discovered by name, not as the primary way
   of setting it.
3. **Wording: keep as drafted** - "Performance Indicator" / "Off" / "On
   except when playing" / "Always on" / "Cycle Performance Indicator".
   Called out as easy to change later if it doesn't read well in place.
4. **Placement: immediately below Toggle Bar Line Indicator**, above Show
   Engraving Details - not grouped with Position Announcer/Metronome
   further down the menu. Still lands in the "Orientation" category
   override in `ShortcutController` alongside those, since that's about
   the Keyboard Shortcuts dialog's own grouping, not menu order.

## Implementation steps (once the above is settled)

1. `models/performance_indicator_mode.py` - three constants + `cycle()`.
2. `persistence/app_settings.py` - new field, loader validation, `set_
   performance_indicator_mode()`.
3. `widgets/menu_builder.py` - new `Actions` fields (the submenu's three
   QActions + the cycle action), the submenu itself (Terminology-style),
   the cycle QAction with `QKeySequence("Ctrl+C")`. Both are inserted
   immediately after `a.bar_line_indicator` / before `a.show_engraving_
   details` in `_options_menu` (menu_builder.py:649-660).
4. `controllers/region_presenter.py` - seed `performance_indicator_mode`
   in `__init__`; accept the new `is_playing` callable param; add `cycle_
   performance_indicator_mode()` and `announce_performance_indicator_mode
   (mode)` (mirrors `announce_play_mode`); the `fire =` gate above inside
   `update_timeline_views`; strip the retiring cue call and now-unused
   `allow_cue` param out of `refresh_region_5`.
5. `main_window.py` - wire the new presenter constructor arg to `self.
   playback.is_play_run_active`; add the `cycle_performance_indicator_mode`
   slot (updates the three submenu QActions' checked state + calls
   `presenter.announce_performance_indicator_mode`); set initial submenu
   checked state from the loaded setting.
6. `controllers/shortcut_controller.py` - add the new display names to
   `_CATEGORY_OVERRIDES` (`"Orientation"`), matching Bar Line Indicator/
   Metronome/Position Announcer. No `_build_reserved` change needed (Ctrl+C
   isn't reserved elsewhere).
7. Tests: `tests/test_main_window_performance.py` already exercises the
   retiring narrow cue via `null_synth.performance_cues` - update those to
   the new trigger condition; add a new test file (`tests/test_
   performance_indicator_cue.py`, mirroring `tests/test_bar_line_
   indicator.py`'s shape) covering: Off never fires; On-except fires on
   nav, not on a simulated playback step; Always-on fires on both; a
   filter-toggle refresh at the same position never fires regardless of
   mode; Ctrl+C cycles and announces; the submenu's checked item follows
   the cycle.
8. `tests/manual/model_fingerprint.py` isn't affected (no `MusicData`
   surface changes - this is presenter/settings only) - skip the fingerprint
   gate.
9. Docs: `docs/keystrokes.md`/`.html` and `docs/user_guide.md`/`.html` gain
   the new Ctrl+C entry and Options menu description (skip `docs/
   user_guideStyleGuide .md`/wishlist per standing rules - only touch the
   user guide itself when asked, which listing a new real shortcut counts
   as, same as any other shipped keystroke).

User decisions:
Q1. Default value — Off (matches every other audio toggle in the app) vs. "On except when playing" (preserves today's    
narrow structural-change behavior almost exactly, since that already never plays during playback).                      
A1. Correct. Default is off.
Q2. Submenu + separate Ctrl+C cycle action, as you described, vs. the simpler single flat "Cycle Performance Indicator"  
item the codebase otherwise uses for this exact shape of setting (Cycle Play Mode, Cycle Loop Repeat Handling).         
A2. We do not have a dialogue for this option so cycling with control+C gets around this.  Additionally, the menu items do allow the user to browse and discover the options.
Q3. Menu/label wording as you wrote it, or adjustments.                                                                  
A3. Stick with my wording for now. Easy to change.
Q4. Confirming placement grouped with Bar Line Indicator/Metronome/Position Announcer.                                   
 A4.  Place it immediately below the bar line indicator menu item.
