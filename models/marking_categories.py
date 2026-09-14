# models/marking_categories.py
"""PerformanceMarkingsStrategy.md section 8 / implementation plan stage 9
(categories) and stage 4 (a Region 5 row, and a category, for every family):
the note-list/Region 5 category a marking row belongs to, so Ctrl+N toggles
one category rather than one marking at a time.

Every inventory family now has a category - "pedal", "octave_shift",
"stave_text" and "fermatas" were the last four without one, because none of
them had a Region 5 row to press Ctrl+N on (D15's "a pedal-heavy piece would
rebuild Region 5 on nearly every bar" reasoning). Stage 4 gave each of them
one, so each also gets a category here.

Region 5 itself filters nothing by category - PerformanceRows' "* " prefix is
cosmetic only, reporting whether the category is currently surfaced
elsewhere. Only MarkingRows' note-list rows (score_level_rows/
part_level_rows/staff_level_rows) actually drop a row when its category is
off.

`stave_text`'s Region 5 row reads the fabricated Stave Text NoteData directly
(parsers/timeline_builder.py's STAVE_TEXT_VOICE_ID voice), so Ctrl+N toggles
its asterisk, but the matching note-list text is rendered by
models/note_renderer.py's main note loop, not MarkingRows, and is not yet
filterable by this category - that wiring is stage 5 work, when stave text
becomes a real DirectionMark/MarkingRow family.

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
    # Stage 4 (PerformanceMarkingsImplementationPlanV2.md): the four families
    # that only just got a Region 5 row to hang Ctrl+N off.
    "pedal",
    "octave_shift",
    "stave_text",
    "fermatas",
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
    "pedal": "Pedal",
    "octave_shift": "Octave shift",
    "stave_text": "Stave text",
    "fermatas": "Fermatas",
}
