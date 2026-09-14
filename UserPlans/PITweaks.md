# PI tweaks

Small, self-contained refinements to the performance-information work that fall
outside `PerformanceMarkingsStrategy.md`'s build sequence. Each item states the
problem and the agreed solution. Nothing here is implemented yet; an
implementation plan follows separately.

---

## 1. Linked parts

### The problem

A score often carries the same music twice - a notated stave and a tablature
stave of the same guitar part - but writes the performance markings onto one of
them only.

`files/etude 1 tablature.mxl` (Carcassi, Etude No.1 Op.60, MuseScore Studio
4.7.4) is the reference case. It has two parts:

* `P1` "Classical Guitar" - treble clef, 43 measures, carries every
  `<direction>` in the file, including the crescendo at bar 3 beat 2.
* `P2` "Guitare classique [Tablature]" - `<clef><sign>TAB</sign></clef>` with
  six `<staff-tuning>` lines, the same 43 measures, and not one `<direction>`,
  wedge, dynamic or word anywhere in its body.

Recall Score surfaces the crescendo under "Classical Guitar" and nothing under
"Guitare classique [Tablature]", which is exactly what the file says. A tab
reader never visits the notated part, so the markings are unreachable for them.

MusicXML has no reliable way to say two parts are the same music. `<part-link>`
exists but links across documents, not within one, and MuseScore does not emit
it. `<part-group>` is a notation bracket, not a claim about content: the same
markup joins a piano's two hands or a pair of horns, where the staves are
complementary rather than duplicate, and its `<group-symbol>` is optional -
`files/bach-bourree-tab.mxl` pairs a notated and a tab stave under a group whose
symbol is the literal value `none`. Part names do not help either; in the
Carcassi file they are in different languages. The score author cannot be relied
on to encode the relationship, so Recall Score should not try to infer it.

### The solution

Let the user declare it. Recall Score gains user-defined LINK GROUPS: a set of
two or more parts the user asserts are the same music. Performance information
found on any part of a group is surfaced in the note list of every part of that
group.

Rules:

* A link group holds two or more parts. A single action can link any number of
  parts at once.
* A part belongs to at most one group. Linking a part that is already linked is
  refused; the user unlinks it first.
* Groups are numbered from 1 in creation order and identified to the user by
  that number.
* Membership is symmetric. There is no source and no target - every member
  contributes its markings to every other member.
* Link groups are display-only. They never change what sounds, and they never
  change what Region 5, the Performance Report or Find report, each of which
  continues to name the part the marking is actually written on.

Independence from part visibility is the point of the feature, not a special
case: a marking borrowed from another part appears in the note list whenever the
BORROWING part is visible, regardless of whether the part it came from is
switched off in Region 2. A tab reader can disable the notated part entirely and
still hear every marking.

### User interface

A Link Parts dialog, opened from the Parts menu. It lists the score's parts, the
user selects two or more and links them, or selects a linked part and unlinks it.
Unlinking a part removes it from its group; a group left with fewer than two
members is dissolved.

Region 2 shows membership by prefixing each linked part's row with its group
number and a full stop, so the Carcassi score reads:

```
1. Classical Guitar
1. Guitare classique [Tablature]
```

and a second linked pair in the same score would be prefixed `2.`. Unlinked
parts are shown unprefixed, exactly as now.

The prefix is a Region 2 display device only. It is never written into
`PartStructureInfo.name` or `NoteData.part_name` - those two already hold the
same fact and are joined by exact text in the Performance Report (invariant 8),
so prefixing either would silently break the report. Region 2 labels are mutated
in place for this, not rebuilt through `load_score_structure`, which would reset
every node to enabled and discard the user's toggles (invariant 11).

### Scope and constraints

* Groups are per score and persist in the `.rsc`.
* Membership is recorded by `part_id`, never by part name, so renaming a part
  cannot break a group.
* Which marking families are borrowed is a deliberate subset. Performance
  markings - hairpins, pedal, octave shift, dashed and bracketed lines, dynamic
  and tempo words, and the generic direction catch-all - are borrowed. Clef
  changes are not: a clef is a property of how a stave is written, and surfacing
  "Clef change: tab" on a notated part is noise.
* If two linked parts both carry the same marking at the same position, the
  borrowed copy is suppressed so the row is not shown twice on one part. Both
  remain listed in Region 5 and in the Performance Report, where they are two
  separate markings in the file and are reported as such.
* Stave text (the `<words>` rows such as "Allegro" and "Staccato") and note
  dynamics travel as `NoteData` rather than as marking rows, so they are out of
  scope for the first cut and are tracked as item 2 below.
* Linking applies to parts, not to individual staves. A score that puts the
  notated and tab staves in a single multi-staff part - `bach-bourree-tab.mxl`
  does - is therefore not addressed by this feature. If that case matters later,
  the fix is to widen group membership from `part_id` to `(part_id, staff)`
  without changing anything else about the model.

---

## 2. Stave text and dynamics on a linked part

Item 1 borrows marking rows. Two neighbouring families are not marking rows and
need their own decision:

* Stave text is fabricated in `parsers/timeline_builder.py` `_handle_direction`
  as a `NoteData` carrying `STAVE_TEXT_VOICE_ID` and the originating part's
  `part_id`, so it reaches the note list as a note row.
* Dynamics are attached to notes through `measure_state.pending_dynamics` and
  become a Region 4 attribute of those notes, so a linked part's notes carry no
  dynamic.

Open: whether either should be borrowed by a link group, and if so what the
borrowed row says and whether it participates in selection and audition.

---

## 3. Tidying and navigating the Performance Report

The Performance Report (Ref 29, `PerformanceRows.get_performance_report_lines`,
shown by `widgets/performance_report_dialog.py`) is currently a flat list of
strings with no interaction. Five changes, mostly one shared solution.

### 3a. Positions past the end of the bar

`files/pachelbels-canon-in-d-string-quartet.mxl` reports dynamics at beat 5 in a
4/4 score. Beat 5 does not exist in 4/4.

The cause is the "end of a bar" convention in `parsers/timeline_builder.py`:
`_PartState.beat_position(m_num, offset_q)` returns `1 + offset_q /
beat_unit_quarter_len`, so an offset of a whole bar (`full_bar_quarters`) yields
`1 + ts_num` - beat 5 in 4/4. `_flush_open_direction_spans` closes every span
still open at the end of a part at exactly that offset, and the barline fermata
moment event hardcodes the same `1.0 + ts_num` (line ~1153). The value is
internally consistent - it means "the barline after beat 4", one unit past the
last beat - but read aloud it is simply wrong.

The fix is at the reporting layer, not in the timeline: a position whose beat
equals `ts_num + 1` is the barline, and should be labelled as such ("end of
Bar 12" / "the barline after Bar 12") rather than "Bar 12 beat 5".
`MusicData._bar_beat_label` is the single place every report and Region 5 row
formats a bar/beat pair, so it is the place to decide this; it needs the bar's
time signature to know what "past the end" is. Audit the same question for span
ends generally - a hairpin that runs to the end of its part hits this path on
every score, so it is not specific to the Canon.

### 3b. Nothing with a count of zero appears

`_tally` already takes `omit_if_empty`, but only some call sites pass it, so a
score with no pedal prints "Pedal marks: 0" and a score with no repeats prints
"Repeated sections: 0". Every category is now omitted entirely - header line
included - when its count is zero. `omit_if_empty` stops being a parameter and
becomes the only behaviour; the hand-rolled sections that do not go through
`_tally` (Dynamics, Pedal marks) are brought into it.

The always-present preamble (title/composer/key/time signature, anacrusis, bar
count) is not a tally and is unaffected.

### 3c. Categories expand and collapse

The report becomes a `QTreeWidget` of two levels: each "<header>: <count>" line
is a top-level item, and its detail lines are its children. Collapsed by
default, so the first thing a screen reader user meets is a short list of what
the score contains rather than several hundred rows.

This reverses two decisions recorded in `PerformanceReportDialog`'s docstring -
"a flat QListWidget ... not a rich/nested tree control" and "deliberately no
jump-to-location navigation". Both were scope cuts, not findings; the docstring
is updated rather than worked around. NVDA reads a tree item's level and
expanded state natively, which is the accessibility argument for the change.

### 3d. Enter jumps to what the row describes

With focus on a row, Enter closes the report and goes there:

* a detail row that has a timeline position - a dynamic, a hairpin start, a
  rehearsal mark, a barline change - moves the cursor to that position and puts
  focus in Region 3 (the note list at the cursor).
* a part row under the parts tally puts focus on that part's row in Region 2.
* a header row, or a detail row with no single position (a bar count, a section
  that is a range), does nothing on Enter. It still expands and collapses with
  the usual keys.

This is what forces the report to stop being a list of strings. A row must
carry its own identity - the quarters-from-start (or slice index) it jumps to,
or the `part_id` it names - as item data, built alongside its text. Matching a
part by parsing its name back out of the row text is exactly the two-copies-of-
one-fact trap of invariant 8, and the note-count tally already joins
`parts_info.name` to `NoteData.part_name` by exact text; the structured row
should carry `part_id` and let the display text be display text.

Expect `get_performance_report_lines` to gain a structured sibling (one
dataclass per row: text, level, and an optional jump target) with the existing
string list kept as a thin wrapper, since `tests/manual/model_fingerprint.py`
fingerprints it and several tests assert on the lines.

### 3e. "Part", not "instrument"

The tally headed "Instruments" is a list of parts, keyed by `parts_info`, and
Region 2 calls them parts. The report says "Parts" too, and the wording is
consolidated on "part" wherever the report, Region 5 and the dialogs currently
say "instrument".

---

## 4. Repeat barline sounds when arrowing left

### The problem

`files/bach-bourree-tab.mxl`, Bar Line Indicator on. Right arrow from bar 8
beat 4.5 to bar 9 beat 1 correctly plays the repeat end sound. Left arrow from
bar 9 beat 1 back to bar 8 beat 4.5 plays only the plain barline beep.

The cause is argument order. `NavigationController.timeline_left` emits
`barline_crossed(before, after)` in the order the cursor moved, so a left step
sends `(9, 8)`. `audio/barline_patterns.py` `pattern_for_crossing` assumes
`before_measure` is the bar to the LEFT of the barline: it looks for a repeat
ending in `before_measure` and a repeat starting in `after_measure`, and does
the same left/right test for `barline_marks`. With `(9, 8)` nothing matches,
so it falls back to the plain beep. Every non-plain pattern (repeat start,
repeat end, both, double, heavy, tick) is affected the same way, not just
repeat end.

### The solution

The barline is the same barline whichever way it is crossed, so the pattern
must not depend on direction. `PlaybackController.play_barline_indicator`
passes `min(before, after), max(before, after)` to `pattern_for_crossing`.
The signal keeps its move-order meaning; only the lookup is normalised. Add a
test in `tests/audio/test_barline_patterns.py` or the playback tests that
crosses each pattern's barline leftward and gets the same kind as rightward.

---

## 5. One row for an ending that starts and ends on one event

### The problem

`files/bach-bourree-tab.mxl` bar 25 is ending 2, one bar long, with a single
event in it. `MarkingRows.score_level_rows` adds an end row when the event is
the last of the span's end bar and a start row when it is the first of the
span's start bar. With one event both hold, so the note list reads "Ending 2
start" and "Ending 2 end" together on the same event.

### The solution

When a span's start and end both land on the same event, emit one row with the
bare name ("Ending 2") instead of the start/end pair. This is the same rule
hairpins already follow (`staff_level_rows`: a wedge whose start and stop
resolve to one position is a point, "Crescendo", with no start/end word).

Apply it in `_add` inside `score_level_rows`, so it covers all three span kinds
it serves - repeats, endings and sections - not just endings. A one-bar repeat
or section containing a single event has the identical double row today.

Why it is safe:

* The start/end word is display text only. Nothing reads a `MarkingRow`'s
  start/end distinction; the row's `marking` is the span object either way.
* It is not a merge in the invariant 14 sense. The file writes one ending
  bracket, and one row reports one bracket. Two different markings on the
  same event (a repeat end and an ending end, say) still get two rows.
* Region 5, the Performance Report and Find are untouched. Region 5 already
  states the span as one range row ("Ending 2 bar 25"), and Find keeps its
  separate "Ending start" / "Ending end" targets, both of which still land on
  the bar.
* A one-bar span with more than one event is unchanged: start on the first
  event, end on the last.

---

## 6. (next item)
