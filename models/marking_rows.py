# models/marking_rows.py
"""PerformanceMarkingsStrategy.md section 5 / implementation plan stage 3:
which marking rows belong in the note list at a given event slice.

A MusicData collaborator in the style of performance_rows.py - it owns no
state of its own, reads spans live off `data`, and builds a small index once
per load (keyed by measure number) so a lookup on every cursor move stays
O(1)-ish rather than a linear scan of every span on every keystroke (Ref 9's
25 ms budget - see the strategy's section 15 "things to hold on to").

Stage 3 covers only the three SCORE-LEVEL span kinds (repeats, endings,
sections - strategy section 4 axis B): one row at the first visible event of
the bar a span opens, one at the last visible event of the bar it closes.
Part/staff-level placement (hairpins, stage 5) is a different collaborator
method, added when that stage lands.
"""
from typing import Dict, List, Optional

from models import marking_labels
from models.region3_row import MarkingRow


class MarkingRows:
    def __init__(self, data):
        self.data = data
        self._built = False
        self._first_quarters_of_measure: Dict[int, float] = {}
        self._last_quarters_of_measure: Dict[int, float] = {}

    def _ensure_index(self) -> None:
        if self._built:
            return
        self._built = True
        for event_slice in self.data._real_timeline_slices:
            m = event_slice.measure
            q = event_slice.quarters_from_start
            if m not in self._first_quarters_of_measure or q < self._first_quarters_of_measure[m]:
                self._first_quarters_of_measure[m] = q
            if m not in self._last_quarters_of_measure or q > self._last_quarters_of_measure[m]:
                self._last_quarters_of_measure[m] = q

    def _is_first_of_measure(self, event_slice) -> bool:
        return event_slice.quarters_from_start == self._first_quarters_of_measure.get(
            event_slice.measure
        )

    def _is_last_of_measure(self, event_slice) -> bool:
        return event_slice.quarters_from_start == self._last_quarters_of_measure.get(
            event_slice.measure
        )

    def score_level_rows(self, event_slice) -> List[MarkingRow]:
        """Section 5's row order at `event_slice`: end rows before start
        rows, repeats then endings then sections - a stable, arbitrary but
        fixed order, since a repeat's end and another span's start cannot
        land on the very same event (they anchor to different bars)."""
        if event_slice is None:
            return []
        self._ensure_index()
        data = self.data
        rows: List[MarkingRow] = []

        def _add(span, name: str) -> None:
            if span.end_measure == event_slice.measure and self._is_last_of_measure(event_slice):
                rows.append(MarkingRow(text=marking_labels.end_label(name), marking=span))
            if span.start_measure == event_slice.measure and self._is_first_of_measure(event_slice):
                rows.append(MarkingRow(text=marking_labels.start_label(name), marking=span))

        for span in data.repeat_spans:
            _add(span, "Repeat")
        for span in data.ending_spans:
            _add(span, f"Ending {span.number}")
        for span in data.section_spans:
            _add(span, f"Section {span.label}" if span.label else "Section")

        return rows
