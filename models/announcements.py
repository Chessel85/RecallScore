# models/announcements.py
"""The wording of every one-off spoken message and of the playback status
fields, shared by the desktop (controllers/region_presenter.py,
controllers/playback_controller.py) and the web version (web/py/web_api.py).

Pure text, no Qt: the desktop speaks these through
widgets/accessible_announcer, the web through its own announcer queue. Keep
the wording here, never in a caller, so the two versions cannot drift
(invariant 8).
"""
from typing import List, Optional, Tuple

from models import marking_categories
from models.performance_indicator_mode import (
    PERFORMANCE_INDICATOR_ALWAYS_ON,
    PERFORMANCE_INDICATOR_OFF,
    PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING,
)
from models.vocabulary import bar_word

_PLAY_MODE_PHRASES = {
    "to_end": "Play mode: play to end.",
    "loop_once": "Play mode: play loop once.",
    "loop_forever": "Play mode: play loop until stopped.",
}

_PERFORMANCE_INDICATOR_PHRASES = {
    PERFORMANCE_INDICATOR_OFF: "Performance indicator off.",
    PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING: "Performance indicator on except when playing.",
    PERFORMANCE_INDICATOR_ALWAYS_ON: "Performance indicator always on.",
}

_LOOP_REPEAT_PHRASES = {
    "first": "Loop repeat handling: repeat the first play-through.",
    "second": "Loop repeat handling: repeat the second play-through.",
    "alternate": "Loop repeat handling: alternate the first and second play-throughs.",
}


def _bars(count: int, uk_terms: bool) -> str:
    plural = "" if count == 1 else "s"
    return f"{count} {bar_word(uk_terms)}{plural}"


def measure_change(measure: int, uk_terms: bool) -> str:
    """A by-bar move or a jump: just the new bar number, "Measure 6." The
    note itself is read by the note list, so it is never repeated here."""
    return f"{bar_word(uk_terms).capitalize()} {measure}."


def attribute_by_number(rows: List[Tuple[str, str, str]], number: int) -> Optional[str]:
    """Ctrl+<number>: Region 4's Nth row (1-based) as displayed, or None
    when there is nothing at that position."""
    if number < 1 or number > len(rows):
        return None
    display_key, _attribute_key, value = rows[number - 1]
    return f"{display_key}: {value}"


def loop_length(bars: int, uk_terms: bool) -> str:
    return f"Loop length {_bars(bars, uk_terms)}."


def play_mode(mode: str) -> str:
    return _PLAY_MODE_PHRASES.get(mode, _PLAY_MODE_PHRASES["to_end"])


def performance_indicator_mode(mode: str) -> str:
    return _PERFORMANCE_INDICATOR_PHRASES.get(
        mode, _PERFORMANCE_INDICATOR_PHRASES[PERFORMANCE_INDICATOR_OFF]
    )


def refresh_on_playback(enabled: bool) -> str:
    return "Region refresh on." if enabled else "Region refresh off."


def loop_repeat_mode(mode: str) -> str:
    return _LOOP_REPEAT_PHRASES.get(mode, _LOOP_REPEAT_PHRASES["first"])


def tempo(music_data) -> str:
    """F/S/D: just the bare playback tempo number, "96."."""
    number = music_data._format_tempo_number(music_data.playback_tempo_display_bpm())
    return f"{number}."


def section_change(music_data) -> str:
    """A multi-section file's section switch: "Exercise 2, section 2 of 2"."""
    position = f"section {music_data.active_section_index + 1} of {len(music_data.sections)}"
    label = music_data.active_section.label
    return f"{label}, {position}." if label else f"{position.capitalize()}."


def marking_category_toggled(category: str, surfaced: bool) -> str:
    name = marking_categories.CATEGORY_NAMES.get(category, category)
    return f"{name}, {'in note list' if surfaced else 'not in note list'}"


def staves_collapsed(collapsed: bool) -> str:
    return "Staves collapsed" if collapsed else "Staves uncollapsed"


def metronome_toggled(enabled: bool) -> str:
    return f"Metronome {'on' if enabled else 'off'}"


def position_announcer_toggled(enabled: bool) -> str:
    return f"Position announcer {'on' if enabled else 'off'}"


def bar_line_indicator_toggled(enabled: bool) -> str:
    return f"Bar line indicator {'on' if enabled else 'off'}"


def lead_in_toggled(enabled: bool) -> str:
    return f"Lead in {'on' if enabled else 'off'}"


# Why a loop command did nothing: said rather than staying silent, which
# reads as "broken" to a screen-reader user.
LOOPING_OFF = "Looping is off"
NO_REPEATS = "This score has no repeats"


def pending_digits(digits: str, uk_terms: bool) -> str:
    """The status bar's position field while a bar number is being typed."""
    return f"Go to {bar_word(uk_terms)}: {digits}"


# --- playback status fields (after MusicData.get_status_bar_fields) -------

PLAYBACK_STOPPED = "Playback: Stopped"
PLAYBACK_PAUSED = "Playback: Paused"
PLAYBACK_PLAYING = "Playback: Playing"
PLAYBACK_LEAD_IN = "Playback: Lead-in"
PLAYBACK_LOOPING = "Playback: Playing (looping)"
PLAYBACK_LOOP_ONCE = "Playback: Playing (loop once)"


def playback_status(run, paused: bool, playing: bool) -> str:
    """The Playing/Paused/Stopped field. `run` is the lead-in/looping play
    run (models/play_plan.py's PlayRun) or None for a plain run.

    A play run reports its own phase first: during the count-in nothing
    is sounding yet and the notes would say "Stopped", which reads as
    "Space did nothing". Looping is called out because it is the one
    state that will not end on its own."""
    if run is not None:
        if not run.playing:
            return PLAYBACK_LEAD_IN
        if run.looping:
            return PLAYBACK_LOOPING if run.settings.loop_forever else PLAYBACK_LOOP_ONCE
        return PLAYBACK_PLAYING
    if paused:
        return PLAYBACK_PAUSED
    if playing:
        return PLAYBACK_PLAYING
    return PLAYBACK_STOPPED


def metronome_status(enabled: bool) -> str:
    return "Metronome: On" if enabled else "Metronome: Off"


def position_announcer_status(enabled: bool) -> str:
    return "Position Announcer: On" if enabled else "Position Announcer: Off"


def loop_length_status(bars: int, uk_terms: bool) -> str:
    return f"Loop length: {_bars(bars, uk_terms)}"
