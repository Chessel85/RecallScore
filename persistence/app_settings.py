# persistence/app_settings.py
import json
import os
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QStandardPaths

from models.app_settings_data import AppSettings
from models.live_midi_input_settings import LiveMidiInputSettings
from models.performance_indicator_mode import (
    DEFAULT_PERFORMANCE_INDICATOR_MODE,
    PERFORMANCE_INDICATOR_MODES,
)
from models.tuner_settings import TunerSettings
from models.voice_control_settings import VoiceControlSettings

__all__ = ["AppSettings", "MAX_RECENT_FILES", "settings_path", "load", "save"]

# File > Recent Files - most-recent-first, capped at this many entries.
MAX_RECENT_FILES = 20


def settings_path() -> Path:
    app_data_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return Path(app_data_dir) / "settings.json"


def load() -> AppSettings:
    path = settings_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppSettings.from_dict(data)
    except FileNotFoundError:
        return AppSettings()
    except (OSError, json.JSONDecodeError) as e:
        print(f"[ERROR] Failed to load app settings from {path}: {e}")
        return AppSettings()


def save(settings: AppSettings) -> None:
    path = settings_path()
    try:
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)
    except OSError as e:
        print(f"[ERROR] Failed to save app settings to {path}: {e}")


def add_recent_file(file_path: str) -> None:
    """Records file_path as the most-recently-opened file - most-recent
    first, no duplicates, capped at MAX_RECENT_FILES. Loads and saves the
    whole settings file itself (load-mutate-save) rather than taking an
    AppSettings in, so callers don't need to worry about clobbering
    uk_terms or vice versa - the same reason set_uk_terms in main_window.py
    must load-mutate-save too, not construct a fresh AppSettings."""
    settings = load()
    recents = [p for p in settings.recent_files if p != file_path]
    recents.insert(0, file_path)
    settings.recent_files = recents[:MAX_RECENT_FILES]
    save(settings)


def set_last_open_dir(directory: str) -> None:
    """Records the folder the File > Open dialog should start in next time,
    load-mutate-save for the same reason as add_recent_file above."""
    settings = load()
    settings.last_open_dir = directory
    save(settings)


def set_live_midi_input_settings(settings: LiveMidiInputSettings) -> None:
    """Records the live-MIDI-input settings, load-mutate-save for the same
    reason as add_recent_file above."""
    current = load()
    current.live_midi_input = settings.copy()
    save(current)


def set_voice_control_settings(settings: VoiceControlSettings) -> None:
    """Records the voice-control settings, load-mutate-save for the same
    reason as add_recent_file/set_live_midi_input_
    settings above."""
    current = load()
    current.voice_control = settings.copy()
    save(current)


def set_musescore_path(path: Optional[str]) -> None:
    """Records the path to the MuseScore 4 executable used to convert
    .mscz/.mscx files on open (parsers/musescore_reader.py). load-mutate-save
    for the same reason as add_recent_file above."""
    current = load()
    current.musescore_path = path or None
    save(current)


def set_tuner_settings(settings: TunerSettings) -> None:
    """Records the tuner settings, load-mutate-save for the same reason as
    add_recent_file/set_live_midi_input_settings
    above."""
    current = load()
    current.tuner = settings.copy()
    save(current)


def set_shortcut_overrides(overrides: Dict[str, str]) -> None:
    """Records the user's keyboard-shortcut overrides (action id -> chosen
    PortableText sequence, or "" for none), load-mutate-save for the same
    reason as add_recent_file above."""
    current = load()
    current.shortcuts = dict(overrides)
    save(current)


def set_marking_categories_off(categories_off) -> None:
    """Records the global default for which note-list marking categories
    (Ctrl+N, strategy section 8) start off in a score that has no .rsc of
    its own yet - load-mutate-save for the same reason as add_recent_file
    above."""
    current = load()
    current.marking_categories_off = sorted(categories_off)
    save(current)


def set_show_engraving_details_enabled(enabled: bool) -> None:
    """Records the Options > Show Engraving Details (Ctrl+V) preference,
    load-mutate-save for the same reason as add_recent_file
    above."""
    current = load()
    current.show_engraving_details_enabled = enabled
    save(current)


def set_performance_indicator_mode(mode: str) -> None:
    """Records the Options > Performance Indicator (Ctrl+C) preference,
    load-mutate-save for the same reason as add_recent_file
    above. An invalid mode falls back to the default,
    matching load()'s own validation."""
    current = load()
    current.performance_indicator_mode = (
        mode if mode in PERFORMANCE_INDICATOR_MODES else DEFAULT_PERFORMANCE_INDICATOR_MODE
    )
    save(current)
