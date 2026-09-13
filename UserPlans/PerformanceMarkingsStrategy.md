# Performance markings strategy

Status: revision 3, 2026-09-13. Revision 1 was the proposal, revision 2 folded in the
first round of review. This revision folds in the second round, closes every open
question, and leaves nothing undecided. Nothing here is implemented yet; the ordered
build sequence is in `UserPlans/PerformanceMarkingsImplementationPlan.md`.

Companion document: `UserPlans/MusicXMLMarkingInventory.md` - every MusicXML element
that can carry a performance marking, what it means, what Recall Score does with it
now, and which class of this strategy it lands in.

Decisions taken in review, in one place:

* Region 5 span rows become a single line stating the whole range.
* Note list rows are toggled with Ctrl+N on the region 5 row, and a surfaced
  category is prefixed with an asterisk in region 5. The context menu stays as the
  discoverable equivalent.
* Toggles are per score.
* Key, time and tempo changes are surfaced in the note list too, and the
  change cue (the clap) is retired as a generic "region 5 changed" signal and
  re-used for exactly those structural changes.
* Marking rows are not skipped by Up/Down in region 3.
* Repeat barline patterns sound even while the metronome is running; the plain
  barline beep stays suppressed.
* More barline sounds: double beep for a double barline, a lower long beep for a
  heavy barline, a softer beep for tick and short barlines.
* A Sound Icon Dictionary page under Help, listing every sound with its meaning and
  a button to play it.
* Directives are score level and are listed in region 1.
* Articulations and ornaments split into two attributes; breath marks read properly.
* Ties are not surfaced; instead a note's duration is the whole tied length.
* Architecture option B - marking rows synthesised at render time.

Decisions taken in the second round of review, folded into the sections below:

* A marking that belongs to a moment rather than to a note becomes its own timeline
  event, in exactly two cases and no others: a fermata on a barline, and a marking
  carried by a tied continuation note. Everything else stays a row anchored to an
  existing event (section 5.1).
* A span contained in one bar reads singular - "Ending 1 bar 12" (section 6).
* One cue for all three structural changes, and only an immediate tempo change fires
  it, never a gradual instruction written as words (section 7).
* Directives are listed in region 1 and are not in the note list by default; Ctrl+N on
  the region 1 entry adds one (section 9).
* The word "hairpin" is not used for a one-event wedge; it reads "Crescendo" or
  "Diminuendo" (section 11).
* With a marking row selected, region 4 shows that marking's own detail (section 4.1).
* The Sound Icon Dictionary is always enabled, with or without a score (section 10.1).
* The asterisk prefix is kept, subject to the live punctuation-level check (section 8).

## 1. The problem in one sentence

Performance information is currently only reachable by leaving the note list and
reading region 5, so in practice it is not read at all while playing through a score.

## 2. What exists today

Four surfaces already carry marking information, each built from its own data:

* Region 3 (the note list). Notes, plus two kinds of fabricated non-note event: a
  "Stave Text" voice entry for every qualifying `<words>` direction, and a
  "Rehearsal mark A" entry on that same voice. Both attach to the real part and staff
  the direction sits in, and both already fall out of region 2's part/staff/voice
  tree for free.
* Region 4 (attributes of the selected notes). Everything hanging off a `<note>`:
  dynamic, articulation (articulations and ornaments merged into one field), tie,
  slur, tuplet, fermata, arpeggio, cautionary accidental, technique, glissando,
  grace, chord symbol, chord diagram, and the `other notation` catch-all. Each is
  toggleable per voice from region 4's context menu, ordered by
  Options > Reorder Attributes.
* Region 5 (performance markings). A start row and an end row for every span
  containing the cursor, plus one-shot rows for a key, time or tempo change landing
  exactly on the cursor, plus point marks. Ctrl+Home and Ctrl+End jump to a row's
  start and end. A change of the row set fires the performance cue.
* The Performance Report and Find. Both read the same span and mark lists, and Find's
  labels are copied verbatim from region 5's wording so the two cannot disagree.

Sound today: Ctrl+B bar line indicator (one high click when a plain Left/Right step
crosses a bar line, suppressed while the metronome is on), the boundary cue at the
ends of the timeline, and the region 5 change cue.

Parser-side the data already exists as `RepeatSpan`, `EndingSpan`, `HairpinSpan`,
`DirectionSpan` (pedal, octave shift, dashes, bracket), `DirectionMark` (rehearsal,
pedal change, dynamics word, tempo word, other direction), `BarlineMark`,
`SectionSpan`, `ClefChangeMark`, `MeasureStyleMark`, `SegnoMark`, `CodaMark`,
`ToCodaMark`, `FineMark`, plus `tempo_changes` and the per-slice key and time
signature. Spans carry `part_id` and `staff` already; hairpins and direction spans
carry both a ts-relative beat position and a monotonic `quarters_from_start` for each
end.

So the raw material is essentially all parsed. This strategy is almost entirely about
presentation rules, plus a short list of parser gaps in the inventory.

## 3. The organising idea

Two regions, two different questions:

* Region 5 answers "what is in effect here" - context. A pedal that started eight
  bars ago is still shown while the cursor is inside it.
* Region 3 answers "what happens here" - events. A marking appears in the note list
  only at the event where it starts, at the event where it ends, or at the single
  event it occupies. It never repeats on the events in between.

Region 1 gains a third question: "what does this score tell the performer overall" -
the directive list of section 9.

## 4. Classifying a marking

Every marking is classified on two independent axes. The classification decides its
behaviour everywhere, so there are no per-element special cases.

Axis A - what it is attached to:

* Note-attached: it hangs off a `<note>` element (articulations, ornaments, slurs,
  technical marks, note-level dynamics). It is an attribute. It stays in regions 3
  and 4 through the existing attribute machinery and never becomes a marking row.
  The boundary rule is purely structural: inside `<note>` means attribute, inside
  `<direction>` or `<barline>` means marking.
* Point marking: a `<direction>` or barline feature that occupies one position and
  has no written extent (segno, coda, fine, da capo, rehearsal mark, pedal change, a
  tempo or dynamics word, a clef change, a double barline, and a zero-length wedge -
  see section 11).
* Span marking: a `<direction>` with a written start and stop (hairpins, pedal,
  octave shift, dashes, bracket), a barline pair (repeat, ending), or a derived span
  (section).
* Structural state: key signature, time signature, tempo. No end; in effect until
  countermanded. Treated as points at the position where they change.

Axis B - who it applies to:

* Score level: applies to every part (tempo, rehearsal marks, jump instructions,
  repeats, endings, sections, barlines, time signature, key signature, directives).
* Part or staff level: applies to one part, and possibly to one staff of it
  (hairpins, pedal, octave shift, stave text, clef changes, dynamics).

Axis B decides exactly one thing: where the row is placed in the note list.

### 4.1 Axis B versus attribute scopes - is there a conflict?

No, and the reason is worth stating plainly because the two look similar.

* An attribute scope (voice, stave, part, score) answers "which voices should display
  this attribute of a note". It is a display filter over note attributes, chosen from
  region 4's context menu, and it never moves anything - a note's attributes are
  always rendered on that note's own row.
* Axis B answers "which row does this marking sit above". It is a placement rule for
  non-note rows and it has no filtering role at all.

They cannot collide because they act on disjoint sets of rows: attribute scopes act
on note rows, axis B acts on marking rows. A marking row has no voice, so nothing in
the voice/stave/part/score scope machinery can reach it, and it needs its own toggle -
which is what Ctrl+N in section 8 is.

Three consequences worth writing into the implementation notes:

* A marking that belongs to a staff appears once above that staff's notes, however
  many voices of that staff are visible. It is a property of the staff, not of a
  voice, so it is not repeated per voice.
* With a marking row selected in region 3, region 4 shows that marking's own detail
  (kind, bar and beat, and for a span its full range) rather than note attributes, and
  the region 4 attribute context menu is not offered - there is no note to scope.
  Ctrl+N still works, because it acts on the marking.
* If every voice of a staff is switched off in region 2, that staff contributes no
  rows at all, marking rows included. The marking is still in region 5, which is the
  safety net.

## 5. Note list rows

Row order in region 3 at a given cursor position, top to bottom:

1. Score-level marking rows for this event.
2. Then, for each visible part in region 2 order, and each staff within it: that
   staff's part-level marking rows, then that staff's notes.

So a hairpin on the piano left hand reads immediately above the left hand's notes,
and a rallentando that applies to everyone reads once at the top.

Row wording, one pattern throughout:

* Span start: "Crescendo start", "Pedal start", "Repeat start", "Octave shift 8va
  start".
* Span end: "Crescendo end", "Pedal end", "Repeat end".
* Point: the bare name, no start or end word - "Segno", "Fine", "Da capo",
  "Rehearsal mark A", "Pedal change", "Double barline", "Crescendo hairpin".
* Structural change: "Key signature change: D major", "Time signature change: 3/4",
  "Tempo change: 96". These are new to the note list in this revision - previously
  they were region 5 only.
* Part prefixing: a note list row is already positioned under its part, so it is not
  part-prefixed.

Anchoring rules, stated once and applied to every kind:

* A span start row attaches to the first visible event at or after the span's start
  position.
* A span end row attaches to the last visible event at or before the span's end
  position - "the last event before a repeat end".
* A point row attaches to the first visible event at or after its position; a
  barline-anchored point attaches to the first event of the bar it opens or the last
  event of the bar it closes.
* Both start and end rows go above that staff's notes. One rule for both is
  deliberate: the word "end" in the label carries the meaning, and a single placement
  rule keeps row order stable, which matters because region 3 is rebuilt on every
  cursor move.
* A combined end-and-start repeat barline produces both rows, end first.
* Nothing is merged or inferred. A dashed line under a "cresc." is still two rows, as
  the file wrote it (CLAUDE.md invariant 14). The one deliberate exception in this
  revision is ties, section 12, where the merge is of a note with itself.

What deliberately does not get a row: a span the cursor is merely inside. That stays
region 5's job, and it is what keeps the note list from filling with "Pedal" on every
event of a pedal-heavy piece.

### 5.1 Markings that get their own event - the narrow rule

Two markings belong to a moment rather than to a note, and anchoring them to a
neighbouring note would misstate where they are. These become real timeline events
that Left/Right lands on:

* A `<fermata>` inside a `<barline>` (section 13).
* A marking carried by a tied continuation note (section 12).

Everything else - rehearsal marks, segno, coda, double barlines, repeat and ending
boundaries, structural changes - stays a row anchored to an existing event under the
rules above. This was weighed in review against generalising "a moment gets its own
event" to every score-level point marking, and the narrow rule was chosen: the broad
version would stop Left/Right on every barline in a repeat-heavy or rehearsal-marked
score, which makes ordinary traversal slower for no gain in information. The rows are
read in region 3 either way; the only difference is whether arrowing halts on them.

A moment event sounds nothing on arrival, has no pitch and no duration, and is score
level, so it reads at the top of the note list. The one exception is the tied
continuation event, which does have a pitch - see section 12.

## 6. Region 5 rows become one line per span

Today a span produces two rows, a start row and an end row. From this revision a span
produces one row stating the whole range:

* "Repeat bars 1 to 8"
* "Crescendo bar 2 beat 3 to bar 4 beat 4"
* "Ending 1 bars 12 to 13"
* "Pedal bar 4 to bar 6 beat 2"
* "Section Chorus, bars 17 to 32"

Rules that follow:

* A span contained in a single bar reads singular, and the bar is named once:
  "Ending 1 bar 12", "Repeat bar 12", "Section Chorus, bar 17", and where beats differ
  within that bar, "Crescendo bar 2 beat 1 to beat 3". The plural "bars N to M" and
  the repeated bar number appear only when the two bar numbers actually differ. This
  is a general rule for every span kind, not a special case for endings.
* A beat is named only when the position is not on the downbeat, which is the
  existing `_bar_beat_label` behaviour. Repeats, endings and sections fall on
  barlines by construction and so never name a beat.
* "bar" versus "measure" still comes from `vocabulary.bar_word`, never a literal.
* An unmatched wedge keeps its current honest wording: "Crescendo from bar 23, no end
  marked in the file".
* Ctrl+Home and Ctrl+End now act on one row rather than two: Home jumps to the start
  of the span, End to the last sounding note of its end bar, exactly as the two rows
  do today. `PerformanceRegionRow` grows a second jump target rather than the list
  growing a second row.
* Point and structural rows are unchanged - they were always one line.
* The note list keeps the "start" and "end" wording of section 5, because there a row
  marks one event rather than describing a range. Both renderings come from one
  labelling module so the vocabulary cannot drift; Find keeps its separate "Crescendo
  start" and "Crescendo end" targets, because those are navigation targets, not
  descriptions.
* Halving the row count also halves what the region 5 diff has to compare, and makes
  the region readable in one pass.

## 7. The change cue (the clap)

Today the clap fires whenever the region 5 row list changes. Once markings are in the
note list that signal is largely redundant - the information is already being spoken
where the user is.

Decision: retire the generic "region 5 changed" trigger and re-use the cue for
structural changes only - a key signature change, a time signature change, and a
tempo change. These are the changes that alter how everything afterwards is read, and
they are otherwise easy to miss.

* The cue fires when the cursor lands on an event carrying a structural change row.
* Never at index 0 - the opening key, time and tempo are already in region 1 and the
  status bar on load.
* Same ordering rule as today: the destination note's audition sounds first, then the
  cue, because the audition's retrigger releases everything on its channel.
* One cue for all three, not three different sounds (decided in review). The row
  itself says which of the three changed, so a second dimension of sound would only
  add something to learn.
* Only an immediate tempo change fires it - a new metronome mark or a `<sound tempo>`
  (decided in review). A gradual instruction written as words, a rallentando or an
  accelerando, does not: it still produces a marking row and a region 5 row, it just
  does not clap. Beyond being the only reliably detectable case today, this is the
  right meaning - the cue says "everything after this is read differently", which is
  true of a new metronome mark and not of a rall. that is already being read as text.

## 8. Turning note list rows on and off

* Default on for every category.
* Granularity: per marking category (repeats and endings, sections, hairpins, jump
  instructions, pedal, octave shift, lines, barlines, stave text, clef changes,
  structural changes), not per individual marking.
* Ctrl+N, with focus on a region 5 row, toggles that row's category in and out of the
  note list, and speaks the new state ("Crescendo, in note list" / "Crescendo, not in
  note list"). The same action is on region 5's context menu (Menu key and Shift+F10)
  so it stays discoverable, and in the Keyboard Shortcuts reference.
* Feedback while arrowing region 5: a category currently surfaced in the note list is
  prefixed with an asterisk and a space - "* Crescendo bar 2 beat 3 to bar 4 beat 4".
* Persistence: per score in the `.rsc` through `ScoreConfig`, with a global default
  in `AppSettings`, matching display attributes and region 2 toggles.

Caveat to check live before committing to the asterisk: NVDA speaks an asterisk as
"star" at its default punctuation level, but a user running punctuation level "none"
will hear nothing at all, and the prefix becomes invisible rather than subtle. The
fallback, if that turns out to matter, is a spoken word prefix, or leaving region 5's
text alone and putting the state in the row's accessible description instead. This is
a five-minute live test, not a design question.

## 9. Directives

`<direction directive="yes">` is MusicXML's one explicit marker for text that is a
score-wide instruction rather than a local one ("Play with vigour", "Jauntily"). They
are score level in scope, but nothing stops an exporter placing them anywhere in the
piece.

* Region 1 gains a Directives list: "Directive: Jauntily (bar 12)", one entry per
  directive in bar order. Region 1 is the score overview, which is exactly what a
  list of the score's standing instructions is.
* A directive is not in the note list by default (decided in review). Some directives
  genuinely belong to a moment in the music and some are standing instructions for the
  whole piece, and the file does not distinguish them - so the choice is the user's.
  Ctrl+N on a region 1 directive entry, and the same item on region 1's context menu,
  adds that directive to the note list as a score-level point row at its own bar, and
  removes it again. The state is per score in the `.rsc`, exactly like the region 5
  toggles of section 8.
* This gives region 1 and region 5 one gesture with one meaning - Ctrl+N on a row that
  describes a marking puts that marking in the note list - rather than two mechanisms
  to learn. It also settles the revision 2 open question about directives appearing in
  both places at once: they appear in region 1 always, and in the note list only when
  asked for.

## 10. Sounds

Existing sounds keep their meanings: the bar line indicator beep, the boundary cue at
the ends of the timeline, the metronome, the position announcer, and the change cue
as redefined in section 7.

New and changed barline sounds:

| Event | Pattern |
|---|---|
| ordinary barline | one short beep (today's behaviour) |
| double barline (light-light) | two short beeps |
| heavy barline (heavy, heavy-light, heavy-heavy) | one long beep, lower pitched |
| tick or short barline (mensurstrich) | one short beep, softer |
| repeat end (backward) | two short, then one long |
| repeat start (forward) | one long, then two short |
| combined end and start | two short, one long, two short |
| end of system | nothing new - the existing cue covers it |
| final barline | nothing - the end of the timeline has its own cue |

The repeat mnemonic is worth putting in the code comment: the shorts are the repeat
dots, and they sit on the side of the long that the repeated music is on, exactly as
the notation prints them.

Rules:

* The plain barline beep stays suppressed while the Ctrl+M metronome is running; the
  repeat, double, heavy and mensurstrich patterns sound anyway, because the metronome
  tells you about beats and nothing about barline meaning. (Decided in review.)
* Every pattern fires after the destination note's own audition, never before.
* All of it is still gated by the Ctrl+B bar line indicator toggle.

Implementation: a single new module beside `audio/boundary_cue.py` and
`audio/performance_cue.py`, owning one reserved channel, with the patterns declared
as data (a list of pitch, length and velocity steps) rather than as code per pattern.
A multi-note pattern must not share a channel with another one-shot, because
FluidSynth releases a ringing note by channel plus key and the two would cut each
other off. Total pattern length matters: the longest is five steps, and it has to fit
comfortably inside a fast Left/Right repeat without queueing up.

### 10.1 Sound Icon Dictionary (Help menu)

A new dialog, Help > Sound Icon Dictionary, listing every sound the app makes: name,
what it means, and when it fires, with a Play button so the user can hear it on
demand. A list plus buttons, so `docs/dialog_widget_patterns.md` applies - and the
initial focus rule from the same document: focus the literal first widget in tab
order.

The dictionary should be generated from the same declarations the audio modules use,
not a hand-written second list, or it will drift from the sounds themselves. Entries
to cover: barline beep and each of its patterns above, boundary cue, structural
change cue, metronome click and accent, position announcer, performance cue, live
MIDI input cue, voice control cues, lead-in.

## 11. Hairpins that are one event long

You are right that a wedge can start and stop at the same position, and it is not the
same thing as a point dynamic.

* A `<wedge>` whose start and stop resolve to the same position becomes a point, not
  a span, and reads "Crescendo" or "Diminuendo" (decided in review: the word "hairpin"
  is not added to the one-event case). The span case keeps "Crescendo start" and
  "Crescendo end", so the three readings stay obviously related without a fourth word.
* The wording therefore has to carry the distinction from a written "cresc.". A
  `<words>` direction reads its literal written text - "cresc.", "dim.", "cresc. poco
  a poco" - exactly as the file wrote it, and "Crescendo" as a bare word is reserved
  for the wedge. Reporting each as written is what keeps them apart, and it is what
  invariant 14 asks for anyway.
* The only case that reads "Hairpin" is a stop with no start anywhere in the file,
  where the direction genuinely is not knowable; the wording there says so: "Hairpin
  ending bar 12, no start marked in the file".
* A crescendo and a diminuendo on the same note (the swell, messa di voce) produces
  two rows, "Crescendo hairpin" then "Diminuendo hairpin", in file order. It is two
  elements in the file and it gets two rows (invariant 14). Nothing merges them into
  a single "swell", because that word is an interpretation and the file does not say
  it.
* This is not covered by a point dynamic being an attribute. A `<dynamics>` mark says
  "be this loud"; a wedge says "change loudness", and on a single note that is an
  instruction about the shape of that one note. They are different elements with
  different meanings and both are reported.
* Span rows stay as they are for wedges with real extent.

## 12. Ties become duration

Decision: ties are not surfaced as a marking or as an attribute. Instead a note's
duration is the whole sounding length of the tied chain.

* The `tie` attribute is removed from region 3, region 4 and the Find target list.
* The head note of a tie chain reports the summed duration, named where a name
  exists - "dotted half", "double whole" - and stated in beats where no single note
  name covers it: "duration 12 beats". Beats are ts-relative, per Ref 18, so a tied
  chain in 6/8 counts in eighths.
* The continuation notes of the chain are not separate events. This follows from the
  timeline convention that navigation lands on attacks only (invariant 15): a tied-to
  note is not a new attack, and leaving it in the timeline would both double-count the
  note and contradict the summed duration.

That last point is the only genuinely invasive change in this document, so it is worth
being explicit about the knock-ons:

* Navigation: a tied chain becomes one stop, not several. Bar counts, Go to Measure
  and Find results are unaffected because they key off bar numbers, not event counts.
* Playback: the note is sounded once and held for the summed duration, which is what
  a tie means and what the current two-attack rendering gets wrong.
* The parser and model fingerprint harnesses will report differences for every score
  containing a tie. That is the intended behaviour change, and the baselines get
  recaptured after review.
* A marking attached to a continuation note (a fermata on the second half of a tie, a
  dynamic, an articulation, a hairpin end) must not vanish with the attack it was on.
  It stays exactly where it is and becomes its own timeline event, which Left/Right
  lands on (decided in review; revision 2 moved it to the head note instead, and this
  supersedes that). Nothing moves and nothing is restated, which is the better fit
  with "report every marking as written".
* A continuation note carrying no marking is not an event at all, so an ordinary tied
  chain is still a single stop.
* A tied continuation event has a pitch, unlike the barline fermata of section 13.
  Arrowing onto it auditions that pitch: navigation audition and sequencer playback
  are separate paths, and the audition's job is to tell you where you are. Playback
  does not re-attack - the note is still being held, which is the whole point of the
  tie.
* The row reads the pitch, a word placing it inside the tie, and the marking:
  "F sharp, tied, fermata". Its duration is the remaining length of the chain from
  that point, because the whole chain's length is already stated at the head note and
  repeating it there would be the one fact written twice (invariant 8).
* Ties across a repeat or into a first-time bar: the summed length is the written
  length, following the ties as printed. No attempt is made to work out what the
  duration would be on a particular pass through the repeat structure.

Grace notes are unaffected and keep their current handling: the step still reads "A
grace B" so the grace note's pitch is spoken, and the `grace` attribute still says
whether it is an acciaccatura or an appoggiatura.

## 13. Fermata on a barline

A `<fermata>` inside a `<barline>` is a pause on the barline itself, currently not
parsed at all.

* It becomes its own timeline event at the barline position, associated with no note
  (decided in review; revision 2 anchored it to the first event of the following bar,
  and this supersedes that). Left/Right lands on it, it reads "Fermata on barline",
  and it sounds nothing - there is no pitch to audition.
* Its position is the end of the bar it closes, so it sits between the last event of
  that bar and the first event of the next. A fermata on the final barline needs no
  special case under this rule: it is simply the last event in the timeline.
* It is score level, so it reads at the top of the note list.
* It is one of the two moment events of section 5.1, and the reason the narrow rule
  exists: a pause on a barline is genuinely not a property of the note before or after
  it, and attaching it to either would say something the file does not say.

## 14. Articulations, ornaments and breath marks

* Articulations and ornaments are split into two attributes, `articulation` and
  `ornament`, instead of today's single merged comma-joined field. Each is separately
  toggleable, separately orderable and separately findable. Both stay label-only - no
  ornament is audibly realised, which remains a standing decision.
* Breath marks are read properly. What "read properly" means, since the inventory
  wording was unclear: today a `<breath-mark>` is only picked up when it happens to
  sit inside `<articulations>`, where it is swept into the merged articulation text
  along with everything else; when an exporter writes it directly under `<notations>`
  it is dropped entirely. The change is to look for it in both places and give it its
  own value in the articulation attribute, so it is reliably present and findable
  rather than dependent on where the exporter put it. The same applies to `caesura`.

## 15. Architecture: how the rows get into region 3

Decided: option B. Marking rows are synthesised at render time, in a new `MusicData`
collaborator (`models/marking_rows.py`), from the span and mark lists plus the
currently visible timeline. The parsers are untouched, so the fingerprint harnesses
stay clean for everything except the tie change of section 12, which is a deliberate
behaviour change.

(Option A - fabricating marking rows as silent events at parse time, the way stave
text already works - was rejected because a span end row has to attach to "the last
visible event before the end", and what is visible depends on the region 2 filter,
which changes long after parsing. A fabricated row would be anchored to a note that
can later be hidden, and the marking would vanish without trace.)

Option B covers every row that hangs off an existing event, which is all of them bar
the two moment events of section 5.1. Those two are not rows at all - they are
timeline entries, because Left/Right has to stop on them, and only the timeline
decides where Left/Right stops. So the work splits cleanly:

* Render time, `models/marking_rows.py`: every marking row in section 5.
* Parse time, the timeline builders: the barline fermata event, and the tied
  continuation event. Both are new event kinds carrying no attack, and both are
  therefore visible to the fingerprint harnesses - expected, and recaptured with the
  tie change of section 12, which they ship alongside.

The option A objection does not apply to these two. It was that a fabricated row
anchored to a note can lose its anchor when region 2 hides that note; a moment event
is anchored to a position, not to a note, so there is nothing to lose. The tied
continuation event does sit inside a part and is hidden with it, which is correct -
it is that part's marking.

What option B costs: region 3's rows become typed (note row or marking row) rather
than bare strings, and the three consumers of the row index - region 4's rows,
`get_playback_events_for_indices`, and the select-all audition - must skip marking
rows. Selecting a marking row shows its own detail in region 4 and sounds nothing.

Things to hold on to while implementing:

* Region 3 is rebuilt on every cursor move, and Ref 9 gives 25 ms for the whole move
  including the audition. The marking lookup must be a prebuilt index (bar number, and
  quarters, to the markings anchored there) built once per load, not a linear scan over
  every span on every keystroke.
* One source for label text. Region 5's one-line range rendering and the note list's
  start/end rendering are two renderings of one vocabulary, in one module, which Find
  and the Performance Report also call.
* The `selectAll` plus explicit `setCurrentRow(0, NoUpdate)` rule (invariant 10)
  still applies. With a marking row possibly at row 0, the current item after a move
  may be a marking row, which is correct - it is the first thing to announce at that
  position - as long as the chord audition still sounds every note row.
* Marking rows are ordinary rows for Up/Down (decided in review: not skipped).
* Ctrl+N goes into `ShortcutController`'s snapshot the same way as every other
  default, declared where its action is built, never copied into a table
  (invariant 16).

## 16. Suggested phasing

1. Region 5's one-line span rows, plus the two jump targets per row. Self-contained,
   immediately useful, and it shrinks what everything downstream has to diff.
2. The typed row model in region 3, moving the existing stave text and rehearsal mark
   entries onto it. Behaviour unchanged, harnesses green.
3. Repeats, endings and sections as note list rows, plus the new barline sound
   patterns and the Sound Icon Dictionary.
4. Hairpins, including the zero-length point case and the vocabulary of section 11,
   with the per-part and per-staff placement rule.
5. Structural changes as note list rows, and the change cue repurposed (section 7).
6. Points: segno, coda, to coda, fine, da capo, dal segno, rehearsal marks, double
   and other barlines, clef changes, the barline fermata, directives and the region 1
   directive list.
7. Spans: pedal, octave shift, dashes, bracket.
8. Ctrl+N, the asterisk prefix, the region 5 context menu and per-score persistence.
   Until this ships, everything above is simply on.
9. The tie and duration change of section 12, on its own, with fresh fingerprint
   baselines.
10. Articulation and ornament split, and breath marks.

Steps 1 to 8 are additive and safe to interleave with other work; step 9 is the one
that changes existing behaviour and deserves its own pass and its own live test.

The Performance Report is deliberately untouched by all of this and is the next piece
of work after it.

## 17. Decisions record - nothing left open

Every question revision 2 raised has an answer. They are recorded here so the
implementation plan can be read without re-deriving them.

1. Ties versus "report every marking as written". Resolved, and better than revision 2
   proposed: a marking on a continuation note does not move to the head note, it
   becomes its own event where it is (section 12). The merge is now only of silence
   with sound - the notes that carry nothing - which is exactly what a tie is. A tied
   chain with no markings in it is a single navigation stop.
2. Directives in region 1 and in the note list. Resolved: region 1 always, note list
   only when Ctrl+N asks for it (section 9).
3. The asterisk prefix. Kept, and still subject to the five-minute live check with
   NVDA punctuation level "none" (section 8). If it fails, the fallback is the row's
   accessible description rather than a more verbose visible prefix.
4. One structural cue or three. One (section 7).
5. Gradual tempo changes. They do not fire the cue - only an immediate change does
   (section 7).
6. Hairpin vocabulary. A one-event wedge reads "Crescendo" or "Diminuendo" with no
   "hairpin"; a written "cresc." reads its own literal text (section 11).
7. Sound Icon Dictionary availability. Always enabled (section 10.1).
8. Region 4 with a marking row selected. It shows that marking's own detail - kind,
   bar and beat, and for a span its full range - rather than the attributes of notes
   the cursor happens to be near (section 4.1). Region 4 describes what is selected,
   and a marking row is what is selected.
9. Whether "a moment gets its own event" generalises beyond ties and the barline
   fermata. It does not - the narrow rule, section 5.1.

The one thing that is still a check rather than a decision is the asterisk. Everything
else is settled, and the build order is in
`UserPlans/PerformanceMarkingsImplementationPlan.md`.
