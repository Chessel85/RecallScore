# models/performance_rows.py
"""S17 extraction: Region 5's row list and the Performance Report's line
list, lifted out of MusicData as their own collaborator.

The two were the largest methods in the codebase (28% of music_data.py).
Like every other S1 collaborator this owns no state - it holds only a
reference back to the MusicData it reads, so section/repeat/ending/hairpin
spans, direction marks, the tempo lookups and the bar-word vocabulary are
all read live. MusicData keeps one-line delegators for
get_performance_region_rows / get_performance_report_lines, so call sites
(RegionPresenter, the Performance Report dialog) and tests are unchanged.

Row/line order is stable and load-bearing: MainWindow._refresh_region_5
diffs the Region 5 label list to detect a real change.
"""
from typing import Dict, List, Optional, Tuple

from models import marking_labels, vocabulary
from models.key_signatures import key_signature_display_name
from models.performance_region_row import PerformanceRegionRow

# Section 3's level order for a Region 5 row: score first, then part, then
# stave. PerformanceMarkingsImplementationPlanV2.md stage 4.
_LEVEL_RANK: Dict[str, int] = {"score": 0, "part": 1, "stave": 2}


class PerformanceRows:
    def __init__(self, data):
        self.data = data

    def get_performance_region_rows(self, index: Optional[int] = None) -> List[PerformanceRegionRow]:
        """Ref 29: Region 5's rows - one line per span active at the given
        position (default: the cursor), stating its whole range
        (PerformanceMarkingsStrategy.md section 6), plus (S7) a one-shot row
        for a key-signature, time-signature, or immediate/point tempo change
        landing exactly here.

        Repeat/ending containment is a measure-number range check (barlines
        fall at measure boundaries); hairpins compare quarters_from_start,
        since a wedge can start or stop mid-measure. Rows are built in a
        fixed kind order (sections, repeats, endings, hairpins, ... the
        one-shot rows last) and then stable-sorted by level - score, part,
        stave (implementation plan stage 4) - so two rows of the same level
        keep that same kind order. MainWindow diffs the resulting label list
        to detect a real change. Wording goes through vocabulary.bar_word and
        models.marking_labels, never a hardcoded "bar"/"measure" or a second
        copy of the range-rendering rules."""
        data = self.data
        resolved_index = data.active_event_index if index is None else index
        slice_ = (
            data.timeline_slices[resolved_index]
            if 0 <= resolved_index < len(data.timeline_slices)
            else None
        )
        if slice_ is None:
            return []

        bar_word = vocabulary.bar_word(data.uk_terms)
        # (level, row) pairs, in build order - _LEVEL_RANK sorts them into
        # score/part/stave order (a stable sort, so build order survives as
        # the tie-break within a level) just before returning.
        entries: List[Tuple[Tuple, PerformanceRegionRow]] = []
        level_of = data.marking_rows.level_of

        def _in_measure(span) -> bool:
            return span.start_measure <= slice_.measure <= span.end_measure

        def _in_quarters(span) -> bool:
            return (span.start_quarters_from_start <= slice_.quarters_from_start
                    <= span.end_quarters_from_start)

        def _span_row(spans, contained, label, *, jump_quarters=False, category=None,
                      level=("score",), level_fn=None):
            """One row per span `contained` at the cursor (section 6): the
            whole range in one line, with both ends as jump targets.
            jump_target_measure/end_target_measure are the span's own
            start/end measure; the *_quarters fields are added only when the
            span can begin or end mid-bar (a hairpin-style line, not a
            repeat/ending barline). `category` (stage 9) is the note-list
            toggle this row's Ctrl+N reaches - see models/marking_categories.py.
            `level_fn(span)` (stage 4), when given, overrides the fixed
            `level` default - the classification-routable families each
            resolve their own score/part/stave placement per instance."""
            for span in spans:
                if not contained(span):
                    continue
                entries.append((level_fn(span) if level_fn else level, PerformanceRegionRow(
                    label=label(span),
                    category=category,
                    jump_target_measure=span.start_measure,
                    jump_target_quarters=(
                        span.start_quarters_from_start if jump_quarters else None
                    ),
                    end_target_measure=span.end_measure,
                    end_target_quarters=(
                        span.end_quarters_from_start if jump_quarters else None
                    ),
                )))

        def _point(marks, label, *, kind=None, jump="slice", category=None,
                   level=("score",), level_fn=None):
            """One row per mark sitting at the resolved slice's own measure.
            `jump` picks the Ctrl+Home/Ctrl+End target: "slice" -> the
            cursor's own position (a harmless no-op, where jumping to what the
            mark points at is out of scope), "measure" -> the mark's bar with
            no beat, "mark" -> the mark's own bar and offset. `category`
            (stage 9) is the note-list toggle this row's Ctrl+N reaches.
            `level_fn(mark)` (stage 4) overrides the fixed `level` default,
            same as in `_span_row`."""
            for mark in marks:
                if kind is not None and mark.kind != kind:
                    continue
                if mark.measure != slice_.measure:
                    continue
                if jump == "measure":
                    jump_m, jump_q = mark.measure, None
                elif jump == "mark":
                    jump_m, jump_q = mark.measure, mark.quarters_from_start
                else:
                    jump_m, jump_q = slice_.measure, slice_.quarters_from_start
                entries.append((level_fn(mark) if level_fn else level, PerformanceRegionRow(
                    label=label(mark),
                    category=category,
                    jump_target_measure=jump_m,
                    jump_target_quarters=jump_q,
                )))

        # P2 / section 6: the song section(s) containing the cursor come
        # first, one row stating the full range (Ctrl+Home -> first bar,
        # Ctrl+End -> last bar). The label only changes when the cursor
        # crosses a section boundary, so _refresh_region_5's diff means one
        # change cue per section.
        _span_row(
            data.section_spans, _in_measure,
            lambda s: f"Section {s.label}, "
                      f"{marking_labels.range_label(bar_word, s.start_measure, 1.0, s.end_measure, 1.0)}",
            category="sections",
        )

        # Repeat / ending spans: a measure-number range check (barlines fall
        # at measure boundaries), so these rows never name a beat and never
        # set jump_target_quarters/end_target_quarters.
        _span_row(
            data.repeat_spans, _in_measure,
            lambda s: (
                f"Repeat {marking_labels.range_label(bar_word, s.start_measure, 1.0, s.end_measure, 1.0)}"
                f"{marking_labels.repeat_times_suffix(s.times)}"
            ),
            category="repeats_endings",
        )
        _span_row(
            data.ending_spans, _in_measure,
            lambda s: f"Ending {s.number} "
                      f"{marking_labels.range_label(bar_word, s.start_measure, 1.0, s.end_measure, 1.0)}",
            category="repeats_endings",
        )

        # Hairpins carry a part_id (collected per part, not first-part-only)
        # and completeness flags. A complete span gets one row stating the
        # full range (section 6); an unmatched wedge gets a single row with
        # the gap stated (section 6's "honest wording"). D5: part-prefixed
        # only when >1 part has a hairpin. Stage 4: placed at score/part/
        # stave via level_of(), same as its note-list row.
        _hairpin_part_ids = [s.part_id for s in data.hairpin_spans]
        for span in data.hairpin_spans:
            if not (span.start_quarters_from_start <= slice_.quarters_from_start
                    <= span.end_quarters_from_start):
                continue
            prefix = data._marking_part_prefix(span.part_id, _hairpin_part_ids)
            kind_label = span.kind.capitalize() if span.kind else "Hairpin"
            start_bb = data._bar_beat_label(bar_word, span.start_measure, span.start_beat_position)
            end_bb = data._bar_beat_label(bar_word, span.end_measure, span.end_beat_position)
            if not span.start_known:
                label = f"{prefix}{kind_label} ending {end_bb}, no start marked in the file"
                jump_m, jump_q = span.end_measure, span.end_quarters_from_start
                end_m, end_q = jump_m, jump_q
            elif not span.end_known:
                label = f"{prefix}{kind_label} from {start_bb}, no end marked in the file"
                jump_m, jump_q = span.start_measure, span.start_quarters_from_start
                end_m, end_q = jump_m, jump_q
            else:
                rng = data._range_label(
                    bar_word, span.start_measure, span.start_beat_position,
                    span.end_measure, span.end_beat_position,
                )
                label = f"{prefix}{kind_label} {rng}"
                jump_m, jump_q = span.start_measure, span.start_quarters_from_start
                end_m, end_q = span.end_measure, span.end_quarters_from_start
            entries.append((level_of(span), PerformanceRegionRow(
                label=label,
                category="hairpins",
                jump_target_measure=jump_m,
                jump_target_quarters=jump_q,
                end_target_measure=end_m,
                end_target_quarters=end_q,
            )))

        # P3: dashed / bracketed lines, octave shift and the D6 catch-all get
        # Region 5 rows (D12 order: after hairpins, before the one-shot
        # rows). D5: a kind's label is part-prefixed only when >1 part
        # contributes a span/mark of that kind - _dir_kind_pids is that
        # lookup, built once here rather than re-concatenating
        # direction_spans + direction_marks on every _dir_prefix call.
        _dir_kind_pids: Dict[str, List[str]] = {}
        for _x in (*data.direction_spans, *data.direction_marks):
            _dir_kind_pids.setdefault(_x.kind, []).append(_x.part_id)

        def _dir_prefix(kind: str, part_id: str) -> str:
            return data._marking_part_prefix(part_id, _dir_kind_pids.get(kind, []))

        _DIR_LINE_LABELS = {"dashes": "Dashed line", "bracket": "Bracket line"}

        _span_row(
            [s for s in data.direction_spans if s.kind in _DIR_LINE_LABELS],
            _in_quarters,
            lambda s: (
                f"{_dir_prefix(s.kind, s.part_id)}{marking_labels.direction_line_name(s)} "
                f"{data._range_label(bar_word, s.start_measure, s.start_beat_position, s.end_measure, s.end_beat_position)}"
            ),
            jump_quarters=True,
            category="lines",
            level_fn=level_of,
        )

        # Stage 4: octave shift gets its own Region 5 row (previously D15
        # kept it, and pedal below, out of Region 5 entirely).
        _span_row(
            [s for s in data.direction_spans if s.kind == "octave_shift"],
            _in_quarters,
            lambda s: (
                f"{_dir_prefix('octave_shift', s.part_id)}{marking_labels.octave_shift_name(s)} "
                f"{data._range_label(bar_word, s.start_measure, s.start_beat_position, s.end_measure, s.end_beat_position)}"
            ),
            jump_quarters=True,
            category="octave_shift",
            level_fn=level_of,
        )

        _point(
            data.direction_marks,
            lambda m: (
                f"{_dir_prefix('other_direction', m.part_id)}"
                f"{marking_labels.other_direction_label(m.label)}"
            ),
            kind="other_direction",
            category="other_directions",
            level_fn=level_of,
        )

        # Rehearsal marks - a landmark, one-shot point row (no start/end
        # pair, no part-name prefix). jump by measure only, so Ctrl+Home/
        # Ctrl+End resolve via first/last_visible_event_index_of_measure.
        # Category "stave_text" (inventory.csv) - stage 5 lets Ctrl+N toggle
        # it alongside generic stave text.
        _point(
            data.direction_marks,
            lambda m: f"Rehearsal mark {m.label}: {bar_word} {m.measure}",
            kind="rehearsal", jump="measure", category="stave_text", level_fn=level_of,
        )

        # Plain-text dynamics / tempo instructions ("cresc.", "rall.") -
        # one-shot point rows at their own position (never a fabricated
        # range), after the direction-line rows and before the P4 rows.
        _dynword_part_ids = [
            m.part_id for m in data.direction_marks if m.kind == "dynamics_word"
        ]

        def _dynword_label(m) -> str:
            prefix = data._marking_part_prefix(m.part_id, _dynword_part_ids)
            return f"{prefix}{marking_labels.dynamics_word_label(m.label)}"

        _point(
            data.direction_marks, _dynword_label, kind="dynamics_word",
            category="dynamics_words", level_fn=level_of,
        )

        _tempword_part_ids = [
            m.part_id for m in data.direction_marks if m.kind == "tempo_word"
        ]
        _point(
            data.direction_marks,
            lambda m: (
                f"{data._marking_part_prefix(m.part_id, _tempword_part_ids)}"
                f"{marking_labels.tempo_word_label(m.label)}"
            ),
            kind="tempo_word",
            category="tempo_words",
            level_fn=level_of,
        )

        # Stage 4: sustain pedal - a whole-instrument control, always
        # PART-level (models/marking_classification.py pins levels=("part",)
        # for <pedal>), never prefixed by part name (matching the Performance
        # Report's own unprefixed "Pedal"/"Pedal change" wording). The change
        # point comes before the span's own row, the same relative order the
        # note list has always used (models/marking_rows.py's _family_rows).
        _point(
            data.direction_marks, lambda m: "Pedal change",
            kind="pedal_change", category="pedal", level_fn=level_of,
        )
        _span_row(
            [s for s in data.direction_spans if s.kind == "pedal"],
            _in_quarters,
            lambda s: (
                f"{marking_labels.pedal_name()} "
                f"{data._range_label(bar_word, s.start_measure, s.start_beat_position, s.end_measure, s.end_beat_position)}"
            ),
            jump_quarters=True,
            category="pedal",
            level_fn=level_of,
        )

        # Stage 5: stave text - a generic <words> direction that failed the
        # dynamics/tempo allow-list, now a real "words" DirectionMark (no
        # more fabricated NoteData/voice). D5: part-prefixed only when >1
        # part carries stave text anywhere in the score.
        _wordtext_part_ids = [
            m.part_id for m in data.direction_marks if m.kind == "words"
        ]

        def _words_label(m) -> str:
            prefix = data._marking_part_prefix(m.part_id, _wordtext_part_ids)
            return f"{prefix}{marking_labels.stave_text_label(m.label)}"

        _point(
            data.direction_marks, _words_label, kind="words",
            category="stave_text", level_fn=level_of,
        )

        # P4: barline / clef-change / measure-style one-shot rows, gated on
        # the mark's own measure (a point mark, like segno below).
        def _barline_label(m) -> str:
            base = (
                "Double barline" if m.kind == "double_barline"
                else f"{m.style.capitalize()} barline"
            )
            return f"{base}: {bar_word} {m.measure}"

        _point(data.barline_marks, _barline_label, jump="measure", category="barlines")

        _clef_pids = {m.part_id for m in data.clef_change_marks}

        def _clef_label(m) -> str:
            prefix = ""
            if len(_clef_pids) > 1:
                name = next((p.name for p in data.parts_info if p.part_id == m.part_id), None)
                prefix = f"{name}: " if name else ""
            return f"{prefix}Clef change: {m.label}, staff {m.staff}"

        _point(data.clef_change_marks, _clef_label, jump="mark", category="clef_changes", level_fn=level_of)

        _point(
            data.measure_style_marks,
            lambda m: f"{marking_labels.measure_style_label(m)}: {bar_word} {m.measure}",
            jump="measure",
            category="measure_styles",
            level_fn=level_of,
        )

        # Stage 4: fermata rows - a note-attached attribute, but one that
        # pauses the whole texture at that moment (same aggregate rule as
        # the note list's own fermata row, models/marking_rows.py's
        # _add_fermata_rows: one score-level row when every part with a note
        # at this event carries a fermata, else one part-level row per
        # carrying part).
        for level, label in self._fermata_region_rows(slice_):
            entries.append((level, PerformanceRegionRow(
                label=label,
                category="fermatas",
                jump_target_measure=slice_.measure,
                jump_target_quarters=slice_.quarters_from_start,
            )))

        # Segno / Coda / To coda / Fine / D.C. / D.S.: one-shot point rows,
        # each a single point (not a start/end pair). jump_target_* is always
        # this row's OWN position (a harmless Ctrl+Home/Ctrl+End no-op) -
        # jumping to where a mark actually points is out of scope;
        # NavigationController.jump_to_span has no concept of that.
        _point(
            data.segno_marks, lambda m: f"Segno{marking_labels.label_suffix(m.label)}",
            category="jump_instructions",
        )
        _point(
            data.coda_marks, lambda m: f"Coda{marking_labels.label_suffix(m.label)}",
            category="jump_instructions",
        )
        _point(
            data.to_coda_marks, lambda m: f"To coda{marking_labels.label_suffix(m.label)}",
            category="jump_instructions",
        )
        _point(data.fine_marks, lambda m: "Fine", category="jump_instructions")
        _point(
            data.navigation_jumps,
            lambda m: "Da capo" if m.kind == "dacapo" else "Dal segno",
            category="jump_instructions",
        )

        # S7/stage 6: a one-shot alert - unlike the three span kinds above,
        # this has no start/end pair, it just fires once at the transition
        # itself. structural_change_labels is the single source for "did a
        # key/time/tempo change land exactly here" - shared with the note
        # list's own structural rows (models/marking_rows.py) and the
        # change cue (RegionPresenter.refresh_region_5), so the three can't
        # disagree about what counts as a change (invariant 8).
        for _kind, label in self.structural_change_labels(resolved_index):
            entries.append((("score",), PerformanceRegionRow(
                label=label,
                category="structural_changes",
                jump_target_measure=slice_.measure,
                jump_target_quarters=slice_.quarters_from_start,
            )))

        # Stage 4: score, then part, then stave - a stable sort, so within a
        # level the rows stay in the build order above (section 3's "level
        # of one marking" rule, applied last so it can act as one pass over
        # rows already carrying whatever the family loops above decided).
        entries.sort(key=lambda entry: _LEVEL_RANK[entry[0][0]])
        rows: List[PerformanceRegionRow] = [row for _level, row in entries]

        # Stage 9 (strategy section 8): "* " on a row whose category is
        # currently surfaced in the note list - i.e. NOT in
        # marking_categories_off. A row with no category never gets the
        # prefix - there is nothing Ctrl+N here could turn off.
        for row in rows:
            if row.category is not None and row.category not in data.marking_categories_off:
                row.label = f"* {row.label}"

        return rows

    def _fermata_region_rows(self, event_slice) -> List[Tuple[Tuple, str]]:
        """(level, label) pairs for `event_slice`'s fermata rows - the exact
        aggregate rule models/marking_rows.py's `_add_fermata_rows` uses for
        the note list, reused here (Region 5) so the two can't disagree about
        what counts as "every part had a fermata here" (invariant 8)."""
        notes_by_part: Dict[str, List] = {}
        for note in event_slice.notes:
            notes_by_part.setdefault(note.part_id, []).append(note)
        if not notes_by_part:
            return []
        fermata_note_by_part = {}
        for part_id, notes in notes_by_part.items():
            fermata_note = next((n for n in notes if n.fermata), None)
            if fermata_note is not None:
                fermata_note_by_part[part_id] = fermata_note
        if not fermata_note_by_part:
            return []
        if len(fermata_note_by_part) == len(notes_by_part):
            first_note = next(iter(fermata_note_by_part.values()))
            return [(("score",), marking_labels.fermata_name(first_note.fermata))]
        return [
            (("part", part_id), marking_labels.fermata_name(note.fermata))
            for part_id, note in fermata_note_by_part.items()
        ]

    def structural_change_labels(self, index: Optional[int] = None) -> List[Tuple[str, str]]:
        """(kind, label) pairs - kind in "key"/"time"/"tempo" - for a key
        signature, time signature, or immediate tempo change landing
        exactly at `index` (default: the cursor). "Previous" is the
        immediately preceding entry in whichever list the resolved slice
        came from (data.timeline_slices), so this works whether or not the
        metronome's synthetic beat markers are currently spliced in - a
        marker slice carries the same real key/time_sig/tempo as its own
        position, same as a real one.

        Never returns anything for index 0 (or an out-of-range index) - the
        score's OPENING key/time signature/tempo are already shown in
        Region 1 and the status bar; alerting on them here on every load
        would just be noise. A score whose key never changes - the common
        case - therefore never gets a key-signature entry at all; that
        silence is this same "no alert on the opening value, no alert on
        no-op repetition" rule, not a separate suppression."""
        data = self.data
        resolved_index = data.active_event_index if index is None else index
        if not (0 < resolved_index < len(data.timeline_slices)):
            return []
        slice_ = data.timeline_slices[resolved_index]
        previous = data.timeline_slices[resolved_index - 1]
        out: List[Tuple[str, str]] = []

        # A key-signature override (S6) forces one constant display key
        # score-wide, so the file's own per-slice key_fifths can no longer
        # disagree with itself in effect - suppress the alert while one is
        # active rather than comparing raw, overridden-away values.
        if data.key_signature_override_fifths is None and previous.key_fifths != slice_.key_fifths:
            key_name = key_signature_display_name(slice_.key_fifths, None)
            out.append(("key", marking_labels.key_signature_change_label(key_name)))
        if previous.time_sig != slice_.time_sig:
            ts_num, ts_den = slice_.time_sig
            out.append(("time", marking_labels.time_signature_change_label(ts_num, ts_den)))
        if data._tempo_change_at(resolved_index - 1) != data._tempo_change_at(resolved_index):
            number = data._format_tempo_number(data.score_tempo_display_bpm(resolved_index))
            unit = data.tempo_beat_unit_name_at(resolved_index)
            out.append(("tempo", marking_labels.tempo_change_label(number, unit)))
        return out

    def get_performance_report_lines(self) -> List[str]:
        """Ref 29: the Performance Report's content - a whole-score summary,
        deliberately independent of the Region 2 filter (unlike every other
        accessor here), since it describes the piece, not the current view."""
        data = self.data
        # Reuses get_region_1_data() wholesale rather than cherry-picking
        # keys like "Title"/"Composer": credit keys come from each file's own
        # <credit-type> text, so no fixed name is guaranteed to exist.
        lines: List[str] = [f"{k}: {v}" for k, v in data.get_region_1_data().items()]

        bar_word = vocabulary.bar_word(data.uk_terms).capitalize()
        anacrusis_slices = [s for s in data.timeline_slices if s.measure == 0]
        if anacrusis_slices:
            beat_position = anacrusis_slices[0].beat_position
            beat_str = (
                str(int(beat_position))
                if float(beat_position).is_integer()
                else str(beat_position)
            )
            lines.append(f"Anacrusis starts on beat {beat_str}")
        lines.append(f"Number of {bar_word.lower()}s: {data.total_measures}")

        def _tally(header, items, line_fn):
            """A "<header>: <count>" line then one `line_fn(item)` line per
            item. The whole block (header included) is omitted when there is
            nothing to list (stage 12 item 3b: no more "X: 0" headers)."""
            if not items:
                return
            lines.append(f"{header}: {len(items)}")
            lines.extend(line_fn(it) for it in items)

        _tally(
            "Sections", data.section_spans,
            lambda s: f"{s.label}: {bar_word} {s.start_measure} to {bar_word} {s.end_measure}",
        )

        note_counts: Dict[str, int] = {}
        for s in data._real_timeline_slices:
            for n in s.notes:
                if n.midi_pitch is not None:
                    note_counts[n.part_name] = note_counts.get(n.part_name, 0) + 1
        _tally(
            "Parts", data.parts_info,
            lambda p: f"{p.name}: {note_counts.get(p.name, 0)} notes",
        )

        _tally(
            "Repeated sections", data.repeat_spans,
            lambda s: f"Repeat: {bar_word} {s.start_measure} to {bar_word} {s.end_measure}",
        )
        _tally(
            "Endings", data.ending_spans,
            lambda s: f"Ending {s.number}: {bar_word} {s.start_measure} to {bar_word} {s.end_measure}",
        )

        # P3: <direction> spans and points. Pedal/octave-shift appear here
        # (and in Find) but never in Region 5 (D15). Beat-precise (not just
        # measure-precise) throughout - reported: a span that starts/ends
        # mid-bar read as "Measure N to Measure N" (looked contained within
        # one bar) even when it actually crossed the barline.
        def _span_range(span) -> str:
            start = data._bar_beat_label(bar_word, span.start_measure, span.start_beat_position)
            end = data._bar_beat_label(bar_word, span.end_measure, span.end_beat_position)
            return f"{start} to {end}"

        def _sp(label) -> str:
            return f" {label}" if label else ""

        def _paren(label) -> str:
            return f" ({label})" if label else ""

        # Dynamics (volume): one chronological list merging every way the
        # file expresses a volume change - real <wedge> hairpins (collected
        # per part now, so part-prefixed like everything else), plain-text
        # swell instructions ("cresc."/"dim.", surfaced as point
        # DirectionMarks), and point <dynamics> marks (mf, f, p, ...). A
        # dashed/bracket line drawn under a "cresc." is a SEPARATE thing in
        # the file and is reported under "Dashed lines:" / "Bracket lines:"
        # as written - not merged in here. An unmatched wedge carries the
        # same "no start/end marked in the file" wording as Region 5.
        def _hairpin_report_text(span) -> str:
            kind_label = span.kind.capitalize() if span.kind else "Hairpin"
            start = data._bar_beat_label(bar_word, span.start_measure, span.start_beat_position)
            end = data._bar_beat_label(bar_word, span.end_measure, span.end_beat_position)
            if not span.start_known:
                return f"{kind_label}: ends at {end}, no start marked in the file"
            if not span.end_known:
                return f"{kind_label}: starts at {start}, no end marked in the file"
            return f"{kind_label}: {start} to {end}"

        _dashes = [s for s in data.direction_spans if s.kind == "dashes"]
        _brackets = [s for s in data.direction_spans if s.kind == "bracket"]

        # (sort_key, line_text, part_id or None)
        _dynamics_events: List[Tuple[float, str, Optional[str]]] = []
        for span in data.hairpin_spans:
            _dynamics_events.append((
                span.start_quarters_from_start,
                _hairpin_report_text(span),
                span.part_id or None,
            ))
        for mark in data.direction_marks:
            if mark.kind != "dynamics_word":
                continue
            sense = vocabulary.dynamics_instruction_kind(mark.label) or "dynamics"
            position = data._bar_beat_label(bar_word, mark.measure, mark.beat_position)
            _dynamics_events.append((
                mark.quarters_from_start,
                f'{sense.capitalize()} (marked "{mark.label}"): {position}',
                mark.part_id or None,
            ))
        _seen_dynamic_marks = set()
        for s in data._real_timeline_slices:
            for n in s.notes:
                if not n.dynamic:
                    continue
                key = (n.part_id, n.staff, s.measure, s.beat_position, n.dynamic)
                if key in _seen_dynamic_marks:
                    continue
                _seen_dynamic_marks.add(key)
                position = data._bar_beat_label(bar_word, s.measure, s.beat_position)
                _dynamics_events.append((
                    s.quarters_from_start, f"Dynamic {n.dynamic}: {position}", n.part_id
                ))

        _dynamics_part_ids = {pid for _, _, pid in _dynamics_events if pid}
        _dynamics_lines: List[str] = []
        for _, event_line, part_id in sorted(_dynamics_events, key=lambda e: e[0]):
            prefix = ""
            if part_id and len(_dynamics_part_ids) > 1:
                name = next((p.name for p in data.parts_info if p.part_id == part_id), None)
                prefix = f"{name}: " if name else ""
            _dynamics_lines.append(f"{prefix}{event_line}")
        _tally("Dynamics", _dynamics_lines, lambda line: line)

        _pedal_spans = [s for s in data.direction_spans if s.kind == "pedal"]
        _pedal_changes = [m for m in data.direction_marks if m.kind == "pedal_change"]
        _pedal_lines = [f"Pedal: {_span_range(span)}" for span in _pedal_spans]
        _pedal_lines.extend(f"Pedal change: {bar_word} {mark.measure}" for mark in _pedal_changes)
        _tally("Pedal marks", _pedal_lines, lambda line: line)

        _octave_spans = [s for s in data.direction_spans if s.kind == "octave_shift"]
        _tally(
            "Octave shifts", _octave_spans,
            lambda s: f"Octave shift{_sp(s.label)}: {_span_range(s)}",
        )

        # Rehearsal marks and plain-text tempo instructions ("rall.",
        # "a tempo") - both omitted entirely when zero (accel./rit. spans are
        # out of scope, nothing parses them yet).
        _rehearsals = [m for m in data.direction_marks if m.kind == "rehearsal"]
        _tally(
            "Rehearsal marks", _rehearsals,
            lambda m: f"Rehearsal mark{_sp(m.label)}: {bar_word} {m.measure}",
        )
        _tempo_words = [m for m in data.direction_marks if m.kind == "tempo_word"]
        _tally(
            "Tempo instructions", _tempo_words,
            lambda m: (
                f'Tempo instruction (marked "{m.label}"): '
                f"{data._bar_beat_label(bar_word, m.measure, m.beat_position)}"
            ),
        )

        # Every dashed / bracketed line, as written - a "cresc." word and the
        # dashed line drawn under it are two things in the file (the word is
        # a point mark in Dynamics above; the line is here).
        _tally("Dashed lines", _dashes,
               lambda s: f"Dashed line{_paren(s.label)}: {_span_range(s)}")
        _tally("Bracket lines", _brackets,
               lambda s: f"Bracket line{_paren(s.label)}: {_span_range(s)}")

        _other_dirs = [m for m in data.direction_marks if m.kind == "other_direction"]
        _tally("Other directions", _other_dirs,
               lambda m: f"Direction {m.label}: {bar_word} {m.measure}")

        # P4: bar-style points (M6), mid-part clef changes (M7),
        # measure-style points (M8).
        _tally("Barline changes", data.barline_marks,
               lambda m: f"{m.style.capitalize()} barline: {bar_word} {m.measure}")
        _tally("Clef changes", data.clef_change_marks,
               lambda m: f"Clef change: {m.label}, staff {m.staff}, {bar_word} {m.measure}")
        _tally("Measure style markers", data.measure_style_marks,
               lambda m: f"{marking_labels.measure_style_label(m)}: {bar_word} {m.measure}")

        _tally("Segno marks", data.segno_marks,
               lambda m: f"Segno{marking_labels.label_suffix(m.label)}: {bar_word} {m.measure}")
        _tally("Coda marks", data.coda_marks,
               lambda m: f"Coda{marking_labels.label_suffix(m.label)}: {bar_word} {m.measure}")
        _tally("To coda marks", data.to_coda_marks,
               lambda m: f"To coda{marking_labels.label_suffix(m.label)}: {bar_word} {m.measure}")
        _tally("Fine marks", data.fine_marks,
               lambda m: f"Fine: {bar_word} {m.measure}")
        _tally("Navigation jumps", data.navigation_jumps,
               lambda nj: f"{'Da capo' if nj.kind == 'dacapo' else 'Dal segno'}: {bar_word} {nj.measure}")

        return lines
