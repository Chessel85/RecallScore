# RSBV proof of concept (Recall Score BV, browser version)

## Status and handoff (2026-10-08)

Phase 0 is finished and the user's decision is GO. This document is the original
plan, written before the spikes. **Do not implement from it as it stands.** The
implementation plan that replaces it is `userPlans/RSBV.md`, written from:

1. `docs/rsbv_spike_findings.md`, especially "Conclusions for the Phase 1
   design". Where it contradicts this file, it wins.
2. This file, for scope, architecture and phase ideas.
3. The spike code in `web/spikes/` (working Pyodide boot, key-capture page,
   announcer experiments, js-synthesizer audio, micropip test), `web/sf/`
   (two candidate SoundFonts) and `tools/stage_web.py` (staging and local
   server: `.venv\Scripts\python.exe tools\stage_web.py --scores --serve 8000`).
   Reuse what worked rather than starting over.

Points in this file that the spikes have overtaken:
* Menu bar: decided. A "Menu" button first in the Tab cycle. F10 and Alt are
  left to the browser. Drop the ARIA `menubar` option.
* Announcer: always go through a queue. `ariaNotify` is available in Chrome and
  Firefox, not only Chrome and Edge; keep the two alternating live regions as
  the full path for Safari and others. Never use a single live region.
* Chords: music21 will not be shipped to the browser. The chord pitch data will
  come from a pure-Python table made some other way (which touches desktop
  parser behaviour: separate plan plus the fingerprint gate). Until it exists,
  show the chord name, play no sound, and say so in Region 3.
* Latency: about 53 ms estimated key to sound, accepted by the user as a known
  deviation from Ref 9's 25 ms.
* Keys: Ctrl+key and bare letters work in focus mode. Escape belongs to NVDA
  (it leaves focus mode), so do not bind it. Pause was never received; verify.
  Use Shift+F10 for the Region 4 scope menu.
* SoundFonts: GeneralUser GS (30.8 MB) sounds better than TimGM6mb (5.7 MB);
  pick one, and decide whether `web/sf/*.sf2` is committed or gitignored.
* Not yet verified: JAWS (spikes 2 and 3), VoiceOver/Safari, a true hidden-tab
  playback measurement (only the ear test exists).
* Branch `rsbv` holds all uncommitted RSBV work. Merging to `main` publishes, so
  it happens only when the user says so.

## Context

Almost nobody in the blind community has tried Recall Score, and having to download it may be the reason. RSBV is a browser version: people visit a URL and use it straight away. There is no central server. It is a static site on GitHub Pages and everything runs in the user's browser.

This plan covers a proof of concept (POC). It is a working, deployable RSBV with the key features, built to answer two questions:

1. Can a screen-reader user drive it as fluently as the desktop app (key capture, announcements, latency)?
2. Do people actually use it once there's no download?

Decisions:
* RSBV lives in a `web/` subfolder of the RecallScore repo and reuses `models/` and `parsers/` as-is (one copy of the parsing logic, no divergence).
* The work happens on branch `rsbv`. Publishing runs only from `main`, so nothing goes public until the user merges.
* Hosting is GitHub Pages at `chessel85.github.io/RecallScore/` (the repo is public, so it's free).
* The first-visit download (about 10 to 40 MB of Pyodide plus the SoundFont) is accepted; we see how it feels in testing.
* Test platforms, in order: the user tests with NVDA in Chrome and Firefox; a JAWS tester follows; a VoiceOver/Safari tester comes in once the user's own testing passes.

## POC scope

In:
* MusicXML files only (`.musicxml`, `.xml`, `.mxl`), loaded with a file picker or drag and drop.
* Six regions in two rows of three: the desktop's five plus Region 6, which replaces the desktop status bar (see "The six regions" below).
* Timeline navigation: Left/Right, Ctrl+Left/Right, Ctrl+Home/End, Ctrl+G to go to a bar.
* Audition on every move.
* Bar line indicator.
* Playback with Space, Pause, the loop cycle (Ctrl+L), lead-in and the metronome toggle.
* Region 2 mute and solo.
* Elevating attributes and performance information into the note list (Region 4's add/remove at voice/stave/part/score scope, plus the performance indicator modes).
* Global settings and per-score settings, saved in the browser.
* Spoken announcements for toggles (metronome on, loop mode and so on).
* An accessible menu bar plus a keyboard help list.

Out (later phases, if the POC shows interest):
* MIDI, Guitar Pro, Ultimate Guitar and MuseScore import.
* Find, the Performance Report, Mixer, tuner, live MIDI input, voice control, shortcut remapping, score edits (rename, reorder, link, key override), stave collapse.
* Offline/installable mode (PWA).
* Saving back to the score file.

## Architecture

### Overview

```
browser page (HTML/JS)  <-->  Pyodide (Python in WebAssembly)  -->  models/ + parsers/ (shared, unchanged API)
        |
        +--> audio: js-synthesizer (FluidSynth in WebAssembly) + Web Audio scheduler
        +--> storage: localStorage (global + per-score JSON)
        +--> announcer: ARIA live regions / ariaNotify
```

* Python does what it does on desktop: parse, build the timeline, render row text, navigate, build playback events, export and apply config.
* JavaScript does what Qt and the controllers do on desktop: widgets, keys, focus, audio, storage.

### The Python side

* Pyodide loads the repo's `models/` and `parsers/` files (copied into the site at deploy time) into its virtual file system.
* A new bridge module, `web/py/rsbv_api.py`, is a thin facade, like a web-only controller layer. Each function returns plain lists and dicts (JSON-able) so JavaScript never touches Python objects. For example:
  * `load(bytes, filename)`
  * `region_rows()`
  * `move(direction)`
  * `playback_events(start, loop)`
  * `toggle_metronome()`
  * `export_config()` / `apply_config(json)`
* It holds the current `MusicData` the same way `ScoreSession` does. Invariant 3 still applies: replace it wholesale on every load.
* The bridge is pure Python, so it gets ordinary pytest tests in `tests/web/` on desktop. No browser is needed to test the logic.
* The desktop `controllers/` aren't reused, because 13 of them import Qt. Where a controller holds real logic the bridge needs (for example the loop cycle or bar-crossing detection in `playback_controller.py`), move that logic into `models/` first, so both versions call the same code instead of copying it.

### Removing music21 from the MusicXML path

music21 is about 460 ms to import on desktop and far heavier in Pyodide. The MusicXML timeline path needs it in only two places:

1. `parsers/timeline_builder.py:7` imports `music21.harmony` at module scope, for chord symbols (`<harmony>`) only.
2. `parsers/timeline_builder_factory.py:31` imports `UgTimelineBuilder`, which imports music21.

`MusicXMLReader.load()` also uses music21 for key, time and tempo, but it already has ElementTree fallbacks (`_extract_tempo_etree`, `_extract_key_and_time_etree`, `_extract_credits_etree`, `_extract_part_structure_etree`).

Desktop-side refactors, each meant to change no behaviour:
* Make the `harmony21` import function-local in `timeline_builder.py`.
* Make the GP, MIDI and UG builder imports in the factory function-local (the same pattern `MusicData.__post_init__` already uses).
* Factor the reader's ElementTree-only metadata path into something the bridge can call without importing music21.

Acceptance gate: `tests/manual/parser_fingerprint.py` and `model_fingerprint.py --check` against a baseline captured before the change. Add a pytest that imports the MusicXML path in a subprocess with music21 blocked, so it stays music21-free (the same subprocess pattern as the Qt-free guard).

Chord symbols in the browser: when the file contains `<harmony>`, install music21 on demand with `micropip` (it is pure Python). Phase 0 checks this works and measures the cost. If it's too heavy, the POC still shows the chord name and skips sounding the chord, and Region 3 says so. It never silently drops the symbol.

### Audio

* Synth: js-synthesizer (FluidSynth compiled to WebAssembly) running in an AudioWorklet. It uses the same SF2 format, the same GM program numbers and the same 1-indexed to 0-indexed conversion as desktop (invariant 9, still done once, in Python).
* SoundFonts: one small General MIDI SF2 for instruments (candidates are TimGM6mb at about 6 MB and GeneralUser GS at about 30 MB; Phase 0 picks one by ear), plus the existing `soundfonts/recall_score_sounds.sf2` (0.8 MB) if it holds the metronome and bar-line sounds. Both are committed under `web/` (well under GitHub's 100 MB limit), downloaded on first visit, then cached by the browser.
* Scheduler: a lookahead scheduler on `AudioContext.currentTime`, not on `setTimeout` alone, so a background tab doesn't stall playback. Events come from `get_playback_events_for_indices` and `next_playback_index` (which already handle repeats, endings, D.C., D.S. and Fine). The scheduler asks Python for the next chunk ahead of time.
* Browsers block audio until the user does something. The AudioContext starts on the first key press or click, and the page says so on first visit.
* Metronome, lead-in and the bar line indicator are scheduled on the same clock.
* Latency target: Ref 9's 25 ms from key press to sound. Measure it in Phase 0 and report the real number honestly; a browser may not meet it everywhere.

### The six regions

* Layout: row 1 is Regions 1, 2 and 6; row 2 is Regions 3, 4 and 5. Existing region numbers keep their desktop meaning.
* Region 1 (score info): identical to desktop.
* Region 6 (status): a list holding the same fields as the desktop status bar, one per row: position, key, time, playback tempo, playback state, metronome, position announcer, preview length. The first four come from `MusicData.get_status_bar_fields()`; the rest from the bridge. It replaces the desktop's F6 pane toggle. Browser-only lines (loading progress, SoundFont status) can be added here later.
* Jump keys: Z/X/C/V/B for Regions 1 to 5 as on desktop, plus N for Region 6 (the next key along the bottom row).
* Tab/Shift+Tab cycle the regions in number order, 1 to 6.
* Each region is a real focusable control:
  * Regions 1, 3, 4, 5 and 6: `role="listbox"` with `aria-activedescendant`.
  * Region 2: `role="tree"`.
  * Region 3 needs multi-select, so selecting all notes in a chord works the way it does on desktop.

### User interface and accessibility

* A single key handler on the document plays the role of `MenuBuilder`'s shortcuts. The region focus cycle has one owner, the same rule as invariant 7.
* The default key map is kept in one table in `web/js/keymap.js`, the web counterpart of `MenuBuilder` (invariant 16's spirit).
* Desktop keys are kept wherever the browser lets the page have them. Ctrl+N, Ctrl+T, Ctrl+W and Ctrl+Tab can never be captured, and none of the POC's keys use them.
* NVDA and JAWS must stay in focus mode so letter keys reach the app. Use widget roles that switch them to focus mode automatically, and test with both screen readers early (Phase 0).
* VoiceOver has no browse/focus mode split but has its own key handling (VO keys, Quick Nav); its key capture is checked when the Safari tester joins.
* Announcer (`web/js/announcer.js`):
  * Uses `ariaNotify()` where the browser has it (Chrome, Edge), otherwise two alternating hidden live regions, so the same text spoken twice in a row is still read. Firefox and Safari use the live-region path, so it must be fully reliable on its own, not just a fallback.
  * A small queue so rapid messages aren't merged or dropped.
  * Assertive for toggles; polite for the position announcer.
* The persistent-state rule still applies: mute and solo put their word in the Region 2 row text, as on desktop.
* Menu bar: an ARIA `menubar` opened with F10 or Alt, if the browser lets the page take those keys (Phase 0 checks). Otherwise a "Menu" button that is the first stop in the Tab cycle.
* F1 opens a keyboard help list.
* Dialogs (go to bar, play settings) are native `<dialog>` elements. Initial focus goes on the first widget in tab order, per the dialog-focus rule.
* Wording follows the PART vs INSTRUMENT terminology rule.

### Settings storage

* Global settings (UK/US terminology, performance indicator mode, marking categories, engraving details): one JSON object in localStorage.
* Per-score settings: the same JSON shape as desktop `.rsc` files, keyed by a SHA-256 hash of the file's bytes, so a renamed copy keeps its settings. A desktop `.rsc` could then be imported later.
* `persistence/score_config.py` has the JSON encode/decode logic, but it imports Qt for `QStandardPaths`. Move the encode/decode functions into a Qt-free `models/score_config_json.py`. Desktop keeps only the file I/O; the bridge uses the same encoder.
* "Export settings" and "Import settings" commands save and restore all of it as one file, because clearing browser data wipes localStorage.
* Every storage call is wrapped so private windows, where storage throws, still work for the session.

### Repo layout

```
web/
  index.html
  css/rsbv.css
  js/        app.js, keymap.js, regions.js, announcer.js, audio.js, scheduler.js, storage.js, py_bridge.js
  py/        rsbv_api.py
  sf/        <chosen GM soundfont>.sf2, recall_score_sounds.sf2
  CLAUDE.md  browser-specific rules (key capture findings, announcer rules, what not to break)
.github/workflows/pages.yml   copies web/ + models/ + parsers/ into the site and publishes from main
tests/web/                    pytest tests for rsbv_api.py
```

* Pyodide and js-synthesizer load from jsDelivr, pinned to exact versions. No build step and no npm for the POC; plain JavaScript modules.
* Local testing: `python -m http.server` from a staging folder made by a small script, `tools/stage_web.py` (stdlib only, as `tools/` requires), which does the same copy as the workflow.

## Phases

### Phase 0: spikes (go/no-go before building the UI)

Each spike is a throwaway page. The user tests each one with NVDA in Chrome and Firefox; the JAWS tester repeats spikes 2 and 3.

1. Pyodide loads the shared code and builds `MusicData` from a fixture. Measure first-load time and parse time for a large score in `files/`.
2. Key capture: which of the planned keys (Space, Ctrl+Space, Ctrl+Alt+Space, Ctrl+L, Ctrl+B, Ctrl+M, Ctrl+G, Ctrl+P, Ctrl+R, Ctrl+H, Alt+Left/Right, F10, Z/X/C/V/B/N) actually reach the page in focus mode in each browser and screen reader. The result is the POC key map; any key that's lost gets a replacement.
3. Announcements: live region vs `ariaNotify`, repeated text, rapid sequences, under NVDA and JAWS.
4. Audio: js-synthesizer plays the candidate SoundFonts; measure key-to-sound latency; check playback keeps going in a background tab.
5. music21 via micropip: does it install, and what does it cost.

Write the findings to `docs/rsbv_spike_findings.md`, then stop and review with the user before Phase 1.

### Phase 1: skeleton and deploy

* The music21-free refactors (with the fingerprint gate) and the score-config JSON move.
* `web/` skeleton, `tools/stage_web.py`, `rsbv_api.load()`, and the Pages workflow publishing to a test path.

### Phase 2: regions and navigation

* All six regions read-only, including Region 6's status fields; navigation keys; focus cycle; Region 2 mute and solo; the announcer.

### Phase 3: sound

* Audition on every move, the bar line indicator, and the metronome toggle.

### Phase 4: playback

* Space, Pause, loop cycle, lead-in, free-running metronome, Play Settings dialog (tempo, lead-in, play mode). Optional refresh-on-playback.

### Phase 5: settings and elevation

* Region 4 add/remove of attributes at each scope (Shift+F10 or the Applications key opens the scope menu); performance indicator modes.
* Global and per-score save and restore; export and import settings.

### Phase 6: testing and soft launch

* The user (NVDA with Chrome and Firefox), then the JAWS tester, run through a checklist (`docs/rsbv_test_checklist.md`).
* Once that passes, a VoiceOver/Safari tester runs the same checklist. Safari is where audio unlocking, AudioWorklet and live-region behaviour are most likely to differ, so expect a round of fixes.
* Fix what they find, then merge `rsbv` to `main` (only on the user's say-so) to publish.
* A short "try it" page and announcement text.

## Testing

* pytest: the bridge (`tests/web/`), the music21-free import guard, and the moved score-config JSON round trip. The existing suite must still pass.
* The fingerprint harnesses gate every change to `parsers/` and `models/`.
* Browser behaviour is checked by hand with a screen reader against the checklist. No automated browser tests in the POC; Playwright can come later if RSBV continues.

## Risks

* NVDA/JAWS taking keys in browse mode: the biggest risk, and the reason for Phase 0, spike 2.
* Latency over 25 ms on some machines: report it; if it's bad, look at a smaller AudioWorklet buffer.
* Pyodide's first load (likely 5 to 15 s, plus the download): show a spoken progress message; later visits use the browser cache.
* Safari/VoiceOver: the least predictable for live regions and Web Audio, and tested last, so problems there surface late.
* Small-SoundFont quality: accepted for the POC.
* Shared-code drift: desktop changes to `models/` or `parsers/` can break RSBV silently. The import guard and the bridge tests in the normal pytest run catch most of it.
