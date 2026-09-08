# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

**Detail lives in `docs/`, not here.** Read the relevant one *before* changing
code in that area:

| Read this | Before touching |
|---|---|
| `docs/architecture.md` | `models/`, `controllers/`, `widgets/`, `audio/`, `persistence/`, the timeline model, Region 5 / Performance Report, Find |
| `docs/parsers.md` | `parsers/` — MusicXML, MIDI, Guitar Pro, Ultimate Guitar, percussion |
| `docs/packaging.md` | anything under `packaging/`, or a failing installer build |
| `docs/dialog_widget_patterns.md` | any new dialog pairing a list with buttons, or mixing `QPushButton`s with a `QDialogButtonBox` |
| `Product Definition Document.md` | any numbered requirement (Ref N) — the authoritative spec |
| `docs/sapi_spike_findings.md` | voice control, if classic SAPI is ever reconsidered |

## Notifications

Handled automatically by Stop/Notification hooks in `~/.claude/settings.json`
(SAPI text-to-speech). No action needed here.

## Project

"Recall Score" (local folder `SReader`, GitHub repo `RecallScore`) — a
screen-reader-first music score and guitar-tab viewer/editor for visually
impaired musicians. `Product Definition Document.md` is the authoritative spec:
roles, numbered functional requirements with acceptance criteria, the 2x2 region
layout, and the intended keystroke map. Read the relevant requirement rows before
implementing a feature; most current code maps directly onto them (pickup-bar
measure numbering is Ref 17, TS-relative beat/duration units Ref 18,
part/staff/voice filtering Ref 7).

**Accessibility is the product, not a polish item.** Notes are rendered as
spoken-friendly text ("F sharp", "B double flat", octave omitted in the note
list), navigation is keyboard-driven with a cyclic region focus loop, and every
timeline move triggers MIDI audition. Ref 9 sets a **25 ms audition latency
budget** — that constraint is why the audio path is in-process FluidSynth rather
than an external MIDI port. Preserve these properties when changing UI or data
formatting.

## Commands

Windows, Python 3.13, dependencies in the checked-out `.venv` (not tracked):

```powershell
.venv\Scripts\python.exe main.py          # run the app
.venv\Scripts\Activate.ps1                # then plain `python main.py`
```

Dependencies are split: `requirements.txt` (runtime — PySide6 6.11, music21
10.5, pyfluidsynth 1.4, python-rtmidi 1.5), `requirements-dev.txt` (pytest,
pytest-qt, pytest-cov), `requirements-build.txt` (pyinstaller, only for the
installer). `mido` is no longer used or installed. No linter is configured.

```powershell
.venv\Scripts\python.exe -m pytest                    # whole suite (~0.6s)
.venv\Scripts\python.exe -m pytest -m "not slow"      # skip music21 tests
.venv\Scripts\python.exe -m pytest tests/models/test_music_data.py::test_name
.venv\Scripts\python.exe -m pytest --cov=models --cov=parsers --cov=widgets
```

VS Code launch config is "Python: Current File" (debugpy) — debug by opening
`main.py` and pressing F5.

### The fingerprint harnesses

**`tests/manual/`** holds two refactor-verification harnesses
(`parser_fingerprint.py`, `model_fingerprint.py`) — **not** pytest tests (pytest
only collects `test_*.py`). They fingerprint every timeline-builder output, and
everything `MusicData` answers, across every score file in `files/`, `examples/`
and `tests/fixtures/`, and `--check` a fresh run against a baseline captured from
an earlier revision.

**Use them as the acceptance gate for any change to `parsers/` or `models/` that
is meant to be behaviour-preserving** — "the tests pass" is not evidence for that
kind of change. See `tests/manual/README.md` for the git-worktree baseline
workflow.

### Two harness invariants (guarded by `tests/test_harness.py`)

* **No window opens.** `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`
  before PySide6 is imported.
* **No audio device opens.** An autouse fixture blocks
  `SynthEngine._init_engine`, so constructing a real engine in a test fails with
  a pointer to the fix. `MainWindow(synth=...)` accepts any object with the
  `SynthEngine` interface; `tests/support/null_synth.py` records calls so tests
  can assert what *would* have sounded.

Timeline tests must build `MusicData(file_path=...)` directly — that walks the
XML with ElementTree in ~1 ms. Going through `MusicXMLReader.load()` also runs
music21 at ~460 ms; those tests carry the `slow` marker.

## Local binaries (never commit these)

`audio/synth_engine.py` needs native FluidSynth DLLs in `bin/` and a SoundFont at
`soundfonts/Airfont_380_final.sf2` (~263 MB). Both directories are gitignored and
exist only in the working tree.

**This is load-bearing.** The soundfont exceeds GitHub's 100 MB file limit;
committing it in August blocked all pushes and cost two days to recover. **Never
`git add` these paths, never remove those `.gitignore` entries**, and if you need
to restore them use `git cat-file blob <sha> > <path>` — `git checkout <commit>
-- bin/` stages the files and reintroduces the problem.

If the binaries are missing the app still runs: `SynthEngine` sets
`FLUIDSYNTH_AVAILABLE = False`, prints a warning, and every playback call becomes
a no-op.

(Airfont_380 replaced the earlier `FluidR3_GM.sf2`, whose piano/viola patches
bake a hard-left/hard-right zone layer into every note — a common GM soundfont
"stereo width" trick that a channel's pan CC can only partially offset — which
defeated the Mixer's pan feature.)

## Packaging (Windows installer)

Three independently runnable steps produce
`dist_installer/RecallScore-Setup-<version>.exe` (an NSIS wizard installing
per-machine to Program Files). All are plain command-line tools the user runs
directly, **in this order**:

```powershell
.venv\Scripts\python.exe -m PyInstaller packaging\VoiceWorker.spec --noconfirm   # MUST run first
.venv\Scripts\python.exe -m PyInstaller packaging\RecallScore.spec --noconfirm
cd packaging; makensis installer.nsi                                             # run from inside packaging\
```

`packaging/build_installer.ps1` is an **optional** wrapper chaining the three
with sanity checks; no step depends on it. `version.txt` (repo root) is the
single, **manually maintained** source of truth for the version — nothing
auto-increments it.

Three gotchas, each with a long explanation in **`docs/packaging.md`** — read it
before changing anything under `packaging/`:

* **NSIS `${__FILEDIR__}`** resolves wrong unless `makensis` is given a bare
  filename from inside `packaging\`, or an absolute path.
* **`console=False` sets `sys.stdout`/`stderr` to `None`**, so this app's
  `print("[ERROR] ...")` handling crashes the bootloader. `main.py`'s
  `_redirect_stdio_if_headless()` fixes it before any other import.
* **The voice worker must be its own `console=True` exe** — three compounding
  reasons, all in `docs/packaging.md`.

Missing optional assets (icon, Vosk model, voice worker) print a `[WARN]` and
degrade the build rather than failing it.

## Architecture

Package-per-domain layout; each module holds one class. Data flows one way:

`main.py` → `MainWindow` → `MusicXMLReader.load()` → `MusicData` → four region
views + `SynthEngine`

| Package | Holds |
|---|---|
| `models/` | `NoteData`, `EventSlice`, `PartStructureInfo`, `MusicData` (the aggregate) and its five collaborators; pure data + lookup tables, **no Qt, no `parsers/` imports** |
| `parsers/` | one `*_source.py` + `*_reader.py` + `*_timeline_builder.py` per format (MusicXML, MIDI, Guitar Pro, Ultimate Guitar), plus `timeline_builder_factory.py` |
| `audio/` | `SynthEngine` (in-process FluidSynth), `Sequencer`, metronome, position announcer, performance cue, live MIDI input, strum/grace scheduling |
| `controllers/` | the behaviour `MainWindow` used to hold: session, playback, navigation, presentation, attributes, focus, persistence, score edits |
| `widgets/` | the five region widgets, the dialogs, `MenuBuilder`, `RegionFocusCycleMixin` |
| `persistence/` | Qt-aware I/O only: global `AppSettings`, per-file `ScoreConfig` (`.rsc`) |
| `tools/` | standalone scripts, **stdlib only, no imports from the app** so they run independently |

### The five regions

Row 1: **1** = score info, **2** = parts/staves/voices. Row 2: **3** = note list
at the cursor, **4** = attributes for the *selected* notes, **5** = performance
markings. Direct-jump shortcuts **Z/X/C/V/B** (regions 1-5, left-to-right on the
bottom row); Tab/Shift+Tab cycle.

### Invariants — break these and something silently regresses

1. **`models/` stays Qt-free**, guarded by
   `test_models_package_does_not_import_qt` **in a subprocess** (the test session
   loads PySide6 via conftest, so in-process `sys.modules` proves nothing).
2. **`models/` never imports from `parsers/`.** That inversion cost 461 ms and
   706 modules to import the data model; it is now 45 ms and 111.
   `MusicData.__post_init__`'s function-local factory import is deliberate —
   don't hoist it to module scope.
3. **`MusicData` is replaced wholesale on every load.** No controller and no
   collaborator may cache it or be cached; everything reads
   `session.music_data` per call.
4. **`MusicData` keeps a one-line delegator for every collaborator method**,
   including private ones tests drive. Put new behaviour in the collaborator that
   owns it.
5. **Put new behaviour in the controller that owns it, not in `MainWindow`.** The
   window is a facade of one-line delegators and read-only properties — the
   stable API region widgets and tests drive. Adding a method there is only right
   if it is wiring. Dialog *construction* stays in the window (tests monkeypatch
   `main_window.<DialogClass>`); the logic behind it belongs to a controller.
6. **`RegionPresenter` is the only controller that touches widgets.**
7. **`RegionFocusCycleMixin` is the single owner of Tab/Shift+Tab.**
   `QAbstractItemView` intercepts Tab at the `event()` level before
   `keyPressEvent()` ever runs, so Tab handling added to a region's
   `keyPressEvent` will not fire. Test the cycle by driving `widget.event(...)`
   and asserting the *cycle method runs*, not just where focus lands.
8. **Two copies of the same fact will diverge** (the "R5 bug class"). A part's
   name lives in both `parts_info.name` and `NoteData.part_name`, joined by exact
   text in the Performance Report; renaming one side silently produces "0 notes"
   for a fully-noted part. Share one source; never write the fact twice.
9. **GM programs are 1-indexed in the model, 0-indexed on the wire.**
   `get_playback_events_for_indices` does the `-1` per part — don't convert
   twice.
10. **After `selectAll()` on Region 3, call `setCurrentRow(0,
    QItemSelectionModel.SelectionFlag.NoUpdate)` outside the `blockSignals`
    window, with the flag explicit.** The one-arg overload collapses the
    selection to row 0 in this PySide6 version, turning "a chord sounds every
    note" into "only the first note sounds". Without any current item, NVDA has
    nothing to announce for a single-note slice.
11. **`Region2ListWidget` labels and row order are mutated in place**
    (`rename_part`, `reorder_parts`), never via `load_score_structure` — that
    resets every node to `enabled=True`, discarding the user's toggles.
12. **`SynthEngine` is only ever touched from the main thread.** Live MIDI input
    keeps that true with an explicit `QueuedConnection` rather than this
    codebase's first lock.
13. **`fluidsynth.Synth(samplerate=...)` must be set in the constructor**, not
    after — setting it later silently keeps rendering at 44100 Hz against a 48000
    Hz stream, i.e. every note ~a semitone sharp.
14. **Report every marking as written.** Never merge, infer, or silently drop —
    a dashed line under a "cresc." is two things in the file and gets two lines.
15. **Timeline conventions:** rests are skipped (navigation lands only on
    attacks); a pickup bar makes the pickup measure **0**; beat positions and
    durations are **relative to the time-signature denominator**, not to quarter
    notes; read repeatable `<notations>` children with `.findall()`, never
    `.find()`.

Everything behind these — why, and what else follows from them — is in
`docs/architecture.md` and `docs/parsers.md`.

## Known gaps

* **Parsing errors are swallowed** with `print("[ERROR] ...")` and partial state.
  Ref 25 / NFR-06 call for an accessible error dialog; prefer moving that way
  over adding more silent prints.
* **Not yet built despite being specified:** voice control, edit mode, MIDI
  export (import is done, Ref 25), Guitar Pro / BME I/O, capo handling, chord
  naming.
* **Metronome click sound** (Ref 14) is functional but not satisfying — two
  synthesis attempts (a sawtooth lead, then GM percussion Claves) were both
  live-tested and found lacking. Functional debt, not a missing feature; see
  tasks.txt E11 / D-14.
* **Voice control (Ref 19):** the classic SAPI 5.4 approach was built,
  live-tested and abandoned (accuracy, not plumbing). Current path is Vosk
  (tasks.txt L1). The code is preserved on branch `feature/voice-control`;
  findings are in `docs/sapi_spike_findings.md`. **None of that code should be
  revived as-is.**
* **Ornaments and notations are parsed as label-only, findable data — never
  audibly realized.** A trill plays as the plain written note, an
  `<octave-shift>` does not transpose playback, a fermata does not lengthen it.
  This is a standing decision, not an oversight: synthesizing a trill/mordent/turn
  needs its auxiliary pitch, which MusicXML doesn't encode directly (the diatonic
  neighbour under the active key, optionally altered by a sibling
  `<accidental-mark>` — a new inference heuristic in the spirit of
  `spell_pitch`). The user weighed that against grace notes' own "brief pre-note,
  not exact performance practice" simplification and judged the inference risk not
  worth it. Ties, arpeggios, pedal and octave shift are likewise label-only.

  What **is** read and surfaced (Region 3/4 text plus Find targets): `tied`,
  `slur`, `fermata`, `arpeggiate`/`non-arpeggiate` on chord notes,
  `time-modification` (tuplet), cautionary/editorial `<accidental>`,
  `glissando`/`slide`, `technical` marks beyond fret/string/fingering/pluck, plus
  a catch-all for any unrecognised `<notations>` or `<direction-type>` child.
  Still genuinely unparsed: `notations/caesura` and `breath-mark` (timing, not
  pitch — though `breath-mark` under `<articulations>` is caught by the wildcard
  merge).

## Working autonomously

The user has given **standing authorization for routine implementation and
debugging actions** during a coding task — running tests, writing and running ad
hoc repro scripts, reading/searching files, non-destructive edits — without
pausing to check in first.

It does **not** extend to destructive or hard-to-reverse actions (force-push,
`reset --hard`, deleting files not created this session), which still need
explicit confirmation each time.

`.claude/settings.json` allowlists `.venv/Scripts/python.exe -m pytest *`
(read-only test runs) to cut down prompts; rerun the `fewer-permission-prompts`
skill periodically as new frequent read-only patterns show up. Ad hoc
`python -c` / interpreter invocations are deliberately **not** allowlisted —
that's equivalent to arbitrary code execution and stays a per-prompt approval,
though the user may grant it locally via `.claude/settings.local.json` (not
checked in).

## Git workflow

Standing authorization to commit and push once the user says "commit" / "push" /
"commit and push" for that request — don't ask again first. Does not extend to
force-push, `reset --hard`, or other destructive operations.

**Merge a feature branch to `main` only on explicit request.** "Commit and push"
on a feature branch does not mean merging it. `feature/ug-import` was created
deliberately off `main` because the whole feature was speculative ("I want to be
able to roll back... if testing shows this rather experimental endeavour does not
work well enough"); it was fast-forward merged on 2026-08-16 (`fb98091`) only
after the user confirmed testing held up. The same reasoning applies to any
future speculative feature.

## Git recovery notes

Local tags `recovered-2026-08-03` (= `b4b7c52`) and `pre-reset-tip` (= `b914f67`)
pin the August commits that a hard reset orphaned, so `git gc` can't drop them.
**Do not push these tags** — their ancestry contains the 148 MB soundfont and the
push will be rejected. The recovered content is already on `main` as `8385e59`,
applied as a fresh tree copy rather than a merge for exactly that reason.

`git show 520f743:test_midi_latency.py` recovers a latency benchmark deleted
before the reset — the only test file this project has ever had.
