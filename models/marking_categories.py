# models/marking_categories.py
"""PerformanceMarkingsStrategy.md section 8 / implementation plan stage 9:
the note-list category a Region 5 row belongs to, so Ctrl+N toggles one
category rather than one marking at a time.

Deliberately narrower than section 8's full eleven-name list. Two of its
categories are left out because there is no Region 5 row to press Ctrl+N
on in the first place:

* "pedal" - the pedal CHANGE point and (stage 5) the pedal span both get a
  note-list row (PART-level, models/marking_rows.py's part_level_rows - a
  sustain pedal is a whole-instrument control, not a per-stave one), but
  neither has a Region 5 row (D15), and nothing puts one there - so there
  is nothing to press Ctrl+N on. Both rows are always on.
* "octave shift" - same reasoning: a note-list row exists (stage 5), no
  Region 5 row does (D15). Always on.

"stave text" is not in this tuple either, for a different reason: the
fabricated Stave Text / Rehearsal Mark rows are real NoteData in the
timeline (parsers/timeline_builder.py), rendered by models/note_renderer.py's
main note loop rather than synthesised from a span/mark list. Suppressing
just their ROW there without touching the underlying timeline event risks a
slice with visible notes but zero Region 3 rows, and can couple to a
neighbouring staff's marking rows in a way the other categories never do.
Left on permanently until that rendering path is revisited.

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
    # Stage 5 (PI tweaks): the note list's default-on families that already
    # had a Region 5 row to hang Ctrl+N off.
    "dynamics_words",
    "tempo_words",
    "other_directions",
    "measure_styles",
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
    "dynamics_words": "Dynamics words",
    "tempo_words": "Tempo words",
    "other_directions": "Other directions",
    "measure_styles": "Measure styles",
}
