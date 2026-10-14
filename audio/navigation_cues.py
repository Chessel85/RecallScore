# audio/navigation_cues.py
"""Which app sounds a timeline move makes beyond the notes themselves: the
metronome click and spoken beat position at the new cursor (Ref 14 AC3,
Ref 28), and the bar line indicator when a plain step crosses a bar line.

Pure decisions over MusicData, no synth and no Qt, so the desktop
(PlaybackController.audition_selection / play_barline_indicator) and the
browser bridge (web/py/web_api.py) sound one definition. Same plain-module
shape as audio/metronome.py; staged for the web in tools/stage_web.py.
"""
from typing import List, Optional, Tuple

from audio.barline_patterns import events_for_pattern, pattern_for_crossing, plain_barline_event
from audio.metronome import click_event_for_beat
from audio.position_announcer import announcement_event_for_beat

Event = Tuple[int, int, int, int, int]


def position_cues(music_data) -> Tuple[Optional[Event], Optional[Event]]:
    """(click, word) for the cursor's current slice: the metronome click if
    the metronome is on and this is a whole beat, the spoken beat position
    if the position announcer is on and there is a word for it. Either may
    be None. Both fire even when the slice sounds no notes (Ref 14 AC3)."""
    current = music_data.get_current_slice()
    if current is None:
        return None, None
    return _beat_cues(music_data, current.beat_position)


def position_cues_at(music_data, index: int) -> Tuple[Optional[Event], Optional[Event]]:
    """position_cues for timeline slice `index` rather than the cursor: what
    each playback step sounds alongside its notes (Ref 14 AC1/AC2, Ref 28
    AC1/AC2), in the Sequencer and the web scheduler alike."""
    return _beat_cues(music_data, music_data.timeline_slices[index].beat_position)


def count_in_cues(music_data, beat_position: float) -> Tuple[Optional[Event], Optional[Event]]:
    """(click, word) for one beat of a lead-in count-in. The click always
    sounds (the lead-in IS "play the count-in click", independent of the
    metronome toggle); the spoken beat number follows the position
    announcer - with it on, hearing "three, four" is the clearest signal of
    where the downbeat lands."""
    word = (announcement_event_for_beat(beat_position)
            if music_data.position_announcer_enabled else None)
    return click_event_for_beat(beat_position), word


def _beat_cues(music_data, beat_position: float) -> Tuple[Optional[Event], Optional[Event]]:
    click = click_event_for_beat(beat_position) if music_data.metronome_enabled else None
    word = (announcement_event_for_beat(beat_position)
            if music_data.position_announcer_enabled else None)
    return click, word


def barline_indicator_events(
    music_data, before_measure: Optional[int] = None, after_measure: Optional[int] = None
) -> List[Event]:
    """The bar line indicator's steps for a plain Left/Right step that went
    from before_measure to after_measure, or [] for silence.

    A repeat/double/heavy/tick bar line sounds its own pattern whatever the
    metronome is doing; the plain beep is suppressed while the metronome is
    on, since that already accents beat 1. The measures are normalised to
    (min, max) first: a bar line sounds the same from either side. See
    PlaybackController.play_barline_indicator for the full reasoning."""
    if not music_data.bar_line_indicator_enabled:
        return []
    if before_measure is not None and after_measure is not None:
        kind = pattern_for_crossing(
            min(before_measure, after_measure), max(before_measure, after_measure),
            music_data.repeat_spans, music_data.ending_spans, music_data.barline_marks,
        )
        if kind is not None:
            return events_for_pattern(kind)
    if music_data.metronome_enabled:
        return []
    return [plain_barline_event()]
