# RSBV implementation plan (Recall Score browser version)

Written 2026-10-08, after Phase 0 (decision: GO).

## Inputs and what wins

1. `docs/rsbv_spike_findings.md`, "Conclusions for the Phase 1 design". It wins
   over everything else here where they disagree.
2. `userPlans/RSBVProofOfConcept.md` for the original scope and architecture.
   Its "Status and handoff" section lists what the spikes overtook; this plan
   folds those in.
3. The spike code: `web/spikes/` (Pyodide boot, key capture, announcer,
   js-synthesizer audio, micropip), `web/sf/` and `tools/stage_web.py`.

Naming: RSBV (also called RSWV, the web version) is one project. Existing names stay as they are
(branch `rsbv`, `docs/rsbv_spike_findings.md`, `tools/stage_web.py`) to avoid
churn. New files use neutral "web" names (`web/py/web_api.py`, `tests/web/`).

Branch: all work on `rsbv`. Merging to `main` publishes, so it happens only on
the user's say-so.

## Model assignment

Every task is tagged Opus or Sonnet.

* Opus: changes to shared `models/` or `parsers/` code that must keep desktop
  behaviour exactly (fingerprint gate), anything timing-critical (the playback
  scheduler), and the parts of the page that set the accessibility architecture
  (focus, announcer, key handling), where a subtle mistake is costly and hard
  to spot in review.
* Sonnet: well-specified, mostly mechanical work with a clear pattern to
  follow or a test to pass: moving code, the staging script, the Pages
  workflow, storage wrappers, dialogs built on an established pattern,
  pytest coverage, docs and checklists.

When a Sonnet task turns out to need a judgement call about shared code or
timing, stop and hand it to Opus rather than guess.

## Settled decisions (from Phase 0)

* Hosting: static site on GitHub Pages, everything in the browser, no server.
* Python: Pyodide 314.0.7 from jsDelivr, pinned. Shared `models/` and
  `parsers/` (plus the Qt-free `audio/` event builders, see the reuse map) are
  shipped as one zip and unpacked into Pyodide, exactly as
  `web/spikes/pyodide_boot.js` does now. One copy of the logic, no fork.
* Load cost: about 1.5 s (Chrome) and 2.4 s (Firefox) to ready on the tester's
  machine; the largest score parses in 0.6 to 0.7 s. A move-and-render step is
  about 2 ms. Python is not the latency problem.
* Audio: js-synthesizer 1.13.0 (libfluidsynth 2.4.6) in an AudioWorklet, pinned.
  App sounds come from `recall_score_sounds.sf2` on their own SoundFont id, as on
  desktop.
* Latency: about 53 ms key to sound, accepted as a known deviation from Ref 9's
  25 ms for the web version. Record it in the user guide and the Product
  Definition decision log.
* No music21 in the browser. Chord symbols use a pure-Python table (task 1.4,
  done).
* Announcer: every message goes through a queue. Use `ariaNotify` where present
  (Chrome 154 and Firefox 157 both have it), and two alternating live regions
  otherwise. Never a single live region, never rapid direct calls.
* Menu: a "Menu" button first in the Tab cycle. F10 and Alt are left to the
  browser.
* Keys: Ctrl+key, bare letters, arrows, Ctrl+arrows, Ctrl+Home/End, Tab,
  Shift+Tab and Alt+Left/Right reach the page in focus mode. Do not bind Escape
  (NVDA uses it to leave focus mode) or Pause (never received) for anything
  essential. Shift+F10 opens the Region 4 scope menu; ContextMenu is handled
  where it arrives.

## Decisions the user needs to make (before or during Phase 1)

1. Instrument SoundFont. Recommendation: GeneralUser GS (30.8 MB, preferred by
   ear), committed under `web/sf/` (well under GitHub's 100 MB limit) and
   cached by the browser after the first visit. Fallback if the first-visit
   download feels too slow in testing: ship TimGM6mb (5.7 MB) as the default
   with GeneralUser GS as an opt-in setting. Check GeneralUser GS's licence
   allows redistribution before committing it.
> Default sfz is general user.  do not plan to use  TimGM6mb unless general user becomes unusable for some reason.
2. Region 6 jump key. N was not received in either browser in spike 2, but the
   tester may simply not have pressed it. Re-test in Phase 2; if it is really
   lost, the fallback is Ctrl+6 (or whatever the re-test shows reaches the page).
> N will work. i just did not press it.  There is no reason to think that N won't work when Z, X, C, V and B all worked fine.
3. Public path: `chessel85.github.io/RecallScore/` (root) or a sub-path such as
   `/RecallScore/app/`, leaving the root free for a landing page. Recommendation:
   the sub-path.
> Use the subpath and we put in a default sign-posting page as the default index.html.

## Progress and handoff notes

Update this section as each task lands, so a fresh session can pick up the
next one after a /clear.

### Done

* 1.1 (2026-10-08). The MusicXML path no longer needs music21.
  `parsers/musicxml_metadata.py` holds the ElementTree half of the reader
  (`extract_*`, `fill_empty_beat_units`, `assemble_music_data`) and the web
  entry point `load_musicxml_without_music21(path)`. `MusicXMLReader` uses it
  and adds music21's tempo, key and time on top. Guard:
  `tests/parsers/test_musicxml_without_music21.py`. Both fingerprints matched,
  and `MusicXMLReader.load()` output was identical on all 99 MusicXML files.
  Commit `9e8ff78`. (Its chord gap was closed by 1.4.)

* 1.2 (2026-10-08, commit `56c2a41`). Score-config and app-settings JSON are
  Qt-free in `models/`: `score_config_json.py` (`config_to_dict`,
  `config_from_dict`) and `app_settings_data.py` (`AppSettings` with
  `to_dict`/`from_dict`). `persistence/` keeps file I/O and `QStandardPaths`;
  `persistence.app_settings` re-exports `AppSettings`. Files written are
  byte-identical to before. Tests: `tests/models/test_score_config_json.py`.
* 1.3 (2026-10-08, commit `92f8c75`). `region2_manager` moved to
  `models/region2_manager.py` (with its two tests in `tests/models/`); importers
  and docs updated. Pure move.
  Both 1.2 and 1.3: full pytest passes, both fingerprints MATCH.

* 1.4 (2026-10-08). Chord symbols no longer need music21, on desktop or web.
  `tools/gen_chord_kinds.py` (needs music21, run by hand, about 2.5 min)
  writes `models/chord_kinds.py`: music21's exact pitch lists for every root
  spelling, kind (55, MusicXML plus music21's own names) and bass, packed
  per kind as zlib + base64 (145 KB file), plus a per-kind label suffix.
  `_resolve_harmony` calls `chord_symbol()`. Ultimate Guitar still uses
  music21 (free-text chords; desktop-only). Sub-plan: `UserPlans/ChordTable.md`.
  Tests: `tests/models/test_chord_kinds.py` (fast hand cases plus a slow
  full sweep against music21, about 3 min, so the full suite now takes about
  4 min; use `-m "not slow"` for quick runs); the music21-blocked guard now
  expects chords with pitches. Both fingerprints MATCH, full pytest passes.
  The web's "chord name, no sound" fallback is no longer needed for MusicXML.
  Not yet committed when these notes were written: if `git status` still
  shows `models/chord_kinds.py` untracked, ask the user before committing it.

* 1.5 (2026-10-08). Skeleton and staging. Source layout: `web/index.html`
  is the root signpost; the app is `web/app/` (`index.html`, `css/rsbv.css`,
  `js/app.js`, `py_bridge.js`, `announcer.js`); `web/py/web_api.py` is the
  bridge (`load(bytes, filename)`, `score_summary()`, errors as
  `{"error": ...}`). Staged site: `/` signpost, `app/`, `py/` (shared.zip plus
  web_api.py, fetched as `../py/`), `sf/`. `stage_web.py` now adds the eight
  Qt-free `audio/` modules, copies only GeneralUser GS (+ its licence text,
  `web/sf/GeneralUser-GS-LICENSE.txt`, which permits use in software) and
  `recall_score_sounds.sf2`, and has `--public` (omits `spikes/`, `scores/`).
  Tests: `tests/web/test_stage_web.py`. Not yet tried in a real browser:
  stage with `--serve 8000` and open `/app/`.

* 1.6 (2026-10-08). `.github/workflows/pages.yml`: on push to `main` (and
  manual dispatch, guarded to `main`), runs `stage_web.py --public` with plain
  Python and deploys `build/rsbv_site` with the official Pages actions. No
  `--scores`. One-time user step: repo Settings > Pages > Source = GitHub
  Actions. Verified only by running the staging command locally.

### Next: finish Phase 1 with 1.5, 1.6, 1.7 (all Sonnet)

Do them in order; each is specified under "Phase 1" below. Read `CLAUDE.md`,
`docs/architecture.md` and `docs/parsers.md` first. User rules: no `**` bold
in replies, short messages (screen reader), do not edit `docs/user_guide.md`
or `wishlist.txt`, commit only when the user says so, never merge to `main`.
After each task, add a Done entry here.

State of the tree that the task list doesn't say:
* Python entry point for the web: `parsers.musicxml_metadata.load_musicxml_without_music21(path)`
  returns a full `MusicData`, chords included. It takes a path, so the bridge
  writes the uploaded bytes to Pyodide's virtual filesystem first (keep the
  original suffix; `.mxl` is a zip and the reader handles it). Nothing in the
  MusicXML path imports music21 any more, so the bridge needs no stub.
* `tools/stage_web.py` today: copies `web/` (skipping `*.sf2`, `__pycache__`,
  `CLAUDE.md`) to `build/rsbv_site`, zips `SHARED_PACKAGES = ("models",
  "parsers")` into `py/shared.zip`, copies `soundfonts/recall_score_sounds.sf2`
  plus every `web/sf/*.sf2` into `sf/` with an `index.json`, and `--serve`s
  with the right MIME types. 1.5 adds the Qt-free `audio/` files listed in the
  reuse map (only those, never `synth_engine.py`, `sequencer.py` or anything
  importing PySide6/fluidsynth); add a pytest or a check in the script that
  each staged `audio/` file imports without PySide6.
* `web/spikes/pyodide_boot.js` is the thing to promote into `web/js/py_bridge.js`.
  Drop its music21-stub option (spike 1 only; `web/spikes/music21_stub.py`
  stays with the spikes). Pyodide 314.0.7 pinned from jsDelivr. Note it
  fetches `../py/shared.zip`, relative to the spikes folder; the app's path
  will differ.
* SoundFonts: `web/sf/GeneralUser-GS.sf2` (32 MB) and `web/sf/TimGM6mb.sf2`
  (6 MB) are both already committed. The user chose GeneralUser GS only.
  Staging should copy just GeneralUser GS (plus `recall_score_sounds.sf2`).
  Do not delete `TimGM6mb.sf2` from git without asking. Still open from
  decision 1: confirm GeneralUser GS's licence allows redistribution and
  commit its licence text next to it (`web/sf/`); if it doesn't, stop and
  tell the user.
* Public layout (decision 3): the site root holds a short signpost
  `index.html` (what Recall Score is, a link to the app); the app itself is
  at the sub-path `app/`, i.e. `chessel85.github.io/RecallScore/app/`. So
  the staged site is `index.html` (signpost), `app/` (the app's html, css,
  js, py), `py/` or `app/py/` for `shared.zip` (pick one and keep paths
  relative), `sf/`. Spikes stay staged locally for testing but are left out
  of the public deploy (1.6): give `stage_web.py` a `--public` flag (or
  similar) that omits `spikes/` and `scores/`.
* 1.5's error reporting: a parse failure must reach the user as an
  accessible message (an alert or a focused message element), not a
  console print. The Python side still prints `[ERROR]` and returns partial
  state in places (CLAUDE.md "Known gaps"); the bridge should catch
  exceptions and return `{"error": ...}` so JS can show it.
* 1.5's announcer use is minimal: loading progress only. The real announcer
  (queue, `ariaNotify`, alternating live regions) is Opus task 2.1, so keep
  1.5's version a small module 2.1 can replace; copy the queue idea from
  `web/spikes/spike3.js` rather than writing to one live region directly.
* 1.6: the workflow publishes from `main` only, and `main` gets `rsbv` only
  on the user's say-so. It must run `stage_web.py` without `--scores`. The
  SoundFonts are in git, so the workflow needs no extra download step.
* 1.7: `tests/web/` imports `web/py/web_api.py` directly in CPython (add the
  path in a conftest or the test). Load at least one fixture per type it
  supports (`tests/fixtures/*.musicxml`, an `.mxl` such as
  `examples/bach-bourree-tab.mxl` (no `.mxl` in `tests/fixtures/`), `chords_and_lyrics.musicxml`
  for chords) and assert the JSON shapes, plus the error dict for a broken
  file. Keep it fast (no `slow` marker needed; no music21).
* After Phase 1 the next step is Phase 2, whose first task (2.1) is Opus.

## Reuse map: desktop piece to web

What ships unchanged in the shared zip (pure Python, Qt-free today):

| Desktop code | Web use |
|---|---|
| `models/` (all of it) | Parsing results, timeline, row text, navigation, find, performance rows, marking rows, play settings, mixer settings, score config data |
| `parsers/` MusicXML path | Loading `.musicxml`, `.xml`, `.mxl` (after task 1.1 makes it music21-free) |
| `parsers/` MIDI and Guitar Pro paths | Loading `.mid` and `.gp*`. Both are stdlib-only (hand-rolled MIDI, zip plus ElementTree for GP), so they cost almost nothing to add (Phase 6) |
| `audio/metronome.py`, `lead_in.py`, `barline_patterns.py`, `boundary_cue.py`, `performance_cue.py`, `position_announcer.py`, `strum_schedule.py`, `grace_note_schedule.py` | The event builders for every app sound. Qt-free; add `audio/` (these files only) to the staged zip so the web plays exactly the desktop's sounds and patterns |
| `widgets/region2_manager.py` | The Region 2 tree model, mute, solo and active-voice filtering. Qt-free but lives in `widgets/`; task 1.3 moves it to `models/` |

What needs logic moved out of a Qt class first (so both versions call one copy):

| Desktop code | Problem | Fix |
|---|---|---|
| `controllers/playback_controller.py` `_PlayRun`, `_build_play_run`, `_refresh_play_span`, `phrase_end_index`, the lead-in and loop-seed logic | Mixed with `QTimer` and signals | Task 4.1: extract a pure play-plan builder into `models/` |
| `audio/sequencer.py` step timing | `QObject` plus `QTimer` | Its timing maths moves with task 4.1; the web scheduler is new JavaScript |
| `persistence/score_config.py` and `app_settings.py` JSON encode and decode | Import `QStandardPaths` | Task 1.2: move encode and decode into `models/` |
| `controllers/region_presenter.py` row text and announcement wording (loop length, play mode, tempo, indicator mode, measure change) | Mixed with widgets | Task 2.2: the wording functions move to `models/` (or the bridge, if trivial); the presenter calls them |
| `controllers/navigation_controller.py` digit entry, jump points, sections, find stepping | `QObject` signals only, logic otherwise plain | Bridge calls the same `MusicData` methods; anything non-trivial moves to `models/` first |
| `controllers/attribute_controller.py` scope menu entries and filters | Builds a `QMenu` | Task 5.1: the action list (`menu_actions`, scope filters) moves to `models/` |
| `controllers/score_edit_controller.py` | Already Qt-free | Bridge can call its logic directly or via `models/` (Phase 6) |

What is rewritten in JavaScript (the Qt layer's job): widgets, focus cycle, key
handling, dialogs, the audio scheduler, storage, the announcer.

## Architecture (short form)

Same shape as the POC plan:

* `web/py/web_api.py`: the bridge. A thin facade like a web-only controller
  layer. It holds the current `MusicData` (replaced wholesale on every load,
  invariant 3), and every function returns plain JSON-able lists and dicts.
* `web/js/`: `app.js`, `keymap.js`, `regions.js`, `focus.js`, `announcer.js`,
  `audio.js`, `scheduler.js`, `storage.js`, `py_bridge.js`, `dialogs.js`.
  Plain ES modules, no build step, no npm.
* Six regions in two rows of three: 1, 2, 6 on top; 3, 4, 5 below. Region 6
  replaces the desktop status bar. Tab cycles Menu button, then Regions 1 to 6.
  Z/X/C/V/B jump to Regions 1 to 5 and the Region 6 key is decided in Phase 2.
* Regions 1, 3, 4, 5, 6 are `role="listbox"` with `aria-activedescendant`;
  Region 3 is multi-select. Region 2 is `role="tree"`, re-verified for keys in
  the real app (the spike's tree gaps were mostly untested keys).
* `web/CLAUDE.md`: browser-specific rules (key findings, announcer queue rule,
  no Escape, the reuse rule: logic goes in `models/`, never copied into JS).

## Phases and tasks

Each phase ends with something the user can open in a browser and test with
NVDA.

### Phase 1: shared-code refactors and skeleton

1.1 Opus. Make the MusicXML path music21-free.
* Make `from music21 import harmony` function-local in
  `parsers/timeline_builder.py` and `parsers/ug_timeline_builder.py`; make the
  GP, MIDI and UG builder imports in `timeline_builder_factory.py`
  function-local (the `MusicData.__post_init__` pattern).
* Factor `MusicXMLReader`'s ElementTree-only metadata path (key, time, tempo,
  credits, part structure fallbacks) into something the bridge can call without
  importing music21.
* Add a pytest that imports the MusicXML path in a subprocess with music21
  blocked (the Qt-free guard's pattern).
* Gate: `parser_fingerprint.py` and `model_fingerprint.py --check` against a
  baseline from before the change. No differences.

1.2 Sonnet. Move score-config and app-settings JSON encode/decode into a
Qt-free `models/score_config_json.py` (and the app-settings equivalent).
Desktop `persistence/` keeps only file I/O and `QStandardPaths`. Round-trip
pytest; existing persistence tests still pass.

1.3 Sonnet. Move `widgets/region2_manager.py` to `models/` and update imports.
Pure move, no behaviour change. Full pytest run.

1.4 Opus. Chord-symbol pitch table without music21 (its own sub-plan,
`userPlans/ChordTable.md`, written first and reviewed by the user, because it
changes the desktop parser's dependencies).
* A `tools/` generator (allowed to import music21, run by hand) that writes a
  pure-Python `models/chord_kinds.py`: MusicXML `<kind>` values to intervals,
  plus whatever music21 does for bass, inversion and voicing.
* `_resolve_harmony` uses the table; music21 is no longer imported for chords
  on desktop either.
* Gate: fingerprints unchanged across the whole corpus, so desktop chords
  sound exactly as before. Add a pytest comparing the table against music21
  for every kind (marked `slow`).
* Can run in parallel with Phases 2 and 3; until it lands the web uses the
  "chord name, no sound, Region 3 says so" fallback.

1.5 Sonnet. Skeleton and staging.
* `web/index.html`, `web/css/rsbv.css`, `web/js/py_bridge.js` (promote
  `web/spikes/pyodide_boot.js`), `web/py/web_api.py` with `load(bytes,
  filename)` and `score_summary()`.
* `tools/stage_web.py`: add `audio/` (the Qt-free event-builder files only) to
  the zip, copy the chosen SoundFont, keep `--scores` local-only.
* File picker and drag and drop; spoken loading progress through the
  announcer; parse errors shown in an accessible error message, not swallowed
  (Ref 25 / NFR-06 direction).
* `.gitignore`/commit the chosen `web/sf/*.sf2` per decision 1.

1.6 Sonnet. GitHub Pages workflow (`.github/workflows/pages.yml`): runs
`tools/stage_web.py` (without `--scores`) and publishes from `main` only.
Until the merge, test by local staging.

1.7 Sonnet. `tests/web/` pytest for the bridge: load each fixture, check the
JSON shapes. Runs in the normal suite, no browser.

### Phase 2: regions, navigation, focus, announcer

2.1 Opus. Page accessibility core: `focus.js` (single owner of the region
cycle, the spirit of invariant 7), `keymap.js` (single key table, invariant
16's spirit), the document-level key handler, and `announcer.js` (queue,
`ariaNotify`, alternating live regions; assertive for toggles, polite for the
position announcer). Promote what worked in `spike2.js` and `spike3.js`.

2.2 Opus. Bridge region rendering: `region_rows(n)` for Regions 1 to 6,
`move(direction)`, `goto_bar(n)`, `jump_point(dir)`, `section(delta)`. Reuse
`NoteRenderer`, `MarkingRows`, `PerformanceRows`, `get_status_bar_fields()`
and the timeline navigator. Move any wording now inside `RegionPresenter`
into `models/` first so both versions share it. Region 3 selection follows
invariant 10's intent: select all, current item on the first note.

2.3 Sonnet. `regions.js`: render the six regions as listboxes/tree from the
bridge's rows, `aria-activedescendant`, multi-select in Region 3, Region 2
tree expand/collapse.

2.4 Sonnet. Region 2 mute and solo (F8, F9, Alt+F8, Alt+F9 as on desktop),
via the moved `region2_manager`. Mute and solo words go in the row text itself
(persistent-state rule).

2.5 Sonnet. Go-to-bar dialog (Ctrl+G, plus typed digits and Enter as on
desktop), Menu button with a menu listing every command and its key, and an
F1 keyboard help list built from `keymap.js`. Native `<dialog>`; initial focus
on the first widget in tab order; every dialog has an explicit Close or
Cancel button, because Escape may never arrive.

2.6 Sonnet. Key re-test page (extend `spike2`) for the keys Phase 0 left
untested: N, F8, F9, Alt+F8/F9, Ctrl+G (Chrome), Ctrl+F (Firefox), F1
(Firefox), Ctrl+Shift+letter combos, Shift+Tab in a listbox, and everything in
a `role="tree"`. User runs it with NVDA in both browsers; results go into
`docs/rsbv_spike_findings.md` and settle decision 2.

2.7 Sonnet. Drift guard: a pytest that builds the desktop `MenuBuilder`
offscreen and checks each web command in `keymap.js` that claims a desktop
equivalent uses the same key, or is listed as a deliberate web difference.

### Phase 3: sound on navigation

3.1 Opus. `audio.js`: synth and SoundFont loading from `spike4.js`, AudioContext
unlock on first key or click (and say so on first visit), program and channel
setup from the bridge (GM programs converted to 0-indexed once, in Python,
invariant 9), pan and volume per channel.

3.2 Sonnet. Audition on every move: the bridge returns the note-on/off events
for the current slice (reusing `get_playback_events_for_indices` for the
single slice and the strum/grace schedules), JS plays them. Boundary ("doh")
cue, bar line indicator (Ctrl+B) and performance cue, using the shared
`audio/` event builders. Chords without pitches (until 1.4) stay silent.

### Phase 4: playback

4.1 Opus. Extract the play plan from `PlaybackController` into a Qt-free
`models/play_plan.py`: span resolution (`_build_play_run`,
`_refresh_play_span`, `phrase_end_index`), pickup handling, lead-in schedule,
loop iteration with repeats and the loop-seed jump state, metronome and
position-announcer beats. Output: a time-ordered list of (offset ms, action)
for a chunk. Desktop `PlaybackController` and `Sequencer` then call it.
* Gate: the existing playback tests pass unchanged, plus new pytest cases
  comparing the plan against what the desktop schedules today for loop,
  lead-in, pickup and repeat fixtures. Fingerprints unchanged.

4.2 Opus. `scheduler.js`: lookahead scheduler on `AudioContext.currentTime`
(or the FluidSynth sequencer, which spike 4 showed works in the worklet),
asking the bridge for the next chunk ahead of time; cursor follows playback in
Region 3; stop, pause and resume; tempo changes take effect at the next chunk.

4.3 Sonnet. Commands on top of 4.1 and 4.2: Space play/stop, Ctrl+Space pause,
Ctrl+Alt+Space, loop cycle (Ctrl+L), loop length, lead-in, metronome toggle
(Ctrl+M) and the free-running metronome, position announcer, tempo faster,
slower and reset. Announcements reuse the shared wording from 2.2.

4.4 Sonnet. Play Settings dialog (tempo, lead-in, play mode, loop length,
loop repeat mode), on the dialog pattern from 2.5.

### Phase 5: settings and elevation

5.1 Opus. Region 4 scope menu (Shift+F10, plus ContextMenu where it arrives):
move the action list and scope filters out of `AttributeController` into
`models/`, then a JS menu built from it. Add/remove at voice, stave, part and
score scope; attribute order and hide dialog if time allows.

5.2 Sonnet. Performance indicator modes and marking categories in the note
list (the presenter's cycle and toggle, via the shared code).

5.3 Sonnet. `storage.js`: global settings in localStorage, per-score settings
keyed by SHA-256 of the file bytes, using the encoder from 1.2 so the JSON is
the desktop `.rsc` shape. Every call wrapped so private windows still work for
the session. Export and import all settings as one file; import of a desktop
`.rsc` for the current score.

5.4 Sonnet. UK/US terminology setting and the other global options the
desktop Options dialog exposes that make sense in a browser.

### Phase 6: wider desktop parity (after the core is tested)

Order by user priority; each is mostly bridge plus UI because the logic is
already in `models/`.

6.1 Sonnet. MIDI and Guitar Pro import (stdlib-only parsers; add the file
types to the picker; fixtures in `tests/web/`).

6.2 Sonnet. Find (Ctrl+F where it arrives, otherwise the re-test's fallback)
with Find Next/Previous on Alt+Right/Left, from `models/find_index.py` and
`find_target.py`.

6.3 Sonnet. Performance Report, from `models/performance_rows.py`, as a
dialog with jump-to-row.

6.4 Opus. Mixer (volume and pan per part) on the web synth: the channel mapping
and live edit/cancel logic currently in `PlaybackController` need moving to
`models/mixer_settings.py` first.

6.5 Sonnet. Score edits from `score_edit_controller.py`: rename and reorder
parts, link parts, key override, stave collapse, instrument choice. Region 2
labels and order mutated in place (invariant 11's intent).

Left out of the web version for now: MuseScore import (needs a local
executable), Ultimate Guitar import (network and CORS), tuner, live MIDI input,
voice control, shortcut remapping, offline/PWA mode, saving back to the score
file.

### Phase 7: testing and soft launch

7.1 Sonnet. `docs/rsbv_test_checklist.md`: one line per command and region,
with the expected speech.

7.2 User. NVDA with Chrome and Firefox through the checklist; then the JAWS
tester (also the outstanding JAWS run of spikes 2 and 3); then a
VoiceOver/Safari tester. Safari is where audio unlocking, AudioWorklet and
live regions most likely differ, so expect a fix round.

7.3 Opus. Triage and fix what testers find in focus, announcer or scheduler
code. Sonnet for UI and wording fixes.

7.4 Sonnet. A short "try it" page and announcement text; user guide section
for the web version, written only when the user asks (standing rule).

7.5 User. Merge `rsbv` to `main` to publish.

## Testing

* pytest: the bridge (`tests/web/`), the music21-free import guard, the moved
  JSON round trips, the play-plan comparisons, the keymap drift guard. The
  existing suite must still pass.
* Fingerprint harnesses gate every change to `parsers/` or `models/` meant to
  keep behaviour (1.1, 1.3, 1.4, 4.1, 5.1, 6.4).
* Browser behaviour is tested by hand with a screen reader. Playwright can be
  added later for smoke tests of load and navigation.

## Risks

* Playback timing (4.1, 4.2): the desktop loop logic carries many live-tested
  fixes. Extracting it is the riskiest refactor; compare schedules before and
  after rather than trusting the tests alone.
* Shared-code drift: desktop changes to `models/` or `parsers/` can break the
  web silently. The bridge tests and import guards in the normal pytest run
  catch most of it.
* Keys in a real tree and in dialogs may differ from the spikes; the 2.6
  re-test is there to catch that early.
* Hidden-tab playback is confirmed only by ear; measure it properly once the
  real scheduler exists.
* Safari/VoiceOver comes last, so its problems surface late.
* First-visit download (Pyodide plus SoundFont) may put people off; keep the
  spoken progress and measure on a slow connection.
