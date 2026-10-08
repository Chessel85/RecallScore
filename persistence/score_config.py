# persistence/score_config.py
"""Reading and writing a ScoreConfig (Ref 27) to its per-score .rsc file.

The ScoreConfig shape itself lives in models/score_config_data.py: this
module imports Qt for QStandardPaths, and MusicData imports ScoreConfig, so
keeping the dataclass here dragged Qt into every models/ import. It is
re-exported below so either import path works. The JSON encode/decode is in
models/score_config_json.py (shared with the web version) - this module
keeps only the file I/O and the QStandardPaths location.
"""
import json
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QStandardPaths

from models.score_config_data import PercussionItemKey, ScoreConfig, StaffKey, VoiceKey
from models.score_config_json import config_from_dict, config_to_dict

__all__ = [
    "ScoreConfig", "StaffKey", "VoiceKey", "PercussionItemKey",
    "config_dir", "path_for", "load_for", "save", "delete_for",
]


def config_dir() -> Path:
    app_data_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return Path(app_data_dir) / "scores"


def path_for(file_path: str) -> Path:
    """Keyed by the music file's basename+extension only, never its folder,
    so moving the file keeps its config. Two different files sharing a name
    will collide - accepted, given loading is best-effort anyway."""
    return config_dir() / f"{os.path.basename(file_path)}.rsc"


def load_for(file_path: str) -> Optional[ScoreConfig]:
    path = path_for(file_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return config_from_dict(data)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"[ERROR] Failed to load score config from {path}: {e}")
        return None


def save(file_path: str, config: ScoreConfig) -> None:
    path = path_for(file_path)
    data = config_to_dict(config)
    try:
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        # Function-local: keeps QMessageBox out of every `from persistence
        # import score_config`, and this is a cold path. Without this cue the
        # user's per-score toggles/mixer/layout are lost on exit silently
        # (CR8thSept2.txt T1).
        from widgets.user_notification import notify_user
        notify_user(
            "error",
            f"Could not save this score's settings to {path}: {e}\n\n"
            "Your changes to its parts, mixer and layout may not be "
            "remembered next time you open it.",
        )


def delete_for(file_path: str) -> None:
    path = path_for(file_path)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"[ERROR] Failed to delete score config at {path}: {e}")
