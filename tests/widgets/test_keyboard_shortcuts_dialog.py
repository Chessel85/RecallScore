# tests/widgets/test_keyboard_shortcuts_dialog.py
"""KeyboardShortcutsDialog (UserPlans/KeyboardShortcuts.md) - driven against
the real `window` fixture and its live ShortcutController, the same pattern
test_metronome_player_dialog.py and test_tuner_controller.py use for a
dialog backed by real app state. QMessageBox.question/warning are
monkeypatched in the dialog's own module namespace, like
test_metronome_player_dialog.py does for QMessageBox.warning."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from widgets.keyboard_shortcuts_dialog import KeyboardShortcutsDialog


def _dialog(qtbot, window):
    dialog = KeyboardShortcutsDialog(window, window.shortcuts)
    qtbot.addWidget(dialog)
    return dialog


def _visible_texts(dialog):
    return [
        dialog.action_list.item(row).text()
        for row in range(dialog.action_list.count())
        if not dialog.action_list.item(row).isHidden()
    ]


def test_filter_metro_shows_exactly_the_three_metronome_actions(qtbot, window):
    dialog = _dialog(qtbot, window)

    dialog.filter_edit.setText("metro")

    visible = _visible_texts(dialog)
    assert len(visible) == 3
    assert any("Play Metronome" in t for t in visible)
    assert any("Toggle Metronome" in t for t in visible)
    assert any("Metronome Player" in t for t in visible)


def test_filter_by_shortcut_text_matches_nothing(qtbot, window):
    dialog = _dialog(qtbot, window)
    dialog.filter_edit.setText("ctrl")
    assert _visible_texts(dialog) == []


def test_filter_by_category_shows_every_action_in_that_category(qtbot, window):
    dialog = _dialog(qtbot, window)
    dialog.filter_edit.setText("playback")
    visible = _visible_texts(dialog)
    assert visible
    assert all(t.lower().startswith("playback:") for t in visible)


def test_clearing_the_filter_shows_every_row(qtbot, window):
    dialog = _dialog(qtbot, window)
    dialog.filter_edit.setText("metro")
    dialog.filter_edit.setText("")
    assert len(_visible_texts(dialog)) == dialog.action_list.count()


def _select(dialog, action_id):
    for row in range(dialog.action_list.count()):
        item = dialog.action_list.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == action_id:
            dialog.action_list.setCurrentRow(row)
            return
    raise AssertionError(f"no row for {action_id!r}")


def test_apply_with_a_free_key_updates_the_row_and_the_qaction(qtbot, window):
    dialog = _dialog(qtbot, window)
    _select(dialog, "mixer")
    dialog.new_shortcut_edit._sequence = "Ctrl+Shift+J"
    dialog.new_shortcut_edit.setText("Ctrl+Shift+J")

    dialog._apply()

    assert window._actions.mixer.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+Shift+J"
    assert "Ctrl+Shift+J" in dialog.action_list.currentItem().text()


def test_apply_with_a_conflict_and_no_changes_nothing(qtbot, window, monkeypatch):
    monkeypatch.setattr(
        "widgets.keyboard_shortcuts_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )
    dialog = _dialog(qtbot, window)
    _select(dialog, "mixer")
    dialog.new_shortcut_edit._sequence = "Ctrl+B"
    dialog.new_shortcut_edit.setText("Ctrl+B")

    dialog._apply()

    assert window._actions.mixer.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+Shift+X"
    assert window._actions.bar_line_indicator.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+B"


def test_apply_with_a_conflict_and_yes_moves_the_key_and_blanks_the_other_row(qtbot, window, monkeypatch):
    monkeypatch.setattr(
        "widgets.keyboard_shortcuts_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    dialog = _dialog(qtbot, window)
    _select(dialog, "mixer")
    dialog.new_shortcut_edit._sequence = "Ctrl+B"
    dialog.new_shortcut_edit.setText("Ctrl+B")

    dialog._apply()

    assert window._actions.mixer.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+B"
    assert window._actions.bar_line_indicator.shortcuts() == []
    _select(dialog, "bar_line_indicator")
    assert "no shortcut" in dialog.action_list.currentItem().text()


def test_apply_with_a_reserved_key_warns_and_changes_nothing(qtbot, window, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "widgets.keyboard_shortcuts_dialog.QMessageBox.warning",
        lambda *a, **k: warnings.append(a),
    )
    dialog = _dialog(qtbot, window)
    _select(dialog, "mixer")
    dialog.new_shortcut_edit._sequence = "Tab"
    dialog.new_shortcut_edit.setText("Tab")

    dialog._apply()

    assert warnings
    assert window._actions.mixer.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+Shift+X"


def test_remove_shortcut_clears_the_action(qtbot, window):
    dialog = _dialog(qtbot, window)
    _select(dialog, "mixer")

    dialog._remove()

    assert window._actions.mixer.shortcuts() == []
    assert dialog.current_shortcut_edit.text() == "None"


def test_restore_defaults_with_no_changes_nothing(qtbot, window, monkeypatch):
    monkeypatch.setattr(
        "widgets.keyboard_shortcuts_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )
    dialog = _dialog(qtbot, window)
    _select(dialog, "mixer")
    dialog._remove()

    dialog._restore_defaults()

    assert window._actions.mixer.shortcuts() == []


def test_restore_defaults_with_yes_restores_the_factory_shortcut(qtbot, window, monkeypatch):
    monkeypatch.setattr(
        "widgets.keyboard_shortcuts_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    dialog = _dialog(qtbot, window)
    _select(dialog, "mixer")
    dialog._remove()

    dialog._restore_defaults()

    assert window._actions.mixer.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+Shift+X"


def test_mnemonics_are_unique_within_the_dialog(qtbot, window):
    dialog = _dialog(qtbot, window)
    mnemonics = []
    for button in (dialog.apply_button, dialog.remove_button, dialog.restore_button):
        text = button.text()
        idx = text.find("&")
        if idx != -1 and idx + 1 < len(text):
            mnemonics.append(text[idx + 1].upper())
    assert len(mnemonics) == len(set(mnemonics))


def test_the_default_button_is_apply(qtbot, window):
    dialog = _dialog(qtbot, window)
    assert dialog.apply_button.isDefault()
    close_button = dialog.close_box.button(QDialogButtonBox.StandardButton.Close)
    assert not close_button.isDefault()
