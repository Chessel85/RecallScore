# models/performance_region_row.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class PerformanceRegionRow:
    """Ref 29: one row of Region 5 (the Performance region) - the single
    line describing a whole RepeatSpan/EndingSpan/HairpinSpan/... active at
    the cursor's current position (PerformanceMarkingsStrategy.md section 6).
    A row carries two jump targets, one per end of the span: the existing
    jump_target_measure/jump_target_quarters fields are the START target
    (unchanged meaning from before the row merge), and end_target_measure/
    end_target_quarters are the END target. jump_target_quarters (and
    end_target_quarters) is None for a repeat/ending row (resolved via
    measure lookup only, since those spans only ever start/end at a measure
    boundary) and set for a hairpin/line row (which can start/stop
    mid-measure, so needs the finer-grained quarters_from_start lookup).
    For a point/structural row, which has only one position, end_target_*
    stays None and NavigationController.jump_to_span falls back to the
    start target for both Ctrl+Home and Ctrl+End.

    Stage 9 (strategy section 8): `category` is one of
    models.marking_categories.ALL_CATEGORIES, or None for a row with no
    note-list toggle (see that module's docstring for what is excluded and
    why). Region5ListWidget's Ctrl+N reads this off the focused row;
    PerformanceRows prefixes the label with "* " when the category is
    currently surfaced in the note list."""

    label: str
    jump_target_measure: int
    jump_target_quarters: Optional[float] = None
    end_target_measure: Optional[int] = None
    end_target_quarters: Optional[float] = None
    category: Optional[str] = None
