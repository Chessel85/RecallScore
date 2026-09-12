# controllers/keyboard_echo_controller.py
"""F12 Keyboard Echo Mode: a tutorial aid. While active, every keypress is
spoken as the name of the action it would perform - not performed - so a new
or visually-impaired user can safely check a keystroke before committing to
it. F12 (or wherever it's been rebound to) exits.

Installed as an application-wide QObject.eventFilter rather than a
MainWindow.keyPressEvent override, because most of what needs intercepting
never reaches MainWindow.keyPressEvent at all: menu QAction/QShortcut
bindings fire from Qt's own shortcut map, and arrow-key list navigation is
handled inside whichever region widget currently has focus. The
ShortcutOverride event.accept()+return True pairing mirrors
widgets/shortcut_capture_edit.py's own capture technique: accepting
ShortcutOverride tells Qt "this key is being handled elsewhere," which
suppresses the shortcut and hands the focus widget an ordinary KeyPress
instead - which this filter then swallows too, before it ever reaches a
widget's keyPressEvent (e.g. an arrow key moving Region 3's selection).

Reuses ShortcutController's own owner_of/reserved_reason lookups rather than
keeping a second table of what each key does (CLAUDE.md invariant 8) - every
menu action, the four "Keyboard only" targets (tempo/chord audition), and
every hardcoded region/window key already resolve through one of those two
calls.
"""
from PySide6.QtCore import QEvent, QKeyCombination, QObject, Qt
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import QWidget

from controllers.shortcut_controller import ShortcutController
from widgets import accessible_announcer

_PortableFormat = QKeySequence.SequenceFormat.PortableText

_IGNORED_KEYS = {
    Qt.Key.Key_Shift,
    Qt.Key.Key_Control,
    Qt.Key.Key_Alt,
    Qt.Key.Key_AltGr,
    Qt.Key.Key_Meta,
    Qt.Key.Key_unknown,
}


class KeyboardEchoController(QObject):
    def __init__(
        self, window: QWidget, shortcuts: ShortcutController,
        action: QAction, action_id: str,
    ):
        super().__init__(window)
        self._window = window
        self._shortcuts = shortcuts
        self._action = action
        self._action_id = action_id
        self._active = False
        # Not connected here: the menu action already routes through
        # MainWindow._toggle_keyboard_echo_mode -> self.toggle() (the usual
        # MenuBuilder wiring, invariant 5) - connecting a second time here
        # would fire toggle() twice per click, entering and immediately
        # exiting again.

    def is_active(self) -> bool:
        return self._active

    def toggle(self) -> None:
        """The menu action's own slot. Reachable by mouse click even while
        active (a menu click bypasses the key-event filter below), so this
        must invert current state rather than assume it only ever enters."""
        self._exit() if self._active else self._enter()

    def _enter(self) -> None:
        self._active = True
        self._action.setChecked(True)
        QGuiApplication.instance().installEventFilter(self)
        accessible_announcer.announce(
            self._window,
            "Keyboard echo mode. Press a key to hear what it does. "
            "Press F12 to exit.",
        )

    def _exit(self) -> None:
        self._active = False
        self._action.setChecked(False)
        QGuiApplication.instance().removeEventFilter(self)
        accessible_announcer.announce(self._window, "Keyboard echo mode off.")

    def eventFilter(self, obj, event) -> bool:
        if not self._active:
            return False
        event_type = event.type()
        if event_type == QEvent.Type.ShortcutOverride:
            # Accepting this suppresses Qt's own shortcut dispatch for the
            # key, in favour of the plain KeyPress handled below - see the
            # module docstring.
            event.accept()
            return True
        if event_type == QEvent.Type.KeyPress:
            self._handle_key(event)
            return True
        if event_type == QEvent.Type.KeyRelease:
            return True
        return False

    def _handle_key(self, event) -> None:
        key = event.key()
        if key in _IGNORED_KEYS:
            return
        modifiers = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        portable = QKeySequence(
            QKeyCombination(modifiers, Qt.Key(key))
        ).toString(_PortableFormat)

        owner_id = self._shortcuts.owner_of(portable)
        if owner_id == self._action_id:
            self._exit()
            return
        if owner_id is not None:
            for target in self._shortcuts.targets():
                if target.id == owner_id:
                    accessible_announcer.announce(self._window, target.name())
                    return

        reason = self._shortcuts.reserved_reason(portable)
        if reason is not None:
            accessible_announcer.announce(self._window, f"Used to {reason}.")
            return

        accessible_announcer.announce(self._window, "Nothing assigned to this key.")
