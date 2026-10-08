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

## Focus: `app/js/focus.js`

The single owner of the cycle Menu button, Regions 1 to 6 (invariant 7's
spirit). Tab is taken over only inside the cycle, so it wraps.

## Speech: `app/js/announcer.js`

Every one-off message goes through `announce()`/`announceUrgent()`: a
queue, `ariaNotify` where present, else two alternating live regions per
priority. Never write to a live region directly and never add another one.
Speak before redrawing, so "Measure 6." comes before the new note.

## Regions: `app/js/regions.js`

One focusable widget per region with `aria-activedescendant`; rows never
take focus. Every render gives rows fresh ids so the screen reader reads
the row even when its text is unchanged.
