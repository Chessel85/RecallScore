# audio/free_metronome.py
"""Playback > Play Metronome (Ctrl+Alt+Space): a free-running click track
for playing along by ear. It sounds at the current playback tempo (F/S/D
adjustments included) in the time signature at the cursor, never moves the
timeline, and is separate from the Ctrl+M score metronome.

One beat at a time, so the tempo and time signature are re-read every beat:
a tempo change or a cursor move to a differently-metred bar is picked up on
the next click rather than needing a restart. Shared by the desktop's
PlaybackController (a QTimer per beat) and the web bridge (which plans the
beats ahead for its scheduler). Qt-free.
"""
from typing import Optional, Tuple

from audio.metronome import click_event_for_beat

ClickEvent = Tuple[int, int, int, int, int]


def free_metronome_beat(music_data, beat: int) -> Tuple[Optional[ClickEvent], int, int]:
    """(click, next_beat, beat_ms) for `beat` (1 is the accented downbeat):
    the click to sound now, the beat after it, and how long until then."""
    ts_num, ts_den = 4, 4
    current = music_data.get_current_slice()
    if current is not None and current.time_sig:
        ts_num, ts_den = current.time_sig
    click = click_event_for_beat(float(beat))
    next_beat = beat + 1 if beat < max(1, ts_num) else 1
    quarter_bpm = music_data.effective_tempo_bpm()
    beat_ms = (4.0 / float(ts_den or 4)) * 60000.0 / float(quarter_bpm)
    return click, next_beat, max(1, int(round(beat_ms)))
