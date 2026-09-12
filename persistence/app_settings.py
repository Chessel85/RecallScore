# persistence/app_settings.py
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QStandardPaths

from models.live_midi_input_settings import LiveMidiInputSettings
from models.play_settings import PlaySettings
from models.refresh_settings import RefreshSettings
from models.tuner_settings import TunerSettings
from models.voice_control_settings import VoiceControlSettings

# File > Recent Files - most-recent-first, capped at this many entries.
MAX_RECENT_FILES = 8


@dataclass
class AppSettings:
    """App-wide preferences that are the same regardless of which score is
    loaded - the UK/US terminology dialect (F4/D-6), the Recent Files list
    and the Play settings (lead-in/looping). Deliberately separate from
    ScoreConfig (persistence/score_config.py), which is per-file.
    uk_terms=None means no preference has been saved yet, so the caller
    should fall back to its own default (OS-locale detection).

    play is global rather than per-score on the user's own decision: a
    lead-in length / looping habit is a practice habit that should follow
    them from piece to piece. (The absolute playback tempo IS per-score -
    ScoreConfig.playback_tempo_bpm.) Defaults live on PlaySettings itself,
    so a settings file written before this field existed simply gets them;
    load() also reads the pre-rename "preview" key.

    live_midi_input (device/instrument/volume/pan for playing a connected
    MIDI keyboard live, controllers/live_midi_input_controller.py) is global
    for the same reasoning as play - confirmed with the user: it's the
    user's hardware setup, not a property of any one score.

    voice_control (device/confidence threshold for hands-free SAPI voice
    control, controllers/voice_control_controller.py) is global for the same
    reasoning as live_midi_input above.

    tuner (instrument/string/reference-pitch offset/input device for
    Tools > Tuner, controllers/tuner_controller.py) is global for the same
    reasoning as live_midi_input/voice_control above - which instrument
    you're tuning and what microphone you use is the user's own practice
    setup, not a property of any one score.

    refresh (whether/how far the regions and status bar refresh during
    playback, controllers/refresh_delay_controller.py) is global for the
    same reasoning as play/live_midi_input/voice_control/tuner above - it's
    a property of how the user hears things, not of the piece.

    shortcuts (action id -> user-chosen QKeySequence, as PortableText, or ""
    for "no shortcut") is global for the same reasoning as live_midi_input/
    voice_control/tuner above - it's the user's own habit, not a property of
    a score. It stores only the user's differences from the factory
    defaults built by MenuBuilder/MainWindow.setup_shortcuts
    (models/shortcut_map.py, controllers/shortcut_controller.py), so a
    changed default in a future version still reaches users who never
    touched that action."""

    uk_terms: Optional[bool] = None
    recent_files: List[str] = field(default_factory=list)
    last_open_dir: Optional[str] = None
    musescore_path: Optional[str] = None
    play: PlaySettings = field(default_factory=PlaySettings)
    live_midi_input: LiveMidiInputSettings = field(default_factory=LiveMidiInputSettings)
    voice_control: VoiceControlSettings = field(default_factory=VoiceControlSettings)
    tuner: TunerSettings = field(default_factory=TunerSettings)
    shortcuts: Dict[str, str] = field(default_factory=dict)
    refresh: RefreshSettings = field(default_factory=RefreshSettings)


def settings_path() -> Path:
    app_data_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return Path(app_data_dir) / "settings.json"


def _str_dict(value: object) -> Dict[str, str]:
    """Coerces a loaded JSON value to a str->str dict, keeping only entries
    where both key and value are strings and returning {} for anything else
    (a missing key, a list, or a hand-edited file with non-str values)."""
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if isinstance(k, str) and isinstance(v, str)}


def load() -> AppSettings:
    path = settings_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppSettings(
            uk_terms=data.get("uk_terms"),
            recent_files=data.get("recent_files", []),
            last_open_dir=data.get("last_open_dir"),
            musescore_path=data.get("musescore_path"),
            play=PlaySettings.from_dict(data.get("play") or data.get("preview")),
            live_midi_input=LiveMidiInputSettings.from_dict(data.get("live_midi_input")),
            voice_control=VoiceControlSettings.from_dict(data.get("voice_control")),
            tuner=TunerSettings.from_dict(data.get("tuner")),
            shortcuts=_str_dict(data.get("shortcuts")),
            refresh=RefreshSettings.from_dict(data.get("refresh")),
        )
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
            json.dump(asdict(settings), f, indent=2)
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


def set_play_settings(settings: PlaySettings) -> None:
    """Records the Play settings, load-mutate-save for exactly the same
    reason as add_recent_file above: constructing a fresh AppSettings here
    would silently wipe uk_terms and the Recent Files list."""
    current = load()
    current.play = settings.copy()
    save(current)


def set_live_midi_input_settings(settings: LiveMidiInputSettings) -> None:
    """Records the live-MIDI-input settings, load-mutate-save for the same
    reason as add_recent_file/set_play_settings above."""
    current = load()
    current.live_midi_input = settings.copy()
    save(current)


def set_voice_control_settings(settings: VoiceControlSettings) -> None:
    """Records the voice-control settings, load-mutate-save for the same
    reason as add_recent_file/set_play_settings/set_live_midi_input_
    settings above."""
    current = load()
    current.voice_control = settings.copy()
    save(current)


def set_musescore_path(path: Optional[str]) -> None:
    """Records the path to the MuseScore 4 executable used to convert
    .mscz/.mscx files on open (parsers/musescore_reader.py). load-mutate-save
    for the same reason as add_recent_file/set_play_settings above."""
    current = load()
    current.musescore_path = path or None
    save(current)


def set_tuner_settings(settings: TunerSettings) -> None:
    """Records the tuner settings, load-mutate-save for the same reason as
    add_recent_file/set_play_settings/set_live_midi_input_settings
    above."""
    current = load()
    current.tuner = settings.copy()
    save(current)


def set_shortcut_overrides(overrides: Dict[str, str]) -> None:
    """Records the user's keyboard-shortcut overrides (action id -> chosen
    PortableText sequence, or "" for none), load-mutate-save for the same
    reason as add_recent_file/set_play_settings above."""
    current = load()
    current.shortcuts = dict(overrides)
    save(current)


def set_refresh_settings(settings: RefreshSettings) -> None:
    """Records the Delay Refresh settings, load-mutate-save for the same
    reason as add_recent_file/set_play_settings above."""
    current = load()
    current.refresh = settings.copy()
    save(current)
