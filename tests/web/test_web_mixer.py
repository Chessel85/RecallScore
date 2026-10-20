"""The Mixer through the browser bridge (RSBV 6.4): rows, live changes,
OK and Cancel, the levels sent on load, and the mixer kept with the
score's settings. The rows and levels are models/mixer_settings.py's,
shared with the desktop's PlaybackController."""
import json
from pathlib import Path

import web_api
from models.mixer_settings import (
    CLICK, CUE, DEFAULT_VOLUME, CENTRE_PAN, channel_levels, pan_percent_to_cc,
    volume_percent_to_cc,
)

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
TWO_PARTS = "hairpins_two_parts.musicxml"


def _load(name=TWO_PARTS, saved=None):
    path = FIXTURES / name
    result = web_api.load(path.read_bytes(), path.name, saved)
    assert result["ok"]
    return result


def test_a_load_sends_every_channels_level():
    result = _load()
    md = web_api._music_data
    json.dumps(result)
    assert result["mixer"] == [list(level) for level in channel_levels(md, md.mixer)]
    assert result["mixer"][0] == [0, DEFAULT_VOLUME, CENTRE_PAN]
    assert len(result["mixer"]) == len(md.parts_info) + 3


def test_the_form_lists_each_part_then_the_three_sounds():
    _load()
    form = web_api.mixer_form()
    json.dumps(form)
    md = web_api._music_data
    labels = [row["label"] for row in form["rows"]]
    assert labels == [p.name for p in md.parts_info] + ["Metronome", "Position Announcer", "Performance Cue"]
    assert form["rows"][0] == {"key": md.parts_info[0].part_id, "label": md.parts_info[0].name,
                               "volume": 100, "pan": 0}
    assert form["rows"][-3]["pan"] == 100  # the click is hard right


def test_a_change_is_sent_at_once_but_kept_only_on_ok():
    _load()
    web_api.mixer_form()
    md = web_api._music_data
    first = md.parts_info[0].part_id

    volume = web_api.mixer_set(first, "volume", 50)
    pan = web_api.mixer_set(CLICK, "pan", -100)

    assert volume == {"change": {"channel": 0, "control": 7, "value": volume_percent_to_cc(50)}}
    assert pan == {"change": {"channel": md.METRONOME_CLICK_CHANNEL, "control": 10, "value": 0}}
    assert md.mixer.is_empty()

    ended = web_api.mixer_end(True)
    assert ended["levels"] == web_api.mixer_levels()
    assert md.mixer.volume_for(first) == volume_percent_to_cc(50)
    assert md.mixer.pan_for(CLICK) == pan_percent_to_cc(-100)
    assert web_api.mixer_levels()[0][1] == volume_percent_to_cc(50)


def test_cancel_puts_every_channel_back():
    _load()
    web_api.mixer_form()
    md = web_api._music_data
    web_api.mixer_set(CUE, "volume", 0)

    ended = web_api.mixer_end(False)

    assert md.mixer.is_empty()
    assert ended["levels"] == web_api.mixer_levels()
    assert [md.PERFORMANCE_CUE_CHANNEL, DEFAULT_VOLUME, CENTRE_PAN] in ended["levels"]


def test_changes_outside_a_session_or_for_unknown_rows_do_nothing():
    _load()
    assert web_api.mixer_set(CLICK, "volume", 10) == {"change": None}
    web_api.mixer_form()
    assert web_api.mixer_set("no such part", "volume", 10) == {"change": None}
    assert web_api.mixer_set(CLICK, "volume", "") == {"change": None}
    assert "error" in web_api.mixer_set(CLICK, "loudness", 10)
    web_api.mixer_end(False)


def test_a_load_ends_an_open_session():
    _load()
    web_api.mixer_form()
    _load()
    assert web_api.mixer_set(CLICK, "volume", 10) == {"change": None}


def test_closing_stops_preview_playback():
    _load()
    web_api.mixer_form()
    assert web_api.play_toggle()["action"] == "start"

    ended = web_api.mixer_end(True)

    assert ended["stopped"]["stopped"] is True
    assert web_api._timeline is None


def test_closing_leaves_the_free_metronome_running():
    _load()
    web_api.play_metronome()
    web_api.mixer_form()
    assert web_api.mixer_end(False)["stopped"] == {"stopped": False}
    assert web_api._timeline is not None
    web_api.play_metronome()


def test_the_mixer_is_kept_with_the_scores_settings():
    _load()
    md = web_api._music_data
    first = md.parts_info[0].part_id
    web_api.mixer_form()
    web_api.mixer_set(first, "pan", 100)
    web_api.mixer_end(True)
    saved = web_api.score_settings_json()

    result = _load(saved=saved)

    assert web_api._music_data.mixer.pan_for(first) == 127
    assert result["mixer"][0] == [0, DEFAULT_VOLUME, 127]


def test_no_score():
    web_api._music_data = None
    assert web_api.mixer_levels() == []
    assert "error" in web_api.mixer_form()
    assert web_api.mixer_end(False)["levels"] == []
