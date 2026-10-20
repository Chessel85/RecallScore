# Recall Score Web Version — User Guide

## 1. Introduction

Recall Score is an application designed to make learning new music faster and more intuitive for visually impaired musicians. This guide covers the web version, which runs in a web browser with nothing to install.

A full desktop version for Windows, with further features, is available from the [Recall Score Download Page](https://chessel85.github.io/RecallScore/web_page).

Because reading notation while playing an instrument is often not feasible, memorising a piece is essential. Recall Score provides tools to navigate scores, inspect details, and build muscle memory through structured practice features.

### Document Navigation

This guide is formatted as a single document. Screen reader users can use heading navigation keys (such as "H" or "1"–"3") to move between sections, or use the search function to find specific topics.

## 2. Getting Started

### 2.1 Running

Go to <https://chessel85.github.io/RecallScore/app/> in a web browser.

The first visit downloads the program and its sounds, which can take a little while; later visits are quicker. Browsers only allow sound after a key press or click, so the first key pressed on the page starts the sound.

### 2.2 Opening Files

* Open File: Use the "Open a score" control at the top of the page, select "Menu > File > Open a score", or drop a file onto the page.

When a file has been loaded, Recall Score automatically plays the notes at the current position.

#### Supported File Formats

* MusicXML: ".musicxml", ".xml" and ".mxl".
* MIDI: ".mid" and ".midi" (Type 0 and 1).
* Guitar Pro: ".gp" (Guitar Pro 7 and 8).

### 2.3 Saved Preferences

Recall Score automatically saves settings in the browser.

* Saved Per Score: Last cursor position, mute/solo states, visible attributes, metronome/announcer states, tempo adjustments, and play settings.
* Saved Globally: Terminology (UK/US), performance indicator, marking types shown in the note list, and engraving details.

Settings for a score are found again when the same file is opened, even under another name. Clearing the browser's data for the site removes them, and in a private window they last only until the window is closed.

## 3. Screen Layout & Navigation

The interface is structured into a Menu button and six screen regions.

* Cycle through Regions: Press "Tab" or "Shift+Tab".
* Jump to Region: Use keys "Z", "X", "C", "V", "B" and "N" (the bottom row of the keyboard, left to right).
* Open the Menu: Press "M". Use "Up Arrow" and "Down Arrow" to move, "Right Arrow" or "Enter" to open a submenu, and "Left Arrow" to close it.
* Keyboard Help: Press "F1" to list every keyboard command.

### 3.1 Region Reference

1. Score Information ("Z"): Displays information such as title, composer, key, time signature, and initial tempo.
2. Parts ("X"): Displays the score structure in a hierarchical tree (Part > Stave > Voice).
   * Use "Up Arrow" and "Down Arrow" to navigate parts.
   * Use "Right Arrow" to expand a part into staves or voices; "Left Arrow" to collapse.
3. Notes ("C"): Lists the musical content at the selected score position.
   * Move horizontally across time using "Left Arrow" and "Right Arrow".
   * Move vertically through notes at the current time position using "Up Arrow" and "Down Arrow".
   * Press "Control+A" to reselect all notes at the current position.
4. Attributes ("V"): Displays note-level details (pitch, step, octave, bar, beat, dynamics, fingering, string/fret).
   * Press "Control+1" through "Control+9" while in the Notes region to quickly speak the corresponding attribute line without moving focus.
5. Performance Information ("B"): Displays global markings (repeats, endings, crescendos, key changes).
   * Press "Alt+N" on a marking type to toggle its visibility in the Notes region. (Items marked with an asterisk "*" are currently visible in the Notes list).
6. Status ("N"): Displays the status fields listed below.

### 3.2 Status Fields

The Status region lists the following information, one field per line:

1. Bar and Beat Position
2. Current Key Signature
3. Current Time Signature
4. Playback Tempo
5. Playback Status (Playing/Paused/Stopped)
6. Metronome (On/Off)
7. Position Announcer (On/Off)
8. Loop Length

## 4. Playback

### 4.1 Playback Controls

* Play / Stop: Press "Spacebar". When stopped, the cursor returns to the start position.
* Pause / Resume: Press "Control+Spacebar" to pause; "Spacebar" to resume.
* Play Selection: Press "Shift+Spacebar" to play all selected notes at the current position.
* Tempo Controls:
  * Press "F" to increase tempo (+10 BPM).
  * Press "S" to decrease tempo (-10 BPM).
  * Press "D" to reset to score default tempo.

Note: Playback automatically follows written repeats, codas, and D.C./D.S. markings. Manual step-by-step navigation via arrow keys bypasses jumps and simply moves through bars.

Written tempo changes (e.g., rallentando) are displayed in Performance Information but do not alter playback speed.

### 4.2 Audio Orientation Aids

* Bar Line Indicator ("Control+B"): Plays unique audio tones when crossing standard bar lines, double bar lines, or repeat boundaries. *Automatically mutes when the metronome is active.*
* Metronome ("Control+M"): Clicks during playback and step navigation.
* Standalone Metronome ("Control+Alt+Spacebar"): Plays a continuous background metronome at the current tempo without advancing the score position.
* Position Announcer ("Control+P"): A spoken metronome that announces beat counts (e.g., "1", "2", or subdivision counts like "and", "e", "a").
* Performance Indicator ("Control+C"): Affects audio cue for performance indicators:
  * Off
  * On during navigation
  * Always On
* Score Boundaries: Reaching the beginning or end of a score plays a boundary sound effect.

## 5. Navigation Commands

| Action | Shortcut |
| :--- | :--- |
| Move One Position Left / Right | "Left Arrow" / "Right Arrow" |
| Move One Bar Left / Right | "Control+Left Arrow" / "Control+Right Arrow" |
| Jump to First / Last Note | "Control+Home" / "Control+End" |
| Go to Specific Bar | Type bar number + "Enter" (or "Control+G") |
| Move to Next / Previous jump point | "Control+Alt+Right Arrow" / "Control+Alt+Left Arrow" |
| Find | "Control+Shift+F" |
| Find Next / Previous | "Alt+Right Arrow" / "Alt+Left Arrow" |

Find lists the attributes and performance markings this score contains, each with how many times it occurs. Type in the Filter box to shorten the list. Choose one with "Enter" or OK to jump to its next occurrence; focus moves to the notes region. "Alt+Right Arrow" and "Alt+Left Arrow" then step through the other occurrences from any region. The boundary sound plays when there is nothing to find, and after the note when the search wraps round to the other end of the score.

## 6. Practicing and Memorising Music

### 6.1 Filtering Parts (Mute & Solo)

Specific parts or voices can be isolated while learning:

1. Press "X" to go to the Parts region, or use the "Tab" key.
2. Arrow up and down to the desired Part.
3. Expand parts with the "Right Arrow" key. Expand parts to expose voices.
4. Press "F8" to mute a part, stave or voice. Notes in a muted element are not shown in the notes list.
5. Press "F9" to "Solo" a part, stave or voice. Soloing supersedes muting. Soloed elements are always included in the note list.
6. Press "Alt+F8" to Unmute All, or "Alt+F9" to Unsolo All.

### 6.2 Managing Visible Note Attributes

To customize what information is spoken when navigating notes:

1. Press "V" to enter the Attributes region or press the "Tab" key.
2. Focus on the attribute to be spoken (e.g., Fingering or Octave).
3. Press "Applications Key" (or "Shift+F10") to open the context menu.
4. Select the scope: "Whole Score", "Same Part", "Same Stave", or "This Voice", then press "Enter".

The selected attribute is now shown on the same row as a note in the note list which is in the requested scope and where the attribute exists.

### 6.3 Practising With Looping and Lead-ins

Default playback for Recall Score is to play from the current position to the end. It can also be set up to loop a defined number of bars. A lead-in metronome count can be defined before each repeat of the loop.

Configure looping and lead-in options in "Menu > Playback > Play Settings" ("Control+Alt+P"):

* Toggle Play Mode. Select "Play to End", "Play Loop Once", and "Play Loop Until Stopped". Cycle through these options in the main app with "Control+L".
* Loop length. Size of the loop in bars. In the main app use "Alt+Page Up" and "Alt+Page Down".
* Toggle lead-in clicks on or off. In the main app, toggle with "Control+I".
* Lead-in. Set length of lead-in clicks in bars and beats.
* Repeat handling. Affects how looping handles repeats with different endings. In the main app, cycle through options with "Control+R".

### 6.4 Screen Reader Speech During Playback

Recall Score updates the notes, attributes, performance and status regions during playback. If focus is on one of these areas the screen reader reads out the new text.

## 7. Reporting A Bug or Requesting A Feature

* Issue Reporting: Submit bug reports at the official [Recall Score Issue Tracker](https://github.com/Chessel85/RecallScore/issues).
* Feature Requests: To suggest a new feature, open a new issue on the same [Recall Score Issue Tracker](https://github.com/Chessel85/RecallScore/issues) and describe what you would like Recall Score to do.
