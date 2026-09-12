# models/refresh_settings.py
"""How the regions and status bar refresh while playback runs (the Delay
Refresh feature): whether they update at all, and how far the text is offset
from the sounding note.

The point is not to delay a redraw for its own sake; it is to move the screen
reader's speech and the sounding note apart in time, in either direction:

* refresh_during_playback False - text does not change during playback at
  all, so NVDA says nothing until pause/stop catches it up.
* delay_ms > 0 - text refreshes AFTER the note has sounded (the note is heard
  clean, the announcement follows it).
* delay_ms < 0 - text refreshes BEFORE the note sounds (NVDA announces the
  note name, then it plays); the music itself is what moves in this case
  (audio/sequencer.py's lead_offset_ms), not just the text.

Stored GLOBALLY (persistence/app_settings.py), same reasoning as
models/play_settings.py: this is a property of how the user hears things, not
of the piece.

stdlib-only - models/ must stay Qt-free (guarded by
test_models_package_does_not_import_qt).
"""
from dataclasses import dataclass
from typing import Optional

# A hand-edited settings.json shouldn't be able to hold playback back (or
# push it ahead) by an absurd amount.
MIN_REFRESH_DELAY_MS = -1000
MAX_REFRESH_DELAY_MS = 1000


def _clamp_delay(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 0
    return max(MIN_REFRESH_DELAY_MS, min(MAX_REFRESH_DELAY_MS, value))


@dataclass
class RefreshSettings:
    """Defaults are today's behaviour exactly: refresh on, no delay. A user
    who never opens the Delay Refresh dialog must notice nothing."""

    refresh_during_playback: bool = True
    delay_ms: int = 0

    def __post_init__(self):
        self.refresh_during_playback = bool(self.refresh_during_playback)
        self.delay_ms = _clamp_delay(self.delay_ms)

    def copy(self) -> "RefreshSettings":
        """An independent snapshot, the same reasoning as
        PlaySettings.copy() - a controller that snapshots settings at some
        point shouldn't see them change under it later."""
        return RefreshSettings(
            refresh_during_playback=self.refresh_during_playback,
            delay_ms=self.delay_ms,
        )

    def to_dict(self) -> dict:
        return {
            "refresh_during_playback": self.refresh_during_playback,
            "delay_ms": self.delay_ms,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "RefreshSettings":
        """A missing key falls back to that field's default, so a settings
        file written by an older version keeps working."""
        if not data:
            return cls()
        defaults = cls()
        return cls(
            refresh_during_playback=data.get(
                "refresh_during_playback", defaults.refresh_during_playback
            ),
            delay_ms=data.get("delay_ms", defaults.delay_ms),
        )
