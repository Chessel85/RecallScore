# parsers/musescore_reader.py
"""Load MuseScore 4 native files (.mscz / .mscx) by shelling out to the
MuseScore 4 command line to convert them to MusicXML, then feeding that
through the ordinary MusicXMLReader pipeline.

MuseScore's .mscz (a zip container around a .mscx) is MuseScore's own
internal schema, which changes between releases - re-implementing a parser
for it would duplicate the whole MusicXML pipeline against a moving target
for no fidelity gain, since the reference exporter is MuseScore itself.
`MuseScore4.exe -o out.musicxml in.mscz` produces exactly what the user
gets by hand today with Save As -> compressed MusicXML, just automated.

The user only needs MuseScore 4+ support.
"""
import functools
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

from parsers.score_load_error import ScoreLoadError

# NB: MusicXMLReader (which pulls in music21, ~460ms) is imported
# function-locally in MuseScoreReader.load, not here - the same deferral
# MusicData.__post_init__ uses. It keeps `import parsers.musescore_reader`
# cheap so main_window.py can import resolve_musescore_path at module scope
# for the Options > Set MuseScore Location picker.

# CREATE_NO_WINDOW: same idiom as audio/voice_recognition.py - suppress the
# console window MuseScore's CLI would otherwise flash on Windows, without
# affecting anything else. The constant is Windows-only; getattr(..., 0) is
# the POSIX no-op default so importing this module can't AttributeError on
# macOS/Linux.
_POPEN_CREATIONFLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# The CLI binary's base name differs per platform: MuseScore4.exe on
# Windows, plain "mscore" inside the .app bundle on macOS, "mscore"/
# "mscore4" on Linux. `-o out in` and `--force` behave identically on all
# three (MuseScore's CLI is cross-platform).
_PATH_NAMES = ("MuseScore4", "mscore4", "MuseScore", "mscore")

# The executable's real name inside a macOS "MuseScore 4.app" bundle, under
# Contents/MacOS/. A user picking MuseScore in a file dialog on macOS
# selects the .app (a directory), so a configured/probed path ending .app
# is transparently redirected here - see _resolve_app_bundle.
_MACOS_BUNDLE_INNER = os.path.join("Contents", "MacOS", "mscore")

_CONVERT_TIMEOUT_SECONDS = 90

# MuseScore 4's CLI is itself a Qt app. If it inherits QT_QPA_PLATFORM=
# offscreen (which this app's own test harness sets, and any Qt app might)
# its convert mode hangs indefinitely instead of writing the file - it
# needs to pick its own platform plugin. Strip every Qt platform hint from
# the child's environment so MuseScore always starts clean. (Confirmed by
# live testing: the identical call converts in <1s without these vars and
# times out at 90s with QT_QPA_PLATFORM=offscreen set.)
_QT_ENV_VARS_TO_DROP = (
    "QT_QPA_PLATFORM",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QT_PLUGIN_PATH",
    "QT_QPA_FONTDIR",
)


def _subprocess_env() -> dict:
    env = os.environ.copy()
    for key in _QT_ENV_VARS_TO_DROP:
        env.pop(key, None)
    return env

# Standard install locations to probe when nothing is configured and the
# executable is not on PATH.
_WINDOWS_CANDIDATES = (
    r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
    r"C:\Program Files (x86)\MuseScore 4\bin\MuseScore4.exe",
)

_MACOS_CANDIDATES = (
    "/Applications/MuseScore 4.app",
    os.path.expanduser("~/Applications/MuseScore 4.app"),
)

_LINUX_CANDIDATES = (
    "/usr/bin/mscore",
    "/usr/local/bin/mscore",
    "/var/lib/flatpak/exports/bin/org.musescore.MuseScore",
    os.path.expanduser("~/.local/share/flatpak/exports/bin/org.musescore.MuseScore"),
)


class MuseScoreNotFoundError(ScoreLoadError, RuntimeError):
    """The MuseScore 4 executable could not be located. Distinct subclass so
    the load-failed handler can offer a file picker instead of only
    reporting. A ScoreLoadError, so its message reaches the user through the
    ordinary accessible error dialog with no special-casing in the worker."""


def _resolve_app_bundle(path: str) -> str:
    """A macOS "MuseScore 4.app" is a directory; the runnable CLI binary is
    Contents/MacOS/mscore inside it. A user picking MuseScore in a file
    dialog (or a probed /Applications path) lands on the .app itself, so
    redirect any *.app to its inner binary. A non-.app path is returned
    unchanged."""
    if path.endswith(".app") and os.path.isdir(path):
        return os.path.join(path, _MACOS_BUNDLE_INNER)
    return path


def resolve_musescore_path(path: Optional[str]) -> Optional[str]:
    """Turn a user-picked or probed path into a runnable executable path,
    or None if it doesn't resolve to a real file. Shared by the Options >
    Set MuseScore Location picker and find_musescore_executable so both
    apply the same .app-bundle redirect."""
    if not path:
        return None
    resolved = _resolve_app_bundle(path)
    return resolved if os.path.isfile(resolved) else None


# The two probes below are memoised for the process: find_musescore_executable
# is called on every File > Open (to decide whether to offer the .mscz/.mscx
# filter) and again on the load thread, and on macOS the Spotlight probe is a
# subprocess.run(["mdfind", ...], timeout=5) that freezes the Qt main thread -
# silence with no cue in a screen-reader-first app (CR8thSept.txt S2). A miss
# result (None) is cached too, so a machine without MuseScore pays the cost at
# most once. clear_musescore_detection_cache() drops both, called from
# Options > Set MuseScore Location so a freshly-pointed-at install is picked up
# with no restart; warm_musescore_detection_cache() fills them off the main
# thread at startup so the first open doesn't block either.
@functools.lru_cache(maxsize=1)
def _musescore_from_windows_registry() -> Optional[str]:
    """Best-effort: locate MuseScore 4 via the .mscz/.mscx file-association
    open command in the registry.

    Current MuseScore 4 installs (via Muse Hub) create no classic
    Uninstall/App Paths keys, but they do register the file-type
    association: HKEY_CLASSES_ROOT\\.mscz (Default) -> a ProgID, and
    HKEY_CLASSES_ROOT\\<ProgID>\\shell\\open\\command (Default) is
    '"...\\MuseScore4.exe" "%1"'. HKCR is the merged HKLM+HKCU classes
    view, so per-user associations are covered too. Returns None on any
    missing key or a non-win32 platform."""
    if sys.platform != "win32":
        return None
    try:
        import winreg

        for ext in (".mscz", ".mscx"):
            try:
                progid = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, ext)
            except OSError:
                continue
            if not progid:
                continue
            try:
                command = winreg.QueryValue(
                    winreg.HKEY_CLASSES_ROOT,
                    rf"{progid}\shell\open\command",
                )
            except OSError:
                continue
            if not command:
                continue
            command = command.strip()
            if command.startswith('"'):
                exe = command[1:].split('"', 1)[0]
            else:
                exe = command.split(None, 1)[0]
            if exe and os.path.isfile(exe):
                return exe
    except (OSError, ValueError):
        return None
    return None


@functools.lru_cache(maxsize=1)
def _musescore_from_spotlight() -> Optional[str]:
    """Best-effort (macOS only): locate a MuseScore 4 .app anywhere via
    Spotlight's bundle-identifier index, then redirect to its inner CLI
    binary. Only runs when the static /Applications probes have already
    missed, so the subprocess cost is a rare one-off."""
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            [
                "mdfind",
                "kMDItemCFBundleIdentifier == 'org.musescore.MuseScore4'",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=_POPEN_CREATIONFLAGS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.endswith(".app"):
            resolved = _resolve_app_bundle(line)
            if os.path.isfile(resolved):
                return resolved
    return None


def find_musescore_executable(configured: Optional[str]) -> Optional[str]:
    """Return a path to a usable MuseScore 4 executable, or None.

    Order: an explicitly configured path wins (with the macOS .app-bundle
    redirect applied); then PATH; then the standard per-platform install
    locations (plus the Windows Store alias under %LOCALAPPDATA%)."""
    from_config = resolve_musescore_path(configured)
    if from_config:
        return from_config

    for name in _PATH_NAMES:
        found = shutil.which(name)
        if found:
            return found

    candidates = list(_WINDOWS_CANDIDATES)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            os.path.join(local_app_data, "Microsoft", "WindowsApps", "MuseScore4.exe")
        )
    candidates.extend(_MACOS_CANDIDATES)
    candidates.extend(_LINUX_CANDIDATES)
    for path in candidates:
        resolved = _resolve_app_bundle(path)
        if os.path.isfile(resolved):
            return resolved

    for probe in (_musescore_from_windows_registry, _musescore_from_spotlight):
        found = probe()
        if found:
            return found

    return None


def clear_musescore_detection_cache() -> None:
    """Drop the memoised registry/Spotlight probe results. Call after the
    configured MuseScore location changes so the next open re-probes."""
    _musescore_from_windows_registry.cache_clear()
    _musescore_from_spotlight.cache_clear()


def warm_musescore_detection_cache(configured: Optional[str]) -> None:
    """Run find_musescore_executable purely to populate the probe caches.
    Safe to call from a background thread: it only reads the filesystem and
    fills a thread-safe lru_cache, and any failure is swallowed."""
    try:
        find_musescore_executable(configured)
    except Exception:
        pass


def convert_musescore_to_musicxml(src_path: str, exe: str) -> str:
    """Run MuseScore's CLI to convert src_path to a temporary .musicxml
    file and return its path. The caller owns cleanup.

    Raises ScoreLoadError on a non-zero exit, a timeout, or an empty/missing
    output file, with the tail of MuseScore's stderr included - so the reason
    reaches the user through the ordinary accessible error dialog.
    """
    fd, out_path = tempfile.mkstemp(suffix=".musicxml")
    os.close(fd)

    def _fail(message: str):
        try:
            os.remove(out_path)
        except OSError:
            pass
        raise ScoreLoadError(message)

    try:
        # --force: "ignore score corruption and version errors when reading
        # a score" (MuseScore CLI docs). Needed to import scores saved by
        # MuseScore 2.x - without it MS4's CLI aborts with exit 40 and no
        # stderr (confirmed live on a MuseScore 2.1.0 file). A harmless
        # no-op for native MuseScore 4 files.
        result = subprocess.run(
            [exe, "--force", "-o", out_path, src_path],
            capture_output=True,
            text=True,
            timeout=_CONVERT_TIMEOUT_SECONDS,
            creationflags=_POPEN_CREATIONFLAGS,
            env=_subprocess_env(),
        )
    except subprocess.TimeoutExpired:
        _fail(
            f"MuseScore did not finish converting within "
            f"{_CONVERT_TIMEOUT_SECONDS} seconds."
        )

    if result.returncode != 0:
        stderr_tail = (result.stderr or "").strip().splitlines()[-3:]
        detail = "\n".join(stderr_tail) if stderr_tail else "(no error output)"
        _fail(
            f"MuseScore failed to convert the file (exit code "
            f"{result.returncode}):\n{detail}"
        )

    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        _fail("MuseScore produced no MusicXML output for the file.")

    return out_path


class MuseScoreReader:
    """Parses a .mscz/.mscx into MusicData - the MuseScore counterpart of
    MusicXMLReader/MidiReader/GpReader/UgFileReader, used the same way by
    workers/score_load_worker.py: MuseScoreReader(path).load().

    After conversion the file is plain MusicXML, so the whole downstream
    pipeline (TimelineBuilder, <harmony>/<lyric> synthetic parts, percussion,
    Region 5, .rsc persistence) is untouched. file_path is reset to the real
    .mscz path after the build so .rsc / the window title / Recent Files all
    key off it - the same "synthesise a file_path that isn't what was
    parsed" move UgReader already makes.
    """

    def __init__(self, file_path: str, configured_exe: Optional[str] = None):
        self.file_path = file_path
        self.configured_exe = configured_exe

    def load(self):
        from parsers.musicXML_reader import MusicXMLReader

        exe = find_musescore_executable(self.configured_exe)
        if exe is None:
            raise MuseScoreNotFoundError(
                "MuseScore 4 was not found. Set its location via "
                "Options > Set MuseScore Location..."
            )
        tmp = convert_musescore_to_musicxml(self.file_path, exe)
        try:
            music_data = MusicXMLReader(tmp).load()
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        # Keep the real .mscz path: the timeline was already built from tmp
        # during MusicData.__post_init__, and is_midi/is_gp/is_ug are all
        # False for both .musicxml and .mscz, so nothing re-dispatches on it.
        music_data.file_path = self.file_path
        return music_data
