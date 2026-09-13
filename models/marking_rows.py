# models/marking_rows.py
"""PerformanceMarkingsStrategy.md section 5 / implementation plan stage 3:
which marking rows belong in the note list at a given event slice.

A MusicData collaborator in the style of performance_rows.py - it owns no
state of its own, reads spans live off `data`, and builds a small index once
per load (keyed by measure number) so a lookup on every cursor move stays
O(1)-ish rather than a linear scan of every span on every keystroke (Ref 9's
25 ms budget - see the strategy's section 15 "things to hold on to").

Stage 3 covers the three SCORE-LEVEL span kinds (repeats, endings, sections
- strategy section 4 axis B): one row at the first visible event of the bar
a span opens, one at the last visible event of the bar it closes.

Stage 5 adds hairpins - the first PART/STAFF-level kind (axis B: applies to
one part, possibly one staff of it) - via staff_level_rows, keyed the same
way but by (part_id, staff) and by quarters_from_start rather than by
measure, since a wedge can start or stop mid-measure. NoteRenderer.
region_3_data groups notes must call this once per (part_id, staff) run and
insert its rows immediately above that group - never per note - or a
multi-voice staff would repeat the marking once per voice (strategy section
4.1's "a property of the staff, not of a voice").
"""
import bisect
from typing import Dict, List, Optional, Tuple

from models import marking_labels
from models.region3_row import MarkingRow


class MarkingRows:
    def __init__(self, data):
        self.data = data
        self._built = False
        self._first_quarters_of_measure: Dict[int, float] = {}
        self._last_quarters_of_measure: Dict[int, float] = {}
        self._staff_built = False
        self._staff_quarters: Dict[Tuple[str, int], List[float]] = {}

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

        # Stage 6: key/time/immediate-tempo changes, via the same source
        # Region 5's one-shot rows and the change cue read
        # (structural_change_labels) - one source keeps the three from
        # disagreeing (invariant 8). Already suppressed at index 0 there.
        for kind, label in data.structural_change_labels():
            rows.append(MarkingRow(text=label, marking=kind))

        return rows

    # --- part/staff-level rows (stage 5 - hairpins) --------------------

    def _ensure_staff_index(self) -> None:
        if self._staff_built:
            return
        self._staff_built = True
        by_staff: Dict[Tuple[str, int], set] = {}
        for event_slice in self.data._real_timeline_slices:
            for note in event_slice.notes:
                key = (note.part_id, note.staff)
                by_staff.setdefault(key, set()).add(event_slice.quarters_from_start)
        self._staff_quarters = {key: sorted(qs) for key, qs in by_staff.items()}

    def _first_at_or_after(self, key: Tuple[str, int], quarters: float) -> Optional[float]:
        arr = self._staff_quarters.get(key, [])
        i = bisect.bisect_left(arr, quarters)
        return arr[i] if i < len(arr) else None

    def _last_at_or_before(self, key: Tuple[str, int], quarters: float) -> Optional[float]:
        arr = self._staff_quarters.get(key, [])
        i = bisect.bisect_right(arr, quarters) - 1
        return arr[i] if i >= 0 else None

    def staff_level_rows(self, event_slice) -> Dict[Tuple[str, int], List[MarkingRow]]:
        """Hairpin rows for `event_slice`, grouped by (part_id, staff) -
        NoteRenderer inserts each group immediately above that staff's note
        rows (strategy section 4.1), never repeated per voice.

        A hairpin whose start and stop resolve to the SAME position is a
        point (section 11): "Crescendo"/"Diminuendo", no "hairpin", no
        start/end word. An incomplete span (only one end known - a bare
        <wedge type="stop"> with nothing to match, or a start that never
        closes) gets only the row for its known end; the "no start/end
        marked in the file" wording stays Region 5's alone (unchanged from
        stage 1)."""
        if event_slice is None:
            return {}
        self._ensure_staff_index()
        result: Dict[Tuple[str, int], List[MarkingRow]] = {}

        def _add(key: Tuple[str, int], row: MarkingRow) -> None:
            result.setdefault(key, []).append(row)

        for span in self.data.hairpin_spans:
            key = (span.part_id, span.staff)
            name = span.kind.capitalize() if span.kind else "Hairpin"

            if (
                span.start_known and span.end_known
                and span.start_quarters_from_start == span.end_quarters_from_start
            ):
                anchor = self._first_at_or_after(key, span.start_quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    _add(key, MarkingRow(text=name, marking=span))
                continue

            if span.end_known:
                anchor = self._last_at_or_before(key, span.end_quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    _add(key, MarkingRow(text=marking_labels.end_label(name), marking=span))
            if span.start_known:
                anchor = self._first_at_or_after(key, span.start_quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    _add(key, MarkingRow(text=marking_labels.start_label(name), marking=span))

        return result
