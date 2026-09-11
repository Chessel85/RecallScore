# Keyboard Shortcuts dialog - implementation plan

Status: planned 2026-09-11, not started. Written for a Sonnet implementation pass.

## What the user asked for

Tools menu item opening a modal dialog to redefine every action's shortcut:

* a filter edit box narrowing the list to actions containing the typed text
* the list of actions, with each one's current shortcut
* an edit box that records a new shortcut (Ctrl / Shift / Alt + key)
* Apply and Close buttons
* Restore Defaults, asking for confirmation first
* one keystroke does one thing: applying a keystroke already in use warns and
  asks whether to continue; if yes, the old action is left with no shortcut
* menus show the updated shortcuts
* today's shortcuts are the factory defaults that Restore Defaults returns to

## Design decisions (made while planning - flag to the user if they object)

1. Menu item: Tools > "&Keyboard Shortcuts..." (the user said "Keystroke
   bindings"; "Keyboard Shortcuts" is the common name, as in VS Code and
   Windows apps). K is a free mnemonic in Tools and at top level. There's no
   default shortcut (it can be given one in the dialog like any other action).
2. Apply commits right away: the shortcut is live in the menus and saved to
   settings.json. Close just closes. There's no Cancel or working copy. This
   departs from the "working-copy Ok/Cancel" pattern in
   `docs/dialog_widget_patterns.md` on purpose, because the user asked for
   Apply + Close. Restore Defaults also commits right away, after it's
   confirmed.
3. Added: a "&Remove Shortcut" button, which leaves the selected action with
   no shortcut. Most shortcut editors have one, and it's otherwise impossible
   to unassign without taking the key for something else.
4. Rebindable = every menu QAction, plus the four window-level QShortcuts that
   are single commands: tempo faster (F), tempo slower (S), tempo reset (D) and
   play the selected notes (Shift+Space).
5. Not rebindable (fixed, and also reserved so nothing else can take them):
   keys handled inside widgets' `keyPressEvent`/`event()` (arrows, Tab
   cycling, Ctrl+1..9, Alt+PageUp/Down, Ctrl+Home/End in Region 5, Shift+F10 /
   Menu), the typed-bar-number family (digits, Enter/Return, Ctrl+Enter/
   Ctrl+Return, Escape), and F6/Shift+F6 (Windows pane-switch convention).
   Making the widget-local keys rebindable would be a much larger refactor of
   hardcoded key handling. If the user wants that, it's a second phase.
6. One combination per action (no multi-key chords like "Ctrl+K, Ctrl+S").
   The one exception is Enter/Return twins: assigning X+Enter or X+Return
   binds both, because Qt treats numpad Enter and main Return as different
   keys (see the Voice Control comment in `menu_builder.py`).

## The central idea: defaults are never written down twice

CLAUDE.md invariant 8 ("two copies of the same fact will diverge") rules out
a separate table of default shortcuts. **`MenuBuilder` and
`MainWindow.setup_shortcuts` stay the single source of the factory defaults**,
including the `_shortcut_for_platform` macOS logic and the
`QKeySequence.Open/Close/Quit` standard keys. At startup, before it applies
any user overrides, the new controller snapshots whatever shortcuts those
objects were built with. That snapshot is the default map. Settings store
only the user's differences from it, so a changed default in a future version
still reaches users who never touched that action.

Keys are stored and compared as `QKeySequence.toString(PortableText)` strings
(for example `"Ctrl+Shift+K"`). Keys are displayed with `NativeText`, which is
what the menus themselves show.

## Files

### 1. `models/shortcut_map.py` (new, Qt-free - invariant 1)

Pure logic on canonical PortableText strings, so it's trivially unit-testable.

```python
def with_twins(seq: str) -> tuple[str, ...]:
    """'Alt+Return' or 'Alt+Enter' -> ('Alt+Enter', 'Alt+Return'); a bare
    'Return'/'Enter' likewise; anything else -> (seq,). Enter first, matching
    the existing Voice Control order so the menu shows the same text.
    Suffix test only (seq == 'Return' or seq.endswith('+Return')) - never
    split on '+', which is itself a key ('Ctrl++')."""

@dataclass
class ShortcutMap:
    defaults: dict[str, tuple[str, ...]]   # action id -> default seqs, in display order
    overrides: dict[str, str] = field(default_factory=dict)  # id -> seq, "" = no shortcut

    def bindings(self) -> dict[str, tuple[str, ...]]
    def owner_of(self, seq: str) -> Optional[str]
    def assign(self, action_id: str, seq: str) -> Optional[str]   # returns displaced id
    def clear(self, action_id: str) -> None
    def restore_defaults(self) -> None
```

Semantics of `bindings()`:

* Walk ids in `defaults` order. Ids with a non-empty override claim
  `with_twins(override)` first. If two overrides claim the same sequence (only
  possible in a hand-edited file), the later one gets `()`.
* An id with override `""` gets `()`.
* An id with no override gets its defaults **minus any sequence an override
  claimed**. That settles a future-version collision (a new default equal to
  an existing user override): the user's choice wins and the default-holder
  loses that key.
* Override ids missing from `defaults` (an action removed in a later version)
  are ignored.

Semantics of `assign(id, seq)`: `displaced = owner_of(seq)` (matching any
twin). If `displaced` is `id`, do nothing and return None. Set
`overrides[id] = seq`, and if something was displaced, set
`overrides[displaced] = ""`. Then normalize: drop every override whose
effective value equals its default (`with_twins(o) == defaults[id]`, or `o ==
""` with an empty default). Return `displaced`.

`clear(id)`: `overrides[id] = ""`, then normalize. `restore_defaults()`:
`overrides.clear()`.

### 2. `persistence/app_settings.py`

* Add `shortcuts: Dict[str, str] = field(default_factory=dict)` to
  `AppSettings`, and extend its docstring: it's global for the same reason as
  `play`/`live_midi_input`, because it's the user's own habit, not a property
  of a score.
* `load()`: `shortcuts=_str_dict(data.get("shortcuts"))`, keeping only
  str->str items from a dict and returning `{}` for anything else.
* `set_shortcut_overrides(overrides: dict)`: load-mutate-save, with the same
  docstring reasoning as its siblings.

### 3. `controllers/shortcut_controller.py` (new)

```python
@dataclass
class ShortcutTarget:
    id: str
    category: str                        # menu title without "&", or "Keyboard only"
    name: Callable[[], str]              # evaluated live - some action texts change
    get: Callable[[], list[QKeySequence]]
    set: Callable[[list[QKeySequence]], None]

class ShortcutController:
    def __init__(self, window, actions: Actions, extra_targets: list[ShortcutTarget])
    def targets(self) -> list[ShortcutTarget]      # display order
    def display_text(self, action_id) -> str       # NativeText of primary binding, "" if none
    def owner_of(self, portable: str) -> Optional[str]
    def reserved_reason(self, portable: str) -> Optional[str]
    def assign(self, action_id, portable) -> Optional[str]
    def clear(self, action_id) -> None
    def restore_defaults(self) -> None
```

Building targets:

* Walk `window.menuBar().actions()` -> each `menu().actions()`, plus one level
  into submenus (Options > Terminology), in order. Skip separators and
  submenu-holder actions such as Recent Files. Map each QAction back to its
  id by reverse lookup over `dataclasses.fields(Actions)`: the field name
  *is* the stable id (`"key_signature"`, `"play_stop"`, ...). Category = the
  top-level menu's text with `&` removed.
* `get=action.shortcuts`, `set=action.setShortcuts`.
* `EXCLUDED_ACTION_IDS = {"commit_digits"}`: a hidden window action,
  typed-number family. `terminology_group` / `recent_files_menu` aren't
  QActions.
* `extra_targets` come from `MainWindow`, category `"Keyboard only"`: ids
  `tempo_faster`, `tempo_slower`, `tempo_reset`, `chord_audition`, wrapping
  the existing `self.tempo_faster_shortcut` etc. with `get=shortcut.keys`,
  `set=shortcut.setKeys`. Names: "Tempo Faster", "Tempo Slower", "Reset
  Tempo", "Play Selected Notes". Check the tempo slots' docstrings for the
  wording the app already uses and match it.
* Display name = `action.text()` with mnemonic `&` removed (`&&` -> `&`), a
  trailing `...` removed, and a trailing mnemonic hint like ` (&Z)` / ` (Z)`
  removed (`Move to Info (&Z)` -> `Move to Info`). Otherwise the dialog would
  show a stale "(Z)" once the user rebinds that action.

Construction order (all in `__init__`):

1. Snapshot defaults:
   `{t.id: tuple(s.toString(PortableText) for s in t.get() if not s.isEmpty())}`.
   **This must happen before any override is applied** - that's the whole
   design.
2. Load `app_settings.load().shortcuts` and validate each value: `""` is
   allowed; otherwise it must parse with `QKeySequence.fromString(s,
   PortableText)` to exactly one non-empty combination (`seq.count() == 1`).
   Drop anything invalid with a `print("[WARN] ...")`.
3. Build the `ShortcutMap` and `_apply()`.

`_apply()`: for each target,
`t.set([QKeySequence.fromString(s, PortableText) for s in bindings[t.id]])`.
Every mutator calls `_apply()` and then
`app_settings.set_shortcut_overrides(dict(self._map.overrides))`, saving
immediately like `set_uk_terms`, so the change survives a crash.

`reserved_reason(portable)` returns a short phrase finishing the sentence
"...is used to <reason>", or None. Build it from a dict of PortableText ->
reason. **Each group gets a comment naming the file that actually handles the
key**, so the next person changing those keys knows to update this list:

| Keys | Reason | Handled in |
|---|---|---|
| Tab, Shift+Tab, Ctrl+Tab, Ctrl+Shift+Tab | move between regions | `widgets/region_focus_cycle.py` |
| F6, Shift+F6 | switch between the regions and the status bar | `main_window.setup_shortcuts` |
| Escape, Enter, Return, Ctrl+Enter, Ctrl+Return, 0-9 | type a bar number or loop length | `main_window.setup_shortcuts` |
| Up, Down, Left, Right, Ctrl+Left, Ctrl+Right, Shift+Up, Shift+Down, PageUp, PageDown | move through the lists | `widgets/timeline_list_widget.py`, Qt list navigation |
| Ctrl+1 ... Ctrl+9 | read an attribute aloud | `widgets/timeline_list_widget.py` |
| Alt+PgUp, Alt+PgDown | change the loop length | `widgets/timeline_list_widget.py` |
| Ctrl+Home, Ctrl+End | move within Performance markings | `widgets/region5_list_widget.py` |
| Shift+F10, Menu | open a context menu | `widgets/region4_list_widget.py` |
| Alt+F4, Alt+Space | close the window / open the window menu (Windows) | OS |

Generate the portable strings through `QKeySequence(...).toString(PortableText)`
rather than typing them by hand. PageUp is spelt `"PgUp"` in PortableText,
for example, and a hand-typed string that never matches would silently
reserve nothing. Home/End are deliberately **not** reserved: they're
Move to First/Last Note's own rebindable defaults, and Region 3's
`keyPressEvent` keeps handling bare Home/End when that action is rebound.

Also reject any sequence containing the Meta modifier when
`sys.platform != "darwin"` (the Windows key belongs to the OS). On macOS,
Meta is the physical Control key and is legitimate (see
`_shortcut_for_platform`).

### 4. `widgets/shortcut_capture_edit.py` (new)

`class ShortcutCaptureEdit(QLineEdit)` records one key combination instead of
accepting typed text.

* Don't make it `setReadOnly(True)`, or NVDA says "read only", which is
  misleading. Instead block all editing: override `keyPressEvent` fully, use
  `setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)` and
  `setAcceptDrops(False)`, and turn off
  `setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)`.
* `setPlaceholderText("Press a key combination")`, plus an accessible
  description: "Press the keys for the new shortcut. Backspace clears."
* `Signal sequence_changed(str)` sends PortableText, or `""` when cleared.
  `sequence() -> str`, `clear_sequence()`.
* Pass-through keys (not recorded, left to the dialog): with no Ctrl/Alt/Meta
  held, Tab, Backtab, Escape, Return and Enter; plus Alt+F4 always. Tab keeps
  normal focus movement, so this is **not a keyboard trap**, which is
  essential for a screen-reader user. Escape closes the dialog, and Enter
  presses the default button (Apply).
* Override `event()`:
  * On `QEvent.ShortcutOverride`: for a pass-through key, return
    `super().event(e)`. For anything else, call `e.accept()` and return True,
    so the dialog's own button mnemonics (Alt+A etc.) and QLineEdit's
    built-in Ctrl+A/C/V are recorded instead of acted on.
  * On a KeyPress of Tab/Backtab with no Ctrl/Alt: `return super().event(e)`
    (QWidget's focus navigation).
* `keyPressEvent(e)`:
  * For a modifier-only key (Control, Shift, Alt, AltGr, Meta, unknown), call
    `e.accept()` and return. Nothing is recorded yet.
  * For a pass-through key: `e.ignore()` and return, so it propagates to
    `QDialog.keyPressEvent`, which handles Escape and the default button.
  * Bare Backspace: `clear_sequence()`.
  * Windows plus Meta held: ignore it.
  * Otherwise, set
    `mods = e.modifiers() & (Ctrl | Shift | Alt | Meta)`, dropping
    `KeypadModifier`. Normalise `Key_Backtab` to `Key_Tab` (Ctrl+Shift+Tab
    arrives as Backtab+Shift). Build
    `QKeySequence(QKeyCombination(mods, Qt.Key(key)))`, `setText(NativeText)`,
    and emit PortableText.

Known limitation, for the doc comment: NVDA consumes its own NVDA-key
combinations before the app sees them, so those can't be recorded. That's
fine, since they couldn't work as app shortcuts anyway.

### 5. `widgets/keyboard_shortcuts_dialog.py` (new)

`KeyboardShortcutsDialog(parent, controller)`. The controller is passed in,
and the dialog only calls the `ShortcutController` methods above, so a test
can pass a fake. It never imports `models/` or `persistence/`.

Layout, in tab order (a `QFormLayout` for the labelled fields; see
`widgets/form_helpers.py` for existing helpers):

1. `&Filter:` QLineEdit
2. `Action &list:` QListWidget, one row per target, text
   `"<name> (<category>): <shortcut>"` or `"<name> (<category>): no shortcut"`,
   with the id in `Qt.ItemDataRole.UserRole`. Rows go in `targets()` order
   (menu order, then "Keyboard only").
3. `Current shortcut:` read-only QLineEdit with no mnemonic, showing the
   selected action's shortcut or "None".
4. `&New shortcut:` ShortcutCaptureEdit
5. Buttons: `&Apply` (the default), `&Remove Shortcut`,
   `Restore &Defaults...`, then a `QDialogButtonBox(Close)`

Check mnemonics against each other: F, L, N, A, R and D are distinct. Follow
`docs/dialog_widget_patterns.md`: call `setAutoDefault(False)` on every button
except Apply, then `apply_button.setDefault(True)` explicitly.

Behaviour:

* Initial focus: in `showEvent`, run `QTimer.singleShot(0,
  self.filter_edit.setFocus)`. The filter is the literal first tab stop (per
  the memory note "dialog initial focus": focus the first widget in tab
  order, never a "more useful" later one). Start the list with row 0 current.
* Filter: live on `textChanged`, case-insensitive substring match against the
  action's display **name only**. It never matches the shortcut text or the
  category (user-specified 2026-09-11). For example, "metro" shows exactly
  Play Metronome (Ctrl+Alt+Space), Toggle Metronome (Ctrl+M) and Metronome
  Player (Ctrl+Shift+M), and typing "ctrl" matches nothing. Leading and
  trailing whitespace is ignored, and an empty filter shows every row. Keep
  the name in its own `UserRole + 1` data slot on each item so the match
  never touches the row's display text. Use `item.setHidden()` rather than
  rebuilding, so ids and rows stay put. If the current row is hidden, make the first visible row current. If
  nothing matches, there's no current row.
* `currentRowChanged`: update Current shortcut, clear New shortcut, refresh
  button states.
* Enabled states: Apply needs a current row and a non-empty capture. Remove
  needs a current row that has a shortcut.
* When the capture changes, `announce(self, native_text)` from
  `widgets/accessible_announcer.py`, so NVDA reliably speaks what was
  recorded. A setText on a focused line edit isn't reliably spoken.
* **Apply**, with `seq = capture.sequence()` and `id` = the current row's id:
  1. If it's already this action's shortcut: announce "<name> already uses
     <keys>" and stop.
  2. `reason = controller.reserved_reason(seq)`: if set, show
     `QMessageBox.warning(self, "Keyboard Shortcuts", "<keys> can't be
     assigned: it is used to <reason>.")` and stop.
  3. `other = controller.owner_of(seq)`: if set, ask with
     `QMessageBox.question(..., "<keys> is already assigned to <other name>.
     Assign it to <name> instead? <other name> will then have no shortcut.",
     Yes|No, default No)`. On No, stop.
  4. `controller.assign(id, seq)`. Refresh the text of this row and of the
     displaced row in place, clear the capture, update Current shortcut, and
     announce "<name> is now <keys>". **Don't move focus** (see the
     dialog-patterns doc).
* **Remove Shortcut**: `controller.clear(id)`, refresh the row, announce
  "<name> has no shortcut". There's no confirmation, which is standard, and
  it can be fixed by assigning again.
* **Restore Defaults...**: ask "Restore every keyboard shortcut to its
  default? All your changes will be lost." with Yes|No, default No. On Yes,
  `controller.restore_defaults()`, refresh every row, and announce "Default
  shortcuts restored".
* **Close** / Escape: `reject()`. Nothing is pending, because every change
  is already live and saved.

### 6. `widgets/menu_builder.py`

* Add `keyboard_shortcuts: Optional[QAction] = None` to `Actions`.
* In `_tools_menu`, after Metronome Player (following a separator), add
  `a.keyboard_shortcuts = self._action("&Keyboard Shortcuts...",
  self.slots._show_keyboard_shortcuts_dialog, status_tip="Change the keyboard
  shortcut for any action")`, with a short comment in the file's style
  explaining why there's no default shortcut.
* Don't change any existing default. The existing tests pin them, and they
  stay the factory defaults.

### 7. `main_window.py` (wiring only - invariant 5)

* Module-level `from widgets.keyboard_shortcuts_dialog import
  KeyboardShortcutsDialog`, so tests can monkeypatch it.
* At the end of `setup_menu()`: `self.shortcuts =
  ShortcutController(self, self._actions, self._keyboard_only_shortcut_targets())`.
  Both the menu actions and the QShortcuts exist by then (`setup_shortcuts`
  runs during UI setup, before `setup_controllers` and `setup_menu`).
  `self.shortcuts` isn't used anywhere yet (checked).
* `_keyboard_only_shortcut_targets()` builds the four `ShortcutTarget`s from
  the existing `tempo_*_shortcut` / `chord_audition_shortcut` attributes.
* `_show_keyboard_shortcuts_dialog()`:
  `with self._preserving_focus(): KeyboardShortcutsDialog(self, self.shortcuts).exec()`.

### 8. Docs

* `docs/architecture.md`: a short "Keyboard shortcuts" section covering the
  snapshot-defaults design, overrides as a diff, where reserved keys come
  from, and that `ShortcutController` holds QActions/QShortcuts but no
  widgets.
* CLAUDE.md, under Invariants: one line saying **"Default shortcuts live only
  where the QAction/QShortcut is built (`MenuBuilder`, `setup_shortcuts`);
  `ShortcutController` snapshots them at startup - never copy them into a
  table. A new hardcoded key in a widget's `keyPressEvent` must also go into
  `ShortcutController`'s reserved list."**
* **Don't** touch `docs/user_guide.md` or `.html`. The user edits the guide
  only on request (memory note). Mention it in the final summary instead.

## Tests

The autouse `_isolate_persistence` fixture (`tests/conftest.py`) already
redirects `settings.json` to `tmp_path`, so existing tests asserting default
shortcuts are safe.

* `tests/models/test_shortcut_map.py`: defaults pass through; an override
  replaces its action's shortcut; assign displaces the owner (owner -> `()`,
  override `""`); assigning an action's own default drops the override
  (normalize); clear; restore; a new-default-vs-override collision means the
  override wins; Enter/Return twins bind both and conflict-match either;
  unknown override ids are ignored.
* `tests/persistence/test_app_settings.py`: round-trip `shortcuts`; malformed
  values (a list, non-str values) load as `{}` or are filtered; the other
  `set_*` helpers don't wipe it.
* `tests/test_shortcut_controller.py` (with the `window` fixture):
  * every `Actions` QAction field is a target except `commit_digits`. This
    guards future actions added without a menu home.
  * The defaults snapshot equals the built shortcuts (for example
    `key_signature` -> `("Ctrl+Shift+K",)`, `voice_control` -> both Enter
    twins).
  * `assign("mixer", "Ctrl+B")` changes `window._actions.mixer.shortcut()`,
    clears `bar_line_indicator`'s, and writes settings.json.
  * `restore_defaults` puts both back.
  * Keyboard-only targets rebind the QShortcut (`tempo_faster_shortcut.key()`).
  * A second `MainWindow` built afterwards starts with the saved override
    applied ("menus reflect it" = `QAction.shortcut()`, which is what Qt
    renders in the menu).
  * Invalid saved strings are dropped.
  * `reserved_reason` covers Tab, Left and Ctrl+1 and returns None for
    Ctrl+Shift+J.
  * Display names strip `&`, `...` and `(Z)`.
* `tests/widgets/test_shortcut_capture_edit.py`: QTest.keyClick
  Ctrl+Shift+K records "Ctrl+Shift+K"; a modifier-only press records nothing;
  Tab/Escape/Return don't record and leave the event ignored (drive
  `keyPressEvent` with a constructed `QKeyEvent`, then check
  `isAccepted()`); Backspace clears; Alt+A is recorded rather than triggering
  a sibling "&Apply" button (put the edit and a button in a parent widget);
  numpad keys drop KeypadModifier.
* `tests/widgets/test_keyboard_shortcuts_dialog.py` (real window +
  `window.shortcuts`, and monkeypatch `QMessageBox.question`/`warning` in the
  dialog's module namespace, the same way
  `tests/widgets/test_metronome_player_dialog.py` handles its warning):
  * filter "metro" leaves exactly the three metronome actions visible
    (Play Metronome, Toggle Metronome, Metronome Player); "ctrl" and a
    category name like "playback" match nothing; clearing the filter shows
    every row
  * Apply with a free key updates the row and the QAction
  * a conflict with No changes nothing; with Yes, it moves the key and
    blanks the other row
  * a reserved key warns and changes nothing
  * Remove Shortcut
  * Restore Defaults with No/Yes
  * mnemonics are unique within the dialog
  * the default button is Apply
* `tests/test_main_window_menus.py`: Tools > Keyboard Shortcuts exists and
  opens the dialog (monkeypatch `main_window.KeyboardShortcutsDialog`). The
  existing `test_no_menu_mnemonic_collisions` must still pass. K is free, but
  let the test prove it.

Run the whole suite. There are no `parsers/`/`models/` behaviour changes, so
the fingerprint harnesses aren't needed.

## Housekeeping for the implementer

* The working tree has unrelated uncommitted edits (`parsers/xml_source.py`,
  `tests/parsers/test_xml_source.py`). Don't touch or commit them.
* Don't bump `version.txt`, commit or push unless the user asks.
* After tests pass, say it needs live NVDA testing, specifically: Tab leaving
  the capture box, what NVDA speaks on each capture, the conflict message box,
  and that the menus show the new shortcut. The offscreen test platform can't
  prove any of those (see `docs/dialog_widget_patterns.md`).
