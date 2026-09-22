# models/note_renderer.py
"""S1 extraction: Ref 15 AC4's attribute display system - turning a
NoteData into the text Region 3 and Region 4 show, plus the per-voice
"which attributes are switched on" state the Region 4 context menu and the
Reorder Attributes dialog drive.

The WHICH half (voice_display_attributes) and the ORDER half
(attribute_order_by_part, one list per part) both still live as fields on
MusicData, because export_config()/apply_config() persist them per score.
Only the logic that reads and mutates them moved here. MusicData keeps a
delegator for every method, including the two private ones tests drive
directly (_note_attribute_pairs, _format_note_for_region_3).

A third mechanism, HIDDEN (hidden_attributes_by_part/hidden_attributes_
for_all - Attribute Management), gates Region 4 and Find only, never Region
3 - see is_attribute_hidden.

The single rule worth restating: an attribute renders only when it is BOTH
switched on for that voice AND present on that note. Absence is the
mechanism, not a bug - see note_attribute_pairs.
"""
from typing import Dict, List, Optional, Set, Tuple

from models import marking_labels, vocabulary
from models.event_slice import EventSlice
from models.note_data import NoteData
from models.region3_row import MarkingRow, NoteRow, Region3Row



# Attribute keys whose value is a start/end state word rather than a
# descriptive word/number - "slur, start", never the run-together "slur
# start" a listener could mistake for a two-word attribute name of its own.
# Every other prefixed attribute (dynamic, articulation, beat position...)
# keeps the plain "label value" join, which reads fine because its value is
# never itself a state word.
SPAN_STATE_ATTRIBUTE_KEYS = frozenset({"slur"})


class NoteRenderer:
    def __init__(self, data):
        self.data = data

    # --- one note's attribute values ----------------------------------

    def note_attribute_pairs(self, note: NoteData) -> Dict[str, str]:
        """Attribute name -> value for one note, shared by Region 3 and
        Region 4 so the two can never disagree on a name or value.

        Only keys the note actually has a value for are included (a rest has
        no octave or midi). That absence is the mechanism that stops either
        region rendering a row for data that doesn't exist."""
        data = self.data

        step_str = note.step_name
        if note.grace_notes:
            # Ref MusicXML <grace> support: "A grace B" - the main note
            # first, then the ornamenting grace note(s) - rather than a
            # separate phantom chord tone (reported bug - see
            # parsers/timeline_builder.py's pending_grace). Shared by both
            # Region 3 and Region 4 since both read this same "step" pair.
            grace_str = ", ".join(g.step_name for g in note.grace_notes)
            step_str = f"{step_str} grace {grace_str}"
        if note.is_tie_continuation:
            # Stage 8: "F sharp, tied" - the pitch plus a word placing it
            # inside the tie; whatever marking made this its own event
            # (fermata, dynamic, ...) still renders through the ordinary
            # attribute pipeline below, exactly as it would on any note.
            step_str = f"{step_str}, tied"

        pairs = {"step": step_str}
        if note.octave is not None:
            pairs["octave"] = str(note.octave)
        if note.midi_pitch is not None:
            pairs["midi"] = str(note.midi_pitch)
        pairs["measure"] = str(note.measure)
        pairs["beat position"] = str(note.beat_position)
        pairs["duration"] = self._duration_text(note)
        pairs["part"] = note.part_name
        pairs["stave"] = data.get_stave_name_for_part(note.part_id, note.staff)
        pairs["voice"] = str(note.voice)

        # The optional per-note tail: each renders only where the parser
        # actually found one. Adding a new one here plus in
        # DISPLAY_ATTRIBUTE_ORDER is the whole job - the toggle menu, scope
        # fan-out and ordering all pick it up for free (see CLAUDE.md).
        for key, value in (
            ("string", note.string),
            ("fret", note.fret),
            ("dynamic", note.dynamic),
            ("articulation", note.articulation),
            ("ornament", note.ornament),
            ("fingering", note.fingering),
            ("pluck", note.pluck),
            ("strum", note.strum),
            # P1: note-attached notations. The
            # attribute key is the spoken word; "other notation" carries a
            # space, like "beat position". `grace` is the spoken summary
            # NoteData.grace holds - the grace_notes list still drives the
            # separate "A grace B" step rendering above. `tie` itself is
            # deliberately NOT rendered here (stage 8, strategy section 12)
            # - a tied chain's duration IS the tie now; note.tie stays a
            # real field only for TimelineBuilder._merge_tied_chains'
            # internal chain detection.
            ("slur", marking_labels.span_state_word(note.slur)),
            ("tuplet", note.tuplet),
            ("grace", note.grace),
            ("arpeggio", note.arpeggio),
            ("fermata", note.fermata),
            ("accidental", note.accidental),
            ("glissando", note.glissando),
            ("technique", note.technique),
            ("other notation", note.other_notation),
            # P2: chord symbol/diagram on a synthetic
            # Chords part/voice note - a findable key distinct from `step`.
            ("chord symbol", note.chord_symbol),
            ("chord diagram", note.chord_diagram),
        ):
            if value is not None:
                pairs[key] = str(value)
        return pairs

    def _duration_text(self, note: NoteData) -> str:
        """The note's duration as a word ("quaver"), or the raw
        time-signature-relative number when no clean name matched - MIDI's
        per-track "too many weird names" fallback, or MusicXML's rare
        no-<type> case. _format_note_for_region_3 checks
        note.duration_name_us itself to decide whether the value can stand
        unlabelled, so the two readings stay in step."""
        if note.duration_name_us is not None:
            return vocabulary.duration_name(note.duration_name_us, self.data.uk_terms)
        ts_duration = note.ts_duration
        return str(int(ts_duration)) if ts_duration.is_integer() else str(ts_duration)

    # --- Region 3 -----------------------------------------------------

    def format_note_for_region_3(self, note: NoteData) -> str:
        """Ref 15 AC4: the note name plus whichever extras its voice has
        switched on, comma-separated. An attribute renders only when it is
        both configured on AND present on the note. A voice with everything
        off renders "" - a blank but still selectable, still audible row."""
        data = self.data
        wanted = self.attributes_for_voice(note.part_id, note.staff, note.voice)
        pairs = self.note_attribute_pairs(note)
        order = self.attribute_order_for_part(note.part_id)
        parts = []
        skip_next_octave = False
        for i, key in enumerate(order):
            if skip_next_octave and key == "octave":
                skip_next_octave = False
                continue
            skip_next_octave = False
            if key not in wanted or key not in pairs:
                continue
            unprefixed = key in data.REGION_3_UNPREFIXED_ATTRIBUTES
            if key == "duration" and note.duration_name_us is None:
                # No clean word match - the raw number needs the label,
                # unlike a self-explanatory word. See _duration_text.
                unprefixed = False
            if key == "step":
                next_key = order[i + 1] if i + 1 < len(order) else None
                # "C4" only when octave immediately follows step in the live
                # order AND is actually rendering (on for this voice, present
                # on the note) - otherwise fall through to the usual
                # "C, octave 4" so a hidden/reordered octave never silently
                # merges into the step text.
                if next_key == "octave" and "octave" in wanted and "octave" in pairs:
                    parts.append(f"{pairs[key]}{pairs['octave']}")
                    skip_next_octave = True
                    continue
            if unprefixed:
                parts.append(pairs[key])
            else:
                label = vocabulary.attribute_label(key, data.uk_terms)
                sep = ", " if key in SPAN_STATE_ATTRIBUTE_KEYS else " "
                parts.append(f"{label}{sep}{pairs[key]}")
        return ", ".join(parts)

    def region_3_data(self) -> List[Region3Row]:
        """PerformanceMarkingsStrategy.md section 15 (stage 2): one typed row
        per visible note, in the same order/indexing _visible_notes() has
        always used, with the score/part/stave marking rows
        (score_level_rows/part_level_rows/staff_level_rows - stave text and
        rehearsal marks among them since stage 5) interleaved ahead of the
        groups they belong to. MusicData.get_region_3_data() is the thin
        string-list wrapper every existing caller still uses.

        Stage 9 (linked parts): part_rows/staff_rows already contain any
        row borrowed from a linked partner part, keyed by the BORROWING
        part's own part_id/staff (models/marking_rows.py). Nothing here
        needs to know a row is borrowed - it shows whenever the borrowing
        part/staff is visible, regardless of the source part's own
        visibility, because it was anchored using the borrowing part's own
        events in the first place."""
        data = self.data
        current = data.get_current_slice()
        score_level_rows = data.marking_rows.score_level_rows(current)
        notes = data._visible_notes()
        if not notes:
            if score_level_rows:
                return score_level_rows
            if (
                data.metronome_enabled
                and current is not None
                and float(current.beat_position).is_integer()
            ):
                return [MarkingRow(text="Click", marking=None)]
            return [MarkingRow(text="None", marking=None)]
        staff_rows = data.marking_rows.staff_level_rows(current)
        part_rows = data.marking_rows.part_level_rows(current)
        rows: List[Region3Row] = list(score_level_rows)
        seen_staff_keys = set()
        seen_part_keys = set()
        for i, note in enumerate(notes):
            # A pedal instruction (PI tweaks follow-up) is part-level, not
            # staff-level - surfaced once, above the first staff group this
            # part shows regardless of which hand/staff that happens to be,
            # so it's heard whichever staff the reader is navigating.
            if note.part_id not in seen_part_keys:
                seen_part_keys.add(note.part_id)
                rows.extend(part_rows.get(note.part_id, []))
            staff_key = (note.part_id, note.staff)
            if staff_key not in seen_staff_keys:
                seen_staff_keys.add(staff_key)
                rows.extend(staff_rows.get(staff_key, []))
            text = self.format_note_for_region_3(note)
            rows.append(NoteRow(text=text, note_index=i))
        return rows

    # --- Region 4 -----------------------------------------------------

    def region_4_rows(self, selected_notes: List[NoteData]) -> List[Tuple[str, str, NoteData, str]]:
        """(display_key, attribute_key, note, value) per Region 4 row.
        display_key carries the "note N " prefix used for a chord;
        attribute_key never does. Shared by all three public Region 4
        accessors below, which differ only in which of these four fields
        they keep. Order follows each note's OWN part's attribute_order_
        for_part - the same live per-part order Region 3 uses - not
        note_attribute_pairs' insertion order, so the two regions can't
        disagree on sequence. A key hidden for this note's part (Attribute
        Management, either tier) is skipped - Region 4 and Find are the
        only two things hiding gates; Region 3 is untouched (see
        format_note_for_region_3)."""
        data = self.data
        is_chord = len(selected_notes) > 1
        rows = []
        for idx, n in enumerate(selected_notes, start=1):
            prefix = f"note {idx} " if is_chord else ""
            pairs = self.note_attribute_pairs(n)
            for attribute_key in self.attribute_order_for_part(n.part_id):
                if attribute_key not in pairs:
                    continue
                if self.is_attribute_hidden(attribute_key, n.part_id):
                    continue
                label = vocabulary.attribute_label(attribute_key, data.uk_terms)
                rows.append((f"{prefix}{label}", attribute_key, n, pairs[attribute_key]))
        return rows

    def region_4_data_for_indices(self, selected_indices: List[int]) -> Dict[str, str]:
        selected_notes = self.data.notes_for_indices(selected_indices)
        if not selected_notes:
            return {"Status": "No note selected"}
        return {
            display_key: value
            for display_key, _, _, value in self.region_4_rows(selected_notes)
        }

    def region_4_rows_for_indices(self, selected_indices: List[int]) -> List[Tuple[str, str, str]]:
        """(display_key, attribute_key, value) triples for Region 4's rows -
        unlike region_4_data_for_indices's plain dict, this keeps
        attribute_key alongside each row, which Region4ListWidget.
        refresh_list needs to re-anchor the current row on the same
        attribute across a rebuild (a big jump like Find's Alt+Right can
        change the attribute set/order entirely, unlike ordinary Left/Right
        between neighbouring notes)."""
        selected_notes = self.data.notes_for_indices(selected_indices)
        if not selected_notes:
            return [("Status", "", "No note selected")]
        return [
            (display_key, attribute_key, value)
            for display_key, attribute_key, _, value in self.region_4_rows(selected_notes)
        ]

    def region_4_row_targets(self, selected_indices: List[int]) -> List[Tuple[str, NoteData]]:
        """(attribute_key, note) per Region 4 row, in the same order as
        region_4_data_for_indices - lets MainWindow map "the Region 4 row
        the context menu was opened on" back to what it should toggle
        (Ref 15 AC4)."""
        selected_notes = self.data.notes_for_indices(selected_indices)
        if not selected_notes:
            return []
        return [
            (attribute_key, note)
            for _, attribute_key, note, _ in self.region_4_rows(selected_notes)
        ]

    def region_4_rows_for_region_3_selection(self, selected_region_3_indices: List[int]) -> List[Tuple[str, str, str]]:
        """Stage 7 (PerformanceMarkingsImplementationPlanV2.md): Region 4's
        content for whatever is selected in Region 3, note rows and marking
        rows both. A selection containing at least one note keeps today's
        behaviour verbatim (region_4_rows_for_indices, keyed by note index).
        A selection of ONLY marking row(s) - a repeat/ending/hairpin/segno/
        barline event/... - gets kind, bar/beat (or a range for a length)
        and, for a barline event, "Measure N"/"Position End of bar" plus one
        row per item it holds. No attribute_key is ever set for these rows
        (empty string), so the Region 4 context menu naturally offers
        nothing (AttributeController.menu_actions keys off
        get_region_4_row_targets, which stays note-only) - Ctrl+N (Region
        5's own shortcut) is unaffected either way."""
        data = self.data
        rows = data.get_region_3_rows()
        selected_rows = [rows[i] for i in selected_region_3_indices if 0 <= i < len(rows)]
        note_indices = [r.note_index for r in selected_rows if isinstance(r, NoteRow)]
        if note_indices:
            return self.region_4_rows_for_indices(note_indices)

        marking_rows = [r for r in selected_rows if isinstance(r, MarkingRow) and r.marking is not None]
        if not marking_rows:
            return [("Status", "", "No note selected")]

        bar_word = vocabulary.bar_word(data.uk_terms)
        multiple = len(marking_rows) > 1
        out: List[Tuple[str, str, str]] = []
        for i, row in enumerate(marking_rows, start=1):
            prefix = f"row {i} " if multiple else ""
            out.extend(self._region_4_rows_for_one_marking(row, bar_word, prefix))
        return out

    def _region_4_rows_for_one_marking(self, row: MarkingRow, bar_word: str, prefix: str):
        data = self.data
        marking = row.marking
        if isinstance(marking, EventSlice):
            out = [
                (f"{prefix}{bar_word.capitalize()}", "", str(marking.measure)),
                (f"{prefix}Position", "", f"End of {bar_word}"),
            ]
            for item in marking.barline_items:
                out.append((f"{prefix}Marking", "", marking_labels.barline_item_label(item)))
            return out

        out = [(f"{prefix}Kind", "", row.text)]
        if hasattr(marking, "start_measure") and hasattr(marking, "end_measure"):
            start_beat = getattr(marking, "start_beat_position", 1.0)
            end_beat = getattr(marking, "end_beat_position", 1.0)
            rng = data._range_label(bar_word, marking.start_measure, start_beat, marking.end_measure, end_beat)
            out.append((f"{prefix}Range", "", rng.capitalize()))
            return out
        measure = getattr(marking, "measure", None)
        if measure is not None:
            beat = getattr(marking, "beat_position", 1.0)
            pos = data._bar_beat_label(bar_word, measure, beat)
            out.append((f"{prefix}Position", "", pos.capitalize()))
        return out

    # --- which attributes a voice shows (F1) --------------------------

    def attributes_for_voice(self, part_id: str, staff: int, voice: int) -> Set[str]:
        """The attribute keys switched on for one voice. A voice with no
        entry falls back to DEFAULT_DISPLAY_ATTRIBUTES, NOT an empty set -
        most voices are never touched by the context menu and must keep
        showing the plain note name."""
        data = self.data
        return data.voice_display_attributes.get(
            (part_id, staff, voice), data.DEFAULT_DISPLAY_ATTRIBUTES
        )

    def display_attribute_present_for_voice(
        self, attribute_key: str, part_id: str, staff: int, voice: int
    ) -> bool:
        """Whether this voice currently shows `attribute_key` in Region 3 -
        drives the Add-vs-Remove variant of the Ref 15 AC4 context menu.
        Takes a bare position rather than a NoteData so it also serves the
        Reorder Attributes dialog's own Add/Remove button, which has a
        Region 2 node rather than a selected note to check."""
        return attribute_key in self.attributes_for_voice(part_id, staff, voice)

    def voice_tuples_for_scope(
        self, part_id: str, staff: int, voice: int, scope: str
    ) -> Set[Tuple[str, int, int]]:
        """Every (part_id, staff, voice) tuple `scope` fans out to from a
        single starting position - "voice" is just that tuple itself,
        "stave"/"part" walk parts_info's staves_voices for siblings, "score"
        is every voice in every part. Ref 15 AC4. Takes the position as
        three plain values rather than a NoteData so it also serves the
        Reorder Attributes dialog's Add/Remove button, which has a Region 2
        node's position, not a note, to fan out from."""
        parts_info = self.data.parts_info
        if scope == "voice":
            return {(part_id, staff, voice)}
        if scope == "score":
            return {
                (p.part_id, s, v)
                for p in parts_info
                for s, vs in p.staves_voices.items()
                for v in vs
            }
        part = next((p for p in parts_info if p.part_id == part_id), None)
        if part is None:
            return {(part_id, staff, voice)}
        if scope == "stave":
            return {(part_id, staff, v) for v in part.staves_voices.get(staff, [])}
        if scope == "part":
            return {
                (part_id, s, v)
                for s, vs in part.staves_voices.items()
                for v in vs
            }
        raise ValueError(f"Unknown display-attribute scope: {scope!r}")

    def apply_display_attribute(
        self, attribute_key: str, voice_keys: Set[Tuple[str, int, int]], add: bool
    ) -> None:
        data = self.data
        for voice_key in voice_keys:
            current = set(
                data.voice_display_attributes.get(voice_key, data.DEFAULT_DISPLAY_ATTRIBUTES)
            )
            if add:
                current.add(attribute_key)
            else:
                current.discard(attribute_key)
            data.voice_display_attributes[voice_key] = current

    def set_display_attribute(
        self, attribute_key: str, scope: str, notes: List[NoteData], add: bool
    ) -> None:
        """Ref 15 AC4: add or remove `attribute_key` for every voice `scope`
        reaches from each note. Plural because a chord selection unions the
        scope across all selected notes - a stave-scope action from a
        two-part chord affects both parts' staves, not just the one the menu
        was opened on."""
        voice_keys: Set[Tuple[str, int, int]] = set()
        for note in notes:
            voice_keys |= self.voice_tuples_for_scope(note.part_id, note.staff, note.voice, scope)
        self.apply_display_attribute(attribute_key, voice_keys, add)

    def set_display_attribute_for_voice(
        self, attribute_key: str, scope: str, part_id: str, staff: int, voice: int, add: bool
    ) -> None:
        """set_display_attribute's counterpart for the Reorder Attributes
        dialog's Add/Remove button: fans out from a single Region 2 node
        position instead of a list of selected notes, since that dialog has
        no note selection of its own to derive one from."""
        voice_keys = self.voice_tuples_for_scope(part_id, staff, voice, scope)
        self.apply_display_attribute(attribute_key, voice_keys, add)

    # --- rendering order (F2, now per-part - hideAttributes.md) --------

    def attribute_order_for_part(self, part_id: str) -> List[str]:
        """The live, mutable rendering order for `part_id` - both
        format_note_for_region_3 and region_4_rows iterate their note's own
        part's copy. Lazily seeded with a fresh copy of
        DISPLAY_ATTRIBUTE_ORDER on first access rather than pre-populated
        for every part up front, so a score gaining a part later needs no
        special-casing."""
        data = self.data
        order = data.attribute_order_by_part.get(part_id)
        if order is None:
            order = list(data.DISPLAY_ATTRIBUTE_ORDER)
            data.attribute_order_by_part[part_id] = order
        return order

    def move_attribute_order_for_part(
        self, part_id: str, attribute_key: str, up: bool, within: Optional[List[str]] = None
    ) -> bool:
        """Per-part counterpart of the old (score-global)
        move_attribute_order: same pop/insert-relative-to-neighbour logic,
        against attribute_order_for_part(part_id). Returns False at a
        boundary or for an unknown key, matching move_timeline_left/right's
        convention.

        `within`, if given, is a subset of this part's order (the dialog's
        own present-in-this-part filtered list) and the move is relative to
        the nearest neighbour IN THAT SUBSET. Entries not in `within` that
        sit between the two are carried along, keeping their order relative
        to each other - what lets a filtered dialog move its visible list by
        exactly one row per click without knowing about hidden attributes.

        Taking the neighbour's index BEFORE popping attribute_key, then
        inserting at that same index, is what makes one pop/insert pair
        correct in both directions with no branching."""
        order = self.attribute_order_for_part(part_id)
        if attribute_key not in order:
            return False
        sequence = within if within is not None else order
        if attribute_key not in sequence:
            return False
        pos = sequence.index(attribute_key)
        neighbor_pos = pos - 1 if up else pos + 1
        if not (0 <= neighbor_pos < len(sequence)):
            return False
        neighbor_key = sequence[neighbor_pos]
        source_index = order.index(attribute_key)
        target_index = order.index(neighbor_key)
        order.pop(source_index)
        order.insert(target_index, attribute_key)
        return True

    def set_attribute_order_within_part(
        self, part_id: str, new_order: List[str], within: List[str]
    ) -> None:
        """Commits the Attribute Management dialog's staged local reordering
        of `within` (a subset of `part_id`'s own order the dialog scoped
        itself to) back into that part's live order in one shot, on OK.

        `within`'s keys occupy some subset of positions in the part's order,
        interleaved with keys outside the dialog's scope. Those slots are
        filled, in ascending order, with `new_order` - the same "hidden
        entries in between keep their place" contract
        move_attribute_order_for_part maintains one step at a time, done
        here as a single bulk replace since the dialog no longer applies
        moves live."""
        order = self.attribute_order_for_part(part_id)
        positions = sorted(order.index(key) for key in within if key in order)
        for pos, key in zip(positions, new_order):
            order[pos] = key

    def attribute_keys_for_part(self, part_id: str) -> List[str]:
        """Every attribute key that has a value on at least one note
        belonging to `part_id`, anywhere in the score (not just the current
        slice), ordered per that part's own attribute_order_for_part.
        Powers the Attribute Management dialog's list - scans
        _real_timeline_slices (the stable, marker-free timeline) rather than
        timeline_slices, since the metronome can temporarily replace the
        latter with a merged view that includes marker-only slices.

        Filters on note.part_id directly rather than going through
        voice_tuples_for_scope/parts_info - parts_info is only populated by
        MusicXMLReader.load() and stays empty for a directly-built
        MusicData(file_path=...) (see MusicData._all_voice_tuples), so this
        must work from the notes themselves like that method does."""
        present: Set[str] = set()
        for event_slice in self.data._real_timeline_slices:
            for note in event_slice.notes:
                if note.part_id == part_id:
                    present |= self.note_attribute_pairs(note).keys()
        return [key for key in self.attribute_order_for_part(part_id) if key in present]

    # --- hiding (Attribute Management, hideAttributes.md) --------------

    def is_attribute_hidden(self, attribute_key: str, part_id: str) -> bool:
        """Whether `attribute_key` is hidden - for `part_id` specifically or
        for the whole score - and so must be skipped by Region 4 and Find.
        Region 3 never calls this: it is gated by voice_display_attributes/
        WHICH instead, and a hidden attribute is never elevated there by
        construction (set_attribute_hidden_for_part/_for_all both refuse to
        hide an elevated attribute)."""
        data = self.data
        return (
            attribute_key in data.hidden_attributes_for_all
            or attribute_key in data.hidden_attributes_by_part.get(part_id, set())
        )

    def _voice_tuples_in_part(self, part_id: str) -> Set[Tuple[str, int, int]]:
        """Every (part_id, staff, voice) belonging to `part_id` - the union
        of what the notes themselves carry (see attribute_keys_for_part for
        why this reads notes rather than parts_info) and whatever
        voice_display_attributes already has an explicit entry for, so a
        voice that is elevated but has (in a unit test, or an edited score)
        no note of its own is still found."""
        data = self.data
        from_notes = {
            (n.part_id, n.staff, n.voice)
            for s in data._real_timeline_slices
            for n in s.notes
            if n.part_id == part_id
        }
        from_display_attrs = {vt for vt in data.voice_display_attributes if vt[0] == part_id}
        return from_notes | from_display_attrs

    def attribute_elevated_for_part(self, attribute_key: str, part_id: str) -> bool:
        """True when `attribute_key` is elevated (present in
        voice_display_attributes) for at least one voice under `part_id` -
        regardless of which of the four add/remove scopes put it there, per
        the user ("if it is elevated at all, prefix with an asterisk").
        Drives the Attribute Management dialog's own part-local asterisk and
        the per-part Hide button's block."""
        data = self.data
        return any(
            attribute_key in data.voice_display_attributes.get(vt, data.DEFAULT_DISPLAY_ATTRIBUTES)
            for vt in self._voice_tuples_in_part(part_id)
        )

    def attribute_elevated_parts(self, attribute_key: str) -> List[str]:
        """Every part_id in the whole score where `attribute_key` is
        elevated for at least one voice - empty means not elevated anywhere.
        Used only for the "Hide for All" block's message, which must name
        every part standing in its way - not for the dialog's own row
        asterisk (attribute_elevated_for_part, part-local by design)."""
        all_part_ids: List[str] = []
        seen: Set[str] = set()
        for event_slice in self.data._real_timeline_slices:
            for note in event_slice.notes:
                if note.part_id not in seen:
                    seen.add(note.part_id)
                    all_part_ids.append(note.part_id)
        # Union in any part_id voice_display_attributes already names but no
        # note carries (a unit test, or an edited score) - same reasoning as
        # _voice_tuples_in_part.
        for vt in self.data.voice_display_attributes:
            if vt[0] not in seen:
                seen.add(vt[0])
                all_part_ids.append(vt[0])
        return [p for p in all_part_ids if self.attribute_elevated_for_part(attribute_key, p)]

    def set_attribute_hidden_for_part(self, attribute_key: str, part_id: str, hidden: bool) -> bool:
        """Refuses (returns False, no state change) a hide while
        `attribute_key` is elevated anywhere in `part_id`, or already hidden
        for the whole score - the model enforces this itself rather than
        leaning on the dialog's own button disablement, so it isn't
        possible to reach an "elevated and hidden" or "hidden-for-part while
        also hidden-for-all" state through any caller."""
        data = self.data
        if hidden:
            if self.attribute_elevated_for_part(attribute_key, part_id):
                return False
            if attribute_key in data.hidden_attributes_for_all:
                return False
            data.hidden_attributes_by_part.setdefault(part_id, set()).add(attribute_key)
        else:
            data.hidden_attributes_by_part.get(part_id, set()).discard(attribute_key)
        return True

    def set_attribute_hidden_for_all(self, attribute_key: str, hidden: bool) -> bool:
        """Refuses (returns False, no state change) a hide while
        `attribute_key` is elevated in any part. On a successful hide, also
        clears that key from every part's own hidden_attributes_by_part
        entry - now redundant/stale, and would otherwise reappear as a
        surprising leftover per-part hide if the score-wide hide is later
        undone."""
        data = self.data
        if hidden:
            if self.attribute_elevated_parts(attribute_key):
                return False
            data.hidden_attributes_for_all.add(attribute_key)
            for hidden_set in data.hidden_attributes_by_part.values():
                hidden_set.discard(attribute_key)
        else:
            data.hidden_attributes_for_all.discard(attribute_key)
        return True
