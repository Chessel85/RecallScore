"""tools/stage_web.py: the staged audio/ files must import without Qt."""
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))
import stage_web  # noqa: E402


def test_staged_audio_modules_import_without_pyside6():
    code = (
        "import sys\n"
        "sys.modules['PySide6'] = None\n"
        "sys.modules['fluidsynth'] = None\n"
        + "".join(f"import audio.{m}\n" for m in stage_web.WEB_AUDIO_MODULES)
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_public_stage_omits_spikes_and_scores(tmp_path):
    stage_web.stage(tmp_path, with_scores=True, public=True)
    assert (tmp_path / "index.html").is_file()
    assert (tmp_path / "app" / "index.html").is_file()
    assert not (tmp_path / "spikes").exists()
    assert not (tmp_path / "scores").exists()
    assert (tmp_path / "sf" / stage_web.WEB_SOUNDFONT).is_file()
    assert not (tmp_path / "sf" / "TimGM6mb.sf2").exists()
    with zipfile.ZipFile(tmp_path / "py" / "shared.zip") as zf:
        names = set(zf.namelist())
    assert "audio/metronome.py" in names
    assert "audio/synth_engine.py" not in names
