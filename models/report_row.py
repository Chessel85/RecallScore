# models/report_row.py
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReportRow:
    """One line of the Performance Report (PITweaksImplementationPlan.md
    stage 6 / PerformanceMarkingsImplementationPlanV2.md stage 8),
    structured for PerformanceReportDialog's tree and for jumping the
    timeline cursor to what a detail row describes.

    level 0 = a header/preamble line, a top-level tree item; level 1 = one
    of its details, a child of the most recent level-0 row.

    Jump targets are carried from the object that produced the text, never
    parsed back out of it (invariant 8):
    * jump_quarters resolves through slice_index_at_or_after_quarters - a
      continuous position (a hairpin, a dynamics word, a note dynamic).
    * jump_measure resolves through first_visible_event_index_of_measure -
      a barline-aligned range or point (a repeat, a key change).
    * jump_index is the row's own, already-known timeline index, used only
      for a barline marker event (models/event_slice.py's barline_items):
      that event's quarters_from_start coincides with the following bar's
      first note (a barline belongs to the end of its bar), so a
      quarters-based lookup could resolve to the wrong slice. Applied with
      no further lookup.
    * part_id, on a Parts row, selects a Region 2 node instead of moving
      the timeline.

    A row with none of the four is a header or a range-only row (Sections,
    Repeated sections, Endings, the preamble) - Enter does nothing for it."""

    text: str
    level: int
    jump_quarters: Optional[float] = None
    jump_measure: Optional[int] = None
    jump_index: Optional[int] = None
    part_id: Optional[str] = None

    def has_jump_target(self) -> bool:
        return (
            self.part_id is not None
            or self.jump_quarters is not None
            or self.jump_measure is not None
            or self.jump_index is not None
        )
