# Performance markings strategy

Revision 4, 2026-09-14.

This document states how Recall Score surfaces performance information. It
describes the target model. Most of it is built. The classification model in
section 3 is new and not built yet; the build order is in
`UserPlans/PerformanceMarkingsImplementationPlanV2.md`.

Element-by-element references:

* `UserPlans/inventory.csv` - the authoritative association (level) for every
  MusicXML element, columns A to E.
* `UserPlans/MusicXMLMarkingInventory.md` - meanings and what the code does
  today. Its class column predates the classification model.

## 1. Purpose

Performance information must be reachable from the note list while reading
through a score, not only by leaving it for region 5.

## 2. Two regions, two questions

* Region 5 answers "what is in effect here". A pedal that started eight bars ago
  is shown while the cursor is inside it.
* Region 3 (the note list) answers "what happens here". A marking appears only at
  the event where it starts, the event where it ends, or the single event it
  occupies. It never repeats on the events in between; that is region 5's job, and
  it keeps a pedal-heavy piece from reading "Pedal" on every event.

## 3. The classification model

Every piece of information has a level and a dimension.

### 3.1 Level

| Level | Where it lives | Can also appear |
|---|---|---|
| Note | Region 4 (attributes of the selected notes) | Inline in the note's region 3 row, per voice, via the region 4 attribute toggles |
| Barline | Its own timeline event, with a measure number and the position "End of bar"; its detail shows in region 4 | - |
| Stave | Region 5 | A row in region 3, above all notes of that stave |
| Part | Region 5 | A row in region 3, above all staves of that part |
| Score | Region 5 | A row in region 3, at the top of the list |

Barline information is rare: a fermata, segno or coda written inside `<barline>`,
and the wavy line crossing a barline. Bar styles, repeats and endings are not
barline level in this sense; they are score or part level (section 3.3).

A barline always comes at the end of a bar, so its position is "End of bar". A pickup
bar is bar 0 and its barline is bar 0 "End of bar". A `location="left"` barline is the
end of the previous bar.

### 3.2 Dimension

* Point - one position.
* Length - a start and an end.

Many tags come in pairs (wedge start and stop, pedal start and stop). A matched pair
is a length. A tag with no partner is a point and is reported as a point, not as a
length with an invented or missing end.

`<dashes>` and `<bracket>` are not markings of their own; they extend the `<words>`
written in the same `<direction>` element. The pair is one length named by its words:
"cresc. start", "cresc. end". A line with no words reads "Dashed line" or "Bracket
line".

### 3.3 Deciding the level of one marking

`inventory.csv` lists the levels an element may take. Where it lists more than one,
the level of a particular instance is resolved in this order:

1. Score, if the element allows only score, or the `<direction>` carries
   `system="only-top"`, `system="also-top"` or `directive="yes"`.
2. Barline styles, repeats, endings, key and time: score when every part writes the
   same thing at that bar, otherwise part for each part that differs. MusicXML writes a
   barline in every part; this keeps a quartet from reading "Repeat start" four times.
3. Stave, if the element allows stave, the part has more than one staff, and the
   element names its `<staff>`.
4. Part otherwise.

Two elements have fixed rules:

* A note-attached `<fermata>` is a note attribute, and also gives one score-level row
  when every part with a note at that event carries a fermata, otherwise one
  part-level row per part carrying one. A fermata on a soloist's part alone is not
  score-wide.
* A `<direction><dynamics>` is a dynamic attribute of the notes at that offset and never
  a row; a row as well would report it twice.

For a one-staff part, stave and part place a row in the same spot.

Evidence for rule 1: `system` is MusicXML 4.0's replacement for the deprecated
`directive` attribute. 12 of the scores in `files/` and `examples/` use
`system="only-top"`, always on score-wide things - metronome marks, tempo words and
rehearsal marks. Multi-part exporters do not otherwise copy directions into every
part: across the orchestral files, only a handful of dynamics appear identically in
every part, and those are genuinely per-part dynamics.


### 3.4 Level versus attribute scopes

They look similar and do not collide:

* An attribute scope (voice, stave, part, score) is a display filter for note
  attributes. It never moves anything; a note's attributes render on that note's row.
* A level is a placement rule for marking rows. It filters nothing.

They act on disjoint rows. A marking row has no voice, so the scope machinery cannot
reach it, which is why marking rows need their own toggle (Ctrl+N, section 8).

Consequences:

* A stave-level marking appears once above that stave's notes, however many of its
  voices are visible. It is not repeated per voice.
* If every voice of a stave is switched off in region 2, that stave contributes no
  rows. The marking is still in region 5.
* A part-level marking is surfaced above the first visible staff of the part, so a
  reader navigating only the right hand of a piano still hears a pedal instruction
  the file recorded against the bass staff.

## 4. Note list rows

Row order at a cursor position:

1. Score-level rows.
2. For each visible part in region 2 order: that part's part-level rows, then for
   each staff: that staff's stave-level rows, then its notes.

Wording:

* Length start and end: "Crescendo start", "Pedal end", "Octave shift 8va start".
* Point: the bare name - "Segno", "Fine", "Rehearsal mark A", "Pedal change".
* A length whose start and end land on the same event reads as one bare row
  ("Ending 2"), not "Ending 2 end" followed by "Ending 2 start". Two different
  markings on one event still get two rows.
* Structural change: "Key signature change: D major", "Time signature change: 3/4",
  "Tempo change: 96".
* No part prefix; the row already sits under its part.

Anchoring:

* A start or point row attaches to the first event of its level at or after its
  position.
* An end row attaches to the last event of its level at or before its end position.
* A measure-anchored point (segno, coda) attaches to the first event of its bar; an
  end-of-bar mark (to coda, fine, da capo, dal segno, a right barline) to the last.
* A combined end-and-start repeat barline gives both rows, end first.
* A multi-bar rest has no event of its own (rests are skipped), so its row lands on
  the next event - read as the reader arrives after the rest.
* Rehearsal marks are snapped to the downbeat of their bar; MuseScore sometimes
  serialises them a few beats in.

Report every marking as written (CLAUDE.md invariant 14). Nothing is merged or
inferred, and one element gives one row. The words of a `<words>` direction read literally ("cresc.", "dim."), and
the bare word "Crescendo" is reserved for a wedge, which is what keeps the two
distinguishable.

## 5. Events that are not attacks

Left/Right lands only on attacks, with exactly two kinds of exception:

* Barline-level information (section 3.1). It sounds nothing, has no pitch, and sits
  between the last event of the bar it closes and the first event of the next. A
  fermata on the final barline is simply the last event. Everything written at one
  barline shares one event.
* A tied continuation note carrying a marking of its own (section 12).

Everything else - rehearsal marks, segno and coda written as directions, double
barlines, repeats, endings, structural changes - is a row on an existing event.
Making every score-level point its own event was rejected: Left/Right would halt on
every barline of a repeat-heavy score, slowing ordinary traversal for no extra
information.

## 6. Region 5

One row per length, stating the whole range:

* "Repeat bars 1 to 8", "Crescendo bar 2 beat 3 to bar 4 beat 4", "Pedal bar 4 to
  bar 6 beat 2", "Section Chorus, bars 17 to 32".
* Within one bar the bar is named once: "Ending 1 bar 12", "Crescendo bar 2 beat 1
  to beat 3".
* A beat is named only when not on the downbeat. Repeats, endings and sections fall
  on barlines and never name a beat.
* A position past the last beat reads "end of bar 12", never "bar 12 beat 5". A
  barline event's own position reads "End of bar". The
  timeline stores the barline after beat 4 of a 4/4 bar as beat 5 (the parser's
  `1 + offset / beat_unit` convention, used by span flushing at the end of a part and
  by the barline fermata); the fix is in the label, not the timeline.
* "bar" or "measure" comes from `vocabulary.bar_word`, never a literal.
* "repeat times" is included: "Repeat bars 1 to 8, play 3 times".
* Ctrl+Home jumps to the start of the row's range, Ctrl+End to the last sounding
  note of its end bar. `PerformanceRegionRow` carries both targets.
* Point and structural rows are one line.

Region 5 is the home of every stave, part and score marking, so every such family
has a region 5 row. Rows are ordered by level: score, then part, then stave.

Region 5's range wording and the note list's start/end wording come from one module,
`models/marking_labels.py`, which Find and the Performance Report also call. Find
keeps separate "Crescendo start" and "Crescendo end" targets, because those are
navigation targets rather than descriptions.

## 7. The change cue

The cue fires when the cursor lands on an event carrying a key signature, time
signature or immediate tempo change.

* Never at index 0; the opening values are already in region 1 and the status bar.
* The destination note's audition sounds first, then the cue. The audition's
  retrigger releases everything on its channel, so the reverse order cuts the cue off.
* One sound for all three; the row says which changed.
* Only an immediate tempo change fires it - a metronome mark or `<sound tempo>`. A
  rallentando written as words gets its rows and no cue.

## 8. Toggling note list rows (Ctrl+N)

* Every category is on by default, per score.
* Categories are per marking family, not per marking.
* Ctrl+N on a region 5 row toggles that row's category in the note list and speaks
  the new state ("Crescendo, not in note list"). The Menu key/Shift+F10 do the
  same toggle but through an actual one-item popup (worded "Add"/"Remove ... from
  note list") rather than firing it immediately - a silent immediate toggle gave
  NVDA nothing to announce on those two keys. All three are in the Keyboard
  Shortcuts reference.
* A category currently in the note list is prefixed "* " in region 5.
* Persistence: per score in the `.rsc` via `ScoreConfig`, global default in
  `AppSettings`.
* Ctrl+N is declared where its action is built and snapshotted by
  `ShortcutController` (invariant 16).
* A family can only be toggled if it has a region 5 row. Section 6 gives every stave,
  part and score family one, so every family gets a category.

The asterisk depends on NVDA's punctuation level: at level "none" it is silent. If
that matters, the fallback is the row's accessible description, not a longer visible
prefix.

## 9. Directives

Directives (`<direction directive="yes">`) are deprecated in MusicXML 4.0 in favour of
the `system` attribute. No score in `files/` or `examples/` uses one; the only
instance is the test fixture `tests/fixtures/stage7_directive.musicxml`.

A directive is parsed silently: it is treated exactly like `system="only-top"`, so its
content is an ordinary score-level direction. There is no region 1 directive list and
no directive-specific toggle.

## 10. Sounds

Existing sounds: the bar line indicator (Ctrl+B), the boundary cue at the timeline
ends, the metronome, the position announcer, and the change cue of section 7.

| Barline | Pattern |
|---|---|
| ordinary | one short beep |
| double (light-light) | two short beeps |
| heavy, heavy-light, heavy-heavy | one long lower beep |
| tick or short | one softer short beep |
| repeat end | two short, then one long |
| repeat start | one long, then two short |
| end and start | two short, one long, two short |
| final | nothing - the timeline end has its own cue |

The short beeps are the repeat dots, on the side of the long beep that the repeated
music is on, as printed.

* The plain beep is suppressed while the metronome runs; the other patterns sound
  anyway, because the metronome says nothing about barline meaning.
* Every pattern fires after the destination note's audition, and all are gated by
  Ctrl+B.
* The pattern is the same whichever direction the barline is crossed; the lookup is
  normalised to (lower bar, higher bar).
* Patterns are data (pitch, length, velocity steps) in `audio/barline_patterns.py` on
  a reserved channel. A multi-step pattern must not share a channel with another
  one-shot: FluidSynth releases a ringing note by channel plus key, so they cut each
  other off.

Help > Sound Icon Dictionary lists every sound with its meaning and a Play button,
always enabled, generated from the same declarations the audio modules use.

## 11. Hairpins

* A wedge whose start and stop resolve to one position is a point reading
  "Crescendo" or "Diminuendo" - never "hairpin".
* A swell (crescendo then diminuendo on one note) is two rows in file order. Nothing
  merges them into "swell"; that word is an interpretation.
* A wedge is not a dynamic. `<dynamics>` says "be this loud", a wedge says "change
  loudness"; both are reported.
* A wedge stop or start with no partner is a point (section 3.2).

## 12. Ties become duration

* The `tie` attribute is not surfaced. The head note of a tied chain reports the
  summed duration, named where a name exists ("dotted half") and otherwise in
  ts-relative beats ("duration 12 beats").
* Continuation notes are not events, so a tied chain is one navigation stop and
  playback sounds it once for the summed length.
* A continuation note carrying a marking (a fermata on the second half of a tie) is
  its own event where it is, so the marking neither vanishes nor moves. It reads
  "F sharp, tied, fermata" with the remaining length of the chain; the whole length is
  stated only at the head note, so the fact is not written twice (invariant 8).
  Arrowing onto it auditions the pitch (the audition says where you are); playback does
  not re-attack.
* Ties across a repeat or into a first-time bar sum the written length as printed,
  with no attempt to work out a particular pass.

Grace notes are unaffected: "A grace B", plus the `grace` attribute.

## 13. Articulations, ornaments and breath marks

* `articulation` and `ornament` are separate attributes, each toggleable, orderable
  and findable. Both are label-only; no ornament is audibly realised (CLAUDE.md
  "Known gaps").
* `breath-mark` and `caesura` are read both under `<notations>` and inside
  `<articulations>`, because exporters use both.
* Default display attributes are step plus the note-attached performance attributes:
  dynamic, articulation, ornament, slur, arpeggio, glissando, technique, other
  notation. A voice with a saved attribute set keeps it.

## 14. Architecture

* Marking rows are synthesised at render time by `models/marking_rows.py`, a
  `MusicData` collaborator, from the span and mark lists plus the visible timeline.
* Fabricating marking rows as silent events at parse time was rejected: an end row
  attaches to "the last visible event before the end", visibility depends on the
  region 2 filter, which changes long after parsing, and a fabricated row anchored to
  a note that is later hidden would vanish without trace.
* The events of section 5 are made at parse time by the timeline builders, because
  only the timeline decides where Left/Right stops. They are anchored to positions,
  not notes, so the objection above does not apply.
* Region 3 rows are typed (note row or marking row). Region 4's build,
  `get_playback_events_for_indices` and the select-all audition go through
  `note_indices_from_selection`, which drops marking rows. A marking row sounds
  nothing. With a marking row selected, region 4 shows that marking's detail (kind,
  bar and beat, range for a length) rather than note attributes.
* Region 3 is rebuilt on every cursor move inside Ref 9's 25 ms. Lookups use indexes
  built once per load (by measure, and by quarters per score, part and staff), never a
  scan of every span per keystroke.
* After `selectAll()` the explicit `setCurrentRow(0, NoUpdate)` rule (invariant 10)
  still applies; the current item may be a marking row, which is correct as long as a
  chord still sounds every note.
* Marking rows are ordinary rows for Up/Down.
* Stave text and rehearsal marks are currently fabricated `NoteData` on a
  `STAVE_TEXT_VOICE_ID` voice. Hiding only their row while the timeline event remains
  can leave a slice with visible notes and no rows, which is why they have had no
  category.

## 15. Out of scope

* Audible realisation of ornaments, trills, octave shifts, pedal and fermatas.
* `docs/user_guide.md` and its HTML, unless asked for separately.
