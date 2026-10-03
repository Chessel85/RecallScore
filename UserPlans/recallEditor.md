# Recall Score - Editor Version

Version 2026.2 of Recall Score lets the user edit existing scores and create new ones from scratch.

It is not a score engraving application. Notes are entered as if onto a formal engraved score, without any concern for rendering it.

The app has a read-only mode and an edit mode, and switching between them takes a deliberate user action. A read-only build may also be offered, so a score cannot be changed by mistake.

Topics still to be covered by the sections below (each is removed from this list once a section decides it):
* Creation of score information
* Adding parts, staves and voices
* Creating, reading, updating and deleting (CRUD) for notes
* Setting attributes for notes
* CRUD for performance indicators
* Keeping bars correct: the notes and rests of each voice in a bar add up to a whole bar
* Formats that can be saved
* How much musical notation is covered. Only what is relevant to playback need be considered.
* Input from connected MIDI devices
* MIDI import
* Copy, cut and paste
* Tools for faster input, such as copying a range, duplicating voices, staves and parts, and selecting similar items
* Guitar-specific features such as chord diagrams
* Entering lyrics

The sections are ordered so that earlier decisions constrain later ones.

### 1. The document model

Decided 2026-09-30.

#### Design

* The MusicXML element tree is the document. Every edit changes the tree, and Save writes the tree.
* MusicData becomes a read-only index rebuilt from the tree after each edit. It is never edited or saved.
* Each NoteData carries a link back to the XML element it came from, so an edit knows what to change.
* After an edit, only the affected bar (or part) is rebuilt. Edits that change everything after them (time signature, key, repeats, inserting or deleting bars) do a full rebuild.
* The edited note sounds as soon as it is entered, before the rebuild, so the 25 ms audition budget (Ref 9) holds regardless of rebuild time.
* Save keeps comments, processing instructions, the XML declaration and the DOCTYPE. ElementTree as used today (xml_source.py) drops all of these on read, so the reader must change.
* After a rebuild the cursor returns to the same bar, beat, part, staff and voice, never the same list index, and Region 2 toggles are kept (invariant 11).
* Imported MIDI, Guitar Pro and Ultimate Guitar files are first converted into a MusicXML tree, which is then edited. That conversion is a feature in its own right.

Why:

* Anything the app does not understand (layout, credits, beaming, lyric details, ignored notation) survives a save untouched. Using music21 streams (about 460 ms per rebuild, and it rewrites MusicXML its own way) or a new app-specific model (most work, and anything not modelled is lost on save) do not give this.
* MusicData is kept because the raw XML cannot directly answer "what sounds at bar 12 beat 3 across all parts". The timeline builder works that out once, and every region, playback, Find and the Performance Report depend on it.
* One place holds each fact (invariant 8). MusicData is always regenerated, so it cannot diverge from the tree.

#### Performance gate

A full rebuild is too slow to run after every keystroke on a large score. Measured 2026-09-30:

* Dvorak Largo (122 KB .mxl): about 440 ms
* Ode to Joy orchestral (1.5 MB .musicxml): about 230 ms
* Blue Danube, Pachelbel quartet: about 220 to 260 ms

About 110 ms of this is reading the file, which an in-memory rebuild skips, leaving about 300 ms.

The builder already walks one part and one bar at a time, carrying a small state object between bars, so rebuilding one bar looks feasible. Not yet proven: the whole-score steps (the first-part scan of bar lengths and repeats, merging parts into slices, the Find index) need incremental versions too.

This is the first thing built and tested. Prototype a single-bar rebuild for note edits and time it on the Dvorak score. Well under about 50 ms and the design stands. Otherwise, revisit this section before anything else is built.

#### The .rsc sidecar

* Listening preferences stay in the sidecar: mute, solo, metronome, announcer, attribute order and hidden attributes, mixer, marking filters, linked parts, last position. They belong to the listener, not the score, and a collaborator should not inherit them.
* Score facts have proper MusicXML homes: part-name, midi-program, midi-unpitched, key, part-list order, sound tempo. In edit mode, changing one edits the tree. In read-only mode it stays a sidecar override, as now.
* MusicXML does allow app-specific data (identification/miscellaneous/miscellaneous-field, and processing instructions), but MuseScore and Sibelius usually drop it on re-save, so nothing that matters is stored only there.

### 2. Mode switching and the keyboard

Decided 2026-09-30.

#### Design

* Ctrl+Shift+E switches between Read-Only and Edit mode, with a spoken announcement (Ref 23). The mode applies to the whole window.
* Two shortcut maps. Each action is scoped to both modes, read-only only, or edit only. A key may be bound twice if the two actions' scopes don't overlap.
* ShortcutController: saved overrides stay keyed by action id, since the scope belongs to the action. `_apply()` binds the active mode's actions and unbinds and disables the rest, which also locks editing controls in read-only mode (Ref 23 criterion 3). The reserved list and `ShortcutMap.owner_of` become mode-aware. The Keyboard Shortcuts dialog shows each action's mode.
* Keys a widget handles itself in `keyPressEvent` must check the mode too.
* Region quick nav moves from Z/X/C/V/B to F1 to F5, freeing letters for note entry.
* In edit mode, digits choose durations and bar-number typing is dropped. Go to Measure is always available through its dialog. Enter becomes free in edit mode.
* All five regions are editable: score information (Region 1), parts, staves and voices (Region 2), notes (Region 3), attributes (Region 4), performance markings (Region 5).
* The same verbs work in every region. For example, Insert adds, Delete removes, and Enter edits the current item.
* Region 1: for a new score, a dialog with labelled fields and a way to add fields. For an existing score, possibly an edit box on each row, with a context menu to add a row.
* Region 2: adding a part probably needs a dialog, since the part needs a name, an instrument and its staves together.
* One undo stack for the whole window. The undo announcement says what went ("Deleted part Viola, 212 notes").
* Voice control works in read-only mode only. When editing, the user is expected to be at the computer keyboard rather than the instrument.

Why:

* Note entry wants bare letters and digits, which read-only mode uses for region jumps and bar-number typing. Two scoped maps keep both sets of keys without chords.
* Voice control is not responsive enough for entering notes.

#### Still open

* A fast way to check the current mode. The title bar is too slow, and the start of the status bar is not wanted.
* F1 is Windows' conventional Help key. Nothing in the app uses F1 to F5 today, but check that users don't expect F1 to open help.
* Final wording for voice control in the phasing: decide at section 15.

### 3. The cursor in edit mode

Decided 2026-09-30.

#### Design

* The cursor moves by event. A separate input duration setting (chosen with the digits, section 2) sets the length of the next note entered.
* The user can also move the cursor to a given beat position in the bar, to add a note there.
* In edit mode the cursor lands on rests and empty bars as well as notes. Read-only mode still skips rests (invariant 15).
* The cursor is always in one part, one staff and one voice. Notes can only be entered on a staff, and every part has at least one staff.
* Alt+1 to Alt+4 choose the voice being written. Nothing uses Alt+digits today.

Why:

* Moving by event with a separate duration setting is how most notation editors work, and it keeps navigation independent of what is about to be entered.
* Moving to a beat covers placing a note where no event starts yet, such as beat 3 of an empty bar.

#### Still open

* How the beat position is typed. In edit mode the digits choose durations and bar-number typing is dropped, so this probably needs a Go to Beat dialog, or a field in the Go to Measure dialog.
* Moving to a beat that falls inside a longer note or rest: split it, or land on the event that covers the beat? Section 5 (overwrite mode) probably decides this.
* How the cursor is placed in a part, staff and voice: from Region 2, by keys in Region 3, or both. What happens when the chosen voice has no music in the current bar.
* Whether voices above 4 need a key. MusicXML allows more, and some imported files use them.

### 4. Note entry model

Decided 2026-09-30.

#### Design

* Pitch: a letter name A to G, with the octave chosen automatically as the one nearest the previous note (as in MuseScore and LilyPond's relative mode). Separate keys force the octave up or down.
* Accidentals come from the key signature. In G major, typing F gives F sharp. The user never enters courtesy accidentals.
* Separate keys force sharp, flat or natural on the current note.
* J toggles the current note between its two enharmonic spellings, for example D sharp and E flat. This also fixes a note entered from a MIDI keyboard, which sends only a key number: the app guesses the name (pitch_spelling.py) and J corrects it.
* Transposing instruments: the user enters written pitch, and midi_pitch follows from the transpose setting (invariant 15).
* Chords: Shift plus a letter adds that pitch to the current chord instead of moving on.
* Tab staff: Up and Down choose the string, typed digits set the fret, and Enter enters the note. Shift+Enter adds it to the current chord.
* Linked staff and tab: a pitch entered on the staff gets the most obvious string and fret, meaning the lowest fret that can play it. A string and fret entered on the tab gives exactly one pitch on the staff. Editing either side re-derives the other.
* Ref 24: every change sounds immediately. What is spoken after each edit is kept short, because a fast typist does not want a sentence after every keystroke.

Why:

* Letter plus automatic octave, with accidentals from the key, means most notes take one keystroke.
* A string and fret always gives one pitch, but a pitch can be played on several strings, so the staff-to-tab direction needs a rule and the tab-to-staff direction does not.

#### Still open

* The default keymap for octave up and down, forced sharp, flat and natural, dots, ties, tuplets and grace notes.
* Accidentals within a bar: after a forced F natural in G major, does a later F in the same bar default to F natural (as a printed score reads) or F sharp (the key)?
* On a tab staff digits enter frets, but section 2 gives digits to durations. Durations on a tab staff need other keys. Multi-digit frets (10 and up) are handled by typing both digits before Enter.
* Up and Down move between the notes of a chord in Region 3 today. On a tab staff in edit mode they choose the string instead, so decide how to move between chord notes there.
* When the lowest-fret choice falls on a string already used by the chord, the next string is taken. Confirm this, and what happens when no string is left.
* The exact wording spoken after each kind of edit, and whether there is a verbosity setting.

### 5. Keeping bars correct

Your list already includes this. Some concrete choices:

* Overwrite mode (as in MuseScore): a new note replaces whatever time it covers, and leftover time becomes rests, so the bar is always full. Simple and always valid. I'd make it the default.
* Insert mode: a new note pushes later music along, rippling across barlines. Powerful, but it can mangle the rest of the piece.
* A note longer than the time left in the bar: split it and tie it across the barline automatically, or refuse?
* Changing the time signature partway through: re-bar the music that follows, or only allow it on empty bars?
* Voices 2 and up: may they be partial (MusicXML allows invisible rests via forward), or must they always be filled?
* Pickup bars (Ref 17) and deliberately short bars, such as a final bar that completes a pickup.
* An accessible "Check score" report, in the style of the Performance Report, listing every overfull or underfull bar by part and voice. Very valuable when the user cannot glance at the page.

### 6. Structure edits

* Insert, delete and append bars: MusicXML partwise needs every part to have the same measures, so a bar operation applies to all parts at once.
* Measure numbering after inserts, especially with a pickup bar.
* Key, time, clef and tempo changes partway through the score.
* Repeats, voltas, D.S., D.C. and Coda change the playback order, so edits here need checks (a repeat with no match, a To Coda with no Coda).
* Deleting a note that a span (hairpin, slur, 8va) starts or ends on: what happens to the span?

### 7. Undo and redo

This isn't on your list yet, and it's essential. Every edit should be undoable from day one: Qt's QUndoStack in the controller layer, with the model staying Qt-free. The undo announcement should say what was undone ("Undo: delete F sharp, bar 12").

### 8. Saving, safety and file formats

* Native format: MusicXML. Compressed .mxl or plain .musicxml by default?
* Imported MIDI, GP and UG files can't be written back to their own format at first, so Save on those becomes Save As MusicXML. Make that explicit so the user is never surprised.
* MIDI export (Ref 26) loses information (no spelling, no tab, no markings). GP and BME export are large separate projects; I would put them off.
* An unsaved-changes flag, a "*" in the title bar, a prompt on close or open, and autosave with crash recovery. All of these matter more for someone who cannot see at a glance that a file is modified.
* Should the first save ask before overwriting the original, or keep a .bak copy?
* Sighted collaborators will open saved files in MuseScore or Sibelius. Even without engraving, the file must make sense there: correct note types and dots, beams, stems, divisions, backup and forward for voices, and accidentals and octave transposing where needed. Decide how much of that the app writes and how much it leaves to the other program's automatic layout.

### 9. Selection, copy, cut and paste

* Today a selection is the notes of one slice in Region 3. Editing needs a time-range selection (from bar and beat to bar and beat) across one or more parts or voices, plus a way to hear and announce its extent.
* Paste over existing music (to match overwrite entry) or insert it?
* Pasting into a different part raises questions: a transposing instrument, a different clef, a different tuning (tab strings and frets need re-deriving), or a different number of staves.
* A system clipboard format (a MusicXML fragment) would allow pasting between Recall Score and other editors. An internal format is simpler.

### 10. Which notation to support

Your list says only notation relevant to playback needs to be considered. Two cautions:

* The reader deliberately reports far more than affects playback: ornaments, fermatas, fingering and technical marks do not sound, but they are read and findable. Users will expect to be able to create what they can read. Decide whether editing covers everything the app displays or a smaller subset, and say which in the user guide.
* With option A in section 1, notation you don't support for editing is still kept on save. With B or C it is lost. That favours A.
* Do we extend playback to cover ornaments and dynamics?

### 11. MIDI input and the DAW question

* MIDI import already exists for reading (Ref 25). For editing, it needs converting to the editable model, plus quantisation, because real MIDI files are rhythmically messy.
* Step-time entry from a MIDI keyboard (play the pitch, choose the duration on the computer keyboard) is simple, accurate and accessible. The live MIDI input controller and metronome already exist.
* Real-time recording is where it crosses into DAW territory. It needs a count-in, quantisation settings, tuplet detection and splitting into voices, and it is where most notation apps are weakest. I'd do step-time in 2026.2 and leave real-time recording for a later release.
* If it does become DAW-like: overdubbing, punch in and out, velocity editing, and whether velocity and timing nuance is kept or quantised away. MusicXML only partly holds that.

### 12. Creating scores and parts

* A "New score" wizard: title, composer, parts, key, time, tempo, pickup bar and number of bars.
* Or allow direct entry of details into regions 1 and 2 
* New part: name, instrument (GM program; keep PART and INSTRUMENT distinct in the UI), clef, number of staves, transposition, tab and tuning, percussion map.
* Duplicate a part, staff or voice, and split or combine (a chord voice into separate voices, or voices into one).

### 13. Guitar and lyrics

* Chord symbols (MusicXML harmony) and chord diagrams (frame) are separate features. Chord naming is already on the unbuilt list.
* Tab: capo handling (also unbuilt) changes what fret numbers mean.
* Lyrics: verses, hyphenated syllables, melismas (extender lines), and how a syllable attaches to a note. Lyrics are partly parsed today, so check how much before designing entry.

### 14. Engineering and testing

* Treat 2026.2 as a speculative feature branch, like feature/ug-import, and merge it only once live testing holds up.
* Keep models/ free of Qt and of parsers/. A writer probably wants its own package (for example writers/) rather than living in parsers/.
* Use a round-trip test as the acceptance gate: load every file in files/, examples/ and tests/fixtures/, save it unchanged, reload it, and require the model fingerprint to match. tests/manual/model_fingerprint.py already does most of this.
* Rebuild cost: see the section 1 performance gate.

### 15. Suggested phasing

* Phase 1: the section 1 performance gate (single-bar rebuild prototype, timed on the largest scores) comes first. Then the edit mode toggle, undo and redo, save as MusicXML with an unsaved-changes flag, round-trip tests.
* Phase 2: add, delete and change notes in one voice with overwrite mode and automatic rests, Region 4 attribute editing (Ref 24), the Check score report.
* Phase 3: bar and structure edits, the new score wizard, adding and duplicating parts.
* Phase 4: range selection, copy and paste, MIDI step-time entry.
* Phase 5: performance indicator editing, lyrics, chord symbols, voice dictation.
* Later: real-time MIDI recording, and MIDI, GP and BME export.