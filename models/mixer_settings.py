# models/mixer_settings.py
"""Per-score mixer state: volume and pan per part, plus the click,
the spoken position announcer and the performance cue (wishlist #4), and
the global mute (wishlist #7).

Edited live by widgets/mixer_dialog.py via controllers/playback_controller.py
(begin_mixer_edit/set_mixer_volume/set_mixer_pan/end_mixer_edit, over this
module's MixerEdit) and by the web version's Mixer dialog through
web/py/web_api.py, and persisted per score through MusicData.mixer /
export_config() / apply_config(). muted (wishlist #7) still has no UI - the
Mixer dialog only exposes per-channel volume/pan. It is stdlib-only for the
same reason as models/score_config_data.py: models/ must stay Qt-free
(guarded by test_models_package_does_not_import_qt).

**Only explicit overrides are stored.** A part absent from part_volumes has
no volume set at all, and the playback path must send no CC for it, leaving
FluidSynth exactly as it is today. That is what makes an empty MixerSettings
- the default for every score without a saved mixer - byte-for-byte
identical to having no mixer at all, rather than "identical because the
defaults happen to match".
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from models.synthetic_parts import LYRICS_PART_ID

# MIDI CC value range. 100 is FluidSynth's own default channel volume and 64
# is centre pan; they are named here for the UI to start from, NOT applied
# as defaults - see the module docstring.
MIN_LEVEL = 0
MAX_LEVEL = 127
DEFAULT_VOLUME = 100
CENTRE_PAN = 64

# Keys for the three non-instrument channels, which have no part_id.
CLICK = "click"
ANNOUNCER = "announcer"
CUE = "cue"


def clamp(value: int) -> int:
    return max(MIN_LEVEL, min(MAX_LEVEL, int(value)))


# The Mixer dialog (wishlist #4) displays volume as 0%..100% and pan as
# -100%..+100%, per the user's own spec, rather than the raw 0-127 MIDI CC
# range everything else in this module works in. MixerSettings itself always
# stores CC values, never percent.
#
# Volume is a MULTIPLIER OF THE DEFAULT PERCEIVED LOUDNESS, not of the raw
# CC7 number: 100% means "unchanged from today's default" (DEFAULT_VOLUME,
# 100), 50% should SOUND half as loud, 0% is silence. This deliberately means
# CC 127 (the true MIDI maximum) is never reachable from this dialog - the
# user's own spec has no "louder than default" concept, only "the default,
# or quieter".
#
# Reported bug, live-tested: a first version used a straight linear
# percent->CC mapping (cc = DEFAULT_VOLUME * percent / 100), matching "50%
# should be half the CC number" - but 25% (CC 25) came out "barely audible",
# far quieter than a quarter of the default's loudness. FluidSynth's own CC7
# handling is not a linear amplitude multiplier - like most GM-compliant
# synths it applies an audio-taper (power-law) response, so a linear CC cut
# compounds into a much steeper perceived loudness cut. sqrt() pre-corrects
# for that assumed square-law response - the standard way to compensate a
# power-law device (cc/default)^2 = fraction, solved for cc - so 50%/25%
# come out sounding roughly half/a quarter as loud rather than far quieter.
def volume_percent_to_cc(percent: float) -> int:
    fraction = max(0.0, percent) / 100.0
    return clamp(round(DEFAULT_VOLUME * math.sqrt(fraction)))


def cc_to_volume_percent(cc: int) -> int:
    fraction = max(0.0, cc) / DEFAULT_VOLUME
    return round(100 * (fraction ** 2))


def pan_percent_to_cc(percent: float) -> int:
    return clamp(round((percent + 100) * MAX_LEVEL / 200))


def cc_to_pan_percent(cc: int) -> int:
    # The general formula is off by 1% at the centre point (64 -> 1%, not
    # 0%) since 0-127 has no exact midpoint - special-cased since centre is
    # by far the most common value (it's every real part's true default).
    if cc == CENTRE_PAN:
        return 0
    return round(cc * 200 / MAX_LEVEL) - 100


# The click/announcer channels' REAL current defaults (SynthEngine.
# _load_click_soundfont sets these explicitly at soundfont-load time, hard
# right/hard left so the two are distinguishable) - duplicated here the same
# way MusicData.RESERVED_CHANNELS duplicates audio/'s channel constants, so
# the Mixer dialog can display/revert-to each row's ACTUAL current default
# rather than one universal centre value that would be wrong for these two.
DEFAULT_PAN_BY_KEY = {CLICK: 127, ANNOUNCER: 0}


def default_pan_for(key: str) -> int:
    return DEFAULT_PAN_BY_KEY.get(key, CENTRE_PAN)


@dataclass
class MixerSettings:
    """volume/pan overrides keyed by part_id, or by CLICK/ANNOUNCER/CUE for
    the three reserved channels. Empty means "nothing overridden"."""

    muted: bool = False
    volumes: Dict[str, int] = field(default_factory=dict)
    pans: Dict[str, int] = field(default_factory=dict)

    def volume_for(self, key: str) -> Optional[int]:
        """The override, or None when there is none - callers must skip
        sending CC entirely on None rather than substituting a default."""
        return self.volumes.get(key)

    def pan_for(self, key: str) -> Optional[int]:
        return self.pans.get(key)

    def set_volume(self, key: str, value: int) -> None:
        self.volumes[key] = clamp(value)

    def set_pan(self, key: str, value: int) -> None:
        self.pans[key] = clamp(value)

    def clear(self, key: str) -> None:
        """Drop a part's overrides, returning it to the engine's own
        defaults."""
        self.volumes.pop(key, None)
        self.pans.pop(key, None)

    def copy(self) -> "MixerSettings":
        """An independent snapshot - volumes/pans are mutable dicts, so
        dataclasses.replace() would alias them rather than copy them. Used
        for the Mixer dialog's snapshot-before-edit/working-copy pattern
        (controllers/playback_controller.py's begin_mixer_edit) and for
        MusicData.export_config()/apply_config(), so a saved ScoreConfig
        can't be mutated by later live edits to the score's own mixer."""
        return MixerSettings(muted=self.muted, volumes=dict(self.volumes), pans=dict(self.pans))

    def is_empty(self) -> bool:
        return not self.muted and not self.volumes and not self.pans

    def to_dict(self) -> dict:
        return {
            "muted": self.muted,
            "volumes": dict(self.volumes),
            "pans": dict(self.pans),
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "MixerSettings":
        if not data:
            return cls()
        return cls(
            muted=bool(data.get("muted", False)),
            volumes={str(k): clamp(v) for k, v in (data.get("volumes") or {}).items()},
            pans={str(k): clamp(v) for k, v in (data.get("pans") or {}).items()},
        )


# --- the Mixer's channels and its edit session ---------------------------------
#
# Shared by the desktop's PlaybackController and the web bridge
# (web/py/web_api.py), so both list the same rows and send the same
# levels. Every function takes music_data per call rather than holding it
# (CLAUDE.md invariant 3: it is replaced wholesale on every load).

# Labels of the three app-sound rows, after the parts.
SOUND_ROW_LABELS = {CLICK: "Metronome", ANNOUNCER: "Position Announcer", CUE: "Performance Cue"}


def mixer_rows(music_data) -> List[Tuple[str, str, int]]:
    """(key, label, channel) for every mixer-controllable channel: each real
    instrument part, in parts_info order, then the click, position announcer
    and performance-cue channels. The Mixer dialog's list is built from
    this. The synthetic Lyrics part is left out: it never sounds, so volume
    or pan on it would do nothing."""
    rows: List[Tuple[str, str, int]] = []
    if music_data is None:
        return rows
    for part in music_data.parts_info:
        if part.part_id == LYRICS_PART_ID:
            continue
        rows.append((part.part_id, part.name, music_data.get_channel_for_part(part.part_id)))
    rows.append((CLICK, SOUND_ROW_LABELS[CLICK], music_data.METRONOME_CLICK_CHANNEL))
    rows.append((ANNOUNCER, SOUND_ROW_LABELS[ANNOUNCER], music_data.POSITION_ANNOUNCER_CHANNEL))
    rows.append((CUE, SOUND_ROW_LABELS[CUE], music_data.PERFORMANCE_CUE_CHANNEL))
    return rows


def channel_for(music_data, key: str) -> Optional[int]:
    for row_key, _, channel in mixer_rows(music_data):
        if row_key == key:
            return channel
    return None


def channel_levels(music_data, mixer: MixerSettings) -> List[Tuple[int, int, int]]:
    """(channel, volume CC, pan CC) for EVERY mixer row: the override where
    there is one, else the real default (DEFAULT_VOLUME, default_pan_for).

    Every row is sent, not just the overridden ones. Reported bug,
    live-tested: the synth outlives a load (one FluidSynth for the whole
    run), so a channel's level from the score open BEFORE survived into the
    next one. A part on the same channel number in both scores silently
    inherited the old override - a cello set to 0% in a MusicXML score
    stayed silent in the MIDI version of the same piece, which had no
    override of its own. The same full resend is what Cancel needs: a live
    preview may have changed a channel that had no override before."""
    levels = []
    for key, _, channel in mixer_rows(music_data):
        volume = mixer.volume_for(key)
        pan = mixer.pan_for(key)
        levels.append((
            channel,
            volume if volume is not None else DEFAULT_VOLUME,
            pan if pan is not None else default_pan_for(key),
        ))
    return levels


class MixerEdit:
    """One Mixer dialog session (wishlist #4): an untouched snapshot of the
    score's mixer for Cancel to go back to, and a working copy the dialog's
    live changes go into. The score's own mixer is not touched until
    commit(). Each change returns the (channel, CC) to send at once, so the
    change is heard while the dialog is open (the live preview)."""

    def __init__(self, mixer: MixerSettings):
        self.original = mixer.copy()
        self.working = mixer.copy()

    def rows(self, music_data) -> List[Tuple[str, str, int, int]]:
        """(key, label, volume percent, pan percent) per row, for the
        dialog. A row with no override shows the channel's REAL default
        (100% volume; 0% pan for a part, but the click's hard right and the
        announcer's hard left, see default_pan_for), not a placeholder."""
        rows = []
        for key, label, _ in mixer_rows(music_data):
            volume = self.working.volume_for(key)
            pan = self.working.pan_for(key)
            rows.append((
                key, label,
                cc_to_volume_percent(volume if volume is not None else DEFAULT_VOLUME),
                cc_to_pan_percent(pan if pan is not None else default_pan_for(key)),
            ))
        return rows

    def set_volume(self, music_data, key: str, percent: int) -> Optional[Tuple[int, int]]:
        """Record the new volume; (channel, CC) to send now, or None for a
        key that is not a mixer row."""
        cc = volume_percent_to_cc(percent)
        self.working.set_volume(key, cc)
        channel = channel_for(music_data, key)
        return None if channel is None else (channel, cc)

    def set_pan(self, music_data, key: str, percent: int) -> Optional[Tuple[int, int]]:
        cc = pan_percent_to_cc(percent)
        self.working.set_pan(key, cc)
        channel = channel_for(music_data, key)
        return None if channel is None else (channel, cc)

    def commit(self, music_data) -> None:
        """OK: the working copy becomes the score's mixer. It is already
        live on the synth from the changes, so nothing more is sent."""
        music_data.mixer = self.working

    def revert_levels(self, music_data) -> List[Tuple[int, int, int]]:
        """Cancel: the levels that put the synth back as it was before the
        dialog opened (every row, see channel_levels)."""
        return channel_levels(music_data, self.original)
