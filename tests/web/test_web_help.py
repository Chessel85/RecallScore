"""Help > Sound Icon Dictionary through the bridge, and the Help pages the
site ships (Quick start, About's version)."""
import web_api
from audio.barline_patterns import STEP_MS
from audio.sound_catalog import build_catalog
from tools import stage_web


def test_catalog_is_the_desktops_without_voice_control():
    rows = web_api.sound_catalog()
    desktop = [e.name for e in build_catalog()]
    assert [r["name"] for r in rows] == [n for n in desktop if not n.startswith("Voice control")]
    assert len(rows) < len(desktop)


def test_catalog_rows_carry_a_plan_steps_apart_or_none():
    rows = {r["name"]: r["sound"] for r in web_api.sound_catalog()}
    assert rows["Live MIDI input"] is None
    lead_in = rows["Lead-in click"]
    assert [s["delay_ms"] for s in lead_in["oneshots"]] == [0, STEP_MS]
    assert lead_in["notes"] == [] and lead_in["stop"] is False


def test_stage_ships_the_web_quick_start_and_version(tmp_path):
    stage_web.stage(tmp_path, with_scores=False, public=True)
    assert (tmp_path / "quick_start_web.html").is_file()
    assert (tmp_path / "version.txt").read_text(encoding="utf-8").strip()
