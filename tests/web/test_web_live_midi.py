"""Live MIDI input through the bridge: the toggle, the settings dialog's
form, preview and OK, the sound sent to the live channel, and the stored
shape (the desktop's global LiveMidiInputSettings)."""
import json

import pytest

import web_api
from audio.midi_input import LIVE_MIDI_INPUT_CHANNEL
from models import announcements
from models.app_settings_data import AppSettings
from models.mixer_settings import pan_percent_to_cc, volume_percent_to_cc


@pytest.fixture(autouse=True)
def _fresh_globals(monkeypatch):
    monkeypatch.setattr(web_api, "_app_settings", AppSettings())


def test_defaults_are_the_desktops_with_a_piano_on_the_live_channel():
    live = web_api.live_midi_state()
    assert live == {
        "enabled": False, "device_name": None, "channel": LIVE_MIDI_INPUT_CHANNEL,
        "program": 0, "volume": volume_percent_to_cc(100), "pan": pan_percent_to_cc(0),
    }


def test_toggle_flips_and_speaks_the_new_state():
    on = web_api.live_midi_toggle()
    assert on["announce"] == "Live MIDI input on"
    assert on["live"]["enabled"] is True
    assert web_api.options_state()["live_midi"] is True
    off = web_api.live_midi_toggle()
    assert off["announce"] == "Live MIDI input off"
    assert web_api.options_state()["live_midi"] is False


def test_form_lists_devices_and_keeps_an_absent_saved_one():
    web_api.live_midi_apply({"enabled": True, "device": "Old Keys", "instrument": "1", "volume": 100, "pan": 0})
    form = web_api.live_midi_form(["USB Piano"])
    fields = {f["name"]: f for f in form["fields"]}
    assert [f["name"] for f in form["fields"]] == ["enabled", "device", "instrument", "volume", "pan"]
    labels = [o["label"] for o in fields["device"]["options"]]
    assert labels == ["(No device)", "USB Piano", "Old Keys (not connected)"]
    assert fields["device"]["value"] == "Old Keys"
    assert len(fields["instrument"]["options"]) == 128
    assert fields["volume"]["max"] == 100 and fields["pan"]["min"] == -100


def test_preview_changes_the_sound_but_stores_nothing():
    preview = web_api.live_midi_preview(
        {"enabled": False, "device": "", "instrument": "25", "volume": "50", "pan": "-100"})
    assert preview["live"]["program"] == 24  # invariant 9: 1-indexed in the model, 0 on the wire
    assert preview["live"]["pan"] == pan_percent_to_cc(-100)
    assert web_api.live_midi_state()["program"] == 0


def test_apply_stores_clamped_values_in_the_global_settings():
    result = web_api.live_midi_apply(
        {"enabled": True, "device": "USB Piano", "instrument": "999", "volume": "250", "pan": "-5"})
    assert result["live"]["program"] == 127
    stored = json.loads(web_api.global_settings_json())["live_midi_input"]
    assert stored == {"enabled": True, "device_name": "USB Piano", "gm_program": 128,
                      "volume_percent": 100, "pan_percent": -5}


def test_no_device_chosen_is_stored_as_none():
    web_api.live_midi_apply({"enabled": True, "device": "", "instrument": "1", "volume": 100, "pan": 0})
    assert web_api.live_midi_state()["device_name"] is None


def test_stored_settings_come_back_after_a_visit():
    web_api.live_midi_apply({"enabled": True, "device": "USB Piano", "instrument": "5", "volume": 80, "pan": 20})
    text = web_api.global_settings_json()
    web_api._app_settings = AppSettings()
    assert web_api.apply_global_settings(text) == {"ok": True}
    live = web_api.live_midi_state()
    assert (live["enabled"], live["device_name"], live["program"]) == (True, "USB Piano", 4)


@pytest.mark.parametrize("kind", ["unsupported", "denied", "no_device", "not_found"])
def test_each_problem_has_its_own_words(kind):
    assert web_api.live_midi_problem(kind) == announcements.live_midi_problem(kind)


def test_problem_wordings_are_distinct_and_unknown_kind_is_general():
    kinds = ["unsupported", "denied", "no_device", "not_found"]
    assert len({announcements.live_midi_problem(k) for k in kinds}) == 4
    assert announcements.live_midi_problem("other") == "Live MIDI input is not available."
