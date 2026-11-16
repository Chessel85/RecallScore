# Functional differences: web version (RSBV) and desktop app

Written 2026-10-20, from the `rsbv` branch at `148d8ff` (RSBV Phase 6
complete). Sources: `web/app/js/keymap.js` (the web key table and its
`difference` notes), `web/app/js/menu.js`, `widgets/menu_builder.py`,
`main_window.py` `setup_shortcuts`, `web/CLAUDE.md` and `UserPlans/RSBV.md`.

Both versions run the same `models/` and `parsers/` code, so row text, note
wording, navigation targets, play plans, find targets, the Performance
Report, mixer levels and score edits behave the same. The differences are
in what is offered, which keys reach it, and the platform underneath.

## 1. Missing from the web version

### File menu

* Import from Ultimate Guitar and Save UG Import (needs music21 and network
  access the browser's CORS rules block).
* Open folder (the settings folder).
* Clear Preferences.
* Exit (closing the tab does that).

### Options menu

* Voice Control (Alt+Enter) and Voice Control Settings (Ctrl+Shift+R).
* Set MuseScore Location.

### Tools menu

* Tuner (Ctrl+Shift+T).
* Strumming Patterns (Ctrl+Shift+U).
* Metronome Player (Ctrl+Shift+M). The free metronome (Ctrl+Alt+Space) is
  there.
* Keyboard Shortcuts (Ctrl+Shift+Y): no shortcut remapping on the web.

### Help menu

* Quick Start.
* Keystrokes (Ctrl+/). F1 keyboard help, built from the key table, takes its
  place.
* Voice Commands.
* Keyboard Echo Mode (F12).
* Sound Icon Dictionary.
* About Recall Score.

### Keys and behaviours without a menu item

* Alt+Home and Alt+End in Region 5 (jump the cursor to the start or end of
  the focused marking's span). Not yet built on the web.
* Escape: on the desktop it cancels a typed bar number, or stops a paused
  playback. The web never binds Escape (NVDA uses it to leave focus mode);
  Backspace cancels a typed number. There is no one key to stop a paused
  plain run: Space resumes it (a paused lead-in or loop run stops, as on
  the desktop), so it takes Space twice.
* F6 and Shift+F6 (between the regions and the status bar). The status bar
  is Region 6 on the web, reached with N or Tab.

### File formats

* MuseScore (.mscz, .mscx): needs the local MuseScore executable.
* Recall Score UG import files (.ug): need music21.

The web reads MusicXML (.musicxml, .xml, .mxl), MIDI (.mid, .midi) and
Guitar Pro (.gp), as the desktop does.

## 2. Same command, different key

Each is forced by a browser keeping the desktop's key for itself.

| Command | Desktop | Web | Why |
|---|---|---|---|
| Close | Ctrl+W | Ctrl+Alt+W | Browsers keep Ctrl+W to close the tab |
| Find | Ctrl+F | Ctrl+Shift+F | Firefox keeps Ctrl+F for its find bar |
| Performance Report | Ctrl+Shift+F | Ctrl+Shift+R | Ctrl+Shift+F went to Find; R is free with no voice control. Also the browsers' hard reload, so it is lost if the page has not taken the key |
| Play Settings | Ctrl+Shift+P | Ctrl+Alt+P | Firefox's private window |
| Key Signature | Ctrl+Shift+K | Ctrl+Alt+K | Firefox's web console |
| Instruments | Ctrl+Shift+I | Ctrl+Alt+I, and Ctrl+Shift+I where it gets through | Developer tools in some browsers; Firefox passes it on |
| Link Parts | Ctrl+Shift+N | Ctrl+Alt+L | Chrome's private window |
| Add or remove a marking category in the note list (Region 5) | Ctrl+N | Alt+N | New window in every browser |
| Refresh on Playback | Ctrl+H | Ctrl+Alt+H | Browsers keep Ctrl+H for history |
| Delay Refresh | Ctrl+Shift+D | Ctrl+Alt+D | Browsers keep Ctrl+Shift+D for bookmarking all tabs |
| Attribute Management | Ctrl+Shift+A | Ctrl+Alt+A, and Ctrl+Shift+A where it gets through | Firefox's add-ons manager |
| Cancel a typed bar number | Escape | Backspace | Escape is never bound on the web |
| Open the menu | Alt or F10 | M (or the Menu button) | Alt and F10 are the browser's |
| Status bar / Region 6 | F6 | N | Region 6 is part of the region cycle |
| Previous and next section | Region 1 tab bar, Ctrl+Tab and Ctrl+Shift+Tab | Left and Right on Region 1's section row | Ctrl+Tab switches browser tabs |

Every other shared command keeps the desktop's key: Z X C V B, the arrows,
Ctrl+arrows, Ctrl+Home/End, Ctrl+Alt+Left/Right, Ctrl+G, digits with Enter
and Ctrl+Enter, Ctrl+A, Shift+arrows in Region 3, F8, F9, Alt+F8, Alt+F9,
Ctrl+Shift+O, Ctrl+Shift+X, Alt+Left/Right, Space, Ctrl+Space,
Ctrl+Alt+Space, Shift+Space, Ctrl+L, Ctrl+I, Ctrl+R, Alt+PageUp/PageDown,
F, S, D, Ctrl+B, Ctrl+M, Ctrl+P, Ctrl+C, Ctrl+V, Ctrl+1 to Ctrl+9, and
Shift+F10 / the Applications key for the Region 2, 4 and 5 menus.

## 3. Only on the web

* Region 6 (status) is a real region in the Tab cycle, with its own key, N.
  It holds what the desktop's status bar shows.
* A Menu button first in the Tab cycle; the menu is an ARIA menu with two
  levels, so the desktop's Terminology and Performance Indicator submenus
  are flattened into the Options menu as radio items. A choice made there
  is spoken, because the menu closes onto a region.
* Drag and drop a score onto the page, and an "Open a score" control at the
  top of the page.
* Settings follow the file's content (keyed by a hash of its bytes), so a
  renamed or moved copy finds them again. The desktop's `.rsc` sits beside
  the score file.
* With nothing saved, terminology follows the browser's language (the
  desktop uses the system's).

## 4. Platform differences in shared features

* Audition latency is about 53 ms key to sound, against Ref 9's 25 ms
  budget, which the desktop meets. Accepted for the web.
* Live MIDI Input (Ctrl+D, or Ctrl+Alt+M where the browser keeps Ctrl+D)
  and Live MIDI Input Settings (Ctrl+Shift+L) use the browser's Web MIDI:
  Chrome, Edge and Firefox on Windows and macOS, not Safari (it says so).
  The browser asks permission the first time. Keys sound only after the
  page has had a key press or click (browser rule), through the same
  SoundFont and the same latency as playback. There is no Refresh button:
  the device list is read each time the dialog opens.
* SoundFont: GeneralUser GS on the web, Airfont 380 on the desktop, so
  instruments sound different. App sounds (clicks, cues) use the same
  `recall_score_sounds.sf2` on both.
* Sound starts only after the first key press or click on the page
  (browser rule). A modifier key or Escape does not count.
* The first visit downloads Python (Pyodide) and the SoundFont; later
  visits use the browser's cache.
* Settings live in the browser's localStorage. They are lost if the site's
  data is cleared, last only for the session in a private window, and do
  not move between browsers. There is no settings import or export, and no
  way to bring in a desktop `.rsc`.
* Menu items and F1 help say "bar" whatever the terminology setting (the
  labels come from the static key table). Region text follows the setting
  as on the desktop.
* Commands the desktop greys out are listed on the web menu as unavailable
  (still reachable, read as unavailable, doing nothing) rather than hidden.

## 5. Deliberately the same on both

Changed on both versions together, so not a difference:

* The free metronome (Ctrl+Alt+Space) is unavailable during playback.
* A bar range row in the Performance Report (jump points, repeated
  sections, endings, wavy lines) jumps to its start bar.
* The performance indicator cue sounds only for a marking in the note list.
* `muted` in the mixer has no user interface on either version.

## 6. Not built on either

Edit mode, MIDI export, Guitar Pro and BME writing, capo handling, chord
naming, and saving changes back to the score file (CLAUDE.md "Known gaps").
