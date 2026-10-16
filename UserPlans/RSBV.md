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

* 1.7 (2026-10-08). `tests/web/test_web_api.py` (conftest puts `web/py` on
  the path) loads `.musicxml` fixtures and `bach-bourree-tab.mxl`, asserts the
  summary JSON shape, the `{"error": ...}` dict for a broken file and an
  unsupported suffix (previous score kept), and no-score handling. Fast, no
  music21. Phase 1 is complete; next is Phase 2 (2.1 is Opus). Before that the
  user should try the skeleton in a browser: `python tools/stage_web.py
  --serve 8000`, open `/app/`.

* 2.1 (2026-10-08). Page accessibility core in `web/app/js/`:
  `announcer.js` (queue at a 250 ms gap, `ariaNotify` else two alternating
  live regions per priority, created by the module; `announce(text,
  priority)`, `announceUrgent`, `dropPolite`; assertive jumps ahead of
  waiting polite messages), `keymap.js` (the single key table as strict JSON
  between `KEYMAP-BEGIN`/`END` markers, `bind(id, handler)`, one capture-phase
  document `keydown` dispatcher; scopes `regionN` > `list` > `cycle` >
  `global`; ignores keys in editable fields and open dialogs; Escape never
  bound), `focus.js` (cycle Menu, Regions 1 to 6, Tab/Shift+Tab wrap only
  inside the cycle, Z X C V B N jumps). Region 6 key is N (decision 2).
  `web/CLAUDE.md` holds the browser rules. Guard:
  `tests/web/test_keymap_table.py`. Menu button is a stub until 2.5.
* 2.2 (2026-10-08). Bridge: `web_api.region_rows(n, selection)`, `view()`,
  `move(direction)` (left, right, bar_left, bar_right, first, last),
  `goto_bar(n)`, `jump_point(dir)`, `section(delta)`,
  `selection_changed(sel)`, `attribute_announcement(n, sel)`,
  `set_uk_terms`. Move results carry `moved`, `boundary`, `announce` (speak
  before redraw), `barline` and Regions 3 to 6 plus Region 3's select-all
  selection (sections re-send all six). Load seeds the desktop's global
  defaults and builds Region 2's tree from the shared
  `Region2HierarchyModel`. Shared code: `models/announcements.py` holds all
  `RegionPresenter` announcement wording and `PlaybackController`'s
  metronome, announcer and loop-length status text; jump-point stepping
  moved to `TimelineNavigator.move_to_jump_point`. Region 1 gets a
  "section" row for multi-section files (Left/Right steps it; its own
  reading replaces the spoken message). Not done: Region 5 Alt+Home/End
  span jumps (logic still in `NavigationController.jump_to_span`). Tests:
  `tests/web/test_web_api.py`, `tests/models/test_announcements.py`.
  Model fingerprint MATCH, fast suite passes. Smoke-tested in headless
  Chrome under real Pyodide, no screen reader yet.
  To make 2.1/2.2 testable, `regions.js` is a minimal renderer (options
  with fresh ids per render, Up/Down/Home/End, Ctrl+A, skip re-render when
  text is unchanged except Region 3); 2.3 extends it (Shift-select, tree
  expand/collapse, Region 4 re-anchor by `key`). Boundary and bar line
  sounds wait for Phase 3, so a move that hits an end is silent for now.

* 2.3 to 2.7 (2026-10-08). Phase 2 is complete, not yet committed.
  2.3: `regions.js` now does Region 3 Shift+Up/Down/Home/End (anchor-based),
  Region 4 keeping the current row on the same attribute `key` across a
  rebuild, and the Region 2 tree (Right opens or steps in, Left closes or
  steps out, collapsing forgets descendants' open state; expand state is the
  page's). 2.4: `web_api.region2_toggle(node_id, kind)` and
  `region2_clear(kind)` (F8, F9, Alt+F8, Alt+F9, Region 2 only); the row text
  carries "muted"/"soloed", only Unmute/Unsolo All are spoken. 2.5:
  `app/js/dialogs.js` (native `<dialog>`: Menu, F1 keyboard help, Go to bar
  on Ctrl+G), all built from the keymap, each with a Close or Cancel
  button. Typed bar number: bare digits accumulate in Python
  (`append_digit`, `commit_digits`, `clear_digits`), Region 6's first field
  shows "Go to measure: 12", Enter jumps (falls through to a focused button
  when nothing is typed), any move cancels it. Backspace cancels too, as the
  web never binds Escape. The Menu lists every bound command except the
  focus-dependent ones, plus "Open a score". 2.6: re-test page is
  `spikes/spike2_keys.html?set=retest`; the user still has to run it with
  NVDA in both browsers and paste results into
  `docs/rsbv_spike_findings.md` ("Key re-test"). 2.7:
  `tests/web/test_keymap_drift.py` checks every row with a `desktopAction`
  against the real desktop menus. Not done: Ctrl+Enter (loop length, Phase 4).
  Smoke-tested in headless Chrome under real Pyodide (tree, mute, typed
  bar, Go to bar, help, menu); no screen reader yet. Fast suite passes.

### RESUME HERE (2026-10-16): merged to main and published

The user tested a desktop build from `rsbv` (all fine) and asked for the
merge (7.5, ahead of 7.1 to 7.4). Before it, GitHub Pages served `docs/`
from `main` (legacy build): the installer download page `web_page/`, the
user guide and friends, linked from the desktop user guide. Switching
Pages to "GitHub Actions" replaces that site, so `stage_web.py` now copies
`docs/*.html`, `docs/licence.rtf` and `docs/web_page/` to the site root
(test in `tests/web/test_stage_web.py`), and leaves out `web/ToRun.txt`.
Markdown pages Jekyll used to render from `docs/*.md` (architecture and
so on) are no longer published; nothing linked to them.
Next: a tester guide (7.1/7.4) for the JAWS tester; feedback route still
to agree with the user.

### Was (2026-10-16): 5.4 committed; Phase 6 skipped, next is letting others use it

The user tested 5.4 with NVDA (Firefox, and Chrome for the Left Arrow
bug) and it passed. Same round added: M opens the Menu from anywhere in
the cycle (closing without a choice goes back to the region M was pressed
in), and Left/Right that no keymap row takes in a list region (Regions 4,
5, 6, Region 1 off its section row) are swallowed in keymap.js: left to
Firefox, NVDA said "Recall Score document" and then went silent in that
region (Chrome was fine; the DOM focus never moved, so it is Firefox's
own handling of the key). Decided in testing: the performance indicator
clap stays as the desktop has it (sounds only for a marking in the note
list; to try it, `dynamics_articulation_fingering.musicxml`, B, Alt+N);
the "Open a score" control at the top stays unless other testers ask.
Fresh-profile terminology (browser language) was not tested; left for now.

Next: the user skips Phase 6 and moves on to letting other people use the
web version (Phase 7: test checklist, testers, the public deploy via 1.6's
GitHub Pages workflow and merging `rsbv` to `main`, 7.5). Plan that step
with the user first.

### Was (2026-10-14, end of day): 5.4 built, NOT committed, user testing not complete

Working tree holds 5.4 uncommitted on `rsbv` (git status shows the
files). Tomorrow: the user finishes testing with NVDA, then commit
(on the user's say-so) and move to Phase 6. Still to check with NVDA, in
Firefox and Chrome:
* Menu > Options: each toggle reads checked/not checked, each radio item
  (terminology, performance indicator) reads its state, and the tick is
  not read aloud as text.
* Choosing UK or US terminology speaks it, then Region 3 reads its row;
  Region 6 and Region 4 show bar/measure, crotchet/quarter.
* Choosing a performance indicator item speaks the mode.
* Ctrl+V reaches the page (not swallowed as paste) in both browsers, says
  "Engraving details on/off", and clef change / octave shift rows appear
  (clef_change.musicxml, octave_shift.musicxml).
* After a reload all three are kept; with a fresh profile the terminology
  follows the browser's language.

The Options menu now holds what the desktop's Options menu has that
makes sense in a browser: UK terminology / US terminology (radio items),
Bar line indicator, the three Performance indicator choices (radio
items) plus Ctrl+C's cycle, Show engraving details (Ctrl+V, new,
desktopAction show_engraving_details), Metronome, Position announcer.
Toggles are `menuitemcheckbox`, choices `menuitemradio`, both with
aria-checked from `web_api.options_state()`; the desktop's two submenus
are flattened (the web menu has two levels). A choice from the menu is
spoken ("US terminology", "Performance indicator always on.") because
focus lands on a region. Terminology redraws Regions 1, 3 to 6 keeping
places and Region 3's selection; Ctrl+V redraws 3 to 6. All three are
global, work with no score and are saved at once.
Default terminology with nothing saved: UK unless the browser's
language names the US region (`models/vocabulary.default_uk_terms`, the
desktop's rule; "en" alone stays UK). Used, not stored, so it follows the
browser until the user picks one. Shared wording added to
`models/announcements.py` (`terminology`, `engraving_details_toggled`;
the desktop's Ctrl+V now uses the latter). Tests:
`tests/web/test_web_options.py`; fast suite passes. Headless Chrome
(clef_change.musicxml, --lang=en-GB): starts UK, US redraws Region 6 to
"Measure"/"quarter", Ctrl+V brings in the clef change rows, all three
survive a reload. Left out as not making sense in a browser (yet): Live
MIDI input (Web MIDI is possible, Phase 6 if wanted), voice control,
MuseScore location; Attribute Management stays 5.1's "if time allows".
Known: menu and F1 labels say "bar" whatever the terminology (static
keymap labels).

### Was (2026-10-14): 5.3 done and committed (e40e10a); next was 5.4

`app/js/storage.js` keeps settings in localStorage: global under
`recallscore.settings` (settings.json text), each score under
`recallscore.score.<SHA-256 of its bytes>` as {name, saved, config}, config
being the desktop `.rsc` dict. Bridge: `global_settings_json()`,
`apply_global_settings(text)` (at start-up), `score_settings_json()`
(export_config plus Region 2's own mute/solo, as
ScorePersistenceController.save_current; the start position while playing),
and `load(bytes, name, saved)` now applies
the stored `.rsc` in MainWindow._on_score_loaded's order (apply_config,
then Region 2's per-node mute/solo); unreadable saved text opens with
defaults and is reported in `settings_error`, spoken after "Loaded".
`_adopt` now reads show_engraving_details from the stored AppSettings.
Writes: global on Ctrl+C and Alt+N; a score's on opening another and on
pagehide/visibilitychange hidden. A storage write failure is spoken once.
Settings import/export (all settings, or a desktop .rsc) was built and then
removed at the user's request: saving is automatic, so add it back only if
a tester asks. Tests: `tests/web/test_web_storage.py`; fast suite passes.
Headless Chrome (hairpins_two_parts.musicxml): Ctrl+M, three Rights and F8
on Guitar survive a reload. Not done: the desktop's "Clear
Preferences" (not in 5.3's scope); uk_terms has no web control yet (5.4).

### Was (2026-10-14): 5.2 done and committed; next was 5.3

Confirmed by the user with NVDA in Firefox: Ctrl+C, Alt+N (it does reach
the page), the Region 5 menu and the cue all work.

Shared code: `audio/navigation_cues.performance_indicator_cue(mode, rows,
manual_move, playing)` is now the one fire decision; RegionPresenter.
update_timeline_views calls it (desktop behaviour unchanged).
`models/marking_categories.note_list_menu_label` words Region 5's menu
item; MainWindow.show_region_5_context_menu uses it. Bridge:
`cycle_performance_indicator()`, `toggle_marking_category(row)`,
`region5_menu(row)`; the mode and the categories are module globals that
outlive a load (the desktop's AppSettings; kept across visits in 5.3).
Every move's sound plan gets a "cue" one-shot when the mode is not Off
and the note list has a marking row; with Always on each playback step
carries it too (the step's note list is read by briefly setting the
cursor to the step while planning). Keys: Ctrl+C (global, Options menu),
Alt+N on a Region 5 row (Ctrl+N on the desktop; browsers keep Ctrl+N for
a new window, so this is a `difference`), Shift+F10 /
ContextMenu / right click on Region 5 for the one-item menu. Tests:
`tests/web/test_web_performance_indicator.py`; fast suite passes.
Headless Chrome (ts_change.musicxml): Ctrl+C speaks the mode, Alt+N
speaks "Structural changes, in note list", Region 5 gains its "* " in
place with focus kept, the note list gains the change row, the menu offers
Remove and its Enter speaks "not in note list" back on the row. Not done: the Options submenu's three direct
choices (the web menu has no radio items; Ctrl+C cycles), and Show
Engraving Details (Ctrl+V on the desktop; outside 5.2's scope).

### Was (2026-10-14): 5.1 done and committed; next was 5.2

5.1 built and confirmed by the user with NVDA. `models/attribute_scopes.py` holds the scope
menu's wording and filters (`scope_action_labels`,
`filter_scopes_for_node_level`, `filter_scopes_for_part`) and
`region_4_scope_menu(music_data, selection, row)`, which AttributeController
(`menu_actions`, `order_menu_actions`) now calls. Bridge:
`region4_menu(row, selection)` gives {title, items: [{scope, label}]}
(title is the Region 4 row's own name, e.g. "note 1 octave");
`region4_apply(row, selection, scope)` changes it and re-sends Regions 3
and 4. Page: key row `attributes.scopeMenu` (Shift+F10, ContextMenu,
Region 4 only), `menu.js` `showContextMenu`, plus a `contextmenu`
listener (ContextMenu key in Firefox, right click). Nothing spoken; focus
returns to the Region 4 row. Tests: `tests/models/test_attribute_scopes.py`,
`tests/web/test_web_attribute_scopes.py`; desktop attribute tests and the
fast suite pass. Headless Chrome: open, Left and Tab close to the row,
choosing "for this voice" turns E into E4, the menu then offers Remove.
Not done (plan's "if time allows"): the Attribute Management dialog
(order, hide, its own Add/Remove). Next: 5.2.

### Was (2026-10-14): 4.3 and 4.4 committed; finish NVDA checks, then Phase 5

User test round 1 (NVDA, Firefox) and fixes, same day:
* F, S, D, Alt+PageUp/PageDown, Ctrl+I and the Playback menu's Play
  Settings work. Ctrl+Shift+P is Firefox's private window, so the web's
  Play Settings key is Ctrl+Alt+P (a `difference` in the key table).
* Lead-in clicks were silent. Cause: the worklet synth ignores init()'s
  settings, so it had 16 channels and dropped every app sound on channels
  251 to 255 (clicks, spoken beats, boundary cue, bar line indicator), by
  key and in playback alike. audio.js now passes SETTINGS to
  createAudioNode (256 channels, gain 0.7 as on the desktop); measured in
  headless Chrome, the count-in clicks now sound. Everything is louder
  than before (gain 0.7 instead of FluidSynth's default 0.2).
* Play Metronome is now unavailable during playback (playing, paused or
  counting in) on both versions: Ctrl+M is for a click with the music
  (user's decision). Round 2: the user asked for default behaviour rather
  than a spoken "Stop playback first", so the desktop greys out the
  QAction (its shortcut then does nothing) and the web Menu marks the item
  aria-disabled from web_api.disabled_commands(); the key does nothing.
  Lead-in clicks confirmed audible by the user.
* Open: the user thought the Bourree from bar 7 with a 10-bar loop did not
  respect the first-time ending. The plan (same on the desktop) plays
  7, 8 (first-time ending), 1 to 7, 9 (second-time ending) for "first";
  asked the user what they heard and expected. Round 3: the user
  re-tested and the endings are handled correctly.
* Round 3 (NVDA, Firefox): every 4.3/4.4 shortcut works. Ctrl+Shift+P
  still opens Firefox's private window, which a page cannot stop; the
  web's Ctrl+Alt+P is the key to use.
* Desktop fix: Metronome Player and Play Metronome stayed greyed out
  after a stop that put the cursor back, because that stop reports
  itself through `cursor_moved`, not `playback_state_changed`.
  MainWindow now refreshes both actions on either signal
  (`_refresh_playback_blocked_actions`). Confirmed working by the user.

4.3 and 4.4 committed as `1a3095d` (not yet pushed). Keys (all global): Ctrl+Alt+Space free
metronome, Ctrl+L play mode, Ctrl+I lead-in, Ctrl+R loop repeat handling,
Alt+PageUp/PageDown loop length, Ctrl+Enter typed loop length, F/S/D
tempo, Shift+Space sounds the selection again (Ref 13), Ctrl+Shift+P Play
Settings (now Ctrl+Alt+P, see below); all on the Playback menu. Shared code: `PlaySettings`
`with_play_mode`/`with_lead_in_enabled`/`with_loop_repeat_mode`/
`next_play_mode`/`next_loop_repeat_mode`, the dialog's labels and
enabled-state rules (`dialog_labels`, `dialog_enabled_states`,
`PLAY_MODE_LABELS`, `LOOP_REPEAT_LABELS`) in `models/play_settings.py`;
`announcements.lead_in_toggled`, `LOOPING_OFF`, `NO_REPEATS`;
`audio/free_metronome.py` (staged). The desktop PlaybackController,
MainWindow and PlaySettingsDialog use them. Bridge: `play_metronome`,
`tempo`, `play_setting`, `commit_loop_length`, `play_settings_form`,
`play_settings_enabled`, `apply_play_settings`. Deliberate difference:
the free metronome is refused during playback on both versions. Tests:
`tests/web/test_web_play_settings.py`, new cases in
`tests/models/test_play_settings.py`. Model and playback fingerprints
MATCH, fast suite passes. Headless Chrome under real Pyodide: every key
speaks the right text, Region 6 follows, the dialog opens on the tempo
field, enables fields as on the desktop, OK applies. Not yet heard or
tried with NVDA before round 1. All tested with NVDA in round 3.
Not done:
Ctrl+H and Delay Refresh (the web always follows playback).

### Was (2026-10-14): 4.2 built; user to test Space and Ctrl+Space, then 4.3

4.2 built, not committed. `models/play_plan.py` gained `PlayTimeline`
(the whole run as timed entries: count, step, restart, end; pause and
resume via per-step walker snapshots) and `StepWalker.snapshot/restore`.
Tests: `tests/models/test_play_plan.py` compares the timeline with the
desktop on a virtual clock (`tests/support/virtual_clock.py`) for 7
play modes on 4 score positions. Shared wording and cues:
`announcements.playback_status` (the desktop status field uses it),
`navigation_cues.position_cues_at` and `count_in_cues` (Sequencer and
the count-in use them). Playback fingerprint still MATCH.
Bridge: `play_toggle`, `play_plan`, `play_cursor`, `play_ended`,
`play_pause`, `play_stop`; Region 6 shows the real playback state; a
move while paused drops to Stopped; a load stops playback. Tests:
`tests/web/test_web_playback.py`. Page: `app/js/scheduler.js` (FluidSynth
sequencer in the worklet, see web/CLAUDE.md "Playback"), Space and
Ctrl+Space in the key table, a Playback menu. Space on a focused button
or input is left to it. Headless Chrome under real Pyodide: play, cursor
follows in time, pause, resume, stop and cursor restore all work, no
errors; not heard yet. Play mode, lead-in and tempo keys are 4.3, so for
now only plain play-to-end can be tried from the page.

### Was (2026-10-14): 4.1 done; next was 4.2 (scheduler.js, Opus)

4.1 built, not yet committed. `models/play_plan.py` holds the play plan
for both versions: `PlayRun` (was `_PlayRun`; the controller keeps the old
name as an alias because tests use it), `build_play_run`,
`refresh_play_span`, `phrase_end_index`, `loop_seed_jump_state`,
`iteration_events` and `plan_iteration` (count-in clicks, then
`("play",)`), `play_from_arguments`, `restart_with_lead_in`,
`ends_when_notes_finish`, `loop_restart_events`, and `StepWalker` (the
Sequencer's jump-aware stepping, bar budget and step delays, now used by
`audio/sequencer.py`). For 4.2: `step_chunk(walker, index, retrigger,
horizon_ms)` gives the steps of the next chunk with offsets, reading the
tempo per chunk. The caller passes the index it is on (the desktop's
resume re-asks from the paused step). `audio/lead_in.py` moved to
`models/lead_in.py` (and out of stage_web's audio list; models/ ships
whole). What sounds at a step is still the caller's: the bridge should
build it from the shared builders, as move results already do.
Gate: new `tests/manual/playback_fingerprint.py` (12 play scenarios per
file on a virtual clock, 108 files) MATCH against a baseline from before
the change; model fingerprint MATCH; fast suite passes; new
`tests/models/test_play_plan.py` compares plan steps with the desktop
Sequencer (repeats, D.C., a budgeted loop, a real score).
For 4.2, the web flow is: `build_play_run` (or, with no lead-in and no
loop, a plain walker from the cursor), `plan_iteration`, walk
`run.events`; at `("play",)` make a `StepWalker` from
`play_from_arguments` and feed `step_chunk` to the scheduler; when the
chunk says the run is over, `ends_when_notes_finish` decides between stop
and `loop_restart_events`, and a restart bumps `iteration_count` then
calls `plan_iteration` with `restart_with_lead_in(run)`.

### Was (2026-10-14): Phase 3 done; Phase 4 (playback) is next

The user heard Phase 3 with NVDA in Firefox: Left/Right, Ctrl+Left/Right
and typing a bar number all sound where the cursor lands. The first try
was silent: the synth started on the first keydown even when it was a
modifier (Shift+Tab), which the browser does not count as a gesture, and
audio.js then awaited `resume()` forever. Fixed in audio.js (see the
Sound section of `web/CLAUDE.md`). Next: Phase 4, task 4.1 (extract the
play plan).

### Was (2026-10-14): Phase 3 built, waiting for the user's NVDA test

Phase 3 (3.1 and 3.2) is built and smoke-tested in headless Chrome:
* `audio/navigation_cues.py` (new, shared): `position_cues` (metronome click,
  spoken beat) and `barline_indicator_events`. PlaybackController now calls
  it (behaviour unchanged, fast suite passes); staged for the web.
* `web_api.py`: every move result carries `sound` (audition of the new
  slice, then position cues, then bar line steps; boundary cue alone on a
  refused move); `audition(selection, cues)`, `toggle(kind)`,
  `synth_setup()` (app channel pans from the Mixer defaults).
* `app/js/audio.js`: js-synthesizer driver, starts on first gesture,
  SynthEngine's retrigger / group note-off / grace / one-shot slots.
* Keys: Ctrl+B, Ctrl+M, Ctrl+P (Options menu too), wording moved into
  `models/announcements.py` (desktop uses it as well). Region 3 Up/Down
  sound the row (notes only), Ctrl+A sounds the chord with cues.
* Not done: the performance indicator cue (its mode is a Phase 5 setting
  and defaults to Off, so it could never fire yet); per-part mixer volume
  and pan (needs saved settings).

### Was (2026-10-14): NVDA silence SOLVED; the Menu dialog is next

The user ran step 5 (PASS) and then the real `/app/` with NVDA in Firefox:
it works. Load, Tab cycle, Z X C V B N, Up/Down in every list, Region 2
expand, single note select, Ctrl+A, Ctrl+Left/Right by bar all speak. The
silence was the old activedescendant/focus code that the roving-focus change
replaced; the bisect is over and `web/basic/` can be deleted (it was never
committed). Not yet tried: F8/F9 mute and solo, typed bar number, Ctrl+G,
F1, the 2.6 key re-test.

The Menu button's dialog was "confusing and not usable" (a modal
`<dialog>` of h3 headings and ~30 buttons). Replaced the same day by
`app/js/menu.js`: a real ARIA menu shaped like the desktop menu bar (File,
Edit, Parts, Navigation, Help as submenus; see web/CLAUDE.md "Menu").
Smoke-tested in headless Chrome (open, arrows, submenus, letters, Escape,
Left, Tab, mute lands on the Region 2 row, Help opens). Next: the user
tries it with NVDA. Then Phase 3.

### Was: bisecting the NVDA silence bottom-up in `web/basic/` (2026-10-13)

Instead of debugging the full app, the user asked to pare back to a trivial
page and add the app's pieces one at a time until NVDA goes silent. All
pages are temporary, uncommitted, staged with the site
(`python tools/stage_web.py --serve 8000`, open `/basic/`, Ctrl+F5 after
each restage). The user tests with NVDA in Firefox.

Results so far (all PASS = NVDA reads every row as arrows move):
* `basic/index.html` Step 1: native `<select size>` with Region 1 rows. PASS.
* Step 2: hand-built `role="listbox"`, roving focus, its own keydown. PASS.
* Step 3 checkboxes, each alone and all together: A capture-phase document
  keydown with stopPropagation; B rebuild the option elements every move;
  C `announceUrgent("Row N")` via the real announcer.js (both row text and
  "Row N" heard); D the app's rsbv.css (no difference to speech);
  E page-handled Tab swapping between the two boxes (wraps; Escape to
  browse mode reaches the checkboxes). PASS.
* `basic/step4.html`: the real index.html region markup + Menu button +
  rsbv.css, the REAL regions.js, keymap.js and focus.js, binding only
  list.*, tree.expand/collapse (Tab, Z X C V B N come from focus.js). Load,
  Z, arrows in every region, Region 2 expand, Tab cycle incl. Menu button.
  PASS.
* `basic/step5.html` (built, NOT yet tested by the user): step 4 plus the
  app's loading behaviour copied from app.js: say() through the announcer
  ("Starting", "Ready", "Loading", "Loaded ..."), the role=alert error box
  and drop zone markup, and `focusRegion(3)` after a load. Headless Chrome
  confirmed it boots to "Ready. Choose a score file."

So regions.js, keymap.js, focus.js, the announcer and the CSS are cleared.
What app.js still adds beyond step 5, the remaining suspects:
* `import "./debug.js"` (inert without ?debug, but it is imported).
* dialogs.js and the Menu button's click handler (showMenu).
* Every other binding: nav.* (Python move + applyMove, which speaks then
  re-renders Region 3 and 4 while focused), section, digits.* (global
  Enter and Backspace!), goto.bar, help.keys, region2 mute/solo,
  attributes.speak, notes.selectAll, list.extend*.
* The "list" handler in app.js also calls refreshRegionFour() on Region 3
  moves (Python call + Region 4 re-render).
Next steps: user tests step 5. If PASS, step 6 = step 5 + dialogs.js and the
Menu click handler + debug.js import; step 7 = the remaining bindings
(likely just point at the real `/app/` again and compare). Also worth
asking the user to retry the real `/app/` as-is: it has not been tried with
NVDA since the roving-focus change was finished, and step 4 shows that
code works.

### OPEN PROBLEM (2026-10-08, end of day): NVDA is silent on the app page

Resume here before anything else. User uses Firefox (default) and Chrome with
NVDA. After loading Cavatina (not in the repo; any score may do):
* Tab reaches Score information, but Down Arrow makes NVDA say "Recall Score
  document" once, then nothing. Same in every region. In Chrome NVDA is fully
  silent. Enter/Space on the Menu button does nothing audible.
* Headless Chrome (CDP script, key events) shows the page is correct: focus
  moves, Down moves the row, F8 mutes, Menu and F1 open dialogs, even on the
  Blue Danube. The Phase 0 spike pages are heard fine on the same machine and
  server, so it is something about the real page, not NVDA, the server or the
  browser. Ctrl+F5 changed nothing.
* Tried: switched regions from `aria-activedescendant` to real roving focus
  (regions.js, focus.js, index.html lost the regions' tabindex). The user said
  that was slightly worse: Tab in browse mode now did nothing and they had to
  press NVDA+Space to get into focus mode; arrows still silent. Roving focus
  is still in the tree, uncommitted. Reverting to activedescendant is the
  fallback if the debug log shows nothing; the earlier version let Tab work.
* Added `web/app/js/debug.js`: open `/app/?debug`; a "Debug log" section at
  the end of the page lists keydown, focusin/focusout and errors (button
  copies it). Next step: user reads or pastes that log (Firefox, load a score,
  Tab, Down, Down, then go to the end of the page in browse mode).
* Ideas not yet tried: NVDA log at "Input/output" level (writes spoken text
  to nvda.log in the temp folder, readable by Claude); bisect against the
  Phase 2.1/2.2 commit (60337ac) to see whether the silence predates 2.3 to
  2.7 (the user never tried that version with NVDA); strip the page down
  (no announcer, no capture-phase key handler) until NVDA speaks; check
  whether `ariaNotify` calls (high priority) are cutting off NVDA speech.
* Staging server: `python tools/stage_web.py --serve 8000` (it can only run
  one at a time on port 8000).

### Next: Phase 3 (sound on navigation), 3.1 is Opus. Before it, the user should try Phase 2 with NVDA and run the 2.6 re-test.

### Was next: Phase 2 from 2.3 (Sonnet)

Read `web/CLAUDE.md` first. Before 2.3, the user should try 2.1/2.2 with
NVDA: `python tools/stage_web.py --serve 8000`, open `/app/`, load a score,
check Tab wrap, Z X C V B N, Left/Right and Ctrl+arrows in Notes, and that
"Measure N." is heard before the note.

### Earlier: finish Phase 1 with 1.5, 1.6, 1.7 (all Sonnet)

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
