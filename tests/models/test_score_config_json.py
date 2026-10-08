"""Round trips for the Qt-free .rsc and settings.json encoders (shared with the web version)."""
import json

from models.app_settings_data import AppSettings
from models.score_config_data import ScoreConfig
from models.score_config_json import config_from_dict, config_to_dict


def _busy_config() -> ScoreConfig:
    cfg = ScoreConfig()
    cfg.parts_muted = {"P1"}
    cfg.staves_muted = {("P1", 2)}
    cfg.voices_muted = {("P2", 1, 3)}
    cfg.parts_soloed = {"P2"}
    cfg.staves_soloed = {("P2", 1)}
    cfg.voices_soloed = {("P1", 1, 2)}
    cfg.metronome_enabled = True
    cfg.voice_display_attributes = {("P1", 1, 1): {"a", "b"}}
    cfg.attribute_order_by_part = {"P1": ["x", "y"]}
    cfg.hidden_attributes_by_part = {"P1": {"y", "z"}}
    cfg.hidden_attributes_for_all = {"q"}
    cfg.part_name_overrides = {"P1": "Lead"}
    cfg.part_program_overrides = {"P1": 25}
    cfg.part_percussion_overrides = {"P3"}
    cfg.key_signature_override_fifths = -2
    cfg.key_signature_override_mode = "minor"
    cfg.playback_tempo_bpm = 93.5
    cfg.percussion_item_overrides = {("P3", 38): 40}
    cfg.percussion_item_name_overrides = {("P3", 38): "Snare"}
    cfg.last_position_index = 7
    cfg.marking_categories_off = {"slur"}
    cfg.part_link_groups = [["P1", "P2"]]
    cfg.collapsed_stave_parts = ["P1"]
    return cfg


def test_score_config_round_trip_through_json_text():
    cfg = _busy_config()
    data = json.loads(json.dumps(config_to_dict(cfg)))
    assert config_from_dict(data) == cfg


def test_score_config_default_round_trip():
    cfg = ScoreConfig()
    assert config_from_dict(config_to_dict(cfg)) == cfg


def test_score_config_dict_is_json_serialisable_with_sorted_sets():
    data = config_to_dict(_busy_config())
    assert data["hidden_attributes_by_part"] == {"P1": ["y", "z"]}
    assert data["voices_muted"] == ["P2|1|3"]
    assert data["percussion_item_overrides"] == {"P3|38": 40}
    json.dumps(data)


def test_score_config_never_writes_the_legacy_flat_attribute_order():
    cfg = _busy_config()
    cfg.attribute_order = ["old"]
    assert "attribute_order" not in config_to_dict(cfg)


def test_score_config_missing_keys_use_defaults():
    cfg = config_from_dict({})
    assert cfg.marking_categories_off  # missing key -> every category off
    assert cfg.parts_muted == set()


def test_app_settings_round_trip_through_json_text():
    s = AppSettings(
        uk_terms=True, recent_files=["x", "y"], last_open_dir="d",
        shortcuts={"a": "Ctrl+A"}, marking_categories_off=["slur"],
        show_engraving_details_enabled=True,
    )
    assert AppSettings.from_dict(json.loads(json.dumps(s.to_dict()))) == s


def test_app_settings_from_empty_dict_is_the_default():
    assert AppSettings.from_dict({}) == AppSettings()


def test_app_settings_drops_bad_shortcuts_and_bad_indicator_mode():
    s = AppSettings.from_dict({"shortcuts": {"a": "Ctrl+A", "b": 3, 4: "x"},
                               "performance_indicator_mode": "nonsense"})
    assert s.shortcuts == {"a": "Ctrl+A"}
    assert s.performance_indicator_mode == AppSettings().performance_indicator_mode
