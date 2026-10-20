# web/CLAUDE.md

Rules for the browser version (RSBV). The plan is `UserPlans/RSBV.md`; the
browser evidence behind these rules is `docs/rsbv_spike_findings.md`.

## Reuse, never copy

Logic lives in `models/` (shared with the desktop) and is reached through
`web/py/web_api.py`. JavaScript draws rows, handles keys and speaks; it
never re-derives row text, navigation targets or wording. If the bridge
needs something a desktop controller computes, move it into `models/` first
and have both call it (as `models/announcements.py` and
`TimelineNavigator.move_to_jump_point` were). The bridge returns plain
dicts and lists only; JavaScript never holds a Python object.

## Keys: `app/js/keymap.js`

* The single key table and the single document `keydown` listener. Add a
  command as a table row plus `bind(id, handler)`; never add another
  `keydown` listener for a command.
* The table between the `KEYMAP-BEGIN`/`KEYMAP-END` markers is strict JSON
  (`tests/web/test_keymap_table.py` parses it).
* Never bind Escape (NVDA leaves focus mode on it) or Pause (never
  received). F10 and Alt alone are the browser's. Every dialog needs a
  Close or Cancel button.
* Letters and digits are named by `event.code` (physical position).
* Left/Right that no row takes while focus is in a list region are
  swallowed (preventDefault), doing nothing as on the desktop. Left to the
  browser, Firefox left NVDA saying "Recall Score document" and then
  silent in that region.
* M opens the Menu from anywhere in the cycle; closing it without a choice
  goes back to that region (`openMenu(back)`).

## Focus: `app/js/focus.js`

The single owner of the cycle Menu button, Regions 1 to 6 (invariant 7's
spirit). Tab is taken over only inside the cycle, so it wraps.

## Speech: `app/js/announcer.js`

Every one-off message goes through `announce()`/`announceUrgent()`: a
queue, `ariaNotify` where present, else two alternating live regions per
priority. Never write to a live region directly and never add another one.
Speak before redrawing, so "Measure 6." comes before the new note.

## Regions: `app/js/regions.js`

Rows take real focus (roving tabindex): the current row is the only
tabbable one and holds the focus; the region element is not focusable.
`aria-activedescendant` was tried first and NVDA stayed silent with it in
Firefox and Chrome. Every render builds fresh row elements, so the screen
reader reads the row even when its text is unchanged. Playback results
are the exception: regions other than 3 change their text in place
(`render(..., {inPlace: true})`), so a reader on Region 6 is not pulled
back to the position line on every note.

## Dialogs: `app/js/dialogs.js`

Native `<dialog>`. First widget in tab order gets focus, there is always a
Close or Cancel button (Escape may never arrive), and keymap.js ignores
every key while one is open. F1 help is built from the key table, so a new
command shows up there by being bound. A settings dialog is built from a
form the bridge describes (`web_api.play_settings_form`: fields, labels,
ranges, values) and asks the bridge which fields are enabled on every
change; labels are separate `<label for>` elements, never wrapped round a
select (its chosen option would be read into the name).

## Menu: `app/js/menu.js`

A real ARIA `menu` (not a dialog), shaped like the desktop menu bar: the
top level is File, Edit, Parts, Navigation, Help, each a submenu. A dialog
of grouped buttons was tried first and the user found it confusing. `MENUS`
lists keymap ids in the desktop's order; an unbound id is left out, so add
a new command's id there when it should be on the Menu. Left must close a
submenu and the menu (Escape may never arrive); keymap.js ignores keys
inside `[role=menu]`. Running a command first focuses the region that
menu acts on (each `MENUS` entry's `region`; none means the Menu button),
then runs it, so the result is heard there. "Back to where focus was" does
not work here: the Menu button is only reached through Region 1 or 6. A
command the desktop greys out is listed by `web_api.disabled_commands()`
and shown `aria-disabled` (still reachable, read as unavailable, does
nothing), never hidden and never answered with bespoke speech.

A checkable desktop action is a `menuitemcheckbox` (a key-driven toggle)
or `menuitemradio` (an extra marked `radio`) with `aria-checked`, from
`web_api.options_state()` read on every open; the tick is drawn
`aria-hidden`. The desktop's Terminology and Performance Indicator
submenus are flattened into the Options menu (this menu has two levels).
A choice made there is spoken, since the menu closes onto a region where
its checked state is not heard.

`showContextMenu()` is the same widget at one level, placed after a
region (Region 4's scope menu: Shift+F10, the ContextMenu key, or a
`contextmenu` event, which is the only form some browsers deliver for
that key). Its items come from the bridge (`web_api.region4_menu`, over
`models/attribute_scopes.py`, shared with the desktop's
AttributeController). Closing without a choice goes back to the row;
choosing redraws and then focuses the row, which reads it. Nothing else
is spoken, as on the desktop. Region 5's menu (same keys) is one item,
"Add/Remove <category> to/from note list" (`web_api.region5_menu`), doing
the same toggle as Alt+N (Ctrl+N on the desktop, which browsers keep):
Region 5 changes in place and the new state is spoken.

## Sound: `app/js/audio.js`

A thin synth driver. The bridge returns a sound plan with every move
(`result.sound`, see the "sound" comment in `web_api.py`) and from
`audition()`; audio.js plays it and decides nothing. Which cues fire is
shared Python (`audio/navigation_cues.py`, also used by the desktop's
PlaybackController), so never decide a cue in JavaScript. Programs arrive
0-indexed (invariant 9, converted once in `models/`). One-shot slots mirror
SynthEngine's: the metronome click and the bar line indicator share
"click", as `play_click` does; the performance indicator cue (Ctrl+C's
mode, `performance_indicator_cue`) has its own "cue" slot, on moves and,
when Always on, with each playback step. Play the sound before speaking or drawing.
The synth starts on the first key press or click (browsers need a
gesture); a plan that arrives before it is ready, or while the browser
has the context suspended, is dropped, never played late. A modifier key
(Shift, Control, the NVDA key) or Escape is not a gesture to the browser:
starting on one left the page silent for good, so those are skipped, the
gesture listeners stay for the page's life and resume a suspended
context, and nothing ever awaits `resume()` (it stays pending, with no
error, while permission is withheld). js-synthesizer's main script must load before the worklet node is
made (`JSSynth` global); audio.js preloads it with the SoundFonts.

## Playback: `app/js/scheduler.js`

Python plans the whole run: `web_api.play_*` over `models/play_plan.py`'s
`PlayTimeline` (count-in, steps, loop restarts, the desktop's timing, the
same code the desktop's PlaybackController and Sequencer use). The page
asks for it a chunk ahead (`play_plan(session, until_ms)`) and puts every
sound on FluidSynth's own sequencer in the worklet, timed in its ticks, so
the notes keep time in a busy or hidden tab. Only refills and the cursor
run on page timers. Never compute timing in JavaScript. A note-off is sent
1 ms early so it cannot cut a note-on at the same moment, and only once
everything starting before it is planned, so a key another group still
holds keeps sounding (SynthEngine's group note-off). The cursor moves when
a step is heard (`play_cursor`), after the output latency. A stop sends
all-notes-off on every channel: a note whose note-off is already queued is
no longer in the page's bookkeeping, and clearing the queue drops it. Pause, resume
and stop are Python's decisions (`play_toggle`, `play_pause`); a call with
an old `session` number is ignored, so a stop always wins. The free
metronome (Ctrl+Alt+Space) is planned the same way, as a timeline of
"click" entries (`web_api._FreeMetronome` over `audio/free_metronome.py`),
so the web has one transport. Space while it runs stops it. While
playback is going it is unavailable, as the desktop greys out its action:
the key does nothing and the Menu item is aria-disabled.

## Mixer

Ctrl+Shift+X (as on the desktop), on the Playback menu. The rows, the edit
session and the levels are `models/mixer_settings.py` (`mixer_rows`,
`channel_levels`, `MixerEdit`), which the desktop's PlaybackController
uses too; the bridge is `web_api.mixer_form`/`mixer_set`/`mixer_end`, and
audio.js only sends the control changes it is given. Every load sends
every channel's level (`result.mixer`), so nothing carries over from the
previous score; audio.js keeps them and sends them again if the synth
starts after the load. The dialog (`showMixer`) copies the desktop's:
list, Volume %, Pan %, Preview Alt+W, OK, Cancel; a change is sent on an
arrow step or a committed value, never per typed digit; Home is the
highest value, End the lowest, Insert the reset. Closing stops Preview
playback and puts focus back in the region it came from (Preview redraws
the regions, so the browser's own focus return finds nothing). The mixer
is saved with the score's settings (`.rsc` shape). `muted` has no UI on
either version.

## Find

Ctrl+F, and Ctrl+Shift+F as well because Firefox did not pass Ctrl+F to
the page in spike 2; on the Navigation menu. The targets, counts and row
wording are `models/` (`FindIndex`, `find_target.find_row_text` and
`find_row_label`, which the desktop's FindDialog uses too); the bridge is
`web_api.find_form`/`find_choose`/`find_step`, after
NavigationController's `_find`. The dialog (`showFind`) copies the
desktop's: list, Filter (matches each row's `filter` text, never the
count), OK, Cancel; Enter on the list is OK. OK arms the target and jumps
forward from the cursor, then focus goes to Region 3. Alt+Right/Left step
through occurrences from any region; with nothing armed or nothing found
the boundary cue plays, and a wrap plays the note then the boundary cue.
The armed target outlives a load, as on the desktop. Alt+Left/Right are
always taken, so they never reach the browser's Back and Forward.

## Stored settings: `app/js/storage.js`

localStorage stands in for the desktop's settings.json and `.rsc` files.
The shapes are Python's: storage.js keeps JSON text from
`web_api.global_settings_json()` (AppSettings) and
`score_settings_json()` (the desktop `.rsc` shape, via
`models/score_config_json.py`), never building either itself. Text, not
dicts, because a None must survive the trip. A score is keyed by the
SHA-256 of its bytes. Every storage call is wrapped, so a private window
or a full quota only means settings last for the session (said once).
Global settings are written when they change (Ctrl+C, Alt+N); a score's
when another is opened and on `pagehide`/hidden, the desktop's "swap files
and shutdown" points. A load passes the stored `.rsc` text into
`web_api.load(..., saved)`, which applies it in
`MainWindow._on_score_loaded`'s order. There is no settings import or
export: saving is automatic, and moving settings between browsers or in
from a desktop `.rsc` was dropped as unneeded (add it back only if a
tester asks).

## Score formats

`web_api.load` picks the reader as the desktop's ScoreLoadThread does
(`models/score_formats.family_for_path`): MusicXML through the
music21-free loader, MIDI and Guitar Pro through their own stdlib-only
readers. The accepted extensions come from `SCORE_FORMATS` (`WEB_FAMILIES`
in the bridge); the picker's `accept` in `app/index.html` lists them again
for the file dialog. MuseScore (local executable) and Ultimate Guitar
(music21) stay desktop-only. The upload is written under its own name,
because a MIDI file is titled by its file name.

## Mute and solo

The words "muted"/"soloed" live in the Region 2 row text (set by
`node_status_label`), never only in a one-off announcement.

## User guide

Help > User guide opens `docs/user_guide_web.html` in a new tab (staged
at the site root beside the desktop's pages). The `.md` is the source;
regenerate the `.html` by hand with `pandoc docs/user_guide_web.md -s
--metadata pagetitle="Recall Score Web Version User Guide" -o
docs/user_guide_web.html` (pagetitle, no --toc: see docs/packaging.md).
Edit either only when the user asks.
