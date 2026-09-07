# tests/test_score_load_failures.py
"""A bad score file surfaces an accessible error and never touches the
previously-loaded score or its .rsc (file-loading resilience work)."""
import types

import pytest

from controllers.score_persistence import ScorePersistenceController
from persistence import score_config
from tests.support.main_window_helpers import load_and_wait

GOOD = "tests/fixtures/chord.musicxml"

MTHD = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0MTrk\x00\x00\x00\x04\x00\xff\x2f\x00"

BROKEN_XML = "<?xml version='1.0'?><score-partwise><part id='P1'><measure></broken>"


@pytest.fixture
def loaded_window(window, qtbot):
    load_and_wait(window, qtbot, GOOD)
    assert window._music_data is not None
    return window


@pytest.fixture
def capture_errors(window, monkeypatch):
    errors = []
    monkeypatch.setattr(window, "_show_load_error", errors.append)
    return errors


def _write_sentinel_rsc(file_path: str) -> tuple:
    path = score_config.path_for(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = '{"schema_version": 3, "metronome_enabled": true, "SENTINEL": 42}'
    path.write_text(payload, encoding="utf-8")
    return path, payload


@pytest.mark.parametrize(
    "name, content, expected_substr",
    [
        ("song.xml", MTHD, "MusicXML"),                     # midi bytes, .xml name
        ("song.mid", b"not midi at all", "MIDI"),           # text, .mid name
        ("truncated.mxl", b"PK\x03\x04" + b"\x00" * 40, "compressed MusicXML"),
        ("empty.mxl", b"", "empty"),
        ("riff.gp", b"just chords: G C D", "Guitar Pro"),
    ],
)
def test_precheck_failure_shows_error_and_leaves_score_untouched(
    loaded_window, qtbot, capture_errors, tmp_path, name, content, expected_substr
):
    good_md = loaded_window._music_data
    bad = tmp_path / name
    bad.write_bytes(content)
    rsc_path, rsc_payload = _write_sentinel_rsc(str(bad))

    load_and_wait(loaded_window, qtbot, str(bad))

    assert len(capture_errors) == 1
    assert expected_substr in capture_errors[0]
    # the good score is still loaded, and no load thread was ever started
    assert loaded_window._music_data is good_md
    assert loaded_window._load_thread is None
    # the bad file's pre-existing .rsc is byte-for-byte intact
    assert rsc_path.read_text(encoding="utf-8") == rsc_payload


def test_reader_parse_failure_shows_error_and_keeps_previous_score(
    loaded_window, qtbot, capture_errors, tmp_path
):
    good_md = loaded_window._music_data
    bad = tmp_path / "corrupt.musicxml"        # passes precheck (looks like xml)
    bad.write_text(BROKEN_XML, encoding="utf-8")
    rsc_path, rsc_payload = _write_sentinel_rsc(str(bad))

    load_and_wait(loaded_window, qtbot, str(bad))

    assert len(capture_errors) == 1
    assert "MusicXML" in capture_errors[0] or "corrupt" in capture_errors[0]
    assert loaded_window._music_data is good_md
    assert rsc_path.read_text(encoding="utf-8") == rsc_payload


def test_save_current_skips_a_score_that_parsed_into_nothing(tmp_path):
    """The .rsc write guard: a MusicData with no parts and no timeline (a
    structurally valid file that yielded nothing) must not overwrite a real
    saved config with defaults."""
    rsc_path, rsc_payload = _write_sentinel_rsc(str(tmp_path / "hollow.mxl"))

    empty_md = types.SimpleNamespace(
        file_path=str(tmp_path / "hollow.mxl"), parts_info=[], timeline_slices=[]
    )
    session = types.SimpleNamespace(music_data=empty_md)

    def _fail(*a, **k):  # pragma: no cover - must never be reached
        raise AssertionError("save_current should have bailed before this")

    empty_md.export_config = _fail
    region_2 = types.SimpleNamespace(
        model_manager=types.SimpleNamespace(
            get_muted_node_keys=_fail, get_soloed_node_keys=_fail
        )
    )

    ScorePersistenceController(session, region_2).save_current()

    assert rsc_path.read_text(encoding="utf-8") == rsc_payload


def test_save_current_still_writes_for_a_real_score(window, qtbot, tmp_path):
    """Guard sanity check: a genuinely loaded score is still persisted."""
    load_and_wait(window, qtbot, GOOD)
    md = window._music_data
    assert md.parts_info  # the fixture has real parts
    window._save_current_score_config()
    assert score_config.path_for(md.file_path).exists()
