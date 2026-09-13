# models/region3_row.py
"""PerformanceMarkingsStrategy.md section 15 / Implementation plan stage 2:
Region 3's rows become typed instead of bare strings, so the note-list
renderer can tell a real note apart from a marking without every consumer
re-deriving that from NoteData fields (invariant 8). Today the only marking
rows are the fabricated Stave Text / Rehearsal mark events; later stages add
markings with no NoteData behind them at all, which is why `marking` is left
untyped here rather than pinned to NoteData."""
from dataclasses import dataclass
from typing import Any, Union


@dataclass
class NoteRow:
    """An ordinary Region 3 row. note_index is this row's position in
    MusicData._visible_notes() - the same index Region 4's build, playback
    and the audition already key off."""
    text: str
    note_index: int


@dataclass
class MarkingRow:
    """A Region 3 row that is not a note. `marking` is whatever object the
    row describes - today the fabricated Stave Text/Rehearsal NoteData, and
    the placeholder "None"/"Click" rows carry None."""
    text: str
    marking: Any


Region3Row = Union[NoteRow, MarkingRow]
