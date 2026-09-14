# Performance markings - implementation plan, version 2

2026-09-14. Implements `UserPlans/PerformanceMarkingsStrategy.md`. Element levels,
dimensions and surfacing are in `UserPlans/inventory.csv`; an element not listed
there is not surfaced. This plan replaces
`PerformanceMarkingsImplementationPlan.md` and stages 6 and 7 of
`PITweaksImplementationPlan.md`.

## 1. Ground rules

* Read `CLAUDE.md` (all invariants) and `docs/architecture.md` before stage 1.
* One stage at a time, in order. Each stage ends with the whole suite green:
  `.venv\Scripts\python.exe -m pytest`.
* Every stage touching `parsers/` or `models/` runs the fingerprint harnesses in
  `tests/manual/` against a baseline from the commit before the stage
  (`tests/manual/README.md`). Each stage names the diff it expects; any other diff is a
  bug. After reviewing an expected diff, recapture the baseline.
* Do not commit or push unless the user asks. Do not edit `wishlist.txt`,
  `docs/user_guide.md`, `docs/user_guide.html` or `docs/quick_start.*`.
* When the spec and the code disagree, stop and report.
* The user reads replies through NVDA: short messages, no bold, `*` bullets.

## 2. Starting state

* The working tree holds uncommitted PI tweaks stage 5: marking rows for every family,
  categories `dynamics_words`, `tempo_words`, `other_directions`, `measure_styles`,
  wider `DEFAULT_DISPLAY_ATTRIBUTES`, pedal and note fermata rows at part level
  (`MarkingRows.part_level_rows`), and directives shown by default.
* Stave text and rehearsal marks are fabricated `NoteData` on `STAVE_TEXT_VOICE_ID`.
* Selecting only marking rows in region 3 gives region 4 "No note selected".

## 3. Rules every stage applies

Level of one marking (strategy 3.3):

1. Score if the element allows only score, or the `<direction>` has
   `system="only-top"`, `system="also-top"` or `directive="yes"`.
2. For barline styles, repeats, endings, key and time: score when every part writes the
   same thing at that bar, otherwise part for each part that differs.
3. Stave if the element allows stave, the part has more than one staff, and the element
   gives `<staff>`.
4. Part otherwise.

Note fermata: the `fermata` attribute stays. It also produces one score-level row when
every part with a note at that event carries a fermata, otherwise one part-level row
per part carrying one.

Direction `<dynamics>`: note attribute only, never a row.

One element, one row. A `<words>` direction gives one row. Its category is
`dynamics_words` or `tempo_words` when the allow-list matches, otherwise `stave_text`.

Dimension:

* A matched pair is a length: start row, end row, one region 5 range row.
* A length whose start and end anchor to the same event is one bare row.
* An unpartnered start or stop is a point, with the bare name.
* `<dashes>` or `<bracket>` in the same `<direction>` as `<words>` is one length named
  by the words ("cresc. start", "cresc. end"). Without words: "Dashed line", "Bracket
  line".

Barline position: a barline belongs to the end of a bar. Its position reads "End of
bar". A pickup bar is bar 0, so its barline is bar 0 "End of bar". A
`location="left"` barline is the end of the previous bar.

## 4. Stages

### Stage 0 - commit the starting state

Run the suite and harness, report, and ask the user to commit. Do not rework the
directive default or the part-level fermata; stages 2 and 3 replace them.

### Stage 1 - classification data and the `system` attribute

* New `models/marking_classification.py`, Qt-free: for each element, its allowed
  levels and dimension, from `inventory.csv` columns Element, Level and Dimension.
  This is the only place levels are declared.
* `parsers/timeline_builder.py`: record on `DirectionMark`, `DirectionSpan` and
  `HairpinSpan` a `system` value (`directive="yes"` recorded as `only-top`) and
  `staff_given: bool`.
* Tests: table lookups; `files/etude 1 tablature.mxl` has a metronome and a words
  direction with `system="only-top"` (build `MusicData(file_path=...)`).

Harness: new fields only.

### Stage 2 - one level rule, one placement path

* `models/marking_rows.py`: add `level_of(marking)` implementing section 3, and one
  path returning rows grouped as score, part (`part_id`) and stave (`part_id, staff`).
  Replace the family lists in `score_level_rows`, `part_level_rows` and
  `staff_level_rows` with it. Reuse `_add_span_rows` and `_add_point_row` with a key
  function per level. Keep `MusicData` delegators (invariant 4).
* Rehearsal marks: score level. Pedal: part level. Fermata rows: section 3.
* Keep the current row order inside each level.
* `models/note_renderer.py` `region_3_data`: score rows first; per part, part rows
  above its first staff group; stave rows above that stave's notes.
* Ref 9: time `region_3_data` over every slice of the largest file in
  `files/ManyParts/` before and after; report the numbers. Index by quarters per level
  if it slows.
* Tests: words with `system="only-top"` at the top; piano hairpin with `<staff>2`
  above the left hand only; the same in a one-staff part above that part; pedal on
  staff 2 above staff 1; repeat in a quartet read once at the top; a fermata on all
  parts gives one score row, on one part a part row.

Harness: region 3 rows change group only.

### Stage 3 - remove directives

* Delete `MusicData.get_directive_rows`, `toggle_directive_in_note_list`,
  `directives_hidden_from_note_list`, `directive_marks`, `models/directive_mark.py`,
  the region 1 Directives list and `directive_toggle_requested`,
  `RegionPresenter.toggle_directive_in_note_list`, the `main_window.py` connection,
  the directive rows in `marking_rows.py`, and the "Region 1 directive" wording in
  `ShortcutController`'s Ctrl+N description.
* `parsers/timeline_builder.py`: delete `_step_directive`. Stage 1 already maps
  `directive="yes"` to `only-top`.
* `ScoreConfig` and `persistence/score_config.py`: drop the directive field; ignore
  `directive_labels_in_note_list` and `directive_labels_hidden_from_note_list` on load.
* Tests: `tests/fixtures/stage7_directive.musicxml` words read as a score-level row;
  an old `.rsc` with either key loads.

Harness: directive fields removed.

### Stage 4 - region 5 rows and categories for every family

* `models/performance_rows.py`: region 5 rows for pedal spans and changes, octave
  shift, stave text, and fermata rows. Wording from `models/marking_labels.py`.
* Order region 5 rows by level: score, part, stave; existing kind order inside each.
* `models/marking_categories.py`: add `pedal` "Pedal", `octave_shift` "Octave shift",
  `stave_text` "Stave text", `fermatas` "Fermatas" to `ALL_CATEGORIES` and
  `CATEGORY_NAMES`. Tag the rows with them in both region 5 and `marking_rows.py`.
  Rewrite the module docstring: every family now has a category.
* Tests: each new region 5 row; Ctrl+N on it toggles its note-list rows and the
  asterisk; `.rsc` round trip.

Harness: region 5 rows added and reordered.

### Stage 5 - stave text and rehearsal marks become marking rows

Ships alone.

* First check and report: does a position holding only stave text currently create a
  Left/Right stop? After this stage it does not; the row anchors to the next event of
  its level.
* `parsers/timeline_builder.py`: stop adding `NoteData` for `<words>` and
  `<rehearsal>`. Record every qualifying `<words>` as a `DirectionMark` of kind `words`
  (allow-list matches keep `dynamics_word` / `tempo_word`). Rehearsal keeps its mark.
* `marking_rows.py`: words and rehearsal rows through stage 2's path, section 3's
  one-row rule and categories.
* Remove `STAVE_TEXT_VOICE_ID` rendering from region 2 and region 3,
  `is_rehearsal_text` and its region 4 label branch, and the note-backed marking-row
  case in `MusicData.note_indices_from_selection`.
* Find and the Performance Report must still list the words; move them onto the marks.
* Tests: "Allegro" above its part; "cresc." as one row; no stave text voice in
  region 2; a text-only position is not a stop.

Harness: expected diff in timeline events and region 3 rows of every score with text.

### Stage 6 - dimension rules

* `parsers/timeline_builder.py`: `_flush_open_direction_spans` no longer closes open
  spans; an unclosed start becomes a point. An unmatched wedge start or stop is a point.
  Dashes or bracket with words in the same `<direction>` produce one span carrying the
  words as its name; no separate words row for that element.
* `models/performance_rows.py` and `marking_labels.py`: remove "no end marked in the
  file" and "no start marked in the file" wording; points read the bare name.
* `CLAUDE.md` invariant 14: replace the example "a dashed line under a cresc. is two
  things in the file and gets two lines" with "a `<words>` and a `<dashes>` in one
  `<direction>` are one length marking named by the words; two separate `<direction>`
  elements are two markings".
* Tests: lone wedge start reads "Crescendo"; unclosed pedal reads "Pedal"; "cresc."
  with dashes gives "cresc. start" and "cresc. end" only; region 5 range row for it.

Harness: expected diff in spans, marks, region 3 and region 5 for affected scores.

### Stage 7 - barline events and region 4 for markings

Ships alone.

* Generalise the barline fermata event: a `<barline>` carrying `fermata`, `segno` or
  `coda` gives one event at the end of its bar (section 3), holding every such item.
  Remove the barline segno and coda rows added by `score_level_rows`. A right barline
  on bar N and a left barline on bar N+1 are the same event.
* Region 4 for a barline event: "Measure N", "Position End of bar", then one row per
  item.
* Region 4 for a selection of only marking rows: kind, bar and beat, and range for a
  length. No attribute context menu; Ctrl+N still works.
* Replace the stored `1.0 + ts_num` beat of the barline event's label with "End of
  bar" wherever it is spoken.
* Tests: `tests/fixtures/stage8_barline_fermata_interior.musicxml` and `_final`; a
  barline segno is an event; a pickup bar's barline event reads bar 0 "End of bar";
  region 4 contents for a barline event and a marking row.

Harness: expected diff on the barline fixtures only.

### Stage 8 - the report as a navigable tree

Implement `PITweaksImplementationPlan.md` stage 6 as written, plus jump targets:
words marks use `quarters_from_start`; barline events use their event index.

### Stage 9 - linked parts

Implement `PITweaksImplementationPlan.md` stage 7 as written, except:

* Borrow part- and stave-level rows only. Score-level rows are never borrowed.
* 7.3's stave text section is replaced: stave text is a marking row after stage 5 and
  is borrowed like any other.
* 7.3's borrowed "Dynamic mf" row is not built.
* A borrowed row keeps its level in the borrowing part.

### Stage 10 - low priority

* Key and time changes at part level when parts disagree (section 3 rule 2).
* `principal-voice` and barline `wavy-line` as lengths.
* Update `UserPlans/MusicXMLMarkingInventory.md` to match `inventory.csv`, or delete it
  if the user prefers.

## 5. Order

0, 1, 2, then 3 and 4 in either order, then 5, 6, 7, 8, 9. Stage 10 any time after 2.
