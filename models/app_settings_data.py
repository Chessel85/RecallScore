# models/app_settings_data.py
"""The AppSettings data shape and its JSON encode/decode, free of Qt.

persistence/app_settings.py imports QStandardPaths for the file location, so
the shape and the dict conversion live here where the web version can share
them; that module re-exports AppSettings so every existing import site is
unaffected and keeps the file I/O and the set_* helpers.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from models import marking_categories
from models.live_midi_input_settings import LiveMidiInputSettings
from models.performance_indicator_mode import (
    DEFAULT_PERFORMANCE_INDICATOR_MODE,
    PERFORMANCE_INDICATOR_MODES,
)
from models.tuner_settings import TunerSettings
from models.voice_control_settings import VoiceControlSettings


@dataclass
class AppSettings:
    """App-wide preferences that are the same regardless of which score is
    loaded - the UK/US terminology dialect (F4/D-6) and the Recent Files
    list. Deliberately separate from
    ScoreConfig (persistence/score_config.py), which is per-file.
    uk_terms=None means no preference has been saved yet, so the caller
    should fall back to its own default (OS-locale detection).

    Play settings (lead-in/looping) are NOT here - they are per-score
    (ScoreConfig.play_settings). An older settings.json's "play" key is
    simply ignored on load.

    live_midi_input (device/instrument/volume/pan for playing a connected
    MIDI keyboard live, controllers/live_midi_input_controller.py) is global
    - confirmed with the user: it's the user's hardware setup, not a property of any one score.

    voice_control (device/confidence threshold for hands-free voice
    control, controllers/voice_control_controller.py) is global for the same
    reasoning as live_midi_input above.

    tuner (instrument/string/reference-pitch offset/input device for
    Tools > Tuner, controllers/tuner_controller.py) is global for the same
    reasoning as live_midi_input/voice_control above - which instrument
    you're tuning and what microphone you use is the user's own practice
    setup, not a property of any one score.

    shortcuts (action id -> user-chosen QKeySequence, as PortableText, or ""
    for "no shortcut") is global for the same reasoning as live_midi_input/
    voice_control/tuner above - it's the user's own habit, not a property of
    a score. It stores only the user's differences from the factory
    defaults built by MenuBuilder/MainWindow.setup_shortcuts
    (models/shortcut_map.py, controllers/shortcut_controller.py), so a
    changed default in a future version still reaches users who never
    touched that action.

    marking_categories_off (PerformanceMarkingsStrategy.md section 8) is the
    global default for a score that has never had its own .rsc written yet -
    once a score is saved, persistence/score_config.py's per-score value
    takes over for that file. Every Ctrl+N toggle writes through to both, so
    a newly opened score inherits whatever the user last chose. The user
    changed their mind on the original "every category on" default, so a
    settings.json with no saved value (or missing the key entirely) now
    defaults to every category off.

    show_engraving_details_enabled (Options > Show Engraving Details,
    Ctrl+V) is global only, with no per-score override - a user-wide
    preference for whether octave-shift/clef-change rows are worth
    surfacing at all (e.g. when collaborating with a sighted musician),
    not a property of any one score. Off by default.

    performance_indicator_mode (Options > Performance Indicator / Ctrl+C,
    models/performance_indicator_mode.py) is global only, for the same
    reasoning as show_engraving_details_enabled - whether the performance
    cue sounds is a personal audio preference, not a property of any one
    score. Off by default (PerformanceIndicatorCue.md decision 1)."""

    uk_terms: Optional[bool] = None
    recent_files: List[str] = field(default_factory=list)
    last_open_dir: Optional[str] = None
    musescore_path: Optional[str] = None
    live_midi_input: LiveMidiInputSettings = field(default_factory=LiveMidiInputSettings)
    voice_control: VoiceControlSettings = field(default_factory=VoiceControlSettings)
    tuner: TunerSettings = field(default_factory=TunerSettings)
    shortcuts: Dict[str, str] = field(default_factory=dict)
    marking_categories_off: List[str] = field(
        default_factory=lambda: list(marking_categories.ALL_CATEGORIES)
    )
    show_engraving_details_enabled: bool = False
    performance_indicator_mode: str = DEFAULT_PERFORMANCE_INDICATOR_MODE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppSettings":
        """Builds settings from a loaded settings.json dict, falling back to
        each field's default for a missing or invalid value."""
        return cls(
            uk_terms=data.get("uk_terms"),
            recent_files=data.get("recent_files", []),
            last_open_dir=data.get("last_open_dir"),
            musescore_path=data.get("musescore_path"),
            live_midi_input=LiveMidiInputSettings.from_dict(data.get("live_midi_input")),
            voice_control=VoiceControlSettings.from_dict(data.get("voice_control")),
            tuner=TunerSettings.from_dict(data.get("tuner")),
            shortcuts=_str_dict(data.get("shortcuts")),
            marking_categories_off=list(
                data.get("marking_categories_off", list(marking_categories.ALL_CATEGORIES))
            ),
            show_engraving_details_enabled=bool(data.get("show_engraving_details_enabled", False)),
            performance_indicator_mode=(
                data.get("performance_indicator_mode")
                if data.get("performance_indicator_mode") in PERFORMANCE_INDICATOR_MODES
                else DEFAULT_PERFORMANCE_INDICATOR_MODE
            ),
        )


def _str_dict(value: object) -> Dict[str, str]:
    """Coerces a loaded JSON value to a str->str dict, keeping only entries
    where both key and value are strings and returning {} for anything else
    (a missing key, a list, or a hand-edited file with non-str values)."""
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if isinstance(k, str) and isinstance(v, str)}
