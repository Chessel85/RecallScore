# MusicXML marking inventory

Revision 3, 2026-09-13. Companion to `UserPlans/PerformanceMarkingsStrategy.md`.
Every MusicXML element that can carry performance information, what it means, what
Recall Score does with it today, and the class it lands in. Revision 2 folded in the
first round of review: ties fold into duration, a zero-length wedge is a point,
directives go to region 1, ornaments split out of articulations, breath marks are read
properly, and the barline fermata is parsed. Revision 3 folds in the second round: the
barline fermata and a marking on a tied continuation note each become their own
timeline event, a one-event wedge drops the word "hairpin", and a directive reaches the
note list only when Ctrl+N asks for it.

Covers MusicXML 4.0 partwise. The classes are the ones from section 4 of the strategy:

* attribute - hangs off a `<note>`, lives in regions 3 and 4 as a note attribute.
* point - one note list row with no start or end word, plus a region 5 row.
* span - a "start" and an "end" note list row, plus a one-line range row in region 5
  while the cursor is inside it.
* structural - key, time, tempo. A point row at the position where it changes, and
  the trigger for the change cue.
* region 1 - listed in the score information region.
* moment event - its own timeline event, landed on by Left/Right, attached to no note
  (strategy section 5.1). Exactly two elements qualify.
* region 5 only - reported and findable, no note list row.
* ignored - deliberately not surfaced (layout, editorial, engraving detail).

"Catch-all" in the Today column means it is not handled by name but still shows up as
the `other notation` attribute or the "Direction" marking, so it is findable rather
than lost.

## 1. `<direction>/<direction-type>` children

The container for almost every printed instruction that is not attached to a single
note. A `<direction>` may carry `<staff>`, `placement`, `directive="yes"` and an
`<offset>`; Recall Score already reads `<staff>` and the offset.

| Element | Meaning | Today | Class |
|---|---|---|---|
| `words` | free text: tempo words, technique words, position marks, "cresc." | Stave Text event in region 3, plus a `dynamics_word` / `tempo_word` point mark when the whole text matches the vocabulary allow-list | point (stave text row, per part and staff); region 1 as well when `directive="yes"` |
| `dynamics` | printed dynamic (p, f, sfz, ...) as a direction | becomes the `dynamic` attribute of the notes at that offset, plus a point mark | attribute, unchanged |
| `wedge` | crescendo or diminuendo hairpin | `HairpinSpan`, region 5, Find, report | span; point reading "Crescendo" or "Diminuendo", never the bare word "hairpin", when start and stop resolve to the same position (strategy section 11) |
| `dashes` | dashed continuation line under an instruction | `DirectionSpan`, region 5 | span |
| `bracket` | bracketed continuation line | `DirectionSpan`, region 5 | span |
| `pedal` | sustain pedal: start, stop, change, sostenuto, resume | `DirectionSpan` plus a `pedal_change` point; Find and report only, no region 5 row today | span, plus point for `change`; gains region 5 and note list rows |
| `octave-shift` | 8va, 8vb, 15ma, 15mb | `DirectionSpan`, label carried | span |
| `metronome` | printed metronome mark | feeds tempo | structural |
| `segno` | segno sign | `SegnoMark` | point |
| `coda` | coda sign | `CodaMark` | point |
| `rehearsal` | rehearsal mark A, 12 | `DirectionMark` plus a Stave Text event in region 3 | point (score level) |
| `symbol` (4.0) | an arbitrary SMuFL symbol as a direction | catch-all | point |
| `harp-pedals` | harp pedal diagram | catch-all | point |
| `damp`, `damp-all` | harp or piano damping | catch-all | point |
| `eyeglasses` | "watch the conductor" | catch-all | point |
| `string-mute` | mute on or off | catch-all | point |
| `scordatura` | retuning instruction | catch-all | point (guitar relevance) |
| `accordion-registration` | accordion stop registration | catch-all | point |
| `principal-voice` | Hauptstimme / Nebenstimme bracket | catch-all | span, low priority |
| `staff-divide` | divisi and unison marks | catch-all | point |
| `percussion` | a percussion pictogram as a direction | catch-all | point |
| `image` | an embedded graphic | catch-all | ignored |
| `other-direction` | explicit escape hatch | catch-all | point |

The `directive="yes"` attribute of the parent `<direction>` is what marks text as a
score-wide instruction. Those go to region 1 as "Directive: Jauntily (bar 12)", and
reach the note list only when Ctrl+N on the region 1 entry asks for it (strategy
section 9).

## 2. `<barline>` and its children

| Element or value | Meaning | Today | Class and sound |
|---|---|---|---|
| `bar-style` regular | ordinary barline | nothing (correct) | no row; one short beep |
| `bar-style` light-light | double barline - a section division, written before a key or metre change and at the end of a section | `BarlineMark` kind `double_barline`, region 5 and Find | point; two short beeps |
| `bar-style` light-heavy | final barline | dropped on the last bar, kept as `other_barline` elsewhere | no row on the last bar; no sound (the timeline end has its own cue) |
| `bar-style` heavy-light | opening of a section | `other_barline` | point; one long lower beep |
| `bar-style` heavy, heavy-heavy | emphatic division | `other_barline` | point; one long lower beep |
| `bar-style` dotted, dashed | a subdividing barline inside a bar, clarifying a compound or irregular metre | `other_barline` | point; one short beep |
| `bar-style` tick, short | mensurstrich-style barline in modern notation | `other_barline` | point; one softer short beep |
| `bar-style` none | invisible barline | `other_barline` | ignored |
| `repeat direction="forward"` | start repeat | `RepeatSpan` start | span start; one long then two short |
| `repeat direction="backward"` | end repeat | `RepeatSpan` end | span end; two short then one long |
| forward and backward at one barline | combined end and start | two spans | both rows, end first; two short, one long, two short |
| `repeat times="N"` | play N times | parsed for looping | include in the row text: "Repeat bars 1 to 8, play 3 times" |
| `repeat winged` | engraving detail of the repeat sign | not read | ignored |
| `repeat after-jump` | the repeat applies only after a da capo or dal segno | not read | worth reading - it changes playback |
| `ending number type="start"/"stop"/"discontinue"` | first and second time bars | `EndingSpan` | span |
| `fermata` | a pause on the barline itself | not read | moment event at the barline position, attached to no note, reading "Fermata on barline" and sounding nothing (strategy section 13) |
| `segno`, `coda` | the sign printed at the barline rather than as a direction | not read from here | point, same handling as the direction form |
| `wavy-line` | trill or vibrato line crossing the barline | not read | span, low priority |

## 3. `<sound>` attributes

`<sound>` is the playback-intent element, either standalone or inside a
`<direction>`. Its attributes are the only machine-readable form of the jump
instructions.

| Attribute | Meaning | Today | Class |
|---|---|---|---|
| `tempo` | beats per minute from here | every occurrence feeds `tempo_changes` | structural |
| `dacapo` | go back to the start | drives the jump marks and playback | point |
| `dalsegno` | go back to the segno | as above | point |
| `segno` | this is the segno | `SegnoMark` | point |
| `coda` | this is the coda | `CodaMark` | point |
| `tocoda` | jump to the coda from here | `ToCodaMark` | point |
| `fine` | end here | `FineMark` | point |
| `forward-repeat` | repeat start for playback | covered by the barline form | none |
| `dynamics` | playback velocity percentage | not read | ignored - the printed dynamic is what the reader needs |
| `pizzicato` | pizz. on or off for playback | not read | point, if a real file needs it |
| `damper-pedal`, `soft-pedal`, `sostenuto-pedal` | pedal as playback state | not read | covered by the printed `<pedal>` span |
| `pan`, `elevation` | stereo placement | not read | ignored - the Mixer owns pan |
| `divisions`, `time-only` | technical | not read | ignored |

The printed words ("D.C. al Fine", "To Coda") are also matched by regex when the
exporter writes no `<sound>` attributes, and such a `<words>` is then deliberately not
repeated as a Stave Text event.

## 4. `<notations>` children (note-attached)

| Element | Meaning | Today | Class |
|---|---|---|---|
| `tied` | tie start and stop | `tie` attribute | not surfaced. The tied chain's total length becomes the head note's duration instead, and a continuation note is an event only when it carries a marking of its own, in which case it is a moment event (strategy section 12) |
| `slur` | slur start and stop | `slur` attribute | attribute |
| `tuplet` | tuplet bracket (the ratio comes from `time-modification`) | `tuplet` attribute, from `time-modification` | attribute |
| `glissando`, `slide` | glissando or slide start and stop | `glissando` attribute | attribute |
| `ornaments` | see section 6 | merged into the `articulation` attribute | new `ornament` attribute of its own |
| `articulations` | see section 5 | `articulation` attribute | attribute |
| `technical` | see section 7 | fret, string, fingering and pluck as their own attributes, the rest merged into `technique` | attribute |
| `dynamics` | a dynamic attached directly to the note | `dynamic` attribute, and it beats an offset-matched direction | attribute |
| `fermata` | pause, with a shape | `fermata` attribute | attribute (the barline form is a point - section 2) |
| `arpeggiate`, `non-arpeggiate` | roll the chord, or explicitly do not | `arpeggio` attribute on chord notes; on a lone note re-read as a strum direction | attribute |
| `breath-mark` | a breath or lift between notes | only read when the exporter put it inside `<articulations>`; dropped when written directly under `<notations>` | attribute, read from both places |
| `accidental-mark` | an accidental printed above an ornament, giving the ornament's auxiliary note | recognised but not surfaced | attribute, low priority - it is the missing piece for ever realising ornaments audibly |
| `footnote`, `level` | editorial metadata | recognised and ignored | ignored |
| `other-notation` | escape hatch | `other notation` attribute | attribute |

## 5. `<articulations>` children

accent, strong-accent, staccato, tenuto, detached-legato, staccatissimo, spiccato,
scoop, plop, doit, falloff, breath-mark, caesura, stress, unstress, soft-accent,
other-articulation.

Today all of these, plus the ornaments of section 6, are merged into one comma-joined
`articulation` attribute.

Change: ornaments move out into their own attribute (section 6), leaving this list as
the `articulation` attribute. `breath-mark` and `caesura` are timing instructions
rather than articulations, and are read from both of the places an exporter can put
them rather than only from inside `<articulations>`.

## 6. `<ornaments>` children

trill-mark, turn, delayed-turn, inverted-turn, delayed-inverted-turn, vertical-turn,
inverted-vertical-turn, shake, wavy-line, mordent, inverted-mordent, schleifer,
tremolo, haydn, other-ornament, plus `accidental-mark`.

Change: split out of `articulation` into their own `ornament` attribute, separately
toggleable, orderable and findable. All stay label-only - no ornament is audibly
realised, which is a standing decision (see CLAUDE.md), not an oversight. `wavy-line`
here is the trill's extension line and would become a span if ever surfaced.

## 7. `<technical>` children

up-bow, down-bow, harmonic, open-string, thumb-position, fingering, pluck,
double-tongue, triple-tongue, stopped, snap-pizzicato, fret, string, hammer-on,
pull-off, bend, tap, heel, toe, fingernails, hole, arrow, handbell, brass-bend, flip,
smear, open, half-muted, harmon-mute, golpe, other-technical.

Today `fret`, `string`, `fingering` and `pluck` each become their own attribute; all
the rest are comma-joined into `technique`. Unchanged. `hammer-on`, `pull-off` and
`bend` carry start and stop types and could be spans, but they are guitar techniques
read note by note, and the note attribute is the right place.

## 8. `<dynamics>` values

p, pp, ppp, pppp, ppppp, pppppp, f, ff, fff, ffff, fffff, ffffff, mp, mf, sf, sfp,
sfpp, fp, rf, rfz, sfz, sffz, fz, n, pf, sfzp, other-dynamics.

Spoken through `dynamic_name` into the `dynamic` attribute, whether the source is a
direction or a note-attached `<dynamics>`. Unchanged. A hairpin is a different thing
from a dynamic mark and is reported separately, even when both sit on one note.

## 9. `<attributes>` and `<measure-style>`

| Element | Meaning | Today | Class |
|---|---|---|---|
| `divisions` | ticks per quarter | used throughout | not a marking |
| `key` | key signature | per-slice `key_fifths`, region 5 one-shot row on change | structural: note list row and the change cue |
| `time` | time signature | per-slice `time_sig`, region 5 one-shot row on change; drives Ref 18 beat units | structural: note list row and the change cue |
| `clef` | clef, including mid-part changes | `ClefChangeMark`, region 5 and Find | point (per part and staff) |
| `staves` | how many staves the part has | used for the part tree | not a marking |
| `part-symbol` | brace or bracket grouping | not read | ignored |
| `transpose` | transposing instrument | shifts `midi_pitch` only (invariant 15) | not a marking |
| `staff-details` | tuning, string count, staff lines | partially used for tab | not a marking |
| `measure-style` multiple-rest | N bars rest printed as one | `MeasureStyleMark`, region 5 and Find | point |
| `measure-style` measure-repeat | repeat the previous bar | `MeasureStyleMark` | point |
| `measure-style` beat-repeat | repeat the previous beat | `MeasureStyleMark` | point |
| `measure-style` slash | slash notation bars | `MeasureStyleMark` | point |
| `for-part` (4.0) | concert versus written pitch for one part | not read | not a marking |

## 10. Other score content

| Element | Meaning | Today | Class |
|---|---|---|---|
| `credit`, `credit-words` | page text: title, composer, copyright | region 1 | region 1, unchanged |
| `work`, `movement-title`, `identification` | score metadata | region 1 | region 1, unchanged |
| `harmony` | chord symbol, with `frame` for a chord diagram | synthetic Chords part, `chord symbol` and `chord diagram` attributes | attribute |
| `figured-bass` | figured bass numerals | not read | attribute, if a real file needs it |
| `lyric` | sung text | synthetic Lyrics part | not a marking |
| `print new-system`, `new-page` | system and page breaks | not read | no row - the end of system already has its own cue |
| `grace` | grace note | its own `GraceNote` list, rendered "A grace B", plus the `grace` attribute | attribute, unchanged: the grace note's pitch is still spoken in the step |
| `cue` | cue-size note | not read | ignored |
| `listen`, `listening` (4.0) | performance-following data | not read | ignored |
| `part-group` | instrument grouping brackets | not read | ignored |

## 11. Parser gaps to close, in priority order

1. Ties summed into duration, and continuation notes removed from the timeline
   (strategy section 12). The one behaviour change in this work.
2. `<barline>/<fermata>` - a pause on the barline, currently invisible.
3. Ornaments split out of the merged articulation attribute.
4. `breath-mark` and `caesura` read from both `<notations>` and `<articulations>`.
5. A zero-length `<wedge>` classified as a point rather than a span, with the
   vocabulary of strategy section 11.
6. `directive="yes"` read, for the region 1 directive list.
7. `repeat times="N"` surfaced in the repeat row text, and `after-jump` read.
8. `<barline>/<segno>` and `<barline>/<coda>` as an alternative source for jump marks.
9. `accidental-mark` - the only element that would make an ornament's auxiliary pitch
   knowable without inference, if audible ornaments are ever revisited.
