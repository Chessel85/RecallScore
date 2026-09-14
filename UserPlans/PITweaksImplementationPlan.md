# PI tweaks - implementation plan

The implementation plan for `UserPlans/PITweaks.md`. Written for a Sonnet
session to execute stage by stage. Read `PITweaks.md` first: it holds the
problem statements. This file says where the code goes, in what order, and
how to prove each stage.

Two decisions from the user (2026-09-14) supersede parts of `PITweaks.md`:

* ALL performance information is surfaced in the note list by default, and
  all of it carries through to linked parts. This widens item 1's borrowed
  subset (only clef changes stay out) and settles item 2's open question:
  stave text and dynamics ARE borrowed (stage 7).
* PART and INSTRUMENT are two distinct concepts, used consistently in every
  menu, report and dialog (stage 3). This replaces item 3e's "consolidate on
  part".

---

## 0. Ground rules for the executing session

* Read `CLAUDE.md` (all 16 invariants) and `docs/architecture.md` before
  stage 1. Read `docs/dialog_widget_patterns.md` before stage 7.
* One stage at a time, in the order below. Each stage ends with the whole
  suite green: `.venv\Scripts\python.exe -m pytest`.
* Stages that touch `models/` or `parsers/` also run the model fingerprint
  harness (see `tests/manual/README.md`). Capture a baseline on the current
  `HEAD` before stage 1, once, and keep it. Each stage says which fingerprint
  fields are EXPECTED to change; any diff outside those is a bug. After a
  stage whose diff is expected and reviewed, re-capture the baseline so the
  next stage's diff is only its own.
* Do not commit or push unless the user asks. Do not edit `wishlist.txt`,
  `docs/user_guide.md`, `docs/user_guide.html` or `docs/quick_start.*`.
* When the spec and the code disagree, stop and report rather than guess.
  Decisions already settled with the user are listed at the end of this
  file; do not reopen them.
* The user reads replies through NVDA: short status messages, no bold
  markdown, `*` bullets.

---

## Terminology (applies to every stage)

* PART - an element of the MusicXML structure: a `<score-part>` / `<part>`,
  identified by `part_id`, named by `<part-name>`, shown as a Region 2 row.
  Muting, soloing, reordering, renaming and linking act on parts. A MIDI or
  Ultimate Guitar import's tracks become parts.
* INSTRUMENT - the General MIDI sound used to render a part (its GM program,
  or for a percussion item its GM percussion key). Choosing a sound, and
  anything that describes what plays back, is about the instrument.

A part HAS an instrument. Never use one word for the other. Everyday English
about the physical object ("play an instrument", the tuner's "stringed
instrument") is not the app concept and is left alone.

---

## Stage order

| Stage | Spec item | Size | Touches |
|---|---|---|---|
| 1 | 4. Barline sound when arrowing left | tiny | `controllers/`, tests |
| 2 | 5. One row for a one-event span | small | `models/marking_rows.py` |
| 3 | 3b + terminology | small | report, menus, dialogs, docs |
| 4 | 3a. "End of bar" instead of beat ts+1 | small | `models/marking_labels.py`, `models/music_data.py` |
| 5 | All performance information in the note list by default | large | `models/`, persistence |
| 6 | 3c + 3d. Report as a navigable tree | medium | models, dialog, window, navigation |
| 7 | 1 + 2. Linked parts, including stave text and dynamics | large | models, persistence, Region 2, dialog, menu |

Stage 5 must land before stage 7: linked parts borrows whatever the note
list shows, so the note list has to be complete first.

---

## Stage 1 - repeat barline sounds when arrowing left (item 4)

Change: `controllers/playback_controller.py` `play_barline_indicator`
(around line 1320). Pass `min(before_measure, after_measure)` and
`max(before_measure, after_measure)` to `pattern_for_crossing`. Do not touch
`NavigationController.barline_crossed` or `pattern_for_crossing` itself.
Add one sentence to the docstring: the lookup is normalised because a
barline is the same barline from either side.

Tests (`tests/test_bar_line_indicator.py`, or wherever
`play_barline_indicator` is already driven - check first):

* Parametrise over repeat start, repeat end, repeat end and start, double,
  heavy, tick. For each, `play_barline_indicator(n, n+1)` and
  `play_barline_indicator(n+1, n)` send the same note through the null synth
  (`tests/support/null_synth.py`).
* A leftward crossing of a plain barline still plays the plain beep.

Fingerprint: not needed.

---

## Stage 2 - one row for a span that starts and ends on one event (item 5)

Change: `models/marking_rows.py` `score_level_rows`, the inner `_add`
(line 86). Compute both conditions first:

```python
is_end = span.end_measure == event_slice.measure and self._is_last_of_measure(event_slice)
is_start = span.start_measure == event_slice.measure and self._is_first_of_measure(event_slice)
if is_start and is_end:
    rows.append(MarkingRow(text=name, marking=span, category=category))
    return
```

then the existing end-row and start-row appends, end before start. One
docstring sentence pointing at the hairpin point rule in `staff_level_rows`.

Tests (`tests/models/test_marking_rows.py`, matching its existing helpers):

* One-bar ending with a single event: one row, "Ending 2".
* Same for a repeat ("Repeat") and a section ("Section A").
* One-bar span with two events: "... start" on the first, "... end" on the
  last, unchanged.
* A repeat end and an ending end on the same single event: still two rows.
* `files/bach-bourree-tab.mxl` bar 25 reads "Ending 2" once (or a minimal
  fixture if tests do not load `files/`).

Fingerprint: Region 3 rows only, only on the single event of a one-bar
repeat, ending or section.

---

## Stage 3 - report tidy (item 3b) and part/instrument terminology

### 3.1 Omit zero counts (3b)

All in `models/performance_rows.py` `get_performance_report_lines`.

* Remove `_tally`'s `omit_if_empty` parameter; empty `items` always appends
  nothing. Update its docstring. Delete `omit_if_empty=True` at every call.
* Route the hand-rolled Dynamics block through `_tally`: build the sorted,
  part-prefixed line strings first, then `_tally("Dynamics", final_lines,
  lambda line: line)`.
* Same for Pedal marks: pedal span lines then pedal change lines, today's
  order, then tally.
* The preamble (Region 1 data, anacrusis, number of bars) is untouched.

### 3.2 Part and instrument, everywhere the user reads

Known hits from a grep of string literals. Make these changes:

| Where | Today | Change to |
|---|---|---|
| `models/performance_rows.py` report tally | "Instruments" | "Parts" |
| `widgets/menu_builder.py` Mixer status tip (line ~574) | "Set volume and pan for each instrument and sound" | "Set volume and pan for each part and sound" - Mixer rows are per part |

The Parts menu does not change (user decision, 2026-09-14): the
"Instruments..." action, its status tip, the Instruments dialog's title and
fields, the `_CATEGORY_OVERRIDES` entry and `docs/keystrokes.md` all stay
as they are.

Leave unchanged, and say so in the stage report: Live MIDI Input's
"&Instrument:" and its status tip (it is the GM sound - correct), the
tuner's "stringed instrument" (physical object), `synth_engine.py`'s
"instrument sound bank" (it is the bank of instrument sounds - correct), and
the Product Definition Document's personas.

Then do the part of this the grep cannot: search user-visible text built at
runtime - f-strings, `status_tip=`, `setToolTip`, `setAccessibleName`,
`QMessageBox` text, Find target labels (`models/find_target.py`), Region 1-5
labels, the Sound Icon Dictionary, error messages in `parsers/` - for
"instrument", "track" and "part", and classify each hit by the terminology
section above. Fix misuses; list every hit and its verdict in the stage
report. Anything in the Parts menu or the Instruments dialog is out of scope (see
above) - list such hits but do not change them. Internal identifiers stay
as they are - renaming them is churn with no user-visible effect. Code comments and docstrings need
changing only where they would now mislead.

Add a short "Terminology" section to `CLAUDE.md` (under Project) with the two
definitions above, and the same paragraph near the top of
`docs/architecture.md`.

Tests: update every test asserting the report's "Instruments", "Pedal
marks: 0", "Dynamics: 0", or the Mixer status tip (grep `tests/`). Add:

* No pedal, no dynamics, no repeats: none of those headers appear.
* With pedal marks: "Pedal marks: N" plus N detail lines, today's order.
* "Parts: N" header.

Fingerprint: `report=` line only.

---

## Stage 4 - positions past the end of the bar (item 3a)

The timeline stays as it is. Only the label changes.

`models/marking_labels.py`:

* `bar_beat_label(word, measure, beat_position, beats_in_bar=None)`. When
  `beats_in_bar` is given and `beat_position >= beats_in_bar + 1`, return
  `f"end of {word} {measure}"`; otherwise today's behaviour. Docstring:
  explain the timeline's "barline after the last beat" convention
  (`_PartState.beat_position`, `_flush_open_direction_spans`, the barline
  fermata's `1.0 + ts_num`) and why the fix is here rather than there.

`models/music_data.py`:

* `_bar_beat_label` stops being a `staticmethod`; same
  `(bar_word, measure, beat_position)` signature. It looks up the bar's time
  signature numerator and passes it as `beats_in_bar`.
* The lookup: a lazily built `{measure: ts_num}` from
  `_real_timeline_slices` (first slice of each measure, `time_sig[0]`).
  Storing it on `MusicData` is safe under invariant 3 - the object is
  replaced on every load. A missing measure passes `None`.
* Grep every caller of `_bar_beat_label` and
  `marking_labels.bar_beat_label`, including any call on the class rather
  than an instance, which would break when the staticmethod goes.
* Audit (the spec asks for it): every span end in Region 5 and the report
  goes through `_bar_beat_label`. Fix any that format "beat" by hand. Report
  what you found.
* Capitalisation: "Crescendo: Bar 3 beat 2 to end of Bar 12". Do not
  capitalise "end".

Tests:

* `bar_beat_label`: beat 5 in 4/4 -> "end of bar 12"; 4.5 -> "bar 12 beat
  4.5"; 1 -> "bar 12"; `beats_in_bar=None` never says "end of"; also 3/4
  (beat 4) and 6/8 (beat 7).
* `examples/pachelbels-canon-in-d-string-quartet.mxl` (under `examples/`):
  no report line contains "beat 5". Use `MusicData(file_path=...)`, not
  music21.
* A hairpin running to the end of its part reads "to end of Bar N".

Fingerprint: `report=` and Region 5 rows only.

---

## Stage 5 - all performance information in the note list by default

### What is missing today

`MarkingRows.score_level_rows` and `staff_level_rows` emit: repeats,
endings, sections, barline fermata, segno/coda/to coda/fine/jumps, barline
marks, directives (only when surfaced with Ctrl+N - off by default), key/
time/tempo changes, hairpins, clef changes, pedal changes. Stave text and
rehearsal marks arrive as fabricated notes.

Not in the note list at all:

| Family | Source | Anchoring |
|---|---|---|
| Pedal span | `direction_spans` kind `pedal` | start/end, like a hairpin |
| Octave shift | `direction_spans` kind `octave_shift` | start/end |
| Dashed line | `direction_spans` kind `dashes` | start/end |
| Bracket line | `direction_spans` kind `bracket` | start/end |
| Dynamics word ("cresc.") | `direction_marks` kind `dynamics_word` | point |
| Tempo word ("rall.") | `direction_marks` kind `tempo_word` | point |
| Other direction (catch-all) | `direction_marks` kind `other_direction` | point |
| Measure style (multi-bar rest, measure repeat, slash) | `measure_style_marks` | point at measure start |

And hidden by default:

* Directives - surfaced one at a time with Ctrl+N.
* Note-attached performance attributes - `DEFAULT_DISPLAY_ATTRIBUTES` is
  `{"step"}`, so dynamic, articulation, ornament and the stage 10 notations
  show only in Region 4 unless the user switches them on per voice.

`DirectionMark`'s docstring lists only rehearsal/pedal_change/
other_direction kinds, but `dynamics_word` and `tempo_word` are in use
(`performance_rows.py`) - fix that comment while here.

### 5.1 Shared wording first (invariant 8)

Region 5 already words every one of these families. Move each label builder
into `models/marking_labels.py` as a plain function and have BOTH Region 5
and the note list call it, so the two cannot drift:

* `direction_line_name(span)` -> "Dashed line", "Dashed line (cresc.)",
  "Bracket line", ... (today `_line_label` in `performance_rows.py`)
* `pedal_name()` -> "Pedal"; `octave_shift_name(span)` -> "Octave shift
  8va" (use the report's existing wording)
* `dynamics_word_label(label)` -> 'Crescendo (marked "cresc.")' (today
  `_dynword_label` minus the part prefix, which stays in Region 5)
* `tempo_word_label(label)` -> "Tempo instruction: rall."
* `other_direction_label(label)` -> "Direction: X"
* `measure_style_label(mark)` -> "8-bar rest" capitalised as Region 5 does

Note list span rows use the existing `start_label`/`end_label`, and the
point rule hairpins already follow (start == end -> bare name). Region 5
and report text must be byte-identical after this refactor - check the
fingerprint before going further.

### 5.2 New staff-level rows

In `MarkingRows.staff_level_rows`, after the existing three families, add
the eight families above, each keyed on `(mark.part_id, mark.staff)` and
anchored exactly like hairpins (spans: `_first_at_or_after` for the start,
`_last_at_or_before` for the end, point when equal; points:
`_first_at_or_after(quarters_from_start)`). `MeasureStyleMark` has no
quarters - anchor on the first event of that part/staff in its measure (add
a small per-(key, measure) index, or resolve through the measure's first
quarters from `_first_quarters_of_measure` then `_first_at_or_after`). A
multi-bar rest has no events of its own (rests are skipped), so it lands on
the next event - that is correct ("8-bar rest" is read as you arrive after
it); say so in a comment.

Before writing it, pull the loops into one private method (e.g.
`_rows_for_markings(event_slice, key_for)`) so the growing family list does
not become eleven copies of the anchoring code. Stage 7 reuses this with a
different `key_for`.

Order inside a staff group, fixed: the existing three first, exactly as
today (hairpins, clef changes, pedal changes), then the new families in the
order of the table above. Existing rows never change position.

Performance (Ref 9): `staff_level_rows` runs on every cursor move. The
per-family scans are linear in the number of marks; if a large score
(examples/ has several) shows a measurable slowdown, index marks by the
anchor quarters once per load, the way `_staff_quarters` is built. Measure
with a quick timing loop over `staff_level_rows` for every slice of the
largest file in `examples/` before and after, and report the numbers.

### 5.3 Categories (Ctrl+N)

Ctrl+N toggles a category from a Region 5 row. Give each new family whose
Region 5 row exists a category so the user can still turn it off:

* dashes/bracket -> existing `"lines"` (Region 5 rows already carry it; the
  note list simply had nothing to hide until now)
* dynamics words -> new `"dynamics_words"`
* tempo words -> new `"tempo_words"`
* other directions -> new `"other_directions"`
* measure style -> new `"measure_styles"`

Add each to `ALL_CATEGORIES` and `CATEGORY_NAMES` ("Dynamics words", "Tempo
words", "Other directions", "Measure styles" - user-approved), and set the
same `category=` on the matching `_point(...)` calls in
`get_performance_region_rows` so Region 5's asterisk and Ctrl+N work. Those
Region 5 rows will now start with "* " - expected.

Pedal and octave shift have no Region 5 row (D15), so nothing can toggle
them. Leave them uncategorised (always on) and update the
`marking_categories.py` docstring, which currently says octave shift "has no
note-list row of any kind yet". If the user later wants them switchable,
that needs a new route (not Ctrl+N on Region 5) - out of scope here.

### 5.4 Directives on by default

Flip the stored set from "surfaced" to "hidden":

* `MusicData.directives_in_note_list: Set[int]` becomes
  `directives_hidden_from_note_list: Set[int]` (default empty = all shown).
  Grep and update every use: `get_directive_rows` (surfaced = index NOT in
  the hidden set), `toggle_directive_in_note_list` (same name, inverted
  bookkeeping, same return meaning: True = now shown),
  `MarkingRows.score_level_rows` (iterate all directive indices not hidden;
  drop the `if data.directives_in_note_list:` guard but keep the early skip
  when `directive_marks` is empty).
* `ScoreConfig.directive_labels_in_note_list` is replaced by
  `directive_labels_hidden_from_note_list: Set[Tuple[int, str]]`, JSON key
  `"directive_labels_hidden_from_note_list"`. An old `.rsc`'s
  `"directive_labels_in_note_list"` is ignored: under the new default every
  directive is shown, which is a superset of what it surfaced. Comment this.
* `export_config`/`apply_config`: same `(measure, label)` matching, on the
  hidden set.

### 5.5 Performance attributes on by default

Change `DEFAULT_DISPLAY_ATTRIBUTES` from `{"step"}` to `step` plus the
note-attached performance information:

`"dynamic", "articulation", "ornament", "fermata", "slur", "arpeggio",
"glissando", "technique", "other notation"`

User-approved list. Deliberately left out as notation or tab detail
rather than performance information: octave, duration, measure, beat
position, part, stave, voice, midi, string, fret, fingering, pluck, strum,
tuplet, grace, accidental, and the chord symbol/diagram keys.

Effects to verify and report:

* A voice with no saved `voice_display_attributes` entry picks up the new
  defaults - including voices in old `.rsc` files that were never touched.
  A voice the user did configure keeps its saved set. That matches "by
  default"; confirm `attributes_for_voice` really works this way.
* Region 3 text for an ordinary note is unchanged (these attributes are
  absent on most notes); a note with a dynamic now reads e.g.
  "C, dynamic mf". Check the `step`+`octave` merge in
  `format_note_for_region_3` is unaffected.
* The Region 4 context menu toggles (Ref 15) show these as ticked by default.
* Find's attribute targets are unaffected (they do not read display
  settings - confirm).

### 5.6 Tests

* `tests/models/test_marking_rows.py` / `test_hairpin_marking_rows.py`: one
  test per new family - start row, end row, point row, correct staff group,
  filtered when its category is off (where it has one). A multi-bar rest
  lands on the next event.
* Region 5 and report text unchanged after 5.1 (compare against the
  fingerprint or assert on a fixture's lines).
* New categories: Ctrl+N on each new Region 5 row toggles the note list
  row; asterisk appears/disappears; persistence round-trip.
* Directives: shown by default; Ctrl+N hides; round-trip; an old `.rsc` with
  only the old key loads with every directive shown.
* Default attributes: a fresh voice shows a note's dynamic in Region 3; a
  voice with a saved attribute set does not gain it.
* Update existing tests that assumed "step only" or "directives off"; do not
  weaken assertions - change the expected text.

Fingerprint: Region 3 rows (new marking rows, new attribute text), Region 5
rows (new asterisks only), directive rows. Report and everything else
unchanged. Review the diff on at least three files by eye before accepting.

---

## Stage 6 - the report as a navigable tree (items 3c and 3d)

### 6.1 Structured rows (model)

New file `models/report_row.py`, Qt-free:

```python
@dataclass(frozen=True)
class ReportRow:
    text: str
    level: int                              # 0 = header/preamble, 1 = detail
    jump_quarters: Optional[float] = None   # a timeline position
    jump_measure: Optional[int] = None      # measure-precise marks
    part_id: Optional[str] = None           # a row under "Parts"
```

In `models/performance_rows.py`:

* The body of `get_performance_report_lines` moves to
  `get_performance_report_rows() -> List[ReportRow]`. `_tally` appends a
  level-0 header and level-1 details; `line_fn` becomes `row_fn` returning
  a `ReportRow` (or a tuple - whichever keeps call sites shortest).
* `get_performance_report_lines` becomes
  `return [r.text for r in self.get_performance_report_rows()]`, byte-
  identical to the end of stage 5.
* `MusicData.get_performance_report_rows` one-line delegator (invariant 4).

Jump targets - carried from the object that made the text, never parsed
back out of it:

| Row | Target |
|---|---|
| Parts | `part_id` |
| Sections, Repeated sections, Endings | none (a range, per spec) |
| Hairpins in Dynamics | `start_quarters_from_start` if `start_known`, else `end_quarters_from_start` |
| Dynamics word, tempo word, pedal change, other direction, rehearsal | `mark.quarters_from_start` |
| Note dynamics | the slice's `quarters_from_start` |
| Pedal, octave shift, dashed, bracket spans | `start_quarters_from_start` |
| Barline changes, clef changes, measure style, segno, coda, to coda, fine, navigation jumps | `jump_measure` (quarters if the mark carries them) |
| Preamble, anacrusis, bar count | none |

### 6.2 Resolving a jump (controller)

`controllers/navigation_controller.py`: `jump_to_report_row(row) -> bool`.
Resolve like `jump_to_span`'s start branch: quarters via
`slice_index_at_or_after_quarters`, else
`first_visible_event_index_of_measure`. `None` -> emit `boundary_hit`,
return False. Success -> set `active_event_index`, emit
`position_changed(True, False)`, return True. Factor the shared resolution
into a private helper used by both methods.

### 6.3 The dialog

`widgets/performance_report_dialog.py`:

* Constructor takes `rows: List[ReportRow]` instead of `lines`.
* `QTreeWidget`, `setHeaderHidden(True)`, one column. Level-0 rows are
  top-level items; each level-1 row is a child of the most recent level-0
  row. The `ReportRow` goes on the item via `setData(0, UserRole, row)`.
  All collapsed. Keep the label buddy.
* `itemActivated` (Enter): if the row has `part_id`, `jump_quarters` or
  `jump_measure`, set `self.chosen_row` and `accept()`; otherwise nothing.
  Headers keep Qt's own expand/collapse keys.
* Close button stays: `reject()`.
* Initial focus: check whether `widgets/list_focus_helper.py` works with a
  `QTreeWidget` (see how Region 2, itself a tree, is focused and
  reannounced); add a tree variant there if not. Current item = the first
  top-level item. Focus the tree, the literal first tab-order widget.
* Rewrite the class docstring: the flat-list and no-jump decisions were
  scope cuts and are reversed; NVDA reads a tree item's level and expanded
  state natively.

### 6.4 The window

`main_window.py` `_show_performance_report_dialog`:

* Build with `rows=self._music_data.get_performance_report_rows()`.
* After an Accepted `exec()` with a `chosen_row`, act OUTSIDE the
  `_preserving_focus()` block (it restores focus on exit and would undo the
  jump):
  * `part_id`: select that part's Region 2 row via
    `self.region_2.select_node(...)` (check the part node_id format in
    `widgets/region2_manager.py`) and focus Region 2 the way the X shortcut
    does.
  * otherwise: the navigation controller's `jump_to_report_row(row)`; on
    True, focus Region 3 the way the C shortcut does.
* Wiring only (invariant 5); if the branch grows, move the decision into a
  controller.

### 6.5 Tests

* Models: row texts equal `get_performance_report_lines()`; details are
  level 1; a dynamic carries its quarters; a part row carries `part_id` and
  no position; a repeat row carries nothing.
* `tests/widgets/test_performance_report_dialog.py` (new): tree shape,
  collapsed by default, activating a header does not close, activating a
  positioned row accepts with `chosen_row` set.
* `tests/test_main_window_performance.py`: update the constructor call
  (line 136). Monkeypatch `main_window.PerformanceReportDialog` with a fake
  returning Accepted and a dynamic row: `active_event_index` moved, Region 3
  focused. Same for a part row and Region 2.
* `jump_to_report_row` with an unresolvable target emits `boundary_hit`.

Fingerprint: no diff.

---

## Stage 7 - linked parts, including stave text and dynamics (items 1 and 2)

Read `PITweaks.md` item 1 "Rules" and "Scope and constraints" again first.
The borrowed subset there is superseded: everything the note list shows for
a part is borrowed, except clef changes.

### 7.1 Model

New collaborator `models/part_links.py`, Qt-free, no state of its own.

`MusicData` gains `part_link_groups: List[List[str]]` (default empty), each
inner list one group's part_ids, outer list in creation order. Group number
= index + 1. Dissolving a group renumbers later ones (user-approved).

Rules as plain module functions (so the dialog in 7.6 uses the same code -
invariant 8), wrapped by a `PartLinks(data)` class with one-line `MusicData`
delegators (invariant 4):

* `link_parts(part_ids) -> bool` - refuse (False, no change) when fewer
  than two distinct ids, any id unknown to `parts_info`, or any id already
  linked; else append a group.
* `unlink_part(part_id) -> bool` - remove it; drop the group if under two
  members. False if not linked.
* `link_group_number(part_id) -> Optional[int]`
* `link_partners(part_id) -> List[str]`
* `set_part_link_groups(groups)` - replace wholesale, validated by the same
  rules.

Membership is by `part_id` only; never read `PartStructureInfo.name` or
`NoteData.part_name` here.

### 7.2 Borrowed marking rows

`MarkingRows.staff_level_rows`, using stage 5's `_rows_for_markings`:

* Own rows: unchanged.
* When `data.part_link_groups` is non-empty (skip entirely otherwise -
  Ref 9): for each part B with partners, run `_rows_for_markings` with a
  `key_for` that maps every partner marking - except clef changes - to
  `(B, borrow_staff)`, where `borrow_staff` is B's lowest staff in
  `_staff_quarters`. Anchoring uses B's own events.
* Dedupe: skip a borrowed row whose text is already in that key's list at
  this slice (own row or earlier borrow).
* `marking_categories_off` applies to borrowed rows too.
* Visibility needs nothing special: `_staff_quarters` comes from the
  unfiltered `_real_timeline_slices`, and `NoteRenderer.region_3_data` emits
  a key's rows when that staff has visible notes - so rows show when the
  BORROWING part is visible, whatever the source part's state. Say so in a
  comment.

Score-level rows (repeats, sections, directives, jumps, barlines,
structural changes) belong to no part and need no borrowing.

### 7.3 Borrowed stave text and dynamics (item 2, settled)

Stave text (`NoteData` with `voice == STAVE_TEXT_VOICE_ID`):

* In `NoteRenderer.region_3_data`, for each visible part B with partners,
  take the stave text notes of partner parts in the current slice's
  UNFILTERED notes (`current.notes`, not `_visible_notes`) and insert a
  `MarkingRow(text=<same formatting as the source row>, marking=note,
  note_index=None)` at the top of B's first staff group.
* "Visible part" here means B has at least one active voice in the Region 2
  filter - not "B has a note at this slice". A stave-text-only slice has no
  notes of B; B's group must still be emitted for the borrowed row. Handle
  the `if not notes:` early branch too, so a tab reader with the notated
  part switched off still hears "Allegro".
* Dedupe against B's own stave text at this slice by text.
* `note_index=None` means the row is not selectable as a note, does not
  sound, and does not reach Region 4 - `notes_indices_for_selection`
  (`music_data.py` ~line 905) already drops such rows. Confirm with a test.

Note dynamics (`NoteData.dynamic`):

* A staff-level borrowed row "Dynamic mf" (wording shared with the report's
  "Dynamic mf" line via a `marking_labels` function) in B's group, anchored
  at B's first event at or after the partner note's slice. Dedupe by
  `(partner part_id, staff, quarters, dynamic)` as the report does, so a
  chord gives one row.
* Suppress it when any of B's notes at that anchor already carries the same
  dynamic.
* No category (always on), `note_index=None`. It is a note-list row only:
  B's notes do not gain a `dynamic` attribute, Region 4 is unchanged, Find
  is unchanged.

Region 5, the Performance Report, Find and playback are NOT changed by any
part of stage 7.

Before relying on borrowed rows, grep every consumer of `MarkingRow.marking`
(Region 3 selection, audition, any Enter/jump handling). A borrowed row's
`marking` is the source part's object; make sure nothing uses its `part_id`
to decide something about the row's own part. Report what you find.

### 7.4 Persistence

* `ScoreConfig.part_link_groups: List[List[str]]`, default empty.
* `persistence/score_config.py`: load `"part_link_groups"` as
  `[[str(p) for p in g] for g in (data.get("part_link_groups") or [])]`;
  save `[list(g) for g in config.part_link_groups]`. No `schema_version`
  bump.
* `export_config` copies the groups. `apply_config` is best-effort: drop
  unknown part_ids, drop a part already in an earlier group, drop groups
  under two, then `set_part_link_groups`.

### 7.5 Region 2 prefix

Display only. Never in `display_name`, `PartStructureInfo.name` or
`NoteData.part_name` (invariant 8).

* `Region2Node` gains `link_group: Optional[int] = None` (part nodes only).
* `node_status_label` prefixes `f"{node.link_group}. "` when set. The path
  label just above it uses `display_name` directly and stays unprefixed -
  confirm that is right for its callers.
* `Region2HierarchyModel.apply_link_groups(numbers: Dict[str, int])` sets
  each root's `link_group`.
* `Region2ListWidget.apply_link_groups(numbers)` calls it then
  `_refresh_all_item_texts_and_notify()`. Never `load_score_structure`
  (invariant 11).
* `RegionPresenter.apply_link_groups` is what controllers call
  (invariant 6).
* Call after every group change, and on load after `apply_config` wherever
  `apply_muted_node_keys` is already called for a restored score.

### 7.6 Controller, dialog, menu

`controllers/score_edit_controller.py`, next to Reorder Parts:

* `link_dialog_rows() -> List[Tuple[str, str, Optional[int]]]` -
  `(part_id, part name, group number)` in current part order.
* `current_part_link_groups()`
* `apply_part_link_groups(groups) -> bool` - False if unchanged; else
  `music_data.set_part_link_groups`, presenter `apply_link_groups`,
  `update_timeline_views(play_all=False)`, True. Mark the config dirty the
  way reorder does, if it does.

`widgets/link_parts_dialog.py`, `LinkPartsDialog` (read
`docs/dialog_widget_patterns.md` first):

* `(parent, rows, groups, initial_part_id)`; works on a copy of the groups
  using the `models/part_links.py` rule functions; `part_link_groups()` for
  the window after Accepted.
* Title "Link Parts". `QListWidget` label "&Parts:", `ExtendedSelection`,
  one row per part: "1. Classical Guitar" or the bare part name, matching
  Region 2.
* "&Link" (enabled when two or more selected rows are all unlinked),
  "&Unlink" (enabled when the current row is linked), then OK/Cancel
  `QDialogButtonBox`.
* After Link/Unlink: update row texts in place, keep the current row on the
  same part, keep focus in the list. If a refusal must be spoken, use the
  app's existing QAccessible announcement helper - never row text.
* `showEvent`: deferred focus to the list, current row = `initial_part_id`,
  as `PartOrderDialog` does.

`widgets/menu_builder.py` `_parts_menu`: `a.link_parts`, "&Link Parts..."
after Reorder Parts, status tip "Mark parts that are the same music, so
each shows the others' performance markings". No default shortcut unless
the user asks. Add "Link Parts": "Parts" to `_CATEGORY_OVERRIDES` in
`controllers/shortcut_controller.py`, and the attribute to `Actions`.

`main_window.py` `_show_link_parts_dialog`, modelled on
`_show_part_order_dialog`: wiring only, dialog constructed there (tests
monkeypatch `main_window.LinkPartsDialog`), apply via
`self.score_edit.apply_part_link_groups(...)` on Accepted, restore Region 2's
selected node afterwards.

Add "Link Parts" to `docs/keystrokes.md` only if it lists menu items
without shortcuts (check the table's convention).

### 7.7 Tests

`tests/models/test_part_links.py` (new): link two; link three at once;
refuse one id, unknown id, already-linked id; unlink from a pair dissolves;
from a triple leaves a pair; renumbering after a dissolve; partners
symmetric.

Borrowed rows, on `files/etude 1 tablature.mxl` (or a minimal two-part
fixture if tests do not load `files/`):

* Linked: P2's staff group at bar 3 beat 2 carries the crescendo start;
  unlinked it does not.
* Still there with every P1 voice switched off.
* A dashed line, a pedal span, a dynamics word and an other direction on P1
  all appear on P2.
* Clef change not borrowed.
* Same marking on both parts at one position: one row on each.
* Category off hides borrowed rows.
* Stave text on P1 appears on P2, including on a slice where P2 has no
  notes and P1 is switched off; selecting it gives no notes and no audition.
* A dynamic on a P1 note appears as "Dynamic mf" on P2; not when P2's note
  already has mf; P2's Region 4 shows no dynamic.
* Region 5 rows, report lines, Find occurrences and playback events are
  identical with and without the link.

Persistence: round trip; stale group pruned; old `.rsc` loads with no groups.

Region 2 (`tests/widgets/test_region2_manager.py`): "1. Name" on linked
rows, bare name otherwise; muted/soloed suffix still follows the name;
toggles survive applying groups; a rename keeps the prefix; `parts_info`
names and `NoteData.part_name` unchanged.

Dialog (`tests/widgets/test_link_parts_dialog.py`, new) and window
(`tests/test_main_window_score_edit.py`): button enablement, Link/Unlink
texts, Cancel discards, OK applies and Region 3 shows a borrowed row, focus
returns, action in the "Parts" shortcut category.

Fingerprint: no `.rsc` means no links, so NO diff. Any diff is a bug.

### 7.8 Docs

`docs/architecture.md`: a short "Linked parts" paragraph - the collaborator,
display-only rule, where borrowing happens (`staff_level_rows`,
`region_3_data`), the Region 2 prefix mechanism. Not the user guide.

---

## Out of scope

* Linking individual staves inside a multi-staff part
  (`bach-bourree-tab.mxl`).
* A toggle for pedal and octave shift rows (no Region 5 row to press Ctrl+N
  on).
* Audibly realising any marking - still label-only (CLAUDE.md "Known gaps").
* Renaming internal identifiers (`InstrumentDialog` etc.) for terminology.

## Decisions settled with the user (2026-09-14)

* Parts menu and Instruments dialog unchanged.
* New note-list rows go after the existing ones; existing order unchanged.
* The four new Ctrl+N category names as written in 5.3.
* The performance attribute list in 5.5.
* Group numbers close up when a group is dissolved.
