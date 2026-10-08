# models/score_config_json.py
"""ScoreConfig <-> plain JSON-able dict (the .rsc file's contents).

Qt-free so the desktop (persistence/score_config.py, which adds the file I/O
and QStandardPaths) and the web version share one encoder: a .rsc written by
either is read by the other. How a tuple key is spelled in a file is
serialisation, not shape, so it lives here rather than in score_config_data.py.
"""
from typing import Any, Dict

from models import marking_categories
from models.mixer_settings import MixerSettings
from models.play_settings import PlaySettings
from models.refresh_settings import RefreshSettings
from models.score_config_data import PercussionItemKey, ScoreConfig, StaffKey, VoiceKey


def _encode_voice_key(key: VoiceKey) -> str:
    part_id, staff, voice = key
    return f"{part_id}|{staff}|{voice}"


def _decode_voice_key(encoded: str) -> VoiceKey:
    part_id, staff, voice = encoded.split("|")
    return (part_id, int(staff), int(voice))


def _encode_staff_key(key: StaffKey) -> str:
    part_id, staff = key
    return f"{part_id}|{staff}"


def _decode_staff_key(encoded: str) -> StaffKey:
    part_id, staff = encoded.split("|")
    return (part_id, int(staff))


def _encode_percussion_item_key(key: PercussionItemKey) -> str:
    part_id, source_key = key
    return f"{part_id}|{source_key}"


def _decode_percussion_item_key(encoded: str) -> PercussionItemKey:
    part_id, source_key = encoded.split("|")
    return (part_id, int(source_key))


def config_from_dict(data: Dict[str, Any]) -> ScoreConfig:
    """Builds a ScoreConfig from a loaded .rsc dict. Raises ValueError (or
    TypeError/AttributeError on a wrong-shaped value) for a malformed file;
    the caller decides how to report it."""
    return ScoreConfig(
        schema_version=data.get("schema_version", 1),
        parts_muted=set(data.get("parts_muted", [])),
        staves_muted={_decode_staff_key(k) for k in data.get("staves_muted", [])},
        voices_muted={_decode_voice_key(k) for k in data.get("voices_muted", [])},
        parts_soloed=set(data.get("parts_soloed", [])),
        staves_soloed={_decode_staff_key(k) for k in data.get("staves_soloed", [])},
        voices_soloed={_decode_voice_key(k) for k in data.get("voices_soloed", [])},
        metronome_enabled=data.get("metronome_enabled", False),
        position_announcer_enabled=data.get("position_announcer_enabled", False),
        bar_line_indicator_enabled=data.get("bar_line_indicator_enabled", False),
        voice_display_attributes={
            _decode_voice_key(k): set(v)
            for k, v in data.get("voice_display_attributes", {}).items()
        },
        # Read for migration only (MusicData.apply_config) - a save from
        # this or a later schema never writes this key back, so it's
        # absent from data on every .rsc but a pre-migration one.
        attribute_order=list(data.get("attribute_order", [])),
        attribute_order_by_part={
            str(k): list(v) for k, v in (data.get("attribute_order_by_part") or {}).items()
        },
        hidden_attributes_by_part={
            str(k): set(v) for k, v in (data.get("hidden_attributes_by_part") or {}).items()
        },
        hidden_attributes_for_all=set(data.get("hidden_attributes_for_all", [])),
        mixer=MixerSettings.from_dict(data.get("mixer")),
        refresh_settings=RefreshSettings.from_dict(data.get("refresh_settings")),
        play_settings=PlaySettings.from_dict(data.get("play_settings")),
        part_name_overrides={
            str(k): str(v) for k, v in (data.get("part_name_overrides") or {}).items()
        },
        part_program_overrides={
            str(k): int(v) for k, v in (data.get("part_program_overrides") or {}).items()
        },
        part_percussion_overrides={
            str(v) for v in (data.get("part_percussion_overrides") or [])
        },
        key_signature_override_fifths=data.get("key_signature_override_fifths"),
        key_signature_override_mode=data.get("key_signature_override_mode"),
        playback_tempo_bpm=data.get("playback_tempo_bpm"),
        percussion_item_overrides={
            _decode_percussion_item_key(k): int(v)
            for k, v in (data.get("percussion_item_overrides") or {}).items()
        },
        percussion_item_name_overrides={
            _decode_percussion_item_key(k): str(v)
            for k, v in (data.get("percussion_item_name_overrides") or {}).items()
        },
        percussion_auto_correct_enabled=data.get("percussion_auto_correct_enabled", False),
        last_position_index=int(data.get("last_position_index", 0)),
        # Stage 3: directives were removed. An older .rsc's
        # "directive_labels_in_note_list" or
        # "directive_labels_hidden_from_note_list" key is simply ignored
        # on load - there is no field left to populate from it.
        #
        # A .rsc predating this key entirely (saved before Stage 9) has
        # no per-score value to take over with, so this falls through to
        # every category off - matching AppSettings.load()'s own
        # missing-key fallback, not the old "every category on" default.
        marking_categories_off=set(
            data.get("marking_categories_off", list(marking_categories.ALL_CATEGORIES))
        ),
        part_link_groups=[
            [str(p) for p in g] for g in (data.get("part_link_groups") or [])
        ],
        collapsed_stave_parts=[
            str(p) for p in (data.get("collapsed_stave_parts") or [])
        ],
    )


def config_to_dict(config: ScoreConfig) -> Dict[str, Any]:
    """The dict a .rsc file holds, in the key order desktop has always written."""
    return {
        "schema_version": config.schema_version,
        "parts_muted": sorted(config.parts_muted),
        "staves_muted": [_encode_staff_key(k) for k in sorted(config.staves_muted)],
        "voices_muted": [_encode_voice_key(k) for k in sorted(config.voices_muted)],
        "parts_soloed": sorted(config.parts_soloed),
        "staves_soloed": [_encode_staff_key(k) for k in sorted(config.staves_soloed)],
        "voices_soloed": [_encode_voice_key(k) for k in sorted(config.voices_soloed)],
        "metronome_enabled": config.metronome_enabled,
        "position_announcer_enabled": config.position_announcer_enabled,
        "bar_line_indicator_enabled": config.bar_line_indicator_enabled,
        "voice_display_attributes": {
            _encode_voice_key(k): sorted(v)
            for k, v in config.voice_display_attributes.items()
        },
        # Old flat "attribute_order" is deliberately never written any more
        # - only attribute_order_by_part is a real save target now
        # (hideAttributes.md); ScoreConfig.attribute_order exists purely to
        # receive an older file's value on load.
        "attribute_order_by_part": {
            k: list(v) for k, v in config.attribute_order_by_part.items()
        },
        "hidden_attributes_by_part": {
            k: sorted(v) for k, v in config.hidden_attributes_by_part.items()
        },
        "hidden_attributes_for_all": sorted(config.hidden_attributes_for_all),
        "mixer": config.mixer.to_dict(),
        "refresh_settings": config.refresh_settings.to_dict(),
        "play_settings": config.play_settings.to_dict(),
        "part_name_overrides": dict(config.part_name_overrides),
        "part_program_overrides": dict(config.part_program_overrides),
        "part_percussion_overrides": sorted(config.part_percussion_overrides),
        "key_signature_override_fifths": config.key_signature_override_fifths,
        "key_signature_override_mode": config.key_signature_override_mode,
        "playback_tempo_bpm": config.playback_tempo_bpm,
        "percussion_item_overrides": {
            _encode_percussion_item_key(k): v for k, v in config.percussion_item_overrides.items()
        },
        "percussion_item_name_overrides": {
            _encode_percussion_item_key(k): v for k, v in config.percussion_item_name_overrides.items()
        },
        "percussion_auto_correct_enabled": config.percussion_auto_correct_enabled,
        "last_position_index": config.last_position_index,
        "marking_categories_off": sorted(config.marking_categories_off),
        "part_link_groups": [list(g) for g in config.part_link_groups],
        "collapsed_stave_parts": list(config.collapsed_stave_parts),
    }
