# Recall Score — User Guide

*Written for version 2026.1.65*

## 1. Introduction

Recall Score is a Windows desktop application designed to make learning new music faster and more intuitive for visually impaired musicians.

Because reading notation while playing an instrument is often not feasible, memorising a piece is essential. Recall Score provides tools to navigate scores, inspect details, and build muscle memory through structured practice features.

### Document Navigation

This guide is formatted as a single document. Screen reader users can use heading navigation keys (such as "H" or "1"–"3") to move between sections, or use the search function to find specific topics.

## 2. Getting Started

### 2.1 Installation and Running

1. Download the installer from the [Recall Score Download Page](https://chessel85.github.io/RecallScore/web_page).
2. Run the executable and grant Windows administrator permissions when prompted.

To uninstall, use standard Windows "Add or Remove Programs". Uninstalling preserves saved score settings.

To run, use the Recall Score icon on the desktop.

### 2.2 Opening and Closing Files

* Open File: Press "Control+O".
* Recent Files: Go to "File > Recent Files" to view the last 20 opened files.
* Close File: Go to "File > Close" to save settings and close the score.

When a file has been loaded, Recall Score automatically plays the notes at the current position.

#### Supported File Formats

* MusicXML: ".musicxml" and ".mxl".
* MuseScore: ".mscz" and ".mscx". Requires MuseScore 4.
* MIDI: ".mid" and ".midi" (Type 0 and 1).
* Guitar Pro: ".gp" (Guitar Pro 7 and 8).
* Ultimate Guitar Imports: Saved ".ug" files.

### 2.3 Importing from Ultimate Guitar

Tabs and chord sheets can be imported directly from the web:

1. Copy the web address of an Ultimate Guitar Chords or ASCII Tab page.
2. Select "File > Import from Ultimate Guitar" and paste the address (including "https://").
3. Use "File > Save Ultimate Guitar Import As" to save a local ".ug" copy for offline use.

*Note: Guitar Pro, Bass Tab, and Ukulele web pages on Ultimate Guitar are not supported via direct URL import. Download these files locally and open them via "File > Open".*

### 2.4 Saved Preferences

Recall Score automatically saves score-specific settings when a file is closed.

* Saved Per Score: Last cursor position, mute/solo states, visible attributes, metronome/announcer states, tempo adjustments, mixer volume/pan, renamed parts/instruments, and key signature overrides.
* Saved Globally: Terminology (UK/US), play mode, lead-in/loop defaults, live MIDI input setup, and voice control settings.

To reset saved settings for a score, select "File > Clear Preferences for [filename]". To view raw settings files, select "File > Open Local Folder".

## 3. Screen Layout & Navigation

The interface is structured into five main screen regions and a Status Bar.

* Cycle through Regions: Press "Tab" or "Shift+Tab".
* Jump to Region: Use keys "Z", "X", "C", "V", and "B" (the bottom row of the keyboard, left to right).
* Move to Status Bar: Press "F6" and press again to return to regions.

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
   * Press "Alt+Home" or "Alt+End" on a marking to jump to its start or end position.
   * Press "Control+N" on a marking type to toggle its visibility in the Notes region. (Items marked with an asterisk "*" are currently visible in the Notes list).

### 3.2 Status Bar Fields

Recall Score has a status bar which can be read with the standard screen reader keystroke for reading the status bar.

For finer control navigate to the status bar with "F6" and use "Tab" to move through the following information:

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
* Pause / Resume: Press "Control+Spacebar" to pause; "Spacebar" to resume; "Escape" to stop.
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
| Search Score Elements | "Control+F" |
| Jump to Next / Previous Search Match | "Alt+Right Arrow" / "Alt+Left Arrow" |

## 6. Practicing and Memorising Music

### 6.1 Overview Tools

* Performance Report ("Control+Shift+F"): Generates a summary of the score, including part names, note counts, dynamics, structural markers, and bar arrangements.
* Reorder Parts ("Control+Shift+O"): Rearranges the sequence of parts. The top-listed part is spoken first in the Notes list.

### 6.2 Filtering Parts (Mute & Solo)

Specific parts or voices can be isolated while learning:

1. Press "X" to go to the Parts region, or use the "Tab" key.
2. Arrow up and down to the desired Part.
3. Expand parts with the "Right Arrow" key. Expand parts to expose voices.
4. Press "F8" to mute a part, stave or voice. Notes in a muted element are not shown in the notes list.
5. Press "F9" to "Solo" a part, stave or voice. Soloing supersedes muting. Soloed elements are always included in the note list.
6. Press "Alt+F8" to Unmute All, or "Alt+F9" to Unsolo All.

### 6.3 Managing Visible Note Attributes

To customize what information is spoken when navigating notes:

1. Press "V" to enter the Attributes region or press the "Tab" key.
2. Focus on the attribute to be spoken (e.g., Fingering or Octave).
3. Press "Applications Key" (or "Shift+F10") to open the context menu.
4. Select the scope: "Whole Score", "Same Part", "Same Stave", or "This Voice", then press "Enter".

The selected attribute is now shown on the same row as a note in the note list which is in the requested scope and where the attribute exists.

The order of attributes in the attribute list and after notes in the note list can be changed. Attributes can also be hidden.

To reorder or hide attributes, select "Options > Attribute Management" ("Control+Shift+A"). In this dialogue:

* Move attribute Up / Down: "Alt+U" / "Alt+D"
* Add / Remove Scope: "Alt+A"
* Hide / Hide for All: "Alt+H" / "Alt+L"

### 6.4 Practising With Looping and Lead-ins

Default playback for Recall Score is to play from the current position to the end. It can also be set up to loop a defined number of bars. A lead-in metronome count can be defined before each repeat of the loop.

Configure looping and lead-in options in "Playback > Play Settings" ("Control+Shift+P"):

* Toggle Play Mode. Select "Play to End", "Play Loop Once", and "Play Loop Until Stopped". Cycle through these options in the main app with "Control+L".
* Loop length. Size of the loop in bars. In the main app use "Alt+Page Up" and "Alt+Page Down".
* Toggle lead-in clicks on or off. In the main app, toggle with "Control+I".
* Lead-in. Set length of lead-in clicks in bars and beats.
* Repeat handling. Affects how looping handles repeats with different endings. In the main app, cycle through options with "Control+R".

### 6.5 Screen Reader Speech During Playback

Recall Score updates the notes, attributes, performance regions and the status bar during playback. If focus is on one of these areas the screen reader reads out the new text. Refresh of text can be controlled as follows:

* Turn spoken announcements during continuous playback on or off: "Control+H".
* Delay Refresh ("Control+Shift+D"): Adjust speech timing relative to audio (-1.0s to +1.0s). Negative values speak notes slightly before sounding; positive values speak notes after.

## 7. Additional Features

### 7.1 Live MIDI Keyboard Input

A MIDI keyboard can be connected to play along using Recall Score's sound engine:

* Toggle MIDI Input: Press "Control+D".
* MIDI Settings: Select "Options > Live MIDI Input Settings" ("Control+Shift+L") to configure devices, instrument voices, volume, and pan.

### 7.2 Mixer

Open via "Playback > Mixer" ("Control+Shift+X"):

* Adjust Volume (0–100%) and Pan (-100% Left to +100% Right) for parts, metronome, announcer, and performance cues.
* Press "Alt+W" to toggle playback preview while making adjustments.

### 7.3 Voice Control

Toggle hands-free listening using "Alt+Enter". Configure microphone settings via "Options > Voice Control Settings" ("Control+Shift+R").

Recall Score responds to the following commands:

* "play", "stop" and "pause"
* "forward" and "back", or "right" and "left"
* "next bar" and "previous bar", or "next measure" and "previous measure"
* "home" and "end"
* "slower", "faster" and "default speed"
* "looping on" and "looping off"
* "lead in on" and "lead in off"
* "go to bar [number]"
* "loop length [number]"
* "attribute [1-9]"

### 7.4 Built-in Utility Tools

* Instrument Configuration ("Control+Shift+I"): Assign General MIDI sound assignments or rename parts.
* Tuner ("Control+Shift+T"): Spoken pitch identification and cent offsets via microphone input.
* Metronome Player ("Control+Shift+M"): Standalone metronome with configurable beat subdivision patterns.
* Strumming Patterns ("Control+Shift+U"): Preview strumming patterns embedded in imported Ultimate Guitar sheets.
* Link Parts ("Control+Shift+N"): Link identical parts (e.g., doubled lines) to share performance markings.
* Keyboard Shortcut Customisation ("Control+Shift+Y"): Rebind keyboard commands.
* Keyboard Echo Mode ("F12"): Practice keys to hear assigned commands without executing them. Press "F12" again to exit.

## 8. Reporting A Bug or Requesting A Feature

* Issue Reporting: Submit bug reports at the official [Recall Score Issue Tracker](https://github.com/Chessel85/RecallScore/issues).
* Feature Requests: To suggest a new feature, open a new issue on the same [Recall Score Issue Tracker](https://github.com/Chessel85/RecallScore/issues) and describe what you would like Recall Score to do.
