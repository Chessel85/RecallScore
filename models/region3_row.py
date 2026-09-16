# models/region3_row.py
"""PerformanceMarkingsStrategy.md section 15 / Implementation plan stage 2:
Region 3's rows become typed instead of bare strings, so the note-list
renderer can tell a real note apart from a marking without every consumer
re-deriving that from NoteData fields (invariant 8). `marking` is left
untyped rather than pinned to NoteData since most markings (spans,
DirectionMarks, ...) carry no NoteData at all."""
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
    row describes - a span object (RepeatSpan/EndingSpan/JumpPoint/...), a
    DirectionMark, a NoteData a fermata row was derived from, or None for
    the placeholder "None"/"Click" rows.

    note_index is never set (PerformanceMarkingsImplementationPlanV2.md
    stage 5 removed the last case that did, a fabricated Stave Text/
    Rehearsal NoteData) - a marking row carries no note of its own, so
    selecting one shows "No note selected" in Region 4 and sounds nothing
    in the audition.

    Stage 9: `category` is one of models.marking_categories.ALL_CATEGORIES
    - MarkingRows filters a row out of the note list entirely when its
    category is in MusicData.marking_categories_off. None (the default)
    means "always on", either because the row has no toggle (a barline
    fermata's category choice aside) or because it comes from a category
    marking_categories.ALL_CATEGORIES deliberately excludes."""
    text: str
    marking: Any
    note_index: Optional[int] = None
    category: Optional[str] = None


Region3Row = Union[NoteRow, MarkingRow]
