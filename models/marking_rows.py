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

PerformanceMarkingsImplementationPlanV2.md stage 2: `level_of(marking)` is
now the ONE place that decides score/part/stave placement for every
classification-routable family (hairpins, clef changes, octave shift,
dashed/bracket lines, dynamics/tempo/other-direction words, measure style,
pedal and pedal change), reading models/marking_classification.py plus the
`system`/`staff_given` fields stage 1 put on DirectionMark/DirectionSpan/
HairpinSpan. `_family_rows` runs every one of those families through it once
per event_slice and buckets the resulting rows into a score list, a
part_id-keyed dict and a (part_id, staff)-keyed dict; score_level_rows/
part_level_rows/staff_level_rows are now thin wrappers around that plus
whatever they already held that isn't classification-routable.

Not routed through level_of() - these have no part_id/staff of their own at
all, so there is nothing for ground rules 1/3/4 to key off, and they stay
exactly where they always were (score level, in score_level_rows):
RepeatSpan/EndingSpan/SectionSpan, BarlineMark, SegnoMark/CodaMark/
ToCodaMark/FineMark/NavigationJump, and the tempo "structural change" label
(structural_change_labels). Ground rule 2 (score when the majority of
parts agree, else part for each differing part - PerformanceMarkings
ImplementationPlanV2.md stage 10) needs a per-part comparison none of
these objects carry today; barline styles/repeats/endings stay
unconditionally score, matching pre-stage-2 behaviour - stage 10 only
covers key and time (see marking_classification.py's own docstring).
Key/time changes ARE routed through level_of() (KeyChangeMark/
TimeChangeMark carry their own resolved is_score_level - see level_of()'s
own docstring), but the score-level (majority) case is rendered via
score_level_rows' own small loop rather than through _family_rows, to
keep its row position exactly where structural_change_labels used to put
it for the common (unanimous) case - see that loop's comment.

dashes/bracket (`inherits_level_from_words`, `levels=()` in the
classification table) are placed via the ordinary stave/part fallback below,
which already gives the right answer: stage 6 makes the parser record their
`system`/`staff_given` off the SAME <direction> element a paired <words>
shares (parsers.timeline_builder._step_direction_line), so there is nothing
further to inherit here - the fallback rule sees exactly what the words
would have.

Note fermata is not classification-routed either, despite having a
CLASSIFICATION entry (`note_fermata_aggregate=True`) - its rule is specific
enough (one score row when every part with a note at the event carries a
fermata, else one part row per carrying part) that it gets its own small
method, `_add_fermata_rows`, rather than being force-fit through the
span/point anchoring machinery the other families share.

PerformanceMarkingsImplementationPlanV2.md stage 9 (PITweaksImplementation-
Plan.md item 1, "linked parts"): every part- or stave-level row a family
above produces is also placed, at the SAME kind of level, in every OTHER
part of data.part_link_groups' group - `_levels_including_borrows` turns
one marking's own level into a list of levels (its own plus one per linked
partner), and `_add_span_rows_by_level`/`_add_point_row_by_level`/
`_add_fermata_rows` each check every one of those levels independently
against ITS OWN nearest event, since a borrowed row is not guaranteed to
land on the same event_slice as the owning part's row. Score-level rows and
clef changes are never borrowed. Skipped entirely (a single `not
data.part_link_groups` check) when nothing is linked, so an unlinked score
pays nothing extra (Ref 9)."""
import bisect
from typing import Dict, List, Optional, Set, Tuple

from models import marking_labels
from models.clef_change_mark import ClefChangeMark
from models.direction_mark import DirectionMark
from models.direction_span import DirectionSpan
from models.hairpin_span import HairpinSpan
from models.key_change_mark import KeyChangeMark
from models.key_signatures import key_signature_display_name
from models.marking_classification import classification_for
from models.measure_style_mark import MeasureStyleMark
from models.region3_row import MarkingRow
from models.time_change_mark import TimeChangeMark

# DirectionMark.kind / DirectionSpan.kind -> the inventory.csv element name
# CLASSIFICATION is keyed by. Several parser-level kinds (dynamics_word,
# tempo_word, other_direction) are all just sub-categorised <words>/other-
# direction-type readings and share one classification entry each with the
# generic element the CSV describes.
_DIRECTION_MARK_ELEMENT: Dict[str, str] = {
    "rehearsal": "rehearsal",
    "pedal_change": "pedal",
    "words": "words",
    "dynamics_word": "words",
    "tempo_word": "words",
    "other_direction": "other-direction",
}
_DIRECTION_SPAN_ELEMENT: Dict[str, str] = {
    "pedal": "pedal",
    "octave_shift": "octave-shift",
    "dashes": "dashes",
    "bracket": "bracket",
    "principal_voice": "principal-voice",
}


class MarkingRows:
    def __init__(self, data):
        self.data = data
        self._built = False
        self._first_quarters_of_measure: Dict[int, float] = {}
        self._last_quarters_of_measure: Dict[int, float] = {}
        self._staff_built = False
        self._staff_quarters: Dict[Tuple[str, int], List[float]] = {}
        self._staves_per_part: Dict[str, Set[int]] = {}
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

    # --- stage 2: one level rule ----------------------------------------

    def _classification_for_marking(self, marking):
        if isinstance(marking, DirectionMark):
            return classification_for("direction", _DIRECTION_MARK_ELEMENT[marking.kind])
        if isinstance(marking, DirectionSpan):
            return classification_for("direction", _DIRECTION_SPAN_ELEMENT[marking.kind])
        if isinstance(marking, HairpinSpan):
            return classification_for("direction", "wedge")
        if isinstance(marking, ClefChangeMark):
            return classification_for("attributes", "clef")
        if isinstance(marking, MeasureStyleMark):
            return classification_for("attributes", "measure-style")
        raise TypeError(f"No marking_classification mapping for {type(marking).__name__}")

    def level_of(self, marking) -> Tuple:
        """Implementation plan section 3's "Level of one marking" rules, for
        any classification-routable marking (DirectionMark/DirectionSpan/
        HairpinSpan/ClefChangeMark/MeasureStyleMark - the families that
        carry their own part_id/staff, unlike the score-only spans/marks
        `score_level_rows` still handles directly). Returns ("score",),
        ("part", part_id) or ("stave", part_id, staff).

        Rule 2 (score-or-part by cross-part agreement) is stage 10 work for
        key/time changes only (barline styles/repeats/endings stay
        unconditionally score - see this module's docstring). KeyChangeMark/
        TimeChangeMark carry their own resolved is_score_level (set once,
        after every part is walked, by TimelineBuilder._resolve_key_time_
        levels) rather than going through classification's levels/system/
        staff rules below - the agreement comparison needs sibling marks at
        the same bar, which a single marking's own fields can't answer."""
        if isinstance(marking, (KeyChangeMark, TimeChangeMark)):
            return ("score",) if marking.is_score_level else ("part", marking.part_id)
        classification = self._classification_for_marking(marking)
        levels = classification.levels
        if levels == ("score",):
            return ("score",)
        if getattr(marking, "system", "") in ("only-top", "also-top"):
            return ("score",)
        part_id = marking.part_id
        staff = marking.staff
        # dashes/bracket declare no levels of their own (inherited from
        # their paired <words>, stage 6) - fall back to the ordinary
        # stave/part rule rather than refusing to place them at all.
        if not levels or "stave" in levels:
            if getattr(marking, "staff_given", True) and len(self._staves_for_part(part_id)) > 1:
                return ("stave", part_id, staff)
        return ("part", part_id)

    def _staves_for_part(self, part_id: str) -> Set[int]:
        self._ensure_staff_index()
        return self._staves_per_part.get(part_id, set())

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

        # Stage 7 (PerformanceMarkingsImplementationPlanV2.md): a barline
        # marker moment event renders one bare point row per item it holds
        # (fermata/segno/coda) - it carries no note, so these are the ONLY
        # rows region_3_data() has for it (the `if not notes:` branch
        # returns score_level_rows verbatim when non-empty). Filtering these
        # rows out when "barlines" is off is safe even when they are the
        # only rows at this event: region_3_data()'s `if not notes:` branch
        # falls through to the metronome-click/"None" placeholder, same as
        # any other event with nothing to show.
        for item in event_slice.barline_items:
            rows.append(MarkingRow(
                text=marking_labels.barline_item_label(item), marking=event_slice, category="barlines"
            ))

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
        # Stage 10: a barline wavy-line, the same bare start/end/one-bar
        # rendering as the three spans above - it too is scanned score-wide
        # (first part only), never per-part.
        for span in data.wavy_line_spans:
            _add(span, "Wavy line", "barlines")

        def _at_first(m_num: int) -> bool:
            return event_slice.measure == m_num and self._is_first_of_measure(event_slice)

        def _at_last(m_num: int) -> bool:
            return event_slice.measure == m_num and self._is_last_of_measure(event_slice)

        # Stage 7 (MusicXMLMarkingInventory.md section 11 priority list):
        # score-level point rows. SegnoMark/CodaMark are written at the
        # START of their measure (their own docstrings); NavigationJump/
        # ToCodaMark/FineMark at the END. Rehearsal marks are NOT added here
        # - they are classification-routed (level "score") and come through
        # _family_rows/level_of below instead, like words/dynamics_word/
        # tempo_word/other_direction.
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

        # Stage 6: immediate-tempo changes, via the same source Region 5's
        # one-shot rows and the change cue read (structural_change_labels) -
        # one source keeps the three from disagreeing (invariant 8). Already
        # suppressed at index 0 there.
        for kind, label in data.structural_change_labels():
            rows.append(MarkingRow(text=label, marking=kind, category="structural_changes"))

        # Stage 10: the majority key/time change at this position - read
        # directly off the is_score_level=True mark (see PerformanceRows.
        # structural_change_labels' docstring for why key/time moved off the
        # old timeline_slices-diffing path). The minority (is_score_level=
        # False, one row per differing part) is handled by _family_rows
        # below instead, at "part" level.
        self._ensure_score_index()
        for mark in data.key_change_marks:
            if not mark.is_score_level or data.key_signature_override_fifths is not None:
                continue
            if self._first_at_or_after_score(mark.quarters_from_start) == event_slice.quarters_from_start:
                key_name = key_signature_display_name(mark.fifths, None)
                rows.append(MarkingRow(
                    text=marking_labels.key_signature_change_label(key_name),
                    marking=mark, category="structural_changes",
                ))
        for mark in data.time_change_marks:
            if not mark.is_score_level:
                continue
            if self._first_at_or_after_score(mark.quarters_from_start) == event_slice.quarters_from_start:
                rows.append(MarkingRow(
                    text=marking_labels.time_signature_change_label(mark.ts_num, mark.ts_den),
                    marking=mark, category="structural_changes",
                ))

        # Stage 2: every classification-routed family's score-level rows
        # (a family only lands here via ground rule 1 - "score if the
        # element allows only score" or a system="only-top"/"also-top"
        # <direction>).
        family_score_rows, _part_rows, _stave_rows = self._family_rows(event_slice)
        rows.extend(family_score_rows)

        # Stage 9 (strategy section 8): drop any row whose category the
        # user has switched off. A row with category=None (every category
        # models.marking_categories deliberately excludes) is never
        # filtered.
        return [r for r in rows if r.category is None or r.category not in data.marking_categories_off]

    # --- score-level quarters index --------------------------------------

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

    def _last_at_or_before_score(self, quarters: float) -> Optional[float]:
        arr = self._score_quarters
        i = bisect.bisect_right(arr, quarters) - 1
        return arr[i] if i >= 0 else None

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
        by_part: Dict[str, Set[int]] = {}
        for part_id, staff in self._staff_quarters:
            by_part.setdefault(part_id, set()).add(staff)
        self._staves_per_part = by_part

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

    # --- generic per-level anchoring (stage 2) --------------------------

    def _first_at_or_after_level(self, level: Tuple, quarters: float) -> Optional[float]:
        if level[0] == "score":
            self._ensure_score_index()
            return self._first_at_or_after_score(quarters)
        if level[0] == "part":
            self._ensure_part_index()
            return self._first_at_or_after_part(level[1], quarters)
        self._ensure_staff_index()
        return self._first_at_or_after((level[1], level[2]), quarters)

    def _last_at_or_before_level(self, level: Tuple, quarters: float) -> Optional[float]:
        if level[0] == "score":
            self._ensure_score_index()
            return self._last_at_or_before_score(quarters)
        if level[0] == "part":
            self._ensure_part_index()
            return self._last_at_or_before_part(level[1], quarters)
        self._ensure_staff_index()
        return self._last_at_or_before((level[1], level[2]), quarters)

    def part_level_rows(self, event_slice) -> Dict[str, List[MarkingRow]]:
        """Every part-level row at `event_slice`, grouped by part_id only -
        NoteRenderer inserts each group above the FIRST staff group it
        encounters for that part (whichever staff that happens to be), so
        each is heard once regardless of which hand/staff the reader is
        navigating."""
        if event_slice is None:
            return {}
        _score_rows, part_rows, _stave_rows = self._family_rows(event_slice)
        off = self.data.marking_categories_off
        return {
            key: [r for r in rows if r.category is None or r.category not in off]
            for key, rows in part_rows.items()
        }

    def staff_level_rows(self, event_slice) -> Dict[Tuple[str, int], List[MarkingRow]]:
        """Every stave-level row at `event_slice`, grouped by
        (part_id, staff) - NoteRenderer inserts each group immediately
        above that staff's note rows (strategy section 4.1), never repeated
        per voice."""
        if event_slice is None:
            return {}
        _score_rows, _part_rows, stave_rows = self._family_rows(event_slice)
        off = self.data.marking_categories_off
        return {
            key: [r for r in rows if r.category is None or r.category not in off]
            for key, rows in stave_rows.items()
        }

    # --- stage 2: one placement path for every classification-routed family

    def _family_rows(
        self, event_slice
    ) -> Tuple[List[MarkingRow], Dict[str, List[MarkingRow]], Dict[Tuple[str, int], List[MarkingRow]]]:
        """Runs every classification-routable family through level_of() and
        buckets the resulting rows into (score list, part dict, stave
        dict). Family order is fixed - hairpins, clef changes, octave
        shift, dashed/bracket lines, dynamics/tempo/other-direction words,
        generic stave text, rehearsal marks, measure style, then the two
        part-only families (pedal change, pedal span) and the fermata
        aggregate - so a row's position inside whichever bucket it lands in
        never moves. Unfiltered by category - callers each apply their own
        filter, matching the pre-stage-2 shape of part_level_rows/
        staff_level_rows."""
        self._ensure_index()
        data = self.data
        score_rows: List[MarkingRow] = []
        part_rows: Dict[str, List[MarkingRow]] = {}
        stave_rows: Dict[Tuple[str, int], List[MarkingRow]] = {}
        # Stage 9: for each key, the bucket index of a currently-standing
        # BORROWED row, by text - lets a same-text OWN row (from the target
        # part's own, separately notated marking) replace it in place rather
        # than sitting alongside it, whichever order the two are produced
        # in (the family loops below process every part's markings in one
        # pass with no guaranteed part order). Deliberately NOT a general
        # same-text dedupe across own rows - two independent own markings
        # that happen to render identical text (e.g. two overlapping
        # hairpins) have always both been kept, unlinked or not, and must
        # stay that way (fingerprint-verified: zero diff with no links).
        borrowed_index: Dict[Tuple, Dict[str, int]] = {}

        def _add(level: Tuple, row: MarkingRow, borrowed: bool = False) -> None:
            if level[0] == "score":
                score_rows.append(row)
                return
            key = level[1] if level[0] == "part" else (level[1], level[2])
            bucket = part_rows.setdefault(key, []) if level[0] == "part" else stave_rows.setdefault(key, [])
            index_map = borrowed_index.setdefault(key, {})
            if borrowed:
                if any(r.text == row.text for r in bucket):
                    return
                index_map[row.text] = len(bucket)
                bucket.append(row)
                return
            if row.text in index_map:
                bucket[index_map.pop(row.text)] = row
                return
            bucket.append(row)

        for span in data.hairpin_spans:
            name = span.kind.capitalize() if span.kind else "Hairpin"
            # Stage 6: a matched pair collapsed to one position (a same-event
            # start/stop) AND an unpartnered start or stop (parser-pinned to
            # start == end) are both a point - one bare-name row, no
            # "start"/"end" suffix. _add_span_rows_by_level implements
            # exactly this (and, stage 9, borrowing across linked parts).
            self._add_span_rows_by_level(_add, event_slice, span, name, "hairpins")

        # Clef changes.
        for mark in data.clef_change_marks:
            level = self.level_of(mark)
            anchor = self._first_at_or_after_level(level, mark.quarters_from_start)
            if anchor == event_slice.quarters_from_start:
                _add(level, MarkingRow(text=f"Clef change: {mark.label}", marking=mark, category="clef_changes"))

        # Octave shift / dashed / bracket lines.
        for span in data.direction_spans:
            if span.kind == "octave_shift":
                self._add_span_rows_by_level(
                    _add, event_slice, span, marking_labels.octave_shift_name(span), "octave_shift"
                )
        for span in data.direction_spans:
            if span.kind == "dashes":
                self._add_span_rows_by_level(
                    _add, event_slice, span, marking_labels.direction_line_name(span), "lines"
                )
        for span in data.direction_spans:
            if span.kind == "bracket":
                self._add_span_rows_by_level(
                    _add, event_slice, span, marking_labels.direction_line_name(span), "lines"
                )
        for span in data.direction_spans:
            if span.kind == "principal_voice":
                self._add_span_rows_by_level(
                    _add, event_slice, span, marking_labels.principal_voice_name(span), "principal_voice"
                )

        # Dynamics word / tempo word / other-direction points.
        for mark in data.direction_marks:
            if mark.kind == "dynamics_word":
                self._add_point_row_by_level(
                    _add, event_slice, mark, marking_labels.dynamics_word_label(mark.label),
                    "dynamics_words", mark.quarters_from_start,
                )
        for mark in data.direction_marks:
            if mark.kind == "tempo_word":
                self._add_point_row_by_level(
                    _add, event_slice, mark, marking_labels.tempo_word_label(mark.label),
                    "tempo_words", mark.quarters_from_start,
                )
        for mark in data.direction_marks:
            if mark.kind == "other_direction":
                self._add_point_row_by_level(
                    _add, event_slice, mark, marking_labels.other_direction_label(mark.label),
                    "other_directions", mark.quarters_from_start,
                )

        # Stage 5 (PerformanceMarkingsImplementationPlanV2.md): generic
        # stave text - a <words> direction that matched neither the
        # dynamics nor tempo allow-list. inventory.csv: "reading the text
        # as written" - unlike Region 5's "Stave text: X" wording, the
        # note-list row is the bare printed text, same as before stage 5
        # replaced the fabricated NoteData with this DirectionMark.
        for mark in data.direction_marks:
            if mark.kind == "words":
                self._add_point_row_by_level(
                    _add, event_slice, mark, mark.label,
                    "stave_text", mark.quarters_from_start,
                )

        # Rehearsal marks - always score level (classification pins
        # levels=("score",)). Category "stave_text" (inventory.csv).
        for mark in data.direction_marks:
            if mark.kind == "rehearsal":
                self._add_point_row_by_level(
                    _add, event_slice, mark, f"Rehearsal mark {mark.label}",
                    "stave_text", mark.quarters_from_start,
                )

        # MeasureStyleMark carries no quarters_from_start of its own - anchor
        # via the measure's own first quarters (the score-level index built
        # by _ensure_index), then that level's first event at or after that.
        # A multi-bar rest has no events of its own (rests are skipped), so
        # it lands on the NEXT event - correct: "8-bar rest" is read as you
        # arrive after it, not as you enter it.
        for mark in data.measure_style_marks:
            measure_quarters = self._first_quarters_of_measure.get(mark.measure)
            if measure_quarters is None:
                continue
            self._add_point_row_by_level(
                _add, event_slice, mark, marking_labels.measure_style_label(mark),
                "measure_styles", measure_quarters,
            )

        # Pedal change point, before the span's own row - the same relative
        # order these two families have always had. Classification pins
        # both permanently to "part" (levels=("part",) - never stave/score),
        # matching the whole-instrument-not-one-hand reasoning below.
        for mark in data.direction_marks:
            if mark.kind == "pedal_change":
                self._add_point_row_by_level(
                    _add, event_slice, mark, "Pedal change", "pedal", mark.quarters_from_start
                )

        for span in data.direction_spans:
            if span.kind == "pedal":
                self._add_span_rows_by_level(
                    _add, event_slice, span, marking_labels.pedal_name(), "pedal"
                )

        # Stage 10: key/time signature changes that disagreed across parts -
        # one part-level row per differing part (level_of()'s KeyChangeMark/
        # TimeChangeMark shortcut). The AGREEING case (is_score_level=True)
        # is NOT handled here: it stays on the pre-stage-10 path
        # (PerformanceRows.structural_change_labels via score_level_rows'
        # own loop) so no existing file's score-level row order shifts - see
        # this module's docstring. No linked-part borrowing: key/time is
        # score-wide state, not this family's business.
        for mark in data.key_change_marks:
            if mark.is_score_level or data.key_signature_override_fifths is not None:
                continue
            anchor = self._first_at_or_after_level(("part", mark.part_id), mark.quarters_from_start)
            if anchor == event_slice.quarters_from_start:
                key_name = key_signature_display_name(mark.fifths, None)
                _add(("part", mark.part_id), MarkingRow(
                    text=marking_labels.key_signature_change_label(key_name),
                    marking=mark, category="structural_changes",
                ))
        for mark in data.time_change_marks:
            if mark.is_score_level:
                continue
            anchor = self._first_at_or_after_level(("part", mark.part_id), mark.quarters_from_start)
            if anchor == event_slice.quarters_from_start:
                _add(("part", mark.part_id), MarkingRow(
                    text=marking_labels.time_signature_change_label(mark.ts_num, mark.ts_den),
                    marking=mark, category="structural_changes",
                ))

        # Fermata (PI tweaks follow-up, reported; PerformanceMarkingsImplem-
        # entationPlanV2.md section 3's aggregate rule): a note-attached
        # attribute, but a fermata pauses the WHOLE texture at that moment.
        # One score-level row when every part with a note at THIS event
        # carries a fermata, else one part-level row per carrying part -
        # deduped across every staff/voice of a part the same way it always
        # was. No cross-slice anchoring needed (the note is already in this
        # event_slice); category "fermatas" (stage 4 - PerformanceRows now
        # has a matching Region 5 row for it).
        self._add_fermata_rows(_add, event_slice)

        return score_rows, part_rows, stave_rows

    def _add_span_rows_by_level(self, _add, event_slice, span, name, category) -> None:
        """One span's rows at `event_slice`, placed via level_of(): a bare
        point row when the span's start and end resolve to the same
        position at its level, otherwise an end row and/or a start row -
        generalises the old staff-only `_add_span_rows` to any of the three
        levels. Stage 9: also placed, at the SAME kind of level, in every
        linked partner part (_levels_including_borrows), each checked
        against ITS OWN nearest event - a borrowed row can land on a
        different event_slice than the owning part's own row."""
        own_level = self.level_of(span)
        for level in self._levels_including_borrows(own_level):
            borrowed = level != own_level
            if span.start_quarters_from_start == span.end_quarters_from_start:
                anchor = self._first_at_or_after_level(level, span.start_quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    _add(level, MarkingRow(text=name, marking=span, category=category), borrowed)
                continue
            end_anchor = self._last_at_or_before_level(level, span.end_quarters_from_start)
            if end_anchor == event_slice.quarters_from_start:
                _add(level, MarkingRow(
                    text=marking_labels.end_label(name), marking=span, category=category
                ), borrowed)
            start_anchor = self._first_at_or_after_level(level, span.start_quarters_from_start)
            if start_anchor == event_slice.quarters_from_start:
                _add(level, MarkingRow(
                    text=marking_labels.start_label(name), marking=span, category=category
                ), borrowed)

    def _add_point_row_by_level(self, _add, event_slice, mark, name, category, quarters) -> None:
        """Stage 9: see _add_span_rows_by_level's docstring - the same
        own-level-plus-borrowed-levels loop, each checked independently."""
        own_level = self.level_of(mark)
        for level in self._levels_including_borrows(own_level):
            anchor = self._first_at_or_after_level(level, quarters)
            if anchor == event_slice.quarters_from_start:
                _add(level, MarkingRow(text=name, marking=mark, category=category), level != own_level)

    # --- stage 9: linked parts borrow part/stave-level rows -------------

    def _levels_including_borrows(self, level: Tuple) -> List[Tuple]:
        """`level` (a marking's own placement) plus one extra level per
        linked partner part, each at the SAME kind of level ("a borrowed
        row keeps its level in the borrowing part" -
        PerformanceMarkingsImplementationPlanV2.md stage 9). Score-level
        rows are never borrowed. Skips the partner lookup entirely when no
        parts are linked at all (Ref 9 - the common case)."""
        if level[0] not in ("part", "stave") or not self.data.part_link_groups:
            return [level]
        partners = self.data.link_partners(level[1])
        if not partners:
            return [level]
        levels = [level]
        if level[0] == "part":
            levels.extend(("part", partner) for partner in partners)
        else:
            for partner in partners:
                borrow_staff = self._borrow_staff(partner)
                if borrow_staff is not None:
                    levels.append(("stave", partner, borrow_staff))
        return levels

    def _borrow_staff(self, part_id: str) -> Optional[int]:
        """The stave a borrowed stave-level row lands on in `part_id` - its
        lowest staff number in _staff_quarters (arbitrary but fixed, since a
        borrowed row is not tied to any one of the source part's staves)."""
        self._ensure_staff_index()
        staves = self._staves_per_part.get(part_id)
        return min(staves) if staves else None

    def _add_fermata_rows(self, _add, event_slice) -> None:
        notes_by_part: Dict[str, List] = {}
        for note in event_slice.notes:
            notes_by_part.setdefault(note.part_id, []).append(note)
        if not notes_by_part:
            return
        fermata_note_by_part = {}
        for part_id, notes in notes_by_part.items():
            fermata_note = next((n for n in notes if n.fermata), None)
            if fermata_note is not None:
                fermata_note_by_part[part_id] = fermata_note
        if not fermata_note_by_part:
            return
        if len(fermata_note_by_part) == len(notes_by_part):
            # Every part present at this event carries a fermata - one
            # score-level row. The first carrying part's own fermata value
            # supplies the wording (shapes are not merged across parts).
            first_note = next(iter(fermata_note_by_part.values()))
            _add(("score",), MarkingRow(
                text=marking_labels.fermata_name(first_note.fermata), marking=first_note, category="fermatas"
            ))
            return
        for part_id, note in fermata_note_by_part.items():
            own_level = ("part", part_id)
            text = marking_labels.fermata_name(note.fermata)
            _add(own_level, MarkingRow(text=text, marking=note, category="fermatas"))
            # Stage 9: borrow to every linked partner, anchored (like every
            # other point row) at THAT partner's own nearest event at or
            # after this one - not necessarily this same event_slice.
            for level in self._levels_including_borrows(own_level):
                if level == own_level:
                    continue
                anchor = self._first_at_or_after_level(level, event_slice.quarters_from_start)
                if anchor == event_slice.quarters_from_start:
                    _add(level, MarkingRow(text=text, marking=note, category="fermatas"), True)

    def has_key_or_time_change_at(self, event_slice) -> bool:
        """Stage 10: True when a key or time signature change - majority
        (is_score_level=True, score level) or minority (False, part level) -
        lands exactly at `event_slice`. Tempo is covered separately by
        PerformanceRows.structural_change_labels(); together the two are
        MusicData.has_key_or_time_change_at, the change cue's
        (RegionPresenter.refresh_region_5) full trigger condition."""
        if event_slice is None:
            return False
        self._ensure_index()
        data = self.data
        for mark in data.key_change_marks:
            if mark.is_score_level and data.key_signature_override_fifths is not None:
                continue
            level = ("score",) if mark.is_score_level else ("part", mark.part_id)
            if self._first_at_or_after_level(level, mark.quarters_from_start) == event_slice.quarters_from_start:
                return True
        for mark in data.time_change_marks:
            level = ("score",) if mark.is_score_level else ("part", mark.part_id)
            if self._first_at_or_after_level(level, mark.quarters_from_start) == event_slice.quarters_from_start:
                return True
        return False
