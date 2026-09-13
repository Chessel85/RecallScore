# event_slice.py
from dataclasses import dataclass, field
from typing import List, Tuple
from models.note_data import NoteData


@dataclass
class EventSlice:
    measure: int
    beat_position: float
    quarter_length: float
    notes: List[NoteData] = field(default_factory=list)

    # Time signature (numerator, denominator) and key signature (fifths,
    # MusicXML convention: positive = sharps, negative = flats) in effect at
    # this slice - both can change mid-score, so they're tracked per-event
    # the same way ts_duration already is (D-11, C6). Drives the status bar.
    time_sig: Tuple[int, int] = (4, 4)
    key_fifths: int = 0

    # Ref 12/E4: real elapsed quarter notes from the start of the piece to
    # this slice, independent of the ts-relative beat_position display units
    # (Ref 18) - the prerequisite for the Sequencer to schedule real-time
    # playback between two events, since beat_position resets every measure
    # and can't express a duration on its own.
    quarters_from_start: float = 0.0

    # Stage 8 (PerformanceMarkingsStrategy.md section 13): True for a
    # synthetic moment event representing a <barline>/<fermata> - a pause
    # on the barline itself, attached to no note. notes is always [] on
    # such a slice. Score level (MarkingRows.score_level_rows reads it),
    # sounds nothing, and is navigable regardless of Region 2 filtering -
    # see MusicData._slice_has_visible_notes.
    barline_fermata: bool = False