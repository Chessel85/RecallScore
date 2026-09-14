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
        self._score_built = False
        self._score_quarters: List[float] = []

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

        # Stage 8 (strategy section 13): the barline fermata moment event
        # renders as one bare point row - it carries no note, so this is
        # the ONLY row region_3_data() has for it (the `if not notes:`
        # branch returns score_level_rows verbatim when non-empty). Filtering
        # this row out when "barlines" is off is safe even though it is the
        # only row at this event: region_3_data()'s `if not notes:` branch
        # falls through to the metronome-click/"None" placeholder, same as
        # any other event with nothing to show.
        if event_slice.barline_fermata:
            rows.append(MarkingRow(text="Fermata on barline", marking=event_slice, category="barlines"))

        def _add(span, name: str, category: str) -> None:
            # A span that opens and closes on the very same event (a one-bar
            # repeat/ending/section whose bar holds a single event) gets one
            # bare row, not "X end" immediately followed by "X start" -
            # mirroring the hairpin point rule in staff_level_rows.
            is_end = span.end_measure == event_slice.measure and self._is_last_of_measure(event_slice)
            is_start = span.start_measure == event_slice.measure and self._is_first_of_measure(event_slice)
            if is_start and is_end:
                rows.append(MarkingRow(text=name, marking=span, category=category))
                return
            if is_end:
                rows.append(MarkingRow(text=marking_labels.end_label(name), marking=span, category=category))
            if is_start:
                rows.append(MarkingRow(text=marking_labels.start_label(name), marking=span, category=category))

        for span in data.repeat_spans:
            _add(span, "Repeat", "repeats_endings")
        for span in data.ending_spans:
            _add(span, f"Ending {span.number}", "repeats_endings")
        for span in data.section_spans:
            _add(span, f"Section {span.label}" if span.label else "Section", "sections")

        def _at_first(m_num: int) -> bool:
            return event_slice.measure == m_num and self._is_first_of_measure(event_slice)

        def _at_last(m_num: int) -> bool:
            return event_slice.measure == m_num and self._is_last_of_measure(event_slice)

        # Stage 7 (MusicXMLMarkingInventory.md section 11 priority list):
        # score-level point rows. SegnoMark/CodaMark are written at the
        # START of their measure (their own docstrings); NavigationJump/
        # ToCodaMark/FineMark at the END. Rehearsal marks are deliberately
        # NOT added here - they already appear in the note list via the
        # existing fabricated Stave Text event (strategy section 2's
        # "what exists today"), and adding a second score-level row would
        # duplicate them.
        for mark in data.segno_marks:
            if _at_first(mark.measure):
                rows.append(MarkingRow(
                    text=f"Segno{marking_labels.label_suffix(mark.label)}", marking=mark,
                    category="jump_instructions",
                ))
        for mark in data.coda_marks:
            if _at_first(mark.measure):
                rows.append(MarkingRow(
                    text=f"Coda{marking_labels.label_suffix(mark.label)}", marking=mark,
                    category="jump_instructions",
                ))
        for mark in data.to_coda_marks:
            if _at_last(mark.measure):
                rows.append(MarkingRow(
                    text=f"To coda{marking_labels.label_suffix(mark.label)}", marking=mark,
                    category="jump_instructions",
                ))
        for mark in data.fine_marks:
            if _at_last(mark.measure):
                rows.append(MarkingRow(text="Fine", marking=mark, category="jump_instructions"))
        for jump in data.navigation_jumps:
            if _at_last(jump.measure):
                name = "Da capo" if jump.kind == "dacapo" else "Dal segno"
                rows.append(MarkingRow(text=name, marking=jump, category="jump_instructions"))

        # Double/other barlines: a `location="left"` barline opens the
        # measure it's recorded against (first event of that bar); the
        # default `"right"` (and `"middle"`) closes it (last event) - the
        # same anchoring rule PerformanceMarkingsStrategy.md section 5 gives
        # every barline-anchored point.
        for mark in data.barline_marks:
            opens = mark.location == "left"
            if opens and not _at_first(mark.measure):
                continue
            if not opens and not _at_last(mark.measure):
                continue
            label = (
                "Double barline" if mark.kind == "double_barline"
                else f"{mark.style.capitalize()} barline"
            )
            rows.append(MarkingRow(text=label, marking=mark, category="barlines"))

        # Directives (strategy section 9): score-level point rows, but only
        # for the ones Ctrl+N has surfaced (off by default) - anchored like
        # any other quarters-positioned point mark, at the first visible
        # event at or after its own position.
        if data.directives_in_note_list:
            self._ensure_score_index()
            for index in data.directives_in_note_list:
                if not (0 <= index < len(data.directive_marks)):
                    continue
                mark = data.directive_marks[index]
                anchor = self._first_at_or_after_score(mark.quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    rows.append(MarkingRow(text=f"Directive: {mark.label}", marking=mark))

        # Stage 6: key/time/immediate-tempo changes, via the same source
        # Region 5's one-shot rows and the change cue read
        # (structural_change_labels) - one source keeps the three from
        # disagreeing (invariant 8). Already suppressed at index 0 there.
        for kind, label in data.structural_change_labels():
            rows.append(MarkingRow(text=label, marking=kind, category="structural_changes"))

        # Stage 9 (strategy section 8): drop any row whose category the
        # user has switched off. A row with category=None (the directive
        # rows above, and every category models.marking_categories
        # deliberately excludes) is never filtered.
        return [r for r in rows if r.category is None or r.category not in data.marking_categories_off]

    # --- score-level quarters index (stage 7 - directives) --------------

    def _ensure_score_index(self) -> None:
        if self._score_built:
            return
        self._score_built = True
        quarters = {event_slice.quarters_from_start for event_slice in self.data._real_timeline_slices}
        self._score_quarters = sorted(quarters)

    def _first_at_or_after_score(self, quarters: float) -> Optional[float]:
        arr = self._score_quarters
        i = bisect.bisect_left(arr, quarters)
        return arr[i] if i < len(arr) else None

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
                    _add(key, MarkingRow(text=name, marking=span, category="hairpins"))
                continue

            if span.end_known:
                anchor = self._last_at_or_before(key, span.end_quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    _add(key, MarkingRow(
                        text=marking_labels.end_label(name), marking=span, category="hairpins"
                    ))
            if span.start_known:
                anchor = self._first_at_or_after(key, span.start_quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    _add(key, MarkingRow(
                        text=marking_labels.start_label(name), marking=span, category="hairpins"
                    ))

        # Stage 7: clef changes and pedal changes - part/staff-level points
        # (strategy axis B), anchored at the first visible event of that
        # staff at or after the mark's own position. "pedal" is not in
        # models.marking_categories.ALL_CATEGORIES (that module's docstring
        # explains why), so tagging it here documents the category without
        # making it filterable.
        for mark in self.data.clef_change_marks:
            key = (mark.part_id, mark.staff)
            anchor = self._first_at_or_after(key, mark.quarters_from_start)
            if anchor == event_slice.quarters_from_start:
                _add(key, MarkingRow(text=f"Clef change: {mark.label}", marking=mark, category="clef_changes"))

        for mark in self.data.direction_marks:
            if mark.kind != "pedal_change":
                continue
            key = (mark.part_id, mark.staff)
            anchor = self._first_at_or_after(key, mark.quarters_from_start)
            if anchor == event_slice.quarters_from_start:
                _add(key, MarkingRow(text="Pedal change", marking=mark, category="pedal"))

        off = self.data.marking_categories_off
        return {
            key: [r for r in rows if r.category is None or r.category not in off]
            for key, rows in result.items()
        }
