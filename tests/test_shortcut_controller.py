# tests/test_shortcut_controller.py
"""ShortcutController (UserPlans/KeyboardShortcuts.md) - the Qt-touching
layer wrapping models/shortcut_map.ShortcutMap. Uses the real `window`
fixture (a MainWindow with a NullSynth) since the controller reads live
QAction/QShortcut objects off it."""
from dataclasses import fields

from PySide6.QtGui import QKeySequence

from controllers.shortcut_controller import EXCLUDED_ACTION_IDS, ShortcutController
from main_window import MainWindow
from persistence import app_settings


def test_every_action_field_is_a_target_except_the_excluded_ones(window):
    target_ids = {t.id for t in window.shortcuts.targets()}
    for f in fields(window._actions):
        value = getattr(window._actions, f.name)
        if value is None or not hasattr(value, "shortcut"):
            continue
        if f.name in EXCLUDED_ACTION_IDS:
            assert f.name not in target_ids
        else:
            assert f.name in target_ids, f"{f.name} has no ShortcutTarget"


def test_defaults_snapshot_matches_what_menu_builder_built(window):
    assert window.shortcuts.display_text("key_signature") == "Ctrl+Shift+K"
    # Enter/Return twins: the primary/displayed shortcut is Enter.
    voice_control_target = next(
        t for t in window.shortcuts.targets() if t.id == "voice_control"
    )
    seqs = [s.toString(QKeySequence.SequenceFormat.PortableText) for s in voice_control_target.get()]
    assert seqs == ["Alt+Enter", "Alt+Return"]


def test_assign_updates_the_action_and_displaces_the_previous_owner(window):
    displaced = window.shortcuts.assign("mixer", "Ctrl+B")

    assert displaced == "bar_line_indicator"
    assert window._actions.mixer.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+B"
    assert window._actions.bar_line_indicator.shortcuts() == []
    assert app_settings.load().shortcuts.get("mixer") == "Ctrl+B"


def test_restore_defaults_puts_both_actions_back(window):
    window.shortcuts.assign("mixer", "Ctrl+B")

    window.shortcuts.restore_defaults()

    assert window._actions.mixer.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+Shift+X"
    assert window._actions.bar_line_indicator.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+B"
    assert app_settings.load().shortcuts == {}


def test_keyboard_only_targets_rebind_the_underlying_qshortcut(window):
    window.shortcuts.assign("tempo_faster", "Ctrl+Shift+J")

    assert window.tempo_faster_shortcut.key().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+Shift+J"


def test_a_saved_override_is_applied_when_a_new_main_window_is_built(qtbot, null_synth):
    app_settings.set_shortcut_overrides({"mixer": "Ctrl+B"})

    w = MainWindow(synth=null_synth, uk_terms=False)
    qtbot.addWidget(w)

    assert w._actions.mixer.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+B"


def test_invalid_saved_shortcut_strings_are_dropped(window):
    app_settings.set_shortcut_overrides({"mixer": "Ctrl+K, Ctrl+S"})

    controller = ShortcutController(window, window._actions, window._keyboard_only_shortcut_targets())

    assert controller.display_text("mixer") == "Ctrl+Shift+X"


def test_reserved_reason_covers_tab_left_and_ctrl_1(window):
    assert window.shortcuts.reserved_reason("Tab") is not None
    assert window.shortcuts.reserved_reason("Left") is not None
    assert window.shortcuts.reserved_reason("Ctrl+1") is not None


def test_reserved_reason_is_none_for_a_free_combination(window):
    assert window.shortcuts.reserved_reason("Ctrl+Shift+J") is None


def test_display_names_strip_mnemonic_ellipsis_and_trailing_hint(window):
    names = {t.id: t.name() for t in window.shortcuts.targets()}
    assert names["key_signature"] == "Key Signature"
    assert names["mixer"] == "Mixer"
    assert names["move_to_metadata"] == "Move to Info"
