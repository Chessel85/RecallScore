# tests/parsers/test_musescore_reader.py
"""MuseScoreReader converts .mscz/.mscx by shelling out to the MuseScore 4
CLI, so these tests monkeypatch subprocess.run - no MuseScore install
needed. The one real dependency is a small MusicXML fixture that stands in
for the CLI's output."""
import os
import subprocess
import sys

import pytest

from parsers import musescore_reader
from parsers.musescore_reader import (
    MuseScoreNotFoundError,
    MuseScoreReader,
    convert_musescore_to_musicxml,
    find_musescore_executable,
    resolve_musescore_path,
)
from parsers.score_load_error import ScoreLoadError

FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "chord.musicxml"
)


# --- find_musescore_executable -----------------------------------------

def test_configured_path_wins_when_it_is_a_real_file(tmp_path):
    exe = tmp_path / "MuseScore4.exe"
    exe.write_text("")
    assert find_musescore_executable(str(exe)) == str(exe)


def test_returns_none_when_nothing_is_found(monkeypatch):
    monkeypatch.setattr(musescore_reader.shutil, "which", lambda name: None)
    monkeypatch.setattr(musescore_reader.os.path, "isfile", lambda p: False)
    monkeypatch.setattr(musescore_reader.os, "environ", {}, raising=False)
    assert find_musescore_executable(None) is None
    assert find_musescore_executable(r"C:\nope\MuseScore4.exe") is None


def test_falls_through_to_path_lookup(monkeypatch):
    monkeypatch.setattr(musescore_reader.os.path, "isfile", lambda p: False)
    monkeypatch.setattr(
        musescore_reader.shutil, "which",
        lambda name: "/usr/bin/mscore4" if name == "mscore4" else None,
    )
    assert find_musescore_executable(None) == "/usr/bin/mscore4"


def test_path_lookup_also_accepts_the_macos_linux_binary_name(monkeypatch):
    monkeypatch.setattr(musescore_reader.os.path, "isfile", lambda p: False)
    monkeypatch.setattr(
        musescore_reader.shutil, "which",
        lambda name: "/usr/local/bin/mscore" if name == "mscore" else None,
    )
    assert find_musescore_executable(None) == "/usr/local/bin/mscore"


# --- Windows registry fallback -------------------------------------

def _stub_registry(monkeypatch, progid, command):
    """Make _musescore_from_windows_registry think it is on win32 with a
    .mscz association resolving to `command`."""
    monkeypatch.setattr(musescore_reader.sys, "platform", "win32")

    class _FakeWinreg:
        HKEY_CLASSES_ROOT = 0

        @staticmethod
        def QueryValue(root, sub):
            if sub in (".mscz", ".mscx"):
                return progid
            if sub == rf"{progid}\shell\open\command":
                return command
            raise FileNotFoundError(sub)

    monkeypatch.setitem(sys.modules, "winreg", _FakeWinreg)


def test_registry_helper_parses_a_quoted_command(monkeypatch, tmp_path):
    exe = tmp_path / "MuseScore4.exe"
    exe.write_text("")
    _stub_registry(
        monkeypatch, "MuseScore.mscz.4.stable", f'"{exe}" "%1"'
    )
    assert musescore_reader._musescore_from_windows_registry() == str(exe)


def test_registry_helper_parses_an_unquoted_command(monkeypatch, tmp_path):
    exe = tmp_path / "mscore4.exe"
    exe.write_text("")
    _stub_registry(monkeypatch, "MuseScore.mscz", f"{exe} %1")
    assert musescore_reader._musescore_from_windows_registry() == str(exe)


def test_registry_helper_rejects_a_missing_file(monkeypatch, tmp_path):
    missing = tmp_path / "gone" / "MuseScore4.exe"
    _stub_registry(monkeypatch, "MuseScore.mscz", f'"{missing}" "%1"')
    assert musescore_reader._musescore_from_windows_registry() is None


def test_registry_helper_is_a_noop_off_win32(monkeypatch):
    monkeypatch.setattr(musescore_reader.sys, "platform", "linux")
    assert musescore_reader._musescore_from_windows_registry() is None


def test_find_falls_through_to_the_registry_helper(monkeypatch, tmp_path):
    exe = tmp_path / "MuseScore4.exe"
    exe.write_text("")
    monkeypatch.setattr(musescore_reader.shutil, "which", lambda name: None)
    monkeypatch.setattr(musescore_reader, "_WINDOWS_CANDIDATES", ())
    monkeypatch.setattr(musescore_reader, "_MACOS_CANDIDATES", ())
    monkeypatch.setattr(musescore_reader, "_LINUX_CANDIDATES", ())
    monkeypatch.setattr(musescore_reader.os, "environ", {}, raising=False)
    monkeypatch.setattr(
        musescore_reader, "_musescore_from_windows_registry",
        lambda: str(exe),
    )
    assert find_musescore_executable(None) == str(exe)


# --- macOS .app bundle resolution -----------------------------------

def _make_fake_app(tmp_path):
    """A stand-in for /Applications/MuseScore 4.app - a directory ending
    .app with Contents/MacOS/mscore inside it."""
    app = tmp_path / "MuseScore 4.app"
    inner = app / "Contents" / "MacOS"
    inner.mkdir(parents=True)
    binary = inner / "mscore"
    binary.write_text("")
    return str(app), str(binary)


def test_resolve_redirects_a_dot_app_directory_to_its_inner_binary(tmp_path):
    app, binary = _make_fake_app(tmp_path)
    assert resolve_musescore_path(app) == binary


def test_resolve_passes_a_plain_executable_through(tmp_path):
    exe = tmp_path / "MuseScore4.exe"
    exe.write_text("")
    assert resolve_musescore_path(str(exe)) == str(exe)


def test_resolve_returns_none_for_a_bundle_with_no_inner_binary(tmp_path):
    app = tmp_path / "Broken.app"
    app.mkdir()
    assert resolve_musescore_path(str(app)) is None
    assert resolve_musescore_path(None) is None


def test_configured_dot_app_is_accepted_and_redirected(tmp_path):
    app, binary = _make_fake_app(tmp_path)
    assert find_musescore_executable(app) == binary


def test_probes_the_standard_macos_install_location(monkeypatch, tmp_path):
    app, binary = _make_fake_app(tmp_path)
    monkeypatch.setattr(musescore_reader.shutil, "which", lambda name: None)
    monkeypatch.setattr(musescore_reader, "_MACOS_CANDIDATES", (app,))
    monkeypatch.setattr(musescore_reader, "_WINDOWS_CANDIDATES", ())
    monkeypatch.setattr(musescore_reader, "_LINUX_CANDIDATES", ())
    monkeypatch.setattr(musescore_reader.os, "environ", {}, raising=False)
    assert find_musescore_executable(None) == binary


# --- convert_musescore_to_musicxml ------------------------------------

def _fake_run_writing(content: str, returncode: int = 0, stderr: str = ""):
    def _run(cmd, **kwargs):
        out_path = cmd[cmd.index("-o") + 1]
        if returncode == 0:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

    return _run


def test_convert_returns_temp_path_that_holds_the_output(monkeypatch):
    with open(FIXTURE, encoding="utf-8") as f:
        xml = f.read()
    monkeypatch.setattr(subprocess, "run", _fake_run_writing(xml))

    out = convert_musescore_to_musicxml("in.mscz", "MuseScore4.exe")
    try:
        assert out.endswith(".musicxml")
        with open(out, encoding="utf-8") as f:
            assert "score-partwise" in f.read()
    finally:
        os.remove(out)


def test_convert_cleans_up_and_raises_on_nonzero_exit(monkeypatch):
    captured = {}

    real_mkstemp = musescore_reader.tempfile.mkstemp

    def _spy_mkstemp(*args, **kwargs):
        fd, path = real_mkstemp(*args, **kwargs)
        captured["path"] = path
        return fd, path

    monkeypatch.setattr(musescore_reader.tempfile, "mkstemp", _spy_mkstemp)
    monkeypatch.setattr(
        subprocess, "run",
        _fake_run_writing("", returncode=1, stderr="boom: bad file"),
    )

    with pytest.raises(ScoreLoadError, match="boom: bad file"):
        convert_musescore_to_musicxml("in.mscz", "MuseScore4.exe")
    assert not os.path.exists(captured["path"])


def test_convert_raises_on_empty_output_file(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run_writing("", returncode=0))
    with pytest.raises(ScoreLoadError, match="no MusicXML output"):
        convert_musescore_to_musicxml("in.mscz", "MuseScore4.exe")


def test_convert_scrubs_qt_platform_env_from_the_child(monkeypatch):
    """MuseScore 4's CLI hangs forever if it inherits QT_QPA_PLATFORM=
    offscreen (which the test harness itself sets) - the child env must
    drop every Qt platform hint. Confirmed by live testing."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("QT_PLUGIN_PATH", "/somewhere")
    seen = {}

    def _run(cmd, **kwargs):
        seen["env"] = kwargs.get("env")
        out_path = cmd[cmd.index("-o") + 1]
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("<score-partwise/>")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    out = convert_musescore_to_musicxml("in.mscz", "MuseScore4.exe")
    os.remove(out)

    assert seen["env"] is not None
    assert "QT_QPA_PLATFORM" not in seen["env"]
    assert "QT_PLUGIN_PATH" not in seen["env"]


# --- MuseScoreReader.load --------------------------------------------

def test_load_builds_music_data_and_removes_temp_file(monkeypatch, tmp_path):
    with open(FIXTURE, encoding="utf-8") as f:
        xml = f.read()
    monkeypatch.setattr(subprocess, "run", _fake_run_writing(xml))

    captured = {}
    real_convert = musescore_reader.convert_musescore_to_musicxml

    def _spy_convert(src, exe):
        out = real_convert(src, exe)
        captured["tmp"] = out
        return out

    monkeypatch.setattr(musescore_reader, "convert_musescore_to_musicxml", _spy_convert)

    exe = tmp_path / "MuseScore4.exe"
    exe.write_text("")
    src = tmp_path / "Song.mscz"
    src.write_text("")

    data = MuseScoreReader(str(src), configured_exe=str(exe)).load()

    assert data.parts_info  # timeline built from the converted MusicXML
    assert data.file_path == str(src)  # real .mscz path kept, not the temp file
    assert not os.path.exists(captured["tmp"])  # temp file cleaned up


def test_load_raises_not_found_when_no_executable(monkeypatch):
    monkeypatch.setattr(
        musescore_reader, "find_musescore_executable", lambda configured: None
    )
    with pytest.raises(MuseScoreNotFoundError, match="Set its location"):
        MuseScoreReader("Song.mscz").load()


# --- dispatch guard --------------------------------------------------

@pytest.mark.parametrize("name", ["Song.mscz", "Song.MSCX", "path/to/Piece.mscx"])
def test_score_load_thread_dispatches_musescore_extensions(monkeypatch, name):
    from workers import score_load_worker

    calls = []

    class _FakeReader:
        def __init__(self, file_path, configured_exe=None):
            calls.append((file_path, configured_exe))

        def load(self):
            return "music_data"

    monkeypatch.setattr(score_load_worker, "MuseScoreReader", _FakeReader)
    monkeypatch.setattr(
        score_load_worker.app_settings, "load",
        lambda: type("S", (), {"musescore_path": "/opt/MuseScore4"})(),
    )

    emitted = []
    thread = score_load_worker.ScoreLoadThread(name)
    thread.loaded.connect(emitted.append)
    thread.run()

    assert calls == [(name, "/opt/MuseScore4")]
    assert emitted == ["music_data"]
