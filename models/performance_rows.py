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

from models import vocabulary
from models.key_signatures import key_signature_display_name
from models.performance_region_row import PerformanceRegionRow


class PerformanceRows:
    def __init__(self, data):
        self.data = data

    def get_performance_region_rows(self, index: Optional[int] = None) -> List[PerformanceRegionRow]:
        """Ref 29: Region 5's rows - a start and an end line per span active
        at the given position (default: the cursor), plus (S7) a one-shot
        row for a key-signature, time-signature, or immediate/point tempo
        change landing exactly here.

        Repeat/ending containment is a measure-number range check (barlines
        fall at measure boundaries); hairpins compare quarters_from_start,
        since a wedge can start or stop mid-measure. The order (repeats,
        endings, hairpins, then the one-shot rows, each in span-list order)
        must stay stable - MainWindow diffs the resulting label list to
        detect a real change. Wording goes through vocabulary.bar_word,
        never a hardcoded "bar"/"measure"."""
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
        rows: List[PerformanceRegionRow] = []

        def _in_measure(span) -> bool:
            return span.start_measure <= slice_.measure <= span.end_measure

        def _in_quarters(span) -> bool:
            return (span.start_quarters_from_start <= slice_.quarters_from_start
                    <= span.end_quarters_from_start)

        def _label_suffix(label: str) -> str:
            return f" {label}" if label and label != "1" else ""

        def _pair(spans, contained, start_label, end_label, *, jump_quarters=False):
            """A start row then an end row for every span `contained` at the
            cursor. jump_target_measure is the span's own start/end measure;
            jump_target_quarters is added only when the span can begin or end
            mid-bar (a hairpin-style line, not a repeat/ending barline)."""
            for span in spans:
                if not contained(span):
                    continue
                rows.append(PerformanceRegionRow(
                    label=start_label(span),
                    jump_target_measure=span.start_measure,
                    jump_target_quarters=(
                        span.start_quarters_from_start if jump_quarters else None
                    ),
                ))
                rows.append(PerformanceRegionRow(
                    label=end_label(span),
                    jump_target_measure=span.end_measure,
                    jump_target_quarters=(
                        span.end_quarters_from_start if jump_quarters else None
                    ),
                ))

        def _point(marks, label, *, kind=None, jump="slice"):
            """One row per mark sitting at the resolved slice's own measure.
            `jump` picks the Ctrl+Home/Ctrl+End target: "slice" -> the
            cursor's own position (a harmless no-op, where jumping to what the
            mark points at is out of scope), "measure" -> the mark's bar with
            no beat, "mark" -> the mark's own bar and offset."""
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
                rows.append(PerformanceRegionRow(
                    label=label(mark),
                    jump_target_measure=jump_m,
                    jump_target_quarters=jump_q,
                ))

        # P2: the song section(s) containing the cursor come first - a start
        # row (Ctrl+Home -> first bar) and an end row (Ctrl+End -> last bar),
        # each stating the full range so one row read alone conveys it. The
        # label only changes when the cursor crosses a section boundary, so
        # _refresh_region_5's diff means one change cue per section.
        def _section_range(s) -> str:
            return f"{bar_word} {s.start_measure} to {bar_word} {s.end_measure}"

        _pair(
            data.section_spans, _in_measure,
            lambda s: f"Section start: {s.label}: {_section_range(s)}",
            lambda s: f"Section end: {s.label}: {_section_range(s)}",
        )

        # Repeat / ending spans: a measure-number range check (barlines fall
        # at measure boundaries), so these rows never name a beat and never
        # set jump_target_quarters.
        _pair(
            data.repeat_spans, _in_measure,
            lambda s: f"Repeat start: {bar_word} {s.start_measure}",
            lambda s: f"Repeat end: {bar_word} {s.end_measure}",
        )
        _pair(
            data.ending_spans, _in_measure,
            lambda s: f"Ending {s.number} start: {bar_word} {s.start_measure}",
            lambda s: f"Ending {s.number} end: {bar_word} {s.end_measure}",
        )

        # Hairpins carry a part_id (collected per part, not first-part-only)
        # and completeness flags. A complete span gets a start row and an end
        # row, each stating the FULL range so one row read alone conveys it;
        # an unmatched wedge gets a single row with the gap stated. The
        # 3-way branch is one label decision producing a small list of
        # (label, jump_measure, jump_quarters) triples, then one append loop.
        # D5: part-prefixed only when >1 part has a hairpin.
        _hairpin_part_ids = [s.part_id for s in data.hairpin_spans]
        for span in data.hairpin_spans:
            if not (span.start_quarters_from_start <= slice_.quarters_from_start
                    <= span.end_quarters_from_start):
                continue
            prefix = data._marking_part_prefix(span.part_id, _hairpin_part_ids)
            kind_label = span.kind.capitalize() if span.kind else "Hairpin"
            start_bb = data._bar_beat_label(bar_word, span.start_measure, span.start_beat_position)
            end_bb = data._bar_beat_label(bar_word, span.end_measure, span.end_beat_position)
            base_start = f"{prefix}{kind_label} start: {start_bb}"
            base_end = f"{prefix}{kind_label} end: {end_bb}"
            if not span.start_known:
                emit = [(f"{base_end}, no start marked in the file",
                         span.end_measure, span.end_quarters_from_start)]
            elif not span.end_known:
                emit = [(f"{base_start}, no end marked in the file",
                         span.start_measure, span.start_quarters_from_start)]
            else:
                emit = [
                    (f"{base_start}, to {end_bb}",
                     span.start_measure, span.start_quarters_from_start),
                    (f"{base_end}, from {start_bb}",
                     span.end_measure, span.end_quarters_from_start),
                ]
            for label, jump_m, jump_q in emit:
                rows.append(PerformanceRegionRow(
                    label=label,
                    jump_target_measure=jump_m,
                    jump_target_quarters=jump_q,
                ))

        # P3: dashed / bracketed lines and the D6 catch-all get Region 5
        # rows (D12 order: after hairpins, before the one-shot rows). Pedal
        # and octave shift deliberately do NOT (D15) - a pedal-heavy piece
        # would rebuild Region 5 and fire the change cue on nearly every bar.
        # D5: a kind's label is part-prefixed only when >1 part contributes a
        # span/mark of that kind - _dir_kind_pids is that lookup, built once
        # here rather than re-concatenating direction_spans + direction_marks
        # on every _dir_prefix call.
        _dir_kind_pids: Dict[str, List[str]] = {}
        for _x in (*data.direction_spans, *data.direction_marks):
            _dir_kind_pids.setdefault(_x.kind, []).append(_x.part_id)

        def _dir_prefix(kind: str, part_id: str) -> str:
            return data._marking_part_prefix(part_id, _dir_kind_pids.get(kind, []))

        _DIR_LINE_LABELS = {"dashes": "Dashed line", "bracket": "Bracket line"}

        def _line_label(s) -> str:
            base = _DIR_LINE_LABELS[s.kind]
            return f"{base} ({s.label})" if s.label else base

        _pair(
            [s for s in data.direction_spans if s.kind in _DIR_LINE_LABELS],
            _in_quarters,
            lambda s: (
                f"{_dir_prefix(s.kind, s.part_id)}{_line_label(s)} start: "
                f"{data._bar_beat_label(bar_word, s.start_measure, s.start_beat_position)}"
            ),
            lambda s: (
                f"{_dir_prefix(s.kind, s.part_id)}{_line_label(s)} end: "
                f"{data._bar_beat_label(bar_word, s.end_measure, s.end_beat_position)}"
            ),
            jump_quarters=True,
        )

        _point(
            data.direction_marks,
            lambda m: f"{_dir_prefix('other_direction', m.part_id)}Direction: {m.label}",
            kind="other_direction",
        )

        # Rehearsal marks - a score-level landmark, one-shot point row (no
        # start/end pair, no part-name prefix). jump by measure only, so
        # Ctrl+Home/Ctrl+End resolve via first/last_visible_event_index_of_measure.
        _point(
            data.direction_marks,
            lambda m: f"Rehearsal mark {m.label}: {bar_word} {m.measure}",
            kind="rehearsal", jump="measure",
        )

        # Plain-text dynamics / tempo instructions ("cresc.", "rall.") -
        # one-shot point rows at their own position (never a fabricated
        # range), after the direction-line rows and before the P4 rows.
        _dynword_part_ids = [
            m.part_id for m in data.direction_marks if m.kind == "dynamics_word"
        ]

        def _dynword_label(m) -> str:
            prefix = data._marking_part_prefix(m.part_id, _dynword_part_ids)
            sense = vocabulary.dynamics_instruction_kind(m.label) or "dynamics"
            return f'{prefix}{sense.capitalize()} (marked "{m.label}")'

        _point(data.direction_marks, _dynword_label, kind="dynamics_word")

        _tempword_part_ids = [
            m.part_id for m in data.direction_marks if m.kind == "tempo_word"
        ]
        _point(
            data.direction_marks,
            lambda m: (
                f"{data._marking_part_prefix(m.part_id, _tempword_part_ids)}"
                f"Tempo instruction: {m.label}"
            ),
            kind="tempo_word",
        )

        # P4: barline / clef-change / measure-style one-shot rows, gated on
        # the mark's own measure (a point mark, like segno below). D15 keeps
        # only pedal/octave-shift out of Region 5; these three stay in (rare,
        # structural).
        def _barline_label(m) -> str:
            base = (
                "Double barline" if m.kind == "double_barline"
                else f"{m.style.capitalize()} barline"
            )
            return f"{base}: {bar_word} {m.measure}"

        _point(data.barline_marks, _barline_label, jump="measure")

        _clef_pids = {m.part_id for m in data.clef_change_marks}

        def _clef_label(m) -> str:
            prefix = ""
            if len(_clef_pids) > 1:
                name = next((p.name for p in data.parts_info if p.part_id == m.part_id), None)
                prefix = f"{name}: " if name else ""
            return f"{prefix}Clef change: {m.label}, staff {m.staff}"

        _point(data.clef_change_marks, _clef_label, jump="mark")

        _point(
            data.measure_style_marks,
            lambda m: f"{m.label.capitalize()}: {bar_word} {m.measure}",
            jump="measure",
        )

        # Segno / Coda / To coda / Fine / D.C. / D.S.: one-shot point rows,
        # each a single point (not a start/end pair). jump_target_* is always
        # this row's OWN position (a harmless Ctrl+Home/Ctrl+End no-op) -
        # jumping to where a mark actually points is out of scope;
        # NavigationController.jump_to_span has no concept of that.
        _point(data.segno_marks, lambda m: f"Segno{_label_suffix(m.label)}")
        _point(data.coda_marks, lambda m: f"Coda{_label_suffix(m.label)}")
        _point(data.to_coda_marks, lambda m: f"To coda{_label_suffix(m.label)}")
        _point(data.fine_marks, lambda m: "Fine")
        _point(
            data.navigation_jumps,
            lambda m: "Da capo" if m.kind == "dacapo" else "Dal segno",
        )

        # S7: a one-shot alert - unlike the three span kinds above, this has
        # no start/end pair, it just fires once at the transition itself.
        # "Previous" is the immediately preceding entry in whichever list
        # slice_ came from (data.timeline_slices), so this works whether or
        # not the metronome's synthetic beat markers are currently spliced
        # in - a marker slice carries the same real key/time_sig/tempo as
        # its own position, same as a real one. Never fires at index 0 (the
        # score's OPENING key/time signature/tempo - already shown in
        # Region 1 and the status bar, alerting on it here on every load
        # would just be noise). A score whose key never changes - the
        # common case - therefore never gets a key-signature row at all;
        # that silence is this same "no alert on the opening value, no
        # alert on no-op repetition" rule, not a separate suppression.
        previous = data.timeline_slices[resolved_index - 1] if resolved_index > 0 else None
        if previous is not None:
            # A key-signature override (S6) forces one constant display key
            # score-wide, so the file's own per-slice key_fifths can no
            # longer disagree with itself in effect - suppress the alert
            # while one is active rather than comparing raw, overridden-away
            # values.
            if data.key_signature_override_fifths is None and previous.key_fifths != slice_.key_fifths:
                key_name = key_signature_display_name(slice_.key_fifths, None)
                rows.append(
                    PerformanceRegionRow(
                        label=f"Key signature change: {key_name}",
                        jump_target_measure=slice_.measure,
                        jump_target_quarters=slice_.quarters_from_start,
                    )
                )
            if previous.time_sig != slice_.time_sig:
                ts_num, ts_den = slice_.time_sig
                rows.append(
                    PerformanceRegionRow(
                        label=f"Time signature change: {ts_num}/{ts_den}",
                        jump_target_measure=slice_.measure,
                        jump_target_quarters=slice_.quarters_from_start,
                    )
                )
            if data._tempo_change_at(resolved_index - 1) != data._tempo_change_at(resolved_index):
                number = data._format_tempo_number(data.score_tempo_display_bpm(resolved_index))
                unit = data.tempo_beat_unit_name_at(resolved_index)
                rows.append(
                    PerformanceRegionRow(
                        label=f"Tempo change: {number} {unit} notes per minute",
                        jump_target_measure=slice_.measure,
                        jump_target_quarters=slice_.quarters_from_start,
                    )
                )

        return rows

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

        def _tally(header, items, line_fn, *, omit_if_empty=False):
            """A "<header>: <count>" line then one `line_fn(item)` line per
            item. `omit_if_empty` drops the whole block (header included)
            when there is nothing to list - matching the sections that were
            hand-written with an `if items:` guard."""
            if omit_if_empty and not items:
                return
            lines.append(f"{header}: {len(items)}")
            lines.extend(line_fn(it) for it in items)

        _tally(
            "Sections", data.section_spans,
            lambda s: f"{s.label}: {bar_word} {s.start_measure} to {bar_word} {s.end_measure}",
            omit_if_empty=True,
        )

        note_counts: Dict[str, int] = {}
        for s in data._real_timeline_slices:
            for n in s.notes:
                if n.midi_pitch is not None:
                    note_counts[n.part_name] = note_counts.get(n.part_name, 0) + 1
        _tally(
            "Instruments", data.parts_info,
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
        lines.append(f"Dynamics: {len(_dynamics_events)}")
        for _, event_line, part_id in sorted(_dynamics_events, key=lambda e: e[0]):
            prefix = ""
            if part_id and len(_dynamics_part_ids) > 1:
                name = next((p.name for p in data.parts_info if p.part_id == part_id), None)
                prefix = f"{name}: " if name else ""
            lines.append(f"{prefix}{event_line}")

        _pedal_spans = [s for s in data.direction_spans if s.kind == "pedal"]
        _pedal_changes = [m for m in data.direction_marks if m.kind == "pedal_change"]
        lines.append(f"Pedal marks: {len(_pedal_spans) + len(_pedal_changes)}")
        for span in _pedal_spans:
            lines.append(f"Pedal: {_span_range(span)}")
        for mark in _pedal_changes:
            lines.append(f"Pedal change: {bar_word} {mark.measure}")

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
            omit_if_empty=True,
        )
        _tempo_words = [m for m in data.direction_marks if m.kind == "tempo_word"]
        _tally(
            "Tempo instructions", _tempo_words,
            lambda m: (
                f'Tempo instruction (marked "{m.label}"): '
                f"{data._bar_beat_label(bar_word, m.measure, m.beat_position)}"
            ),
            omit_if_empty=True,
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
               lambda m: f"{m.label.capitalize()}: {bar_word} {m.measure}")

        def _label_suffix(label: str) -> str:
            return f" {label}" if label and label != "1" else ""

        _tally("Segno marks", data.segno_marks,
               lambda m: f"Segno{_label_suffix(m.label)}: {bar_word} {m.measure}")
        _tally("Coda marks", data.coda_marks,
               lambda m: f"Coda{_label_suffix(m.label)}: {bar_word} {m.measure}")
        _tally("To coda marks", data.to_coda_marks,
               lambda m: f"To coda{_label_suffix(m.label)}: {bar_word} {m.measure}")
        _tally("Fine marks", data.fine_marks,
               lambda m: f"Fine: {bar_word} {m.measure}")
        _tally("Navigation jumps", data.navigation_jumps,
               lambda nj: f"{'Da capo' if nj.kind == 'dacapo' else 'Dal segno'}: {bar_word} {nj.measure}")

        return lines
