# models/marking_categories.py
"""PerformanceMarkingsStrategy.md section 8 / implementation plan stage 9:
the note-list category a Region 5 row belongs to, so Ctrl+N toggles one
category rather than one marking at a time.

Deliberately narrower than section 8's full eleven-name list. Three of its
categories are left out because there is no Region 5 row to press Ctrl+N
on in the first place:

* "pedal" - only the pedal CHANGE point gets a note-list row (staff-level,
  models/marking_rows.py); the pedal span itself is Region-5-only (D15),
  and nothing puts a pedal-change row into Region 5.
* "octave shift" - has no note-list row of any kind yet (D15 excludes the
  span; there is no point sub-event the way pedal has a "change").
* "stave text" - the fabricated Stave Text / Rehearsal Mark rows are real
  NoteData in the timeline (parsers/timeline_builder.py), rendered by
  models/note_renderer.py's main note loop rather than synthesised from a
  span/mark list. Suppressing just their ROW there without touching the
  underlying timeline event risks a slice with visible notes but zero
  Region 3 rows, and can couple to a neighbouring staff's marking rows in
  a way the other eight categories never do. Left on permanently until
  that rendering path is revisited.

A category not in this tuple is simply never off - its rows always render
regardless of marking_categories_off (see MarkingRows filtering and
PerformanceRows' asterisk logic, both of which treat category=None the
same way as a category outside ALL_CATEGORIES)."""
from typing import Dict, Tuple

ALL_CATEGORIES: Tuple[str, ...] = (
    "repeats_endings",
    "sections",
    "hairpins",
    "jump_instructions",
    "lines",
    "barlines",
    "clef_changes",
    "structural_changes",
)

# Short, screen-reader-friendly names for the Ctrl+N state announcement
# ("Hairpins, in note list") - not the individual row's own wording, which
# can be a long range description.
CATEGORY_NAMES: Dict[str, str] = {
    "repeats_endings": "Repeats and endings",
    "sections": "Sections",
    "hairpins": "Hairpins",
    "jump_instructions": "Jump instructions",
    "lines": "Lines",
    "barlines": "Barlines",
    "clef_changes": "Clef changes",
    "structural_changes": "Structural changes",
}
