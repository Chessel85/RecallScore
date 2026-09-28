# Recall Score — User Guide

*Written against version 2026.1.62*

## 1. Introduction

This guide describes Recall Score, a Windows desktop application aimed at making learning new music repertoire easier and quicker for visually impaired musicians.

visually impaired musicians
usually can't read notation and play an instrument at the same time, so
memorising a piece well enough to play it from memory matters more than
it does for a sighted player. Recall Score provides tools to make this process efficient.  It covers both the initial memorisation and then embedding it into muscle memory.

This document is one long page. 
Use screen reader quick navigation keystrokes to move between headings.
or search the page directly for key words.

## 2. Getting Started

~~~ Quick start 

Look in the Help menu for a [Quick Start Guide], a [Keystrokes listing] and a [Sound Dictionary].

### 2.1 Installing Recall Score (Windows)

The latest Recall Score Windows installer  is available at
the (Recall Score download page)[https://chessel85.github.io/RecallScore/web_page].
It is a standard installer.

Uninstall by using the Windows Add/Remove Programs feature.

### 2.2 Opening a Score File

Open a score file with the File > Open menu item.  This is a standard open dialogue.  Navigate to a folder and select a file.  Hit enter to open it.

When a file has been opened Recall Score will play any notes at the beginning of the score.

Recall Score remembers many settings from when a score was previously opened.  to clear these details use the Clear Settings menu item in the File menu.

Recall Score supports the following file types:

* MusicXML files - `.xml` and `.musicxml`, 
* MuseScore files - .mscx.  Requires MuseScore to be installed on the computer.
* Midi files (types 0 and 1) - .mid
* Guitar Pro files - .gp, .gpx

### Ultimate Guitar Web page Import

Recall Score can import a song directly from an Ultimate Guitar web page.
Use the Import Ultimate Guitar web page from the file menu and paste the URL (including the https//) into the dialogue and hit enter.
Recall Score will then read the web page to extract chord names, lyrics, strumming patterns, tab and the position of verses, choruses etc.

Use the Save Ultimate Guitar web page to save all this information locally so next time the File / Open dialogue can be used rather than pasting in a web address.

## Simple Playback

To  play the current score press spacebar.  
recall 
score matches instruments to parts of the score as best it can and plays via a General Midi player.  Spacebar stops playback.

Press control+spacebar during playback to pause and spacebar to resume or escape to go back to a stopped state.  

Use S to slow the tempo and F to go faster.  D reverts to the default score tempo.

## Screen Layout 

Recall Score consists of a standard menu, the main application area divided into five regions and a status bar.

Tab and shift+tab cycle through the five regions forward and backward.  There are also quick nav keys of Z, X, C, V and B which jump to the five regions from anywhere.

F6 cycles to the status bar and back to the five regions.  When on the status bar, use tab to move through its constituent parts.

### Score Information

Shows high level information such as the score's title, composer or artist, key signature, time
signature and starting tempo, although exactly what is shown depends on the contents of the file.

### Parts 

A score is made up of one or more parts.  The exact name depends on how the author of the score named the part and usually matches the instrument that plays it e.g. Piano, saxophone.  Use arrow keys to move up and down the list of parts.

Each part is made up of at least one stave.  Most instruments have one stave.  A piano normally has two staves.  A guitar may have both a music notation stave and a tablature stave.  
Use the right arrow key on a part to expand it and show the staves.  Arrow down to go through the staves.  Left arrow key colapses a part.

A stave is made up of at least one voice and instruments that can only play one sound at a time typically have just one voice.  A polyphonic instrument like those in the keyboard family, percussion kits or plucked instruments may have more than one voice.  A voice is a series of notes that make up an element of the music such as a melody, counter melody or bass line.  Use the right arrow key to expand a stave into its voices and left arrow key to collapse it.

Score files can also carry chord information which is shown as a stave within a part.  Lyrics also show up as a separate stave within a part.

### Notes 

This region lists notes at a particular position within the score.  It is the region where most time is spent when learning a new piece.

A new score opens at the bar and beat where the first note occurs, typically bar one beat 1.  Use the right and left arrow keys to move forwards and bckwards along the score.  The notes are played as progress is made through the score.

If there is  more than one note at a time position use the up and down arrow keys to select each one indvidually.  All notes are selected at a time position when moving left and right.  Use control+A to select all the notes again after using the up and down arrow keys.

A key feature of Recall Score is that extra information about notes or performance of the piece can be brought in from the [attributes] and [performance information] regions as desired by the user.  

### Attributes 

Shows extra information for the selected notes and score information shown in the notes region.  What is listed depends on the information held in the score. 

Notes always have a step, octave, bar, position and duration plus some others.  Performance indicators have different attributes depending on the type.

Use the context menu opened by the right alt key on the keybboard or with shift F10) to bring up a menu to add the attribute to notes.  Use the Reorder Attributes dialogue from the Options menu to change the order they are displayed.

### Performance Information 

Lists information applicable to one or all staves/parts.  Examples include crescendos, repeats, endings and codas.

For information which has a start and end position, alt+home moves Recall Score to the start and alt+end moves to the end.

Pressing control+N or bringing up the context menu on a line adds and removes the information to the notes list.  An asterisk starts the line for information added to the note list.

### Status Bar

The status bar is made up of six individually focusable fields: 

* Measure and beat position,
*  Key signature
* Time signature
* Playback tempo
* Playback status

Bar and beat are first in the order so a screen reader command to read the status bar announces the current position.

Access the status bar with F6 and use tab to move through each element.

Tempo shows the current playback tempo.  Key and time signature reflect the current values based on the current position.  Don't ask me what happens if different parts have different values.  I have only just thought about this.

## Orientation

It is important to keep a sense of the current position within a score.  There are several ways Recall Score helps with this:

### Bar and beat position in the status bar

Press the screen reader keystroke to read the  status bar.  This is NVDA+End for NVDA and Jaws+Page Down for Jaws.  [What is narrator?]

The bar and beat position are the first two pieces of information announced.

### Bar Line Indicator

The bar line indicator plays a short beep whenever a barline is crossed.  Toggle this feature on/off with control+B.

There are different sounds for repeat barlines, double bar lines and thick bar lines.

#### Metronome

Toggle the metronome  on/off with control+M.  The metronome sounds during playback.  It also sounds when moving through the time line and acts as a position to land on even if there are no notes present.

### Position Announcer

A talking metronome toggled on/off with control+P.
This speaks the beat position plus a matching 'e', 'and' and 'a' sound.  
It only announces when a note is present at the position.

### Position Attribute 

All notes have the bar and position attribute.  Select any note from the notes list and tab to the attribute list.  Arrow down to 'position' and bring up the context menu.  Arrow down the popup menu.
The attribute can be added to notes just in the same voice, same stave, same part or all parts in the score.

# Setting Up A MIDI Keyboard

If there is a MIDI keyboard /  controller attached to the computer, Recall Score can link to it and notes played on the keyboard come through the same sound engine as the score playback.  

Toggle live input with control+D.  Setting it up is via the Live MIDI Input Settings menu item, or control+shift+L.

The settings dialogue lists the available input devices.  The associated general MIDI instrument, pan and volume are also set here.

# Learning A Score

## Familiarisation

When learning a new piece, play it through several times in its entireity.  It is valuable to have a feel of the general shape of the piece.  

Load the score file and press space to play.  If the instruments do not sound correct, use the Instruments dialogue  in the Parts menu (control+shift+I) which allows each part of the score to have a new general MIDI instrument associated with it.

These instruments are stored and will be the same the next time the score is loaded.

## Performance Report

The Performance Report in the Tools menu (control+shift+F) gives an overview of the score.  title, composer etc but also structural innformation such as repeats, endings and codas.

## Filtering Parts

For scores with many parts, the note list can become very busy.  Recall Score can filter notes at the part, stave and voice level to reduce the note list down to the notes of particular interest.  Usually those that need memorising or give context.

Jump to the parts region with the X uick nav keystroke.  use the mute and solo options from the Parts menu, or use the F8 keystroke for mute and F9 keystroke for solo, to filter what notes are listed.  

These keystrokes apply at the part, stave and voice levels of the Parts tree.  

Notes from a muted item do not appear in the notes list.

Notes in a soloed item always appear in the note list, superseding mutes at the same and lower levels.

Alt+F8 unmutes all and alt+F9 unsoloes all.

## Learning a bar

With the parts filtered to show the desired notes, press tab or C to move to the notes list.  

Check the status bar to confirm the time signature that applies to this bar.  

Use the right and left arrow keys to move along the time line.  All notes at a time position are selected and all notes are sounded.

Use up and down arrow keys to identify each note at the current time position.  Each note is sounded as it is selected.  Use the screen reader "read current line" to repeat the current row.

The bar line  indicator, toggled with control+B, makes a noise when a bar line is crossed.  This is useful to help stay within one bar.  Trying to move beyond the first and last available notes causes a bump noise to be sounded indicating the limits of the timeline.

By default, just the note name is displayed. Extra information about notes can be added from the attributes region such as octave, duration and beat position.  

To do this tab to the attributes region or press the V quick nav shortcut.  Arrow to the attribute to be added and bring up the context menu by pressing the right-hand alt key or shift+F10.  Arrow down through the options to select the scope and hit enter.

Return to the note list and, if the attribute is available for the note, it is displayed on the same line as the note.  

The order of attributes can be changed using the Rearrange Attributes dialogue from the Options menu.  This dialogue lists the available attributes and they can be moved up and down the list with the up button, shortcut alt U, and down button, shortcut alt+D.  Hit enter to close the dialogue and apply the changes.  The attributes now appear in the specified order in both the note list and the attributes region.


## Playing One Bar

Recall Score can be set up to play just one bar, to repeat the playback non-stop, and to play a lead in metronome click for each repeat.  This allows playing along with the music to embed the learnt notes.

Playback Settings, from the Playback menu or control+shift+P, contains the following:

* Tempo for playback.  Playback tempo can also be changed with S and F on the keyboard.
*  Lead in tickbox.  Can also be toggled with control+I from any region.
* Number of lead in bars 
* Lead in beats
* Play mode.  

** Play End.  Starts playback from the current position until the end of the score respecting any repeats, endings and codas.
** Play loop once.  Plays the score for the length of the loop from the start of the current bar.
** Play loop until stopped.  Plays the length of the loop repeatedly from the start of the current bar.

* Loop length.  Number of bars for the loop.  Can be changed when in a region with alt+page up and alt+page down. Or set a specific length by typing a number and pressing control+enter. 
       * Repeat mode. Defines how repeats and endings are handled if the playback of the loop encounters these.

A metronome can be toggled on with control+M.  A position announcer, a talking metronome, can be toggled using control+P or from the Options menu.

## Note Refresh On, Off and Offset

By default, the notes, attributes and performance indicator regions are updated on playback as each note is played.  If focus is on one of these regions, the screen reader will read out the new text as playback progresses.  

This can be useful if the note list is showing just one note e.g. a monophonic part, as the note to be played is announced.  Changing the playback speed, or the speed of the screen reader voice may help with clarity.

If screen reader feedbback is not wanted, refresh can be toggled from the Playback menu or with control+H.  

Alternatively, the refresh can be set to occur with a time offset from playback. Use the Delay Playback dialogue available from the Playback menu or with control+shift+D. A positive or negative offset can be set.  This means the screen reader announces the new text at a different time to the note playback either to say what the upcoming note is or what the just played note is.  
 
## Extending To More Bars

Once a single bar has been learned, move to the next bar with just the right arrow key or with the next bar shortcut of control+right arrow.  Repeat the learning process for this bar.

Once the second bar has been learned, move back to the first bar with the left arrow key, or the move bar shortcut control+left arrow.

with the playback mode on looping, set the length of the loop to two bars:

* Press alt+page up

or

* Press 2 on the keyboard and press control+enter 

or

* Change the loop length in the playback settings dialogue (control+shift+P)

Pressing spacebar to play now plays back two bars.  Accompany playback to embed the two bars into memory.

There are several strategies for memorising bars:

* Learn one new bar at a time adding the new bar onto the end of what has already been learned. e.g. Learn bar 1, then bar 2,  Embed bars 1 and 2.  Learn bar 3.  Embed bars 1, 2 and 3 and so on.
* Doubling up.  Learn bar 1, then bar 2.  Embed this by doubling up to both bars 1 and 2.  Then learn bar 3, then bar 4.  embed bars 3 and 4 together.  Then embed bars 1, 2, 3 and 4 together.
* Reverse.  Learn the bars in reverse order.  As you embed each new  bar, you are repeating already familiar bars as you play to the end.

# voice Control

A more experimental feature is voice control.  This allows Recall Score to be controlled hands free so they can remain on the instrument being played.

Toggle voice control with alt + enter or from the |Options menu.  A short double beep indicates if voice control has started or just finished.

Clearly saying commands like play and stop control Recall Score.  There are commands for navigating, looping and setting the length of the loop.  The full list of commands is available from the |Help menu.

## Navigation 

To move through the score:

* \Press right and left arrow keys to move one time step at a time
* Press control + left / right arrow keys to move one measure at a time
* Press control + home and control + end to move to the first and last time step 
* |Just type a number and hit enter to jump to that bar e.g. Type 12 and hit enter.



'' Find

Control + F launches the find dialogue. A list of all items that can be searched for are listed.  

Arrow down the list and hit enter on the item being searched for.  Recall Score jumps to the next  occurance and puts focus in the note list.

Press alt + left / right arrow keys to move to the previous and next occurances.  This feature wraps around the score making the score end sound if needed.



' Mixer

The mixer allows the volume and pan of parts, metronome, position announcer and performance cue to be  adjusted.

|Launch the mixer from the playback menu or with control \+ alt + X.

Arrow through the list of options and tab to the areas to adjust volume and pan.  A volume of 100% is full volume.  A pan of -100% is full left and 100% is full right.

The preview button plays two bars to enable further adjustements without closing the dialogue.


## Guitar Pro 

Recall Score can load Guitar Pro files in the version 7 and version 8 formats.  These have file extensions of .GPX and .GP.

Not much else to say really.

## Ultimate Guitar

Ultimate Guitar is a web site with a vast repository of pieces.  Some ways to use it are:

* Do a Google search for a piece and add uultimate guitar to the search string e.g. Hotel California ultimate guitar
* Go to the page and copy the URL.
* In Recall Score file menu, select Import from \ultimate Guitar and paste in the full \url.
\* Recall Score now reads the web page and adds chords and lyrics as parts.
* Use the file menu option to save the \ultimte Guitar score as a local file which can be opened using file open.

\ultimate Guitar does hold strumming information.  Use the Tools menu to locate the strumming tool.  Select the strumming pattern from the dropdown list and then press play to here it.

\ultimate Guitar does have a powerful search feature.  From a browser go to the \ultimate Guitar home page.  \press E to do a search and type in a song name.  The search results are displayed and give an indication of how popular different version of the same song are.  \it is possible to download the files in various formats including Guitar \pro and \music XML.


## \midi files 

MIDI files can be very basic.  At their simplest, they are just a series of notes with no extra information like time or key signature.  Recall Score can load this format but does not make any assumptions so only basic information is available.  But all notes can be played and moved through in the normal way.

MIDI files can also support rich musical information including key and time signatures, and these are used to improve navigation.

The \Instruments menu item in the \parts menu allows the instrument used for playback to be set for each part.  This is useful when the MIDI file does not contain this information.






