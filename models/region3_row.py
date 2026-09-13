# models/region3_row.py
"""PerformanceMarkingsStrategy.md section 15 / Implementation plan stage 2:
Region 3's rows become typed instead of bare strings, so the note-list
renderer can tell a real note apart from a marking without every consumer
re-deriving that from NoteData fields (invariant 8). Today the only marking
rows are the fabricated Stave Text / Rehearsal mark events; later stages add
markings with no NoteData behind them at all, which is why `marking` is left
untyped here rather than pinned to NoteData."""
from dataclasses import dataclass
from typing import Any, Optional, Union


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
    row describes - a fabricated Stave Text/Rehearsal NoteData, a span
    object (RepeatSpan/EndingSpan/SectionSpan/...) from stage 3 on, or None
    for the placeholder "None"/"Click" rows.

    note_index is set ONLY when `marking` is itself a real NoteData drawn
    from MusicData._visible_notes() (the Stave Text/Rehearsal case) - it is
    that note's position there, which is what lets
    MusicData.note_indices_from_selection keep resolving such a row to its
    own attributes (stage 2's guarantee). A span-based marking row (stage 3
    on) carries no note at all, so this stays None - selecting one shows
    "No note selected" in Region 4 (section 4.1's fuller "the marking's own
    detail" is not yet built) and sounds nothing in the audition."""
    text: str
    marking: Any
    note_index: Optional[int] = None


Region3Row = Union[NoteRow, MarkingRow]
