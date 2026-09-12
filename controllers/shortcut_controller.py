# controllers/shortcut_controller.py
"""Keyboard shortcut rebinding (UserPlans/KeyboardShortcuts.md).

The only place that touches Qt for this feature - models/shortcut_map.py
holds the pure-logic ShortcutMap this wraps, and stdlib-only tests drive
that separately. This module owns the QAction/QShortcut objects (via
ShortcutTarget.get/set) but never touches a widget.

CLAUDE.md invariant: default shortcuts live only where the QAction/QShortcut
is built (MenuBuilder, MainWindow.setup_shortcuts). This controller
snapshots them at construction, before any saved override is applied - that
snapshot IS the factory-defaults table; it is never typed out separately
(invariant 8, "two copies of the same fact will diverge"). A new hardcoded
key added to a widget's keyPressEvent must also be added to _build_reserved
below, or the new dialog will silently let the user steal it.
"""
import sys
from dataclasses import dataclass, fields
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt, QKeyCombination
from PySide6.QtGui import QAction, QKeySequence

from models.shortcut_map import ShortcutMap
from persistence import app_settings
from widgets.menu_builder import Actions

_PortableFormat = QKeySequence.SequenceFormat.PortableText
_NativeFormat = QKeySequence.SequenceFormat.NativeText

# Hidden window action for the typed-bar-number family (main_window.py's
# setup_menu / _playback_menu) - not a menu item, so nothing to rebind.
EXCLUDED_ACTION_IDS = {"commit_digits"}


@dataclass
class ShortcutTarget:
    id: str
    category: str                          # menu title without "&", or "Keyboard only"
    name: Callable[[], str]                # evaluated live - some action texts change
    get: Callable[[], List[QKeySequence]]
    set: Callable[[List[QKeySequence]], None]


def _display_name(text: str) -> str:
    """'Move to Info (&Z)' -> 'Move to Info'; '&Keyboard Shortcuts...' ->
    'Keyboard Shortcuts'. Strips a trailing mnemonic hint like ' (&Z)' or
    ' (Z)', then the '&' mnemonic marker itself (turning '&&' into a literal
    '&' first, since that's the Qt escape for a real ampersand), then a
    trailing '...'."""
    import re

    text = re.sub(r"\s*\(&?[A-Za-z0-9]\)$", "", text)
    text = text.replace("&&", "\x00")
    text = text.replace("&", "")
    text = text.replace("\x00", "&")
    if text.endswith("..."):
        text = text[: -len("...")]
    return text.strip()


def _seq(key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> str:
    """Generate a PortableText string through QKeySequence rather than
    typing it by hand - PageUp is spelt "PgUp" in PortableText, for example,
    and a hand-typed string that never matches would silently reserve
    nothing."""
    return QKeySequence(QKeyCombination(modifiers, key)).toString(_PortableFormat)


def _build_reserved() -> Dict[str, str]:
    """PortableText -> a short phrase completing "...it is used to <reason>."
    Each group's comment names the file that actually handles the key, so
    the next person changing those keys knows to update this list.

    Home/End are deliberately NOT reserved: they're Move to First/Last
    Note's own rebindable defaults, and Region 3's keyPressEvent keeps
    handling bare Home/End when that action is rebound."""
    reserved: Dict[str, str] = {}
    Key = Qt.Key
    Mod = Qt.KeyboardModifier

    def add(reason: str, *seqs: str) -> None:
        for s in seqs:
            reserved[s] = reason

    # widgets/region_focus_cycle.py
    add(
        "move between regions",
        _seq(Key.Key_Tab),
        _seq(Key.Key_Tab, Mod.ShiftModifier),
        _seq(Key.Key_Tab, Mod.ControlModifier),
        _seq(Key.Key_Tab, Mod.ControlModifier | Mod.ShiftModifier),
    )
    # main_window.setup_shortcuts
    add(
        "switch between the regions and the status bar",
        _seq(Key.Key_F6),
        _seq(Key.Key_F6, Mod.ShiftModifier),
    )
    # main_window.setup_shortcuts
    add(
        "type a bar number or loop length",
        _seq(Key.Key_Enter),
        _seq(Key.Key_Return),
        _seq(Key.Key_Enter, Mod.ControlModifier),
        _seq(Key.Key_Return, Mod.ControlModifier),
        *[_seq(Qt.Key(Key.Key_0 + d)) for d in range(10)],
    )
    # main_window.setup_shortcuts / main_window._on_escape
    add(
        "cancel a typed bar number, or stop a paused playback",
        _seq(Key.Key_Escape),
    )
    # widgets/timeline_list_widget.py, Qt list navigation
    add(
        "move through the lists",
        _seq(Key.Key_Up),
        _seq(Key.Key_Down),
        _seq(Key.Key_Left),
        _seq(Key.Key_Right),
        _seq(Key.Key_Left, Mod.ControlModifier),
        _seq(Key.Key_Right, Mod.ControlModifier),
        _seq(Key.Key_Up, Mod.ShiftModifier),
        _seq(Key.Key_Down, Mod.ShiftModifier),
        _seq(Key.Key_PageUp),
        _seq(Key.Key_PageDown),
    )
    # widgets/timeline_list_widget.py
    add(
        "read an attribute aloud",
        *[_seq(Qt.Key(Key.Key_1 + d), Mod.ControlModifier) for d in range(9)],
    )
    # widgets/timeline_list_widget.py
    add(
        "change the loop length",
        _seq(Key.Key_PageUp, Mod.AltModifier),
        _seq(Key.Key_PageDown, Mod.AltModifier),
    )
    # widgets/region5_list_widget.py
    add(
        "move within Performance markings",
        _seq(Key.Key_Home, Mod.ControlModifier),
        _seq(Key.Key_End, Mod.ControlModifier),
    )
    # widgets/region4_list_widget.py
    add(
        "open a context menu",
        _seq(Key.Key_F10, Mod.ShiftModifier),
        _seq(Key.Key_Menu),
    )
    # OS (Windows)
    add(
        "close the window or open the window menu",
        _seq(Key.Key_F4, Mod.AltModifier),
        _seq(Key.Key_Space, Mod.AltModifier),
    )
    return reserved


# clear_preferences' own QAction text quotes the loaded file
# (score_persistence.clear_action_text) so the File menu stays specific;
# the dialog needs a name that doesn't change out from under the filter
# and row text on every file load.
_NAME_OVERRIDES: Dict[str, str] = {
    "clear_preferences": "Close Preferences for Current File",
}

# The dialog's own grouping, chosen by the user while classifying the
# UserPlans/ShortcutClassification.csv spreadsheet (2026-09-11) - deliberately
# not the menu title a target was found under (e.g. "Select All" moved out of
# "Edit" into "Notes", the five region jumps moved into "Quick nav" alongside
# the tempo keys). Keyed by display name rather than action id because that's
# what the classification spreadsheet had to work with; applied once in
# ShortcutController.__init__ after _build_targets/extra_targets have set the
# menu-derived default.
_CATEGORY_OVERRIDES: Dict[str, str] = {
    "Open": "File",
    "Import from Ultimate Guitar": "File",
    "Save Ultimate Guitar Import As": "File",
    "Close": "File",
    "Open Local Folder": "File",
    "Close Preferences for Current File": "File",
    "Exit": "File",
    "Select All": "Notes",
    "Key Signature": "Notes",
    "Instruments": "Parts",
    "Reorder Parts": "Parts",
    "Solo": "Parts",
    "Mute": "Parts",
    "Unsolo All": "Parts",
    "Unmute All": "Parts",
    "Move to First Note": "Navigation",
    "Move to Last Note": "Navigation",
    "Go to Measure": "Navigation",
    "Select Section": "Navigation",
    "Find": "Navigation",
    "Find Next": "Navigation",
    "Find Previous": "Navigation",
    "Previous Section": "Navigation",
    "Next Section": "Navigation",
    "Move to Info": "Quick nav",
    "Move to Parts List": "Quick nav",
    "Move to Notes": "Quick nav",
    "Move to Attributes": "Quick nav",
    "Move to Performance": "Quick nav",
    "Play/Stop": "Playback",
    "Pause": "Playback",
    "Play Metronome": "Playback",
    "Play Settings": "Playback",
    "Cycle Play Mode": "Playback",
    "Toggle Lead-in": "Playback",
    "Cycle Loop Repeat Handling": "Playback",
    "Mixer": "Playback",
    "UK": "Language",
    "US": "Language",
    "Toggle Bar Line Indicator": "Orientation",
    "Toggle Metronome": "Orientation",
    "Toggle Position Announcer": "Orientation",
    "Toggle Live MIDI Input": "Options",
    "Live MIDI Input Settings": "Options",
    "Toggle Voice Control": "Voice control",
    "Voice Control Settings": "Voice control",
    "Reorder Attributes": "Options",
    "Set MuseScore Location": "Options",
    "Tuner": "Tools",
    "Performance Report": "Tools",
    "Strumming Patterns": "Tools",
    "Metronome Player": "Tools",
    "Keyboard Shortcuts": "Tools",
    "User Guide": "Help",
    "About Recall Score": "Help",
    "Tempo Faster": "Quick nav",
    "Tempo Slower": "Quick nav",
    "Reset Tempo": "Quick nav",
    "Play Selected Notes": "Quick nav",
}


def _maybe_add_target(
    targets: List[ShortcutTarget],
    id_by_action: Dict[int, str],
    action: QAction,
    category: str,
) -> None:
    action_id = id_by_action.get(id(action))
    if action_id is None or action_id in EXCLUDED_ACTION_IDS:
        return
    override = _NAME_OVERRIDES.get(action_id)
    name = (lambda: override) if override is not None else (lambda a=action: _display_name(a.text()))
    targets.append(
        ShortcutTarget(
            id=action_id,
            category=category,
            name=name,
            get=action.shortcuts,
            set=action.setShortcuts,
        )
    )


def _build_targets(window, actions: Actions) -> List[ShortcutTarget]:
    """Walk the menu bar in display order, mapping each QAction back to its
    stable id by reverse lookup over the Actions dataclass fields (the field
    name IS the id). Recurses one level into any submenu encountered
    (Options > Terminology) - a submenu whose items don't match any Actions
    field (Recent Files, whose entries are dynamic file paths) contributes
    nothing and is silently skipped."""
    id_by_action: Dict[int, str] = {}
    for f in fields(actions):
        value = getattr(actions, f.name)
        if isinstance(value, QAction):
            id_by_action[id(value)] = f.name

    targets: List[ShortcutTarget] = []
    for top_action in window.menuBar().actions():
        menu = top_action.menu()
        if menu is None:
            continue
        category = _display_name(menu.title())
        for action in menu.actions():
            if action.isSeparator():
                continue
            submenu = action.menu()
            if submenu is not None:
                for sub_action in submenu.actions():
                    if sub_action.isSeparator():
                        continue
                    _maybe_add_target(targets, id_by_action, sub_action, category)
                continue
            _maybe_add_target(targets, id_by_action, action, category)
    return targets


def _load_valid_overrides() -> Dict[str, str]:
    raw = app_settings.load().shortcuts
    valid: Dict[str, str] = {}
    for action_id, value in raw.items():
        if value == "":
            valid[action_id] = value
            continue
        parsed = QKeySequence.fromString(value, _PortableFormat)
        if parsed.count() == 1:
            valid[action_id] = value
        else:
            print(f"[WARN] Ignoring invalid saved shortcut for {action_id!r}: {value!r}")
    return valid


class ShortcutController:
    """The single owner of shortcut rebinding state. KeyboardShortcutsDialog
    only calls the methods below, so a test can pass a fake instead."""

    def __init__(self, window, actions: Actions, extra_targets: List[ShortcutTarget]):
        self._targets = _build_targets(window, actions) + list(extra_targets)
        for t in self._targets:
            t.category = _CATEGORY_OVERRIDES.get(t.name(), t.category)
        # Must happen before any override is applied - this snapshot IS the
        # factory defaults table (see module docstring).
        defaults = {
            t.id: tuple(
                s.toString(_PortableFormat) for s in t.get() if not s.isEmpty()
            )
            for t in self._targets
        }
        overrides = _load_valid_overrides()
        self._reserved = _build_reserved()
        self._map = ShortcutMap(defaults=defaults, overrides=overrides)
        self._apply()

    def targets(self) -> List[ShortcutTarget]:
        return self._targets

    def display_text(self, action_id: str) -> str:
        seqs = self._map.bindings().get(action_id, ())
        if not seqs:
            return ""
        return QKeySequence.fromString(seqs[0], _PortableFormat).toString(_NativeFormat)

    def owner_of(self, portable: str) -> Optional[str]:
        return self._map.owner_of(portable)

    def reserved_reason(self, portable: str) -> Optional[str]:
        if sys.platform != "darwin" and "Meta" in portable.split("+"):
            return "operate as the Windows key"
        return self._reserved.get(portable)

    def assign(self, action_id: str, portable: str) -> Optional[str]:
        displaced = self._map.assign(action_id, portable)
        self._apply()
        self._save()
        return displaced

    def clear(self, action_id: str) -> None:
        self._map.clear(action_id)
        self._apply()
        self._save()

    def restore_defaults(self) -> None:
        self._map.restore_defaults()
        self._apply()
        self._save()

    def _apply(self) -> None:
        bindings = self._map.bindings()
        for t in self._targets:
            seqs = bindings.get(t.id, ())
            t.set([QKeySequence.fromString(s, _PortableFormat) for s in seqs])

    def _save(self) -> None:
        app_settings.set_shortcut_overrides(dict(self._map.overrides))
