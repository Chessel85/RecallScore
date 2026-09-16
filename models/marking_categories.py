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

A category not in this tuple is simply never off - its rows always render
regardless of marking_categories_off (see MarkingRows filtering and
PerformanceRows' asterisk logic, both of which treat category=None the
same way as a category outside ALL_CATEGORIES)."""
from typing import Dict, Optional, Tuple

ALL_CATEGORIES: Tuple[str, ...] = (
    "repeats_endings",
    "jump_points",
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
    # Stage 10 (PerformanceMarkingsImplementationPlanV2.md): principal-voice
    # is now a real span family (previously the other_direction catch-all),
    # so it gets its own toggle like octave_shift's.
    "principal_voice",
)

# Short, screen-reader-friendly names for the Ctrl+N state announcement
# ("Hairpins, in note list") - not the individual row's own wording, which
# can be a long range description.
CATEGORY_NAMES: Dict[str, str] = {
    "repeats_endings": "Repeats and endings",
    "jump_points": "Jump points",
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
    "principal_voice": "Principal voice",
}

# Options > Show Engraving Details (Ctrl+V). These two categories describe
# engraving/layout choices a blind musician doesn't need to reproduce the
# performance - an octave shift and a clef change are both already realised
# by playing the printed note at its correct pitch. Off by default; when off
# they are dropped outright (not just cosmetically asterisked) from the note
# list, Region 5 and Find - unlike marking_categories_off/Ctrl+N, which never
# touches Find or removes a Region 5 row. Kept as a fixed pair rather than a
# generic "engraving" flag on every category, since the user may name more
# candidates later and each addition should be a deliberate one-line change
# here, not an accidental side effect of some other property.
ENGRAVING_DETAIL_CATEGORIES = frozenset({"clef_changes", "octave_shift"})


def category_visible(
    category: Optional[str], marking_categories_off, show_engraving_details_enabled: bool
) -> bool:
    """True if a row/Find-target with this category should be surfaced,
    folding together the two independent gates: Ctrl+N's per-category
    marking_categories_off (note-list only, cosmetic elsewhere) and the
    engraving-details toggle (drops the row everywhere when off). A
    category of None - every family without a Region 5 row to hang Ctrl+N
    on - is always visible, matching both gates' existing treatment of it."""
    if category is None:
        return True
    if category in ENGRAVING_DETAIL_CATEGORIES and not show_engraving_details_enabled:
        return False
    return category not in marking_categories_off
