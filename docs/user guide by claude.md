# Recall Score — User Guide

*Written against version 2026.1.64*

## 1. Introduction

Recall Score is a Windows desktop application that makes learning new music quicker and easier for visually impaired musicians.

Visually impaired musicians usually can't read notation and play an instrument at the same time. Memorising a piece well enough to play it from memory matters more than it does for a sighted player. Recall Score provides tools to make this efficient. It covers both the first memorisation and then embedding the music into muscle memory.

This document is one long page. Use screen reader quick navigation keys to move between headings, or search the page for a key word.

## 2. Getting Started

The Help menu has a Quick Start guide, a Keyboard Shortcuts Reference (control+/) and a Sound Icon Dictionary. The Sound Icon Dictionary lists every sound Recall Score makes, with a button to hear each one.

### 2.1 Installing Recall Score

The latest Windows installer is on the [Recall Score download page](https://chessel85.github.io/RecallScore/web_page). It is a standard installer. Windows asks for administrator permission during setup.

Uninstall with the Windows Add/Remove Programs feature. Uninstalling does not delete the settings saved for each score.

### 2.2 Opening a Score File

Use File > Open or control+O. This is a standard open dialogue. Navigate to a folder, select a file and press enter.

When a file opens, Recall Score plays the notes at the current position.

File > Recent Files lists the last 20 files opened, numbered, most recent first.

File > Close closes the current score and saves its settings.

Recall Score opens these file types:

* MusicXML - .xml, .musicxml and the compressed .mxl format.
* MuseScore - .mscz and .mscx. This needs MuseScore 4 installed. If Recall Score can't find it, use Options > Set MuseScore Location. MuseScore files are not offered in the open dialogue until MuseScore is found.
* MIDI - .mid and .midi (types 0 and 1).
* Guitar Pro 7 and 8 - .gp.
* Saved Ultimate Guitar imports - .ug.

### 2.3 Settings Are Remembered

Recall Score remembers many settings for each score and restores them next time the file is opened. These include:

* The last position in the score.
* Mutes and solos.
* Which attributes are shown, and their order.
* Metronome, position announcer and bar line indicator on or off.
* Playback tempo.
* Mixer volume and pan.
* Renamed parts and changed instruments.
* Part order and linked parts.
* A key signature override.

To clear them, use File > Clear Preferences for (file name). File > Open Local Folder opens the folder where the settings are stored.

Some settings apply to every score, such as UK/US terminology, play mode, lead-in and loop settings, live MIDI input and voice control.

### 2.4 Ultimate Guitar Web Page Import

Recall Score can import a song directly from an Ultimate Guitar web page. Chords pages and ASCII tab pages are supported. Guitar Pro tab, bass tab and ukulele pages are not.

Use File > Import from Ultimate Guitar. Paste the full web address, including https://, and press enter.

Recall Score reads the page for chord names, lyrics, strumming patterns, tab, and the positions of verses, choruses and other sections.

Use File > Save Ultimate Guitar Import As to save it locally. Next time, open it with File > Open instead of pasting the web address.

## 3. Simple Playback

Press spacebar to play from the current position. Spacebar again stops.

Recall Score matches an instrument to each part of the score as best it can, and plays through a General MIDI sound engine.

Press control+spacebar during playback to pause. Press spacebar to resume, or escape to stop.

When playback stops, the position returns to where playback started.

Use S to slow the tempo and F to go faster, in steps of 10. D returns to the score's own tempo.

Shift+spacebar plays all the selected notes at the current position together.

Playback follows repeats, endings, codas and D.C./D.S. instructions. Moving with the arrow keys does not. It steps through the bars in written order.

Tempo changes written in the score, such as rall. or a new tempo marking, are shown but not played. Playback holds one steady tempo.

## 4. Screen Layout

Recall Score has a standard menu, a main area divided into five regions, and a status bar.

Tab and shift+tab cycle forward and backward through the five regions. The quick nav keys Z, X, C, V and B jump to the five regions from anywhere. They are the bottom row of the keyboard, left to right, in region order.

F6 moves between the regions and the status bar. In the status bar, tab moves through its fields.

### 4.1 Score Information (Z)

Shows high level information such as the title, composer or artist, key signature, time signature and starting tempo. Exactly what is shown depends on the file.

These are the opening values. For the values at the current position, check the status bar.

Some MusicXML files hold several separate pieces, such as a book of exercises. For these, a row of tabs sits above the score information, one per piece. Use left and right arrow keys to switch between them.

### 4.2 Parts (X)

A score is made up of one or more parts. The part name comes from the author of the score and usually matches the instrument that plays it, for example Piano or Saxophone. Use the up and down arrow keys to move through the parts.

Each part has at least one stave. Most instruments have one stave. A piano normally has two. A guitar may have a notation stave and a tablature stave. Press right arrow on a part to expand it and show its staves. Left arrow collapses it.

A stave has at least one voice. Instruments that play one note at a time usually have one voice. Keyboards, plucked instruments and drum kits may have more. A voice is a line of the music, such as a melody, counter melody or bass line. Press right arrow on a stave to expand it into its voices. Left arrow collapses it.

A drum kit's voices are its individual drum sounds, such as Snare or Closed Hi-Hat.

If a score contains chord symbols or lyrics, they appear as extra parts called Chords and Lyrics. In a Guitar Pro file, chords appear as a Chords voice within the guitar part.

A MIDI file, and an Ultimate Guitar import, shows parts only, with no staves or voices underneath.

Each row says "muted" or "soloed" when that applies.

### 4.3 Notes (C)

This region lists the notes at one position in the score. It is where most time is spent when learning a piece.

A new score opens at the first note, usually bar 1 beat 1. A score opened before returns to where it was left. Use the right and left arrow keys to move forwards and backwards through the score. The notes play as you move.

If there is more than one note at a position, use the up and down arrow keys to select each one on its own. Moving left or right selects all the notes at a position. Control+A selects all the notes again after using up and down.

By default a note is just its name, for example F sharp. The octave is left out. A grace note is read with its main note, for example "A grace B", and sounds briefly before it.

A key feature of Recall Score is that extra information about notes, or about performance of the piece, can be brought into this list from the Attributes and Performance Information regions as wanted.

Control+1 to control+9 speaks that numbered row of the Attributes region without leaving the note list.

### 4.4 Attributes (V)

Shows extra information for the notes selected in the Notes region. What is listed depends on what the score holds.

Notes always have a step, octave, bar, beat position and duration. Other attributes, such as dynamics, articulation, fingering, string and fret, appear when the score has them.

Open the context menu with the applications key or shift+F10 to add an attribute to the note list, or remove it. See section 7.3.

### 4.5 Performance Information (B)

Lists markings that apply at the current position across one or all parts. Examples are repeats, endings, crescendos, codas, and key, time and tempo changes.

For a marking with a start and an end, alt+home moves to its start and alt+end moves to its end.

A short sound plays whenever this list changes as you move, as a cue to check it.

Control+N, or the context menu on a line, adds or removes that type of marking to or from the note list. It acts on every marking of that type, not just the one line. A line starting with an asterisk is a type currently shown in the note list.

### 4.6 Status Bar

The status bar has eight fields, each reachable with tab:

* Bar and beat position
* Key signature
* Time signature
* Playback tempo
* Playback status (playing, paused, stopped)
* Metronome on or off
* Position announcer on or off
* Loop length

Bar and beat come first, so the screen reader's read status bar command announces the current position first.

Key and time signature show the values at the current position, so they follow any change partway through the score.

## 5. Orientation

It is important to keep a sense of position within a score. Recall Score helps in several ways.

### 5.1 Bar and Beat in the Status Bar

Press the screen reader's read status bar keystroke. This is NVDA+end in NVDA and insert+page down in JAWS. The bar and beat are announced first.

### 5.2 Bar Line Indicator

The bar line indicator plays a short sound whenever a bar line is crossed with the arrow keys. Toggle it with control+B.

There are different sounds for double bar lines, heavy bar lines, repeat starts and repeat ends. Hear them all in the Sound Icon Dictionary.

It is silent while the metronome is on, because the metronome already marks beat 1.

### 5.3 Metronome

Toggle the metronome with control+M. It clicks during playback, with an accent on beat 1.

It also sounds when moving through the score. Every beat becomes a position to land on, even where no note starts.

Playback > Play Metronome, or control+alt+spacebar, plays a free-running click at the current tempo without moving through the score.

### 5.4 Position Announcer

A talking metronome, toggled with control+P. It speaks the beat number, or "e", "and" or "a" for positions between beats.

It speaks only where something starts, so it announces the position of each note. With the metronome on, it also speaks on every beat.

### 5.5 Position Attribute

All notes have bar and beat position attributes. Add them to the note list so every note says where it is. See section 7.3.

### 5.6 Performance Indicator

Options > Cycle Performance Indicators plays a short ding when the position reaches a performance marking. Control+C cycles through off, on except when playing, and always on.

### 5.7 End of the Score

Trying to move past the first or last note plays a bump sound. The position does not change.

## 6. Setting Up a MIDI Keyboard

If a MIDI keyboard or controller is attached, Recall Score can play it through the same sound engine as the score.

Toggle live input with control+D. Set it up with Options > Live MIDI Input Settings, or control+shift+L.

The settings dialogue lists the available input devices, with a Refresh button for a device plugged in after the dialogue opened. The General MIDI instrument, volume and pan are also set here.

## 7. Learning a Score

### 7.1 Familiarisation

When learning a new piece, play it through several times from start to end. It is valuable to get a feel for the general shape of the piece.

Load the score and press spacebar. If the instruments don't sound right, use Parts > Instruments (control+shift+I). It gives each part a new General MIDI instrument, and can rename a part. For a drum kit, each drum sound can be changed.

These choices are saved and used next time the score is loaded.

### 7.2 Performance Report

Tools > Performance Report (control+shift+F) gives an overview of the score. It lists title, composer and so on, plus the number of bars, a note count for each part, and structural information such as repeats, endings and codas. It also lists dynamics and tempo instructions by bar.

### 7.3 Filtering Parts

For scores with many parts, the note list can get very busy. Recall Score filters notes by part, stave and voice to show just the notes of interest. Usually those that need memorising, or give context.

Jump to the Parts region with X. Use F8 to mute and F9 to solo the current row, or use Mute and Solo in the Parts menu.

These work at the part, stave and voice levels of the tree.

Notes from a muted item do not appear in the note list and are not played.

When anything is soloed, only soloed items appear and play. Mutes are set aside, not cleared.

Alt+F8 unmutes everything. Alt+F9 unsolos everything.

Parts > Reorder Parts (control+shift+O) changes the order parts are listed. The first part is read first in the note list. For example, put Lyrics above Chords to hear the words first.

### 7.4 Learning a Bar

With the parts filtered, press tab or C to move to the note list.

Check the status bar for the time signature of this bar.

Use the right and left arrow keys to move along the score. All the notes at a position are selected and played.

Use the up and down arrow keys to hear each note at the position. Each note plays as it is selected. Use the screen reader's read current line command to repeat it.

The bar line indicator, control+B, sounds when a bar line is crossed. This helps you stay within one bar.

By default only the note name is shown. Extra information, such as octave, duration and beat position, can be added from the Attributes region.

To do this, tab to the Attributes region or press V. Arrow to the attribute and open the context menu with the applications key or shift+F10. Choose how far it applies:

* Whole score
* Same part
* Same stave
* This voice

Press enter. Return to the note list. Wherever a note has that attribute, it is shown on the same line as the note.

To change the order attributes are read, use Options > Attribute Management (control+shift+A). It works on the part currently selected in the Parts region.

* Move Up (alt+U) and Move Down (alt+D) change the order.
* Add/Remove (alt+A) adds or removes the attribute, with the same choices as the context menu. This is useful for an attribute on only a few notes.
* Hide (alt+H) hides an attribute for this part. Hide for All (alt+L) hides it for the whole score.

An asterisk marks an attribute that has been added. Press enter to keep the changes, or escape to cancel them all. The attributes then appear in the new order in both the note list and the Attributes region.

### 7.5 Playing One Bar

Recall Score can play just one bar, repeat it non-stop, and play a lead-in click before each repeat. This lets you play along to embed the notes you have learnt.

Playback > Play Settings (control+shift+P) has:

* Playback tempo, from 5 to 300. S, F and D also change it.
* Play a lead-in metronome click. Control+I toggles this from anywhere.
* Lead-in bars.
* Extra lead-in beats.
* Play mode. Control+L cycles through the three modes:
    * Play to end. Plays from the current position to the end of the score, following repeats, endings and codas.
    * Play loop once. Plays the loop once, starting at the beginning of the current bar.
    * Play loop until stopped. Plays the loop over and over, starting at the beginning of the current bar.
* Loop length in bars, from 1 to 64. Alt+page up and alt+page down change it from anywhere. Or type a number and press control+enter.
* Repeat handling while looping. This decides what happens when the loop cuts across a repeat. Control+R cycles through the choices: first time through, second time through, or alternate.
* Play the lead-in again on every repeat.

The play mode, lead-in and loop settings apply to every score. The tempo is saved with each score.

### 7.6 Note Refresh On, Off and Offset

By default, the Notes, Attributes and Performance Information regions update during playback as each note plays. If focus is in one of these regions, the screen reader reads the new text as playback goes along.

This is useful when the note list shows one note at a time, for example a single melody, because each note is announced as it plays. Slowing playback, or speeding up the screen reader voice, can help.

If screen reader speech during playback is not wanted, toggle refresh with Playback > Toggle Refresh on Playback, or control+H.

Alternatively, the refresh can happen slightly before or after the note plays. Use Playback > Delay Refresh (control+shift+D). Set a delay from -1 to 1 second.

* A positive delay announces the note just after it plays.
* A negative delay announces the note just before it plays.

These settings are saved with each score.

### 7.7 Extending to More Bars

Once a bar is learnt, move to the next bar with the right arrow key, or control+right arrow to jump a whole bar. Learn this bar the same way.

Then move back to the first bar with the left arrow key, or control+left arrow.

With a loop play mode on, set the loop length to two bars:

* Press alt+page up

or

* Type 2 and press control+enter

or

* Change the loop length in Play Settings (control+shift+P)

Spacebar now plays two bars. Play along to embed them.

Some strategies for memorising bars:

* Add one bar at a time. Learn bar 1, then bar 2. Embed bars 1 and 2. Learn bar 3. Embed bars 1, 2 and 3. And so on.
* Doubling up. Learn bar 1, then bar 2, and embed them together. Learn bar 3, then bar 4, and embed them together. Then embed bars 1 to 4 together.
* Reverse. Learn the bars from the end backwards. As you add each new bar, you play on into bars that are already familiar.

## 8. Navigation

To move through the score:

* Right and left arrow keys move one position at a time.
* Control+right and control+left arrow keys move one bar at a time. The new bar number is announced.
* Control+home and control+end move to the first and last note.
* Type a number and press enter to jump to that bar, from anywhere. For example, type 12 and press enter. Escape cancels a half-typed number.
* Control+G opens a Go to Bar dialogue.

A pickup bar is numbered bar 0.

In a MIDI file or an Ultimate Guitar import, bar numbers are an approximation. An Ultimate Guitar import counts each chord change as one bar.

### 8.1 Find

Control+F opens the Find dialogue. It lists everything in this score that can be searched for, such as articulations, dynamics, ties, repeats and tempo changes, each with how many times it occurs. Type in the Filter box to narrow the list.

Arrow down the list and press enter. Recall Score jumps to the next occurrence and puts focus in the note list.

Press alt+right and alt+left arrow to move to the next and previous occurrence. This works from anywhere. At the end of the score it wraps round and plays the bump sound.

### 8.2 Sections

For an Ultimate Guitar import, control+alt+right and control+alt+left arrow jump to the start of the next and previous section, such as a verse or chorus.

## 9. Mixer

The Mixer sets the volume and pan of each part, the metronome, the position announcer and the performance cue.

Open it with Playback > Mixer, or control+shift+X.

Arrow through the list and tab to the volume and pan boxes. Volume runs from 0 to 100%. Pan runs from -100%, full left, to 100%, full right.

Changes are heard straight away. The Preview button (alt+W) starts and stops playback using the current play mode and loop settings, to hear the changes without closing the dialogue. OK keeps the changes. Cancel undoes them.

To silence a part completely, mute it in the Parts region instead.

## 10. Voice Control

Voice control is an experimental feature. It lets you control Recall Score hands free, so your hands stay on your instrument.

Toggle voice control with alt+enter, or from the Options menu. A short sound confirms whether listening has started or stopped.

Options > Voice Control Settings (control+shift+R) chooses the microphone and how confident recognition must be before a command is acted on. The Test button lets you practise commands without controlling the app.

Say commands clearly. The commands are:

* play, stop, pause
* forward or right, back or left
* next bar, previous bar (or measure)
* home, end
* slower, faster, default speed
* looping on, looping off
* lead in on, lead in off
* go to bar (number)
* loop length (number)
* attribute (number), to hear that row of the Attributes region

## 11. Guitar Pro

Recall Score opens Guitar Pro 7 and 8 files, which have the extension .gp. Older Guitar Pro files, such as .gpx, .gp5 and .gp4, are not supported. Guitar Pro can save to the newer format.

A Guitar Pro stave is shown as a tab stave. String and fret numbers are available as attributes. If the file has chord names or strum marks, the part gets a Chords voice.

## 12. Ultimate Guitar

Ultimate Guitar is a website with a huge collection of songs. One way to use it:

* Search the web for the song and add "ultimate guitar", for example Hotel California ultimate guitar.
* Open the page and copy its web address.
* In Recall Score, choose File > Import from Ultimate Guitar and paste in the full address.
* Recall Score reads the page and adds Chords and Lyrics parts. A tab page also adds a Tablature part.
* Use File > Save Ultimate Guitar Import As to save it as a local file, which can be opened with File > Open.

Minor chords are spoken in full, for example "A minor" rather than "Am".

A tab page has no rhythm. Its notes are laid out evenly, as a reading aid rather than the real timing.

Ultimate Guitar pages can hold strumming patterns. Use Tools > Strumming Patterns (control+shift+U), which is available only when the song has one. Choose the pattern from the list, then press Play pattern (alt+P) to hear it. Each slot of the pattern is listed with its beat position and stroke.

Ultimate Guitar also has a powerful search. In a web browser, go to the Ultimate Guitar home page and search for a song name. The results show how popular each version of the song is. Many songs can be downloaded in other formats, including Guitar Pro and MusicXML.

## 13. MIDI Files

MIDI files can be very basic. At their simplest they are just a series of notes, with no time signature, key signature or part names. Recall Score loads these but makes no guesses, so only basic information is available. All notes can still be played and moved through as normal.

MIDI files can also hold richer information, including key and time signatures. Recall Score uses these to improve navigation.

Parts > Instruments (control+shift+I) sets the instrument used for each part. This is useful when the MIDI file does not say.

Edit > Key Signature (control+shift+K) sets the key signature when the MIDI file has none, or the wrong one.

## 14. Other Tools and Options

### 14.1 Tuner

Tools > Tuner (control+shift+T) tunes a guitar, bass, violin or other stringed instrument through the microphone. Play a string and the tuner speaks the note and how many cents sharp or flat it is. Its Settings button sets the reference pitch, the microphone and how loud a note must be.

### 14.2 Metronome Player

Tools > Metronome Player (control+shift+M) is a practice metronome that doesn't need a score. Choose a time signature, a click pattern for each beat and a tempo. Play/Pause is alt+P, or spacebar.

### 14.3 Link Parts

Parts > Link Parts (control+shift+N) marks parts that are the same music, such as a doubled melody. Each linked part then shows the performance markings of the others.

### 14.4 Terminology

Options > Terminology chooses UK or US wording, for example bar or measure, and crotchet or quarter note.

### 14.5 Show Engraving Details

Options > Show Engraving Details (control+V) shows octave shift and clef change markings. They are hidden by default because they don't change the sound.

### 14.6 Keyboard Shortcuts

Tools > Keyboard Shortcuts (control+shift+Y) changes the shortcut for any action.

Help > Keyboard Echo Mode (F12) lets you press a key to hear what it does, without doing it. Press F12 again to leave.

## 15. Problems

If there is no sound, Recall Score still runs and can be navigated, but is silent. Check that Windows sound works outside Recall Score.

Help > About Recall Score shows the version number. Include it when reporting a problem at https://github.com/Chessel85/RecallScore/issues.

---

## Review notes (not part of the guide)

Corrections to the original draft, checked against the code:

* Mixer shortcut is control+shift+X, not control+alt+X.
* The Mixer Preview button does not play two bars. It starts and stops normal playback using the current play mode and loop length.
* "Reorder Attributes" / "Rearrange Attributes" is now Options > Attribute Management (control+shift+A). It works per part, and also has Add/Remove, Hide and Hide for All. Enter keeps changes, escape cancels them.
* "Delay Playback" dialogue is called Delay Refresh. Range is -1 to +1 second. Positive announces after the note, negative before.
* "Clear Settings" is File > Clear Preferences for (file name).
* MuseScore files are .mscz and .mscx (draft said .mscx only), and need MuseScore 4.
* Guitar Pro: only .gp (versions 7 and 8). .gpx is Guitar Pro 6 and is not supported.
* Missing file types: .mxl (compressed MusicXML, very common), .midi, and saved .ug imports.
* The status bar has eight fields, not six (draft listed five). The extra ones are metronome, position announcer and loop length.
* Chords and lyrics in a MusicXML file are separate parts called Chords and Lyrics, not a stave within a part. Only Guitar Pro puts a Chords voice inside the guitar part.
* The attribute context menu now lists scopes in the order whole score, part, stave, voice.
* Help menu items are called Keyboard Shortcuts Reference and Sound Icon Dictionary.
* The full voice command list is not in the Help menu. It was only in the User Guide; now listed in section 10.
* Position announcer: speaks wherever something starts. With the metronome on, that includes every beat.
* Bar line indicator: silent while the metronome is on. Sound types are double, heavy, repeat start, repeat end, and combined repeat end and start.
* Region 5 asterisk: correct as written (asterisk means shown in note list). Worth saying control+N acts on the whole type of marking, not one line.
* Narrator: I could not confirm a Narrator command to read the status bar, so I left Narrator out rather than guess.
* The line "Don't ask me what happens if different parts have different values" is a note to yourself. The status bar shows the values at the current position; I did not verify which part's values win when parts differ.

Added material the draft omitted:

* Control+O, Recent Files, Close, Open Local Folder.
* What settings are remembered per score and globally.
* Shift+spacebar, escape to stop from pause, position returns to start after stop, playback follows repeats but arrow keys don't, tempo changes not played.
* Control+1 to 9 attribute lookup, grace notes.
* Multi-piece MusicXML tabs in Score Information.
* Performance Information change cue.
* Performance indicator ding (control+C).
* Play Metronome (control+alt+spacebar).
* Control+L, control+R, repeat handling, lead-in on every repeat.
* Go to Bar (control+G), pickup bar 0, escape cancels typed number, Find filter and counts.
* Section jumps (control+alt+arrows).
* Reorder Parts, Link Parts, Key Signature, Terminology, Show Engraving Details.
* Tuner, Metronome Player, Keyboard Shortcuts, Keyboard Echo Mode.
* Voice control settings and full command list.
* A short Problems section.
