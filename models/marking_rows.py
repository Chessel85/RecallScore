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
        self._part_built = False
        self._part_quarters: Dict[str, List[float]] = {}
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

        # Directives (strategy section 9; PI tweaks stage 5: on by default
        # now): score-level point rows for every directive Ctrl+N has NOT
        # hidden - anchored like any other quarters-positioned point mark,
        # at the first visible event at or after its own position.
        if data.directive_marks:
            self._ensure_score_index()
            for index, mark in enumerate(data.directive_marks):
                if index in data.directives_hidden_from_note_list:
                    continue
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

    # --- part-level rows (PI tweaks follow-up - pedal) ------------------
    #
    # A sustain pedal is a whole-instrument control, not a per-stave one -
    # even though the file's own <direction> sits against one staff
    # (conventionally the bass staff, for a piano), the note-list row must
    # surface once for the PART, above every one of its staff groups, not
    # buried in whichever staff the XML happened to record it against
    # (reported: a right-hand-only reader never heard a pedal instruction
    # anchored to the left-hand staff). _part_quarters is the union of
    # every staff's quarters in the part, so "first/last event of the
    # part" means "first/last event of ANY staff of it".

    def _ensure_part_index(self) -> None:
        if self._part_built:
            return
        self._part_built = True
        self._ensure_staff_index()
        by_part: Dict[str, set] = {}
        for (part_id, _staff), quarters in self._staff_quarters.items():
            by_part.setdefault(part_id, set()).update(quarters)
        self._part_quarters = {part_id: sorted(qs) for part_id, qs in by_part.items()}

    def _first_at_or_after_part(self, part_id: str, quarters: float) -> Optional[float]:
        arr = self._part_quarters.get(part_id, [])
        i = bisect.bisect_left(arr, quarters)
        return arr[i] if i < len(arr) else None

    def _last_at_or_before_part(self, part_id: str, quarters: float) -> Optional[float]:
        arr = self._part_quarters.get(part_id, [])
        i = bisect.bisect_right(arr, quarters) - 1
        return arr[i] if i >= 0 else None

    def part_level_rows(self, event_slice) -> Dict[str, List[MarkingRow]]:
        """Pedal span, pedal-change point, and fermata rows for
        `event_slice`, grouped by part_id only - NoteRenderer inserts each
        group above the FIRST staff group it encounters for that part
        (whichever staff that happens to be), so each is heard once
        regardless of which hand/staff the reader is navigating. Pedal
        rows use the same start/end/point anchoring rule as
        `_add_span_rows`/`_add_point_row`, against `_part_quarters` instead
        of one staff's; the fermata row instead reads directly off this
        event_slice's own notes (see below - no separate span/mark object
        or cross-slice anchoring exists for it). No category on any of
        these (D15: pedal has no Region 5 row; nor does a note-attached
        fermata) - always on, never filtered by Ctrl+N."""
        if event_slice is None:
            return {}
        self._ensure_part_index()
        result: Dict[str, List[MarkingRow]] = {}
        name = marking_labels.pedal_name()

        # Pedal-change points before the span's own row - the same relative
        # order staff_level_rows gave them before both moved here together.
        for mark in self.data.direction_marks:
            if mark.kind != "pedal_change":
                continue
            part_id = mark.part_id
            anchor = self._first_at_or_after_part(part_id, mark.quarters_from_start)
            if anchor == event_slice.quarters_from_start:
                result.setdefault(part_id, []).append(
                    MarkingRow(text="Pedal change", marking=mark, category=None)
                )

        for span in self.data.direction_spans:
            if span.kind != "pedal":
                continue
            part_id = span.part_id
            if span.start_quarters_from_start == span.end_quarters_from_start:
                anchor = self._first_at_or_after_part(part_id, span.start_quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    result.setdefault(part_id, []).append(
                        MarkingRow(text=name, marking=span, category=None)
                    )
                continue
            end_anchor = self._last_at_or_before_part(part_id, span.end_quarters_from_start)
            if end_anchor == event_slice.quarters_from_start:
                result.setdefault(part_id, []).append(
                    MarkingRow(text=marking_labels.end_label(name), marking=span, category=None)
                )
            start_anchor = self._first_at_or_after_part(part_id, span.start_quarters_from_start)
            if start_anchor == event_slice.quarters_from_start:
                result.setdefault(part_id, []).append(
                    MarkingRow(text=marking_labels.start_label(name), marking=span, category=None)
                )

        # Fermata (PI tweaks follow-up, reported): a note-attached attribute,
        # but a fermata pauses the WHOLE texture at that moment, not one
        # hand/voice - even when the file stamps a <fermata> on more than
        # one simultaneous note (one per staff), it is one instruction, so
        # it gets ONE part-level row here, deduped across every staff/voice
        # of the part that carries one at THIS event. No cross-slice
        # anchoring needed - the note already sits in this event_slice, so
        # this reads event_slice.notes directly rather than going through
        # _part_quarters. Scans every note in the slice (not just the
        # currently visible ones), the same "borrow across the Region 2
        # filter" reasoning the pedal rows above follow - a fermata on a
        # muted voice still pauses the part's other, visible voices. No
        # category (no Region 5 row exists for a note-attached fermata to
        # hang Ctrl+N off).
        seen_fermata_parts = set()
        for note in event_slice.notes:
            if not note.fermata or note.part_id in seen_fermata_parts:
                continue
            seen_fermata_parts.add(note.part_id)
            result.setdefault(note.part_id, []).append(
                MarkingRow(text=marking_labels.fermata_name(note.fermata), marking=note, category=None)
            )
        return result

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
        stage 1).

        Stage 5 (PI tweaks): the families the note list was missing entirely
        (pedal/octave-shift/dashed/bracket spans, dynamics/tempo/other-
        direction points, measure style) go through `_span_rows`/
        `_point_rows` below, same anchoring rule, added AFTER the three
        existing families in the fixed order the plan lays out - existing
        rows never change position."""
        if event_slice is None:
            return {}
        self._ensure_index()
        self._ensure_staff_index()
        result: Dict[Tuple[str, int], List[MarkingRow]] = {}

        def _add(key: Tuple[str, int], row: MarkingRow) -> None:
            result.setdefault(key, []).append(row)

        def _key(mark) -> Tuple[str, int]:
            return (mark.part_id, mark.staff)

        for span in self.data.hairpin_spans:
            key = _key(span)
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

        # Stage 7: clef changes - a staff-level point (strategy axis B),
        # anchored at the first visible event of that staff at or after the
        # mark's own position. Pedal changes moved to part_level_rows below
        # (PI tweaks follow-up) - same "whole instrument, not one stave"
        # reasoning as the pedal span.
        for mark in self.data.clef_change_marks:
            key = _key(mark)
            anchor = self._first_at_or_after(key, mark.quarters_from_start)
            if anchor == event_slice.quarters_from_start:
                _add(key, MarkingRow(text=f"Clef change: {mark.label}", marking=mark, category="clef_changes"))

        # Stage 5: the eight families the note list was missing entirely
        # (strategy's "not in the note list at all" table), in that table's
        # order. Pedal/octave-shift have no Region 5 row (D15) so carry no
        # category (always on, same as pedal change above); the other six
        # already had one, so they carry the stage 5 category that lets
        # Ctrl+N reach them (models/marking_categories.py). Pedal moved to
        # part_level_rows (PI tweaks follow-up) - not handled here.
        for span in self.data.direction_spans:
            if span.kind == "octave_shift":
                self._add_span_rows(
                    _add, event_slice, [span], marking_labels.octave_shift_name(span), None, _key
                )
        for span in self.data.direction_spans:
            if span.kind == "dashes":
                self._add_span_rows(
                    _add, event_slice, [span], marking_labels.direction_line_name(span), "lines", _key
                )
        for span in self.data.direction_spans:
            if span.kind == "bracket":
                self._add_span_rows(
                    _add, event_slice, [span], marking_labels.direction_line_name(span), "lines", _key
                )

        for mark in self.data.direction_marks:
            if mark.kind == "dynamics_word":
                self._add_point_row(
                    _add, event_slice, mark, marking_labels.dynamics_word_label(mark.label),
                    "dynamics_words", _key, mark.quarters_from_start,
                )
        for mark in self.data.direction_marks:
            if mark.kind == "tempo_word":
                self._add_point_row(
                    _add, event_slice, mark, marking_labels.tempo_word_label(mark.label),
                    "tempo_words", _key, mark.quarters_from_start,
                )
        for mark in self.data.direction_marks:
            if mark.kind == "other_direction":
                self._add_point_row(
                    _add, event_slice, mark, marking_labels.other_direction_label(mark.label),
                    "other_directions", _key, mark.quarters_from_start,
                )

        # MeasureStyleMark carries no quarters_from_start of its own - anchor
        # via the measure's own first quarters (the score-level index built
        # by _ensure_index), then the staff's first event at or after that.
        # A multi-bar rest has no events of its own (rests are skipped), so
        # it lands on the NEXT event of that staff - correct: "8-bar rest"
        # is read as you arrive after it, not as you enter it.
        for mark in self.data.measure_style_marks:
            measure_quarters = self._first_quarters_of_measure.get(mark.measure)
            if measure_quarters is None:
                continue
            self._add_point_row(
                _add, event_slice, mark, marking_labels.measure_style_label(mark),
                "measure_styles", _key, measure_quarters,
            )

        off = self.data.marking_categories_off
        return {
            key: [r for r in rows if r.category is None or r.category not in off]
            for key, rows in result.items()
        }

    def _add_span_rows(self, _add, event_slice, spans, name, category, key_for) -> None:
        """One span's rows at `event_slice`: a bare point row when the span's
        start and end resolve to the same staff position, otherwise an end
        row and/or a start row - the same rule the hairpin loop above
        follows, generalised so the growing stage 5 family list isn't eleven
        copies of this anchoring code."""
        for span in spans:
            key = key_for(span)
            if span.start_quarters_from_start == span.end_quarters_from_start:
                anchor = self._first_at_or_after(key, span.start_quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    _add(key, MarkingRow(text=name, marking=span, category=category))
                continue
            end_anchor = self._last_at_or_before(key, span.end_quarters_from_start)
            if end_anchor == event_slice.quarters_from_start:
                _add(key, MarkingRow(
                    text=marking_labels.end_label(name), marking=span, category=category
                ))
            start_anchor = self._first_at_or_after(key, span.start_quarters_from_start)
            if start_anchor == event_slice.quarters_from_start:
                _add(key, MarkingRow(
                    text=marking_labels.start_label(name), marking=span, category=category
                ))

    def _add_point_row(self, _add, event_slice, mark, name, category, key_for, quarters) -> None:
        key = key_for(mark)
        anchor = self._first_at_or_after(key, quarters)
        if anchor == event_slice.quarters_from_start:
            _add(key, MarkingRow(text=name, marking=mark, category=category))
