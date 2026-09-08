# widgets/form_helpers.py
"""Shared helpers for building QFormLayout rows accessibly."""
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget


def add_buddy_row(form: QFormLayout, label_text: str, field, buddy: QWidget) -> QLabel:
    """Add a ``label_text``/``field`` row to ``form`` with an explicit
    ``QLabel`` whose buddy is ``buddy``.

    ``QFormLayout.addRow(str, QLayout)`` - the overload that runs when
    ``field`` is a layout (e.g. a device combo + Refresh button in a
    QHBoxLayout) - creates the label but sets NO buddy and does not parse
    the ``&`` mnemonic the way ``addRow(str, QWidget)`` does. So the
    combo gets no accessible-name relationship and Alt+<key> does nothing.
    Constructing the ``QLabel`` directly and calling ``setBuddy`` sidesteps
    whichever ``addRow`` overload is used.

    ``tuner_settings_dialog.py`` carried this fix inline first; this is the
    shared version so a fourth device-combo dialog can't reintroduce the
    bug (S1, code review 8 Sept).
    """
    label = QLabel(label_text, buddy.parentWidget())
    label.setBuddy(buddy)
    form.addRow(label, field)
    return label
