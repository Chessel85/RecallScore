# Packaging: the Windows installer

Read this before changing anything under `packaging/`, or when a build
misbehaves. The commands themselves are in `CLAUDE.md`.

Three independently runnable steps produce
`dist_installer/RecallScore-Setup-<version>.exe` — a standard NSIS wizard
installing to Program Files (per-machine, requires admin — a deliberate choice,
confirmed with the user) with a real uninstaller under Add/Remove Programs. All
are plain command-line tools the user runs directly, **in this order**:

```powershell
.venv\Scripts\python.exe -m PyInstaller packaging\VoiceWorker.spec --noconfirm   # MUST run first
.venv\Scripts\python.exe -m PyInstaller packaging\RecallScore.spec --noconfirm
cd packaging; makensis installer.nsi                                             # run from inside packaging\
```

`packaging/build_installer.ps1` is an **optional** one-command wrapper chaining
the three with sanity checks; none of the steps depend on it.

### The three real gotchas

* **NSIS 3.11 `${__FILEDIR__}`** resolves to a doubled, wrong path when the
  script is passed as a relative path with a directory component (e.g.
  `makensis packaging\installer.nsi` from the repo root). Only a bare filename
  (cwd already inside `packaging\`) or a fully absolute path resolves correctly.
  `build_installer.ps1` is unaffected since it always passes an absolute path.
* **`console=False` nulls `sys.stdout`/`sys.stderr`** (sets them to `None`, not
  just closed). This app's error handling is `print("[ERROR] ...")`-based
  throughout, so the moment anything on that path prints — e.g. `_init_engine`
  catching a WASAPI failure on a machine with no sound device — `print()` itself
  throws `AttributeError: 'NoneType' object has no attribute 'write'`, surfacing
  as "Failed to execute script 'main'". `main.py`'s
  `_redirect_stdio_if_headless()` (called before any other import) redirects to
  `%LOCALAPPDATA%\Recall Score\recall_score.log` (falling back to `os.devnull`)
  so every existing `print()` keeps working unmodified.
* **The voice worker must be its own `console=True` exe.** Three compounding
  reasons: `audio/voice_recognition.py` never imports `vosk`/`sounddevice`
  itself (only the worker script does, in a child process, to dodge a DLL-name
  collision with FluidSynth's bundled MinGW runtime), so a single combined build
  never discovers them; once frozen, `sys.executable` **is** `RecallScore.exe`
  (no separate `python.exe` ships) and the `.py` source isn't a loose file; and
  `console=False` would break the worker's newline-delimited-JSON stdio protocol
  per the point above. Launched by `_worker_command()` with the Windows
  `CREATE_NO_WINDOW` flag so no console is shown.

### Spec details worth knowing

* **`packaging/VoiceWorker.spec`** explicitly collects `libvosk.dll` (plus its
  bundled MinGW runtime copies) via `collect_dynamic_libs("vosk")`, since
  `vosk/__init__.py`'s `open_dll()` `dlopen`s it relative to
  `dirname(vosk.__file__)` — not discoverable by PyInstaller's import-graph scan.
  `sounddevice`'s PortAudio DLL needs no equivalent (`pyinstaller-hooks-contrib`
  covers it). `VOSK_AVAILABLE`/`MODEL_DIR`/`WORKER_EXE` are frozen-aware:
  `find_spec("vosk")` always reports unavailable in the frozen **main** process
  by design, so frozen availability checks `WORKER_EXE`'s existence instead.
* **`packaging/RecallScore.spec`** bundles `bin/*.dll` and the SoundFont into the
  frozen app — this works with **zero changes** to `synth_engine.py`'s
  `PROJECT_ROOT`/`BIN_DIR` resolution, because PyInstaller fakes frozen modules'
  `__file__` to a path under `sys._MEIPASS` matching the source tree. **The same
  `sys._MEIPASS`-aware idiom is used everywhere** a bundled asset is resolved:
  `version.txt` (`version.py`), the icon (`main.py`'s `_app_icon_path()`),
  `docs/user_guide.html`, `examples/*`, and `MODEL_DIR`.

  It excludes music21's bundled example-score corpus (~58 MB — the app only ever
  calls `converter.parse()` on the user's own file, never `music21.corpus`) and
  excludes `matplotlib`/`PIL` entirely, which music21 declares as hard
  dependencies purely for its unused `graph`/`audioSearch` modules.

  It also bundles the ~205 MB Vosk model (`vosk_model_large/`, gitignored, not
  pip-installable) and `VoiceWorker.spec`'s already-built output
  (`voice_worker/`) via `Tree(...)` post-`Analysis`. Both are guarded like
  `icon_path`: **missing either prints a `[WARN]` and degrades the build to "no
  voice control" rather than failing it.** `voice_worker/` is bundled as a
  subfolder of `RecallScore`'s own dist output specifically so `installer.nsi`'s
  recursive `File /r` copy needs no changes.

  It regenerates `packaging/version_info.txt` (the Windows exe version resource,
  not tracked in git) from `version.txt` on every run.
* **`version.txt`** (repo root) — the single, **manually maintained** source of
  truth for the app version, read by `version.py` (About dialog),
  `RecallScore.spec`, and `installer.nsi`. Nothing derives or auto-increments it.
* **`packaging/installer.nsi`** — self-contained, no `/D` defines needed.
  Resolves `DIST_DIR`/`OUT_DIR` via `${__FILEDIR__}`, reads `APP_VERSION` from
  `version.txt` at compile time via `!searchparse /file`, and validates that
  `dist\RecallScore\RecallScore.exe`, `version.txt` and `LICENSE` exist (NSIS has
  no built-in `!ifexist`). Per-user settings already live under each user's own
  `AppData` via `QStandardPaths`, so a per-machine install does **not** make
  preferences shared across users — confirmed with the user before choosing
  Program Files. Uninstalling deliberately does not delete that config; Edit >
  "Open Local Folder" exposes it if the user wants to clear it by hand.
* **`docs/user_guide.md`** / **`.html`** — the `.md` is the maintained source;
  the `.html` is a **checked-in, manually regenerated** artifact (deliberately
  not a build step, to avoid making `pandoc` a build dependency). After editing
  the `.md`, run `pandoc docs/user_guide.md -s --toc --metadata title="Recall
  Score User Guide" -o docs/user_guide.html` and commit both together.
* **`docs/quick_start.md`** / **`.html`** — same pattern as the user guide
  above: the `.md` is the maintained source, the `.html` is a checked-in,
  manually regenerated artifact. After editing the `.md`, run `pandoc
  docs/quick_start.md -s --metadata title="Recall Score Quick Start
  Guide" -o docs/quick_start.html` and commit both together. No `--toc` here
  (unlike the user guide) — it's short enough that a table of contents is
  just an extra screen-reader landmark with nothing to navigate to.
* **`examples/`** — git-tracked (unlike `bin/`/`soundfonts/`), bundled example
  scores for end users. Distinct from `files/` at the repo root, which holds
  developer/test fixtures. Drop `.xml`/`.musicxml`/`.mxl` in and the next build
  picks them up automatically; no other file types are swept up.
* **`packaging/RecallScore.ico`** — checked into git normally (a small real
  asset). Read by `RecallScore.spec`, `installer.nsi` (`MUI_ICON`/`MUI_UNICON`)
  and `main.py`'s `_app_icon_path()`; **all three check for existence and skip
  gracefully**, so a missing file degrades to no icon rather than a build
  failure.
* **`LICENSE`** (repo root) — MIT, copyright held as "Recall Score Contributors"
  rather than a named individual (the user's choice). Compatible with
  redistributing the bundled LGPL FluidSynth/GLib/libsndfile/libinstpatch DLLs;
  `packaging/THIRD_PARTY_NOTICES.txt` carries their attribution (they are
  dynamically loaded via `ctypes.CDLL`, not statically linked, satisfying the
  LGPL re-linking requirement) plus a note that the Airfont_380 SoundFont's own
  licensing is **not confirmed** and should be attached separately if the
  installer is redistributed.

