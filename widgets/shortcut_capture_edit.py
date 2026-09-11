# widgets/shortcut_capture_edit.py
"""Keyboard shortcut rebinding (UserPlans/KeyboardShortcuts.md): a QLineEdit
that records one key combination instead of accepting typed text."""
import sys

from PySide6.QtCore import Qt, QKeyCombination, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QLineEdit

_PortableFormat = QKeySequence.SequenceFormat.PortableText
_NativeFormat = QKeySequence.SequenceFormat.NativeText

_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_AltGr,
    Qt.Key.Key_Meta,
    Qt.Key.Key_unknown,
}

# With no Ctrl/Alt/Meta held, these keys are left to the dialog rather than
# recorded: Tab/Backtab keep normal focus movement (this is NOT a keyboard
# trap - essential for a screen-reader user), Escape closes the dialog, and
# Enter/Return press the default button (Apply). Alt+F4 always passes
# through regardless of modifiers.
_PASS_THROUGH_KEYS = {
    Qt.Key.Key_Tab,
    Qt.Key.Key_Backtab,
    Qt.Key.Key_Escape,
    Qt.Key.Key_Return,
    Qt.Key.Key_Enter,
}

_RELEVANT_MODIFIERS = (
    Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.ShiftModifier
    | Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.MetaModifier
)


class ShortcutCaptureEdit(QLineEdit):
    """Records one key combination (Ctrl/Shift/Alt + key) instead of typed
    text.

    Known limitation: NVDA consumes its own NVDA-key combinations before the
    app sees them, so those can't be recorded here. That's fine, since they
    couldn't work as app shortcuts anyway.
    """

    sequence_changed = Signal(str)  # PortableText, or "" when cleared

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence = ""
        # Not setReadOnly(True): NVDA would say "read only", which is
        # misleading - this field isn't read-only, it just doesn't accept
        # typed text. Block editing by other means instead.
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setAcceptDrops(False)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)
        self.setPlaceholderText("Press a key combination")
        self.setAccessibleDescription(
            "Press the keys for the new shortcut. Backspace clears."
        )

    def sequence(self) -> str:
        return self._sequence

    def clear_sequence(self) -> None:
        self._sequence = ""
        self.setText("")
        self.sequence_changed.emit("")

    def _is_pass_through(self, key: int, modifiers: Qt.KeyboardModifier) -> bool:
        if key == Qt.Key.Key_F4 and modifiers & Qt.KeyboardModifier.AltModifier:
            return True
        if modifiers & _RELEVANT_MODIFIERS:
            return False
        return key in _PASS_THROUGH_KEYS

    def event(self, e):
        if e.type() == e.Type.ShortcutOverride:
            if self._is_pass_through(e.key(), e.modifiers()):
                return super().event(e)
            e.accept()
            return True
        if e.type() == e.Type.KeyPress:
            key = e.key()
            modifiers = e.modifiers()
            if (
                key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
                and not modifiers & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                )
            ):
                return super().event(e)
        return super().event(e)

    def keyPressEvent(self, e):
        key = e.key()
        modifiers = e.modifiers()

        if key in _MODIFIER_KEYS:
            e.accept()
            return

        if self._is_pass_through(key, modifiers):
            e.ignore()
            return

        if key == Qt.Key.Key_Backspace and not modifiers & _RELEVANT_MODIFIERS:
            self.clear_sequence()
            return

        mods = modifiers & _RELEVANT_MODIFIERS
        # The Windows key belongs to the OS; on macOS Meta is the physical
        # Control key and is legitimate (see menu_builder._shortcut_for_platform).
        if mods & Qt.KeyboardModifier.MetaModifier and sys.platform != "darwin":
            e.accept()
            return

        mods &= ~Qt.KeyboardModifier.KeypadModifier
        if key == Qt.Key.Key_Backtab:
            key = Qt.Key.Key_Tab
            mods |= Qt.KeyboardModifier.ShiftModifier

        seq = QKeySequence(QKeyCombination(mods, Qt.Key(key)))
        self._sequence = seq.toString(_PortableFormat)
        self.setText(seq.toString(_NativeFormat))
        self.sequence_changed.emit(self._sequence)
