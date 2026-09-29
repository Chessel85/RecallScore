# Recall Score - Editor Version

It is proposed that version 2  of Recall Score enables the user to edit existing scores or create new ones from scratch.  This will be version 2026.2.

It is expected that Recall Score will operate in read-only mode and edit mode.

There are many design decisions that need to be made on the behaviour of the app.  Examples include:
* Creation of score information
* Adding parts, staves and voices
* Creating, reading, updating and deleting (CRUD) for notes
* Setting attributes for notes
* CRUD for performance indicators
* Approach to correct content of bars.  That is, ensuring notes and rests for each voice in a bar add up to a whole bar.
* Formats that can be saved 
* How exhaustively musical notation is covered as there are hundreds of details about musical scores.  Only those relevant to playback need be considered.
* Is support provided for input by connected MIDI devices?
* Can MIDI be imported 
* How does copying, cutting  and pasting  work?
* Tools for speeding up input such as copying a range, duplicating voices, staves and parts, selecting similar items
* Guitar specific features like chord diagrams 
* Entering lyrics 

A key point is that this is not a music score engraving application.  It is focused on entering notes as if being placed on a formal engraved score but without the concern of rendering it as such.  

Is there a crossover to becoming a DAW for MIDI input?  Yes.  

## Further things to think about (added by Claude, 2026-09-29)

These are grouped roughly in the order I'd want them decided, because the early ones constrain everything after them.

### 1. The document model: what is the source of truth?

This is the biggest decision and it should come first. Today the app is read-only by design:

* MusicData is rebuilt wholesale from the file on every load (CLAUDE.md invariant 3). It holds a flattened, derived view: NoteData with beat positions already converted to time-signature units, rests skipped, and part names copied onto every note.
* That view loses information. It is built for navigation and playback, not for writing back out.

So if you edit NoteData directly and write it out, you lose everything the app does not model. Options:

* A. Keep the MusicXML element tree as the document of record. Every edit changes the tree, then MusicData is rebuilt from it (the ElementTree timeline build is already about 1 ms for typical files). Save just writes the tree. Anything the app does not understand (layout, credits, beaming, lyric details, notation it ignores) survives a round trip untouched. My recommendation.
* B. Use music21 streams as the model. Rich, but about 460 ms per rebuild, and music21 has its own opinions about how to rewrite MusicXML.
* C. Build a new editable model made for this app. Cleanest API, most work, and anything not modelled is lost on save.

With A, imported MIDI, Guitar Pro and Ultimate Guitar files would first be converted into a MusicXML tree, which then becomes the thing being edited. That conversion is a feature in its own right.

Related questions:

* After an edit, how is the cursor restored after the rebuild? It should come back to the same measure, beat, part and voice, not the same list index.
* Region 2 toggles must survive a rebuild (invariant 11 already warns about this).
* Invariant 8 ("two copies of the same fact diverge") matters much more once you can edit: every edit must write exactly one place.
* What happens to .rsc sidecar overrides (renamed parts, instrument overrides, key override) on save? Write them into the file, keep them in the sidecar, or ask?

### 2. Mode switching and the keyboard

* Ref 23 already specifies Ctrl+Shift+E for switching between Read-Only and Edit mode, with a spoken announcement.
* In edit mode, letter keys will want to mean note entry (A to G). That collides with the Z/X/C/V/B region jumps and other single-letter shortcuts. Decide whether edit mode has its own shortcut map, and how ShortcutController's reserved list and user customisation handle two maps.
* Is the mode per window or per region? For example, only Regions 3 and 4 might become editable.
* Voice control: dictation ("C sharp quarter", "rest eighth") is a very natural way to enter notes for this user base. Decide early whether voice commands are part of edit mode's design rather than added later.

### 3. The cursor in edit mode

* Navigation currently lands only on attacks: rests are skipped (invariant 15). An editor needs to land on rests, on empty bars, and on an insertion point between events.
* Does the cursor move by event, by the current input duration, or by beat? Most notation editors move by event and keep a separate "input duration" setting.
* Which part, staff and voice is the cursor in? Today Region 2 filters what is shown. In edit mode it probably also has to choose the one voice being written.

### 4. Note entry model

* Pitch entry: letter name plus an automatic octave (nearest to the previous note, as in MuseScore and LilyPond's relative mode), with keys to force the octave up or down.
* Accidentals: taken from the key signature by default, or always explicit? How do you enter a courtesy accidental?
* Spelling: a MIDI keyboard gives a number, not a name. pitch_spelling.py already guesses, but the user needs a quick "respell enharmonically" command.
* Transposing instruments: the user enters written pitch, and midi_pitch follows from the transpose setting (invariant 15 already keeps these apart).
* Guitar and tab: enter by string and fret, or by pitch and let the app choose string and fret from the tuning? Both, with one derived from the other? What happens to string and fret when a pitch is edited, or to pitch when the fret is edited?
* Chords: a key to add a note to the current chord, separate from moving on.
* Tuplets, dotted notes, ties and grace notes each need a way to enter them.
* Ref 24: play every change immediately. Also decide what is spoken after each edit, and how much. A fast typist does not want a long sentence after every keystroke.

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
* Rebuild cost on large scores: about 1 ms is fine for small files, but edit mode rebuilds after every keystroke, so check the biggest files. Rebuilding one measure at a time may be needed later.  This sounds like a big issue.

### 15. Suggested phasing

* Phase 1: decide the document model, the edit mode toggle, undo and redo, save as MusicXML with an unsaved-changes flag, round-trip tests.
* Phase 2: add, delete and change notes in one voice with overwrite mode and automatic rests, Region 4 attribute editing (Ref 24), the Check score report.
* Phase 3: bar and structure edits, the new score wizard, adding and duplicating parts.
* Phase 4: range selection, copy and paste, MIDI step-time entry.
* Phase 5: performance indicator editing, lyrics, chord symbols, voice dictation.
* Later: real-time MIDI recording, and MIDI, GP and BME export.