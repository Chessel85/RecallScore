# Performance markings - implementation plan

Revision 1, 2026-09-13. The build sequence for
`UserPlans/PerformanceMarkingsStrategy.md` revision 3, whose decisions this plan
assumes and does not re-argue. `UserPlans/MusicXMLMarkingInventory.md` revision 3 is
the element-by-element reference.

Nothing here is implemented yet. The plan is written so each stage ships on its own,
is testable on its own, and leaves the app usable if the next stage never happens.

## How the work divides

Three kinds of change, deliberately kept apart because they have different risk:

* Presentation only. New rows, new wording, new toggles. No parser change, no timeline
  change, so the fingerprint harnesses stay green throughout and a mistake is visible
  immediately in the region it affects. Stages 1 to 6 and 9.
* Parser additions. New data read out of the file that was previously ignored. The
  harnesses report new fields, never changed ones. Stages 7 and 10.
* Timeline changes. The event list itself changes, so navigation, playback, the
  Performance Report and every harness baseline move together. Stage 8 alone, and it
  is the only stage that changes behaviour the user already relies on.

Stage 8 is last among the risky work for that reason, and it gets its own live test
before anything is built on top of it.

## The acceptance gate, stated once

Every stage that touches `parsers/` or `models/` runs the fingerprint harnesses of
`tests/manual/` against a baseline captured from the commit before the stage started,
per `tests/manual/README.md`. "The pytest suite passes" is not evidence for a change
meant to preserve behaviour.

* Stages 1 to 7, 9, 10: the harness diff must be empty, except for fields that are
  purely additive and named in the stage's own notes.
* Stage 8: the diff is expected and is the deliverable. It is read line by line, then
  the baseline is recaptured.

## Stage 1 - Region 5 becomes one row per span

Strategy section 6. Self-contained, no dependencies, and it shrinks what every later
stage has to diff.

* `models/performance_region_row.py`: `PerformanceRegionRow` grows a second jump
  target. Today one row carries one target and the start and end rows each carry their
  own; after this a row carries both. Keep the existing field as the start target so
  no call site changes meaning, and add the end target beside it.
* `models/performance_rows.py`: `get_performance_region_rows` emits one row per span
  instead of two. The row-order contract in its docstring stays - repeats, endings,
  hairpins, then the one-shot rows - and the diff `RegionPresenter.refresh_region_5`
  performs still works, on a shorter list.
* New `models/marking_labels.py`: the single source of label text. It owns the range
  rendering ("Repeat bars 1 to 8"), the singular single-bar rendering ("Ending 1 bar
  12"), the start/end rendering the note list will need in stage 3, and the bar word
  from `vocabulary.bar_word`. `performance_rows.py`, Find and the Performance Report
  all call it rather than formatting text themselves. Writing this module now, before
  there is a second consumer, is what stops the two renderings drifting later
  (invariant 8 - two copies of the same fact will diverge).
* `controllers/navigation_controller.py`: the Ctrl+Home / Ctrl+End handler at line 175
  branches on which target it wants rather than on which row it was given.
* `widgets/region5_list_widget.py`: unchanged in behaviour; its key handling at line
  94 already passes the focused row through.

Tests: the singular/plural boundary (a span inside one bar, a span across two bars, a
hairpin inside one bar at two beats), an unmatched wedge keeping its honest wording,
both jump targets resolving from one row, and `bar_word` respected in both renderings.

## Stage 2 - Region 3 rows become typed

Strategy section 15. Pure refactor. Behaviour identical at the end of it, which is
what makes it safe to build five stages on.

* `models/note_renderer.py`: `region_3_data()` returns typed rows rather than bare
  strings - a note row carrying its note index, or a marking row carrying its marking.
  `MusicData.get_region_3_data` keeps its current string-list signature as a thin
  wrapper so nothing outside breaks in this stage, and a new accessor returns the typed
  rows for the callers that need them.
* Move the existing fabricated rows onto the new type: the Stave Text entries and the
  Rehearsal mark entries, which today are synthetic voice events. They become marking
  rows and stop being fake notes. This is the part of the stage that proves the type
  works, and it removes a long-standing oddity in region 2's voice tree.
* `controllers/region_presenter.py`: `update_timeline_views` and
  `refresh_region_3_labels` render from the typed rows. The `selectAll` plus explicit
  `setCurrentRow(0, NoUpdate)` sequence at line 152 is untouched and stays commented as
  it is (invariant 10).
* The three index consumers learn to skip marking rows: region 4's row build,
  `get_playback_events_for_indices`, and the select-all audition. Selecting a marking
  row sounds nothing.

Tests: a score with stave text renders the same strings as before; a marking row in
the selection contributes no playback event; the chord audition still sounds every
note of a chord when row 0 is a marking row.

## Stage 3 - Repeats, endings and sections in the note list

Strategy sections 5 and 5.1 (rows only; no moment events yet).

* New `models/marking_rows.py`, a `MusicData` collaborator in the style of
  `performance_rows.py`: it owns no state, reads spans and marks live, and answers
  "which marking rows belong at this event". It builds its index once per load, keyed
  by measure and by quarters, because region 3 is rebuilt on every cursor move inside
  Ref 9's 25 ms budget - a linear scan over every span per keystroke is the one
  implementation that cannot be made to fit.
* `MusicData` gains a one-line delegator for it (invariant 4).
* Row placement follows the axis B rule: score-level rows at the top, part and staff
  rows immediately above that staff's notes.
* Labels come from `models/marking_labels.py`, in its start/end rendering.

Tests: a repeat start row on the first event of the bar it opens; a repeat end row on
the last event before the barline; a combined end-and-start barline producing both,
end first; an ending row under region 2 filtering; row order with two parts visible.

## Stage 4 - Barline sounds and the Sound Icon Dictionary

Strategy section 10. Independent of stages 1 to 3, so it can slot in wherever it suits.

* New `audio/barline_patterns.py`, beside `boundary_cue.py` and `performance_cue.py`
  and in the same bare-module shape: the patterns declared as data (pitch, length,
  velocity steps), one reserved channel of its own. A multi-step pattern must not share
  a channel with another one-shot - FluidSynth releases a ringing note by channel plus
  key, so two patterns on one channel cut each other off.
* The repeat mnemonic goes in the code comment: the short beeps are the repeat dots and
  they sit on the side of the long beep that the repeated music is on.
* Suppression rule: the plain barline beep stays suppressed while the metronome runs;
  the repeat, double, heavy and mensurstrich patterns sound anyway. All of it stays
  gated by the Ctrl+B toggle, and every pattern fires after the destination note's
  audition.
* New `widgets/sound_icon_dictionary_dialog.py`, Help menu, always enabled with or
  without a score. A list plus buttons, so `docs/dialog_widget_patterns.md` applies,
  including focusing the literal first widget in tab order.
* The dictionary is generated from the same declarations the audio modules use. A
  hand-written second list would drift from the sounds themselves - the R5 bug class
  again.

Tests: pattern selection per bar style with a null synth recording what would have
sounded; metronome suppression applying to the plain beep only; the dictionary listing
one entry per declared sound with no score loaded.

## Stage 5 - Hairpins

Strategy section 11, and the first stage to need per-part and per-staff placement.

* A `<wedge>` whose start and stop resolve to one position becomes a point, reading
  "Crescendo" or "Diminuendo" - never "hairpin".
* A `<words>` direction keeps reading its own literal text, which is what keeps a
  written "cresc." distinct from a wedge.
* A swell (crescendo then diminuendo on one note) produces two rows in file order, and
  nothing merges them.
* An unmatched stop keeps "Hairpin ending bar 12, no start marked in the file".

Tests: zero-length wedge as a point; swell as two rows in file order; a hairpin on the
piano left hand appearing above the left hand's notes only, and not repeated per voice
of that staff.

## Stage 6 - Structural changes and the cue

Strategy section 7.

* Key, time and tempo changes become note list rows: "Key signature change: D major",
  "Time signature change: 3/4", "Tempo change: 96".
* `controllers/region_presenter.py` line 332 and line 345: the cue stops firing on a
  region 5 row-set diff and fires when the cursor lands on an event carrying a
  structural change row. One sound for all three.
* Never at index 0 - the opening key, time and tempo are already in region 1 and the
  status bar on load.
* Only an immediate tempo change fires it. A rallentando written as words gets its row
  and its region 5 line and no clap.
* Ordering is unchanged and load-bearing: audition first, then the cue, because the
  audition's retrigger releases everything on its channel.

Tests: cue fires on a mid-score key change and not at index 0; a words-only rall.
produces a row and no cue; the audition-then-cue order holds.

## Stage 7 - Points, directives and the region 1 list

Strategy sections 5 and 9. The first stage with real parser additions, all of them
additive.

* Parser gaps closed here, from the inventory's priority list: `directive="yes"`;
  `repeat times="N"` surfaced in the row text and `after-jump` read;
  `<barline>/<segno>` and `<barline>/<coda>` as an alternative source for jump marks.
* Point rows: segno, coda, to coda, fine, da capo, dal segno, rehearsal marks, double
  and other barlines, clef changes, pedal change.
* Region 1 gains the Directives list, in bar order.
* Ctrl+N on a region 1 directive entry adds it to the note list and removes it again,
  with the same context menu item region 5 will get in stage 9. Directives are not in
  the note list by default.

Harness note: new fields appear for directives, repeat times and after-jump. Nothing
existing changes.

Tests: a directive listed in region 1 and absent from the note list until toggled; the
toggle surviving a save and reload; "Repeat bars 1 to 8, play 3 times".

## Stage 8 - Ties, and the two moment events

Strategy sections 12, 13 and 5.1. The one stage that changes existing behaviour. It
ships alone, with its own live test, and nothing else goes in the same commit.

Three changes that have to land together because each is wrong without the others:

* A tied chain becomes one attack with the summed duration, named where a name exists
  and stated in ts-relative beats where it is not. Playback holds it once.
* A continuation note carrying a marking becomes its own timeline event at its own bar
  and beat, reading "F sharp, tied, fermata" with the remaining length of the chain.
  Arrowing onto it auditions the pitch; playback does not re-attack it. A continuation
  note carrying nothing is not an event.
* A `<fermata>` inside a `<barline>` becomes its own timeline event at the barline
  position, attached to no note, reading "Fermata on barline", sounding nothing, score
  level. A fermata on the final barline needs no special case - it is simply the last
  event.
* The `tie` attribute leaves region 3, region 4 and the Find target list.

Where the code changes:

* `parsers/timeline_builder.py` and the MusicXML path: chain detection, duration
  summing, and the two new event kinds. The other three formats inherit whatever the
  shared builder does and are checked rather than changed.
* `models/event_slice.py` and `models/note_data.py`: an event kind that carries no
  attack, and enough on it for the renderer to speak it.
* `models/playback_event_builder.py`: one attack per chain, held for the summed
  length. This is the bug the current two-attack rendering has, so playback gets
  better as a side effect.
* The navigator: a moment event is a stop, and a marking-free continuation is not.

Ties across a repeat or into a first-time bar sum the written length as printed. No
attempt is made to work out the duration on a particular pass through the repeat
structure.

Harness: every score containing a tie reports a difference. That is the deliverable.
Read the diff, confirm each difference is a tie or a barline fermata and nothing else,
then recapture both baselines.

Live test before anything is built on top: a tied chain of three, a tied chain with a
fermata in the middle, a tie across a barline with a fermata on that barline, and a
chord where one note is tied and the others are not.

## Stage 9 - Ctrl+N, the asterisk, and persistence

Strategy section 8. Until this ships, every category from the stages above is simply
on, which is why it can come this late.

* Ctrl+N with focus on a region 5 row toggles that row's category in and out of the
  note list and speaks the new state. Same item on region 5's context menu (Menu key
  and Shift+F10), and in the Keyboard Shortcuts reference.
* Ctrl+N is declared where its action is built and snapshotted by
  `ShortcutController`, never copied into a table (invariant 16).
* A surfaced category is prefixed with an asterisk and a space in region 5.
* Per score in the `.rsc` through `ScoreConfig`, with a global default in
  `AppSettings`, matching display attributes and the region 2 toggles.

The asterisk check, five minutes with NVDA and the only thing in this plan that is a
question rather than a decision: at punctuation level "none" an asterisk may be spoken
as nothing at all, which makes the prefix invisible rather than subtle. If it fails,
the fallback is the row's accessible description, not a more verbose visible prefix.
Do this check at the start of the stage, not the end.

## Stage 10 - Articulations, ornaments and breath marks

Strategy section 14. Independent of everything else; it is here because it is the
least urgent, not because it is blocked.

* Ornaments split out of the merged `articulation` attribute into their own `ornament`
  attribute - separately toggleable, orderable and findable.
* `breath-mark` and `caesura` read from both `<notations>` and `<articulations>`, so
  they no longer depend on where the exporter put them.
* Both stay label-only. No ornament is audibly realised - a standing decision, not an
  oversight.

Harness: a new `ornament` field appears and `articulation` loses the ornament values.
Both are expected and are read as a pair.

## What this plan does not touch

* The Performance Report. It reads the same spans and marks and picks up the new
  labelling module for free in stage 1. Its own redesign is the next piece of work
  after this one.
* `docs/user_guide.md` and its HTML. Not touched unless asked for separately.
* Playback of ornaments, trills and octave shifts. Still label-only.

## Order in one line

Stage 1 and stage 4 can start immediately and in either order. Stage 2 gates 3, 5, 6
and 7. Stage 8 waits for a quiet moment and ships alone. Stage 9 comes after whatever
categories exist. Stage 10 whenever.

User decisions:
Q1. Default value — Off (matches every other audio toggle in the app) vs. "On except when playing" (preserves today's    
narrow structural-change behavior almost exactly, since that already never plays during playback).                      
A1. Correct. Default is off.
Q2. Submenu + separate Ctrl+C cycle action, as you described, vs. the simpler single flat "Cycle Performance Indicator"  
item the codebase otherwise uses for this exact shape of setting (Cycle Play Mode, Cycle Loop Repeat Handling).         
A2. We do not have a dialogue for this option so cycling with control+C gets around this.  Additionally, the menu items do allow the user to browse and discover the options.
Q3. Menu/label wording as you wrote it, or adjustments.                                                                  
A3. Stick with my wording for now. Easy to change.
Q4. Confirming placement grouped with Bar Line Indicator/Metronome/Position Announcer.                                   
 A4.  Place it immediately below the bar line indicator menu item.
