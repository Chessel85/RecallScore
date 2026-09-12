# tests/test_main_window_menus.py
"""Menu shortcuts and mnemonics, the Ctrl+G / Ctrl+F wiring checks, the About dialog, and the goto-measure dialog focus. Split from test_main_window.py (S10).
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialog, QLabel

from widgets.about_dialog import AboutDialog
from widgets.goto_measure_dialog import GotoMeasureDialog
from widgets import menu_builder
from widgets.menu_builder import _shortcut_for_platform
from tests.support.main_window_helpers import _focus, _show, load_and_wait


def test_navigation_menu_items_use_home_and_end_shortcuts(window):
    assert window._actions.first_measure.shortcut() == QKeySequence(Qt.Key.Key_Home)
    assert window._actions.last_measure.shortcut() == QKeySequence(Qt.Key.Key_End)
    assert window._actions.goto_measure.shortcut() == QKeySequence("Ctrl+G")
    assert window._actions.move_to_notes.shortcut() == QKeySequence("C")
    assert window._actions.move_to_metadata.shortcut() == QKeySequence("Z")
    assert window._actions.move_to_parts.shortcut() == QKeySequence("X")
    assert window._actions.move_to_attributes.shortcut() == QKeySequence("V")
    assert window._actions.move_to_performance.shortcut() == QKeySequence("B")


def test_refresh_on_playback_action_is_checkable_with_ctrl_h(window):
    assert window._actions.refresh_on_playback.shortcut() == QKeySequence("Ctrl+H")
    assert window._actions.refresh_on_playback.isCheckable()
    assert window._actions.refresh_on_playback.isChecked() is True


def test_toggle_refresh_on_playback_flips_the_gate_persists_and_announces(
    window, qtbot, minimal_score, monkeypatch
):
    from persistence import score_config
    from widgets import accessible_announcer

    load_and_wait(window, qtbot, minimal_score)

    announced = []
    monkeypatch.setattr(
        accessible_announcer, "announce", lambda widget, message: announced.append(message)
    )

    window.toggle_refresh_on_playback()

    assert window.refresh_gate.settings.refresh_during_playback is False
    assert window._actions.refresh_on_playback.isChecked() is False
    assert announced == ["Text refresh off."]

    window._save_current_score_config()
    assert score_config.load_for(minimal_score).refresh_settings.refresh_during_playback is False

    window.toggle_refresh_on_playback()

    assert window.refresh_gate.settings.refresh_during_playback is True
    assert window._actions.refresh_on_playback.isChecked() is True
    assert announced[-1] == "Text refresh on."


def test_toggle_refresh_on_playback_is_a_noop_with_no_score(window, monkeypatch):
    """Per-score (UserPlans/DelayRefresh.md), like toggle_metronome - there
    is nothing to store the flag on before a score is loaded."""
    from widgets import accessible_announcer

    announced = []
    monkeypatch.setattr(
        accessible_announcer, "announce", lambda widget, message: announced.append(message)
    )

    window.toggle_refresh_on_playback()

    assert window.refresh_gate.settings.refresh_during_playback is True
    assert window._actions.refresh_on_playback.isChecked() is True
    assert announced == ["Text refresh on."]


def test_delay_refresh_action_has_ctrl_shift_d(window):
    assert window._actions.delay_refresh.shortcut() == QKeySequence("Ctrl+Shift+D")
    assert not window._actions.delay_refresh.isCheckable()


def test_pause_and_metronome_shortcuts_dodge_reserved_macos_keys(window, monkeypatch):
    """Qt remaps its "Ctrl" token to Command on macOS, which would turn
    Pause (Ctrl+Space) into Cmd+Space (Spotlight, swallowed system-wide) and
    Toggle Metronome (Ctrl+M) into Cmd+M (Minimize on the Window menu). Both
    fall back to the physical Control key - Qt "Meta" - on darwin only. This
    test runs on Windows and still exercises the darwin branch, the class of
    guard ToMac.md asks for on every platform branch."""
    # Windows path: the historical bindings are unchanged.
    assert window._actions.pause_resume.shortcut() == QKeySequence("Ctrl+Space")
    assert window._actions.metronome.shortcut() == QKeySequence("Ctrl+M")

    monkeypatch.setattr(menu_builder.sys, "platform", "win32")
    assert _shortcut_for_platform("Ctrl+Space", "Meta+Space") == "Ctrl+Space"
    assert _shortcut_for_platform("Ctrl+M", "Meta+M") == "Ctrl+M"

    monkeypatch.setattr(menu_builder.sys, "platform", "darwin")
    assert _shortcut_for_platform("Ctrl+Space", "Meta+Space") == "Meta+Space"
    assert _shortcut_for_platform("Ctrl+M", "Meta+M") == "Meta+M"


def _mnemonic(text: str):
    """The '&'-prefixed letter Qt uses as this action/menu's Alt-access
    key, or None if it has none. '&&' is Qt's escape for a literal
    ampersand, not a mnemonic marker, and must be skipped rather than
    read as one."""
    i = 0
    while True:
        i = text.find("&", i)
        if i == -1:
            return None
        if text[i:i + 2] == "&&":
            i += 2
            continue
        return text[i + 1].upper() if i + 1 < len(text) else None


def test_reorder_and_performance_report_actions_have_global_dialog_shortcuts(window):
    """User-requested 2026-08-26: these three open a dialog exactly like
    Instruments/Key Signature/Mixer/etc, which all get a real
    Ctrl+Shift+<letter> shortcut - but these three never had one, only an
    Alt-only menu mnemonic that NVDA nonetheless announced as if it were a
    real global shortcut. Now they have the real thing, and (see the next
    test) no mnemonic to cause that confusion."""
    assert window._actions.attribute_order.shortcut() == QKeySequence("Ctrl+Shift+A")
    assert window._actions.part_order.shortcut() == QKeySequence("Ctrl+Shift+O")
    assert window._actions.performance_report.shortcut() == QKeySequence("Ctrl+Shift+F")


def test_set_musescore_location_menu_item_stores_the_chosen_path(window, monkeypatch, tmp_path):
    """Options > Set MuseScore Location... writes the picked path to
    AppSettings (global preference) so .mscz/.mscx opens can find the
    MuseScore 4 CLI (parsers/musescore_reader.py)."""
    from persistence import app_settings
    import main_window as main_window_module

    action = window._actions.set_musescore_location
    assert action is not None
    assert "&" not in action.text()

    exe = tmp_path / "MuseScore4.exe"
    exe.write_text("")
    monkeypatch.setattr(
        main_window_module.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(exe), "")),
    )

    action.trigger()

    assert app_settings.load().musescore_path == str(exe)


def _capture_open_filter(window, monkeypatch, musescore_found):
    """Trigger the File > Open dialog with find_musescore_executable stubbed
    and QFileDialog.getOpenFileName captured; return the filter string it
    was passed (the 4th positional arg)."""
    import main_window as main_window_module

    monkeypatch.setattr(
        main_window_module, "find_musescore_executable",
        lambda configured: "/x/MuseScore4.exe" if musescore_found else None,
    )
    seen = {}

    def _fake(*args, **kwargs):
        seen["filter"] = args[3] if len(args) > 3 else kwargs.get("filter")
        return ("", "")

    monkeypatch.setattr(
        main_window_module.QFileDialog, "getOpenFileName", staticmethod(_fake)
    )
    window._open_score_file_dialog(start_dir="")
    return seen["filter"]


def test_open_dialog_offers_musescore_files_when_musescore_is_found(window, monkeypatch):
    flt = _capture_open_filter(window, monkeypatch, musescore_found=True)
    assert "MuseScore Files (*.mscz *.mscx)" in flt
    assert "*.mscz *.mscx *.mid" in flt  # inside the combined Score Files group


def test_open_dialog_hides_musescore_files_when_musescore_is_absent(window, monkeypatch):
    flt = _capture_open_filter(window, monkeypatch, musescore_found=False)
    assert "mscz" not in flt
    assert "mscx" not in flt
    assert "MuseScore Files" not in flt
    # every other group still present and ;;-joined
    for group in (
        "Score Files (*.xml *.musicxml *.mxl *.mid *.midi *.gp *.ug)",
        "MusicXML Files (*.xml *.musicxml *.mxl)",
        "MIDI Files (*.mid *.midi)",
        "Guitar Pro Files (*.gp)",
        "Recall Score UG Import Files (*.ug)",
        "All Files (*)",
    ):
        assert group in flt
    assert flt.count(";;") == 5


def test_items_with_no_menu_mnemonic_have_no_ampersand(window):
    """User-requested 2026-08-26: NVDA was announcing an "alt+<letter>"
    hint for several items where that access key either duplicated a real
    global shortcut's own letter with no added value (Reorder Attributes/
    Parts, Performance Report - see the test above) or was never wanted at
    all (UK/US: "the user just changes them with the menu"; Help menu:
    "no shortcuts needed"). All of these must now have a literal "&"-free
    label so Qt never registers a mnemonic for them."""
    no_mnemonic_actions = [
        window._actions.attribute_order,
        window._actions.part_order,
        window._actions.performance_report,
        window._actions.uk_language,
        window._actions.us_language,
        window._actions.user_guide,
        window._actions.quick_start,
        window._actions.keystrokes,
        window._actions.about,
    ]
    for action in no_mnemonic_actions:
        assert "&" not in action.text(), f"{action.text()!r} still has a mnemonic"


def test_no_menu_mnemonic_collisions(window):
    """Regression guard for the 2026-08-26 mnemonic-collision sweep (see
    'Menus and shortcuts.txt'): within every menu, each item's mnemonic
    must be distinct from its siblings' AND from the menu's own top-level
    mnemonic. Both collision classes caused real, live NVDA bugs before
    being fixed (Tools > Tuner both "T"; several sibling pairs sharing a
    letter, e.g. Playback's old &Mute/&Mixer both "M") - this walks every
    menu (and one level into any submenu, e.g. Options > Language) rather
    than hardcoding the fixed set found by hand, so a future menu item
    that reintroduces either class of collision fails here instead of
    waiting for another live report."""
    for top_action in window.menuBar().actions():
        menu = top_action.menu()
        if menu is None:
            continue
        top_mnemonic = _mnemonic(top_action.text())
        seen = {}
        for action in menu.actions():
            if action.isSeparator():
                continue
            mnemonic = _mnemonic(action.text())
            if mnemonic is not None:
                assert mnemonic != top_mnemonic, (
                    f"{action.text()!r} in {top_action.text()!r} repeats "
                    f"its own menu's mnemonic ({mnemonic})"
                )
                assert mnemonic not in seen, (
                    f"{action.text()!r} and {seen.get(mnemonic)!r} in "
                    f"{top_action.text()!r} both use mnemonic {mnemonic}"
                )
                seen[mnemonic] = action.text()

            submenu = action.menu()
            if submenu is None:
                continue
            sub_seen = {}
            for sub_action in submenu.actions():
                if sub_action.isSeparator():
                    continue
                sub_mnemonic = _mnemonic(sub_action.text())
                if sub_mnemonic is None:
                    continue
                assert sub_mnemonic not in sub_seen, (
                    f"{sub_action.text()!r} and {sub_seen.get(sub_mnemonic)!r} "
                    f"in {action.text()!r} both use mnemonic {sub_mnemonic}"
                )
                sub_seen[sub_mnemonic] = sub_action.text()


def test_goto_measure_dialog_shows_with_focus_on_the_edit_field(window, qtbot):
    """The dialog used to call setFocus() in __init__, before the native
    window existed - Qt's own focus tracking accepted it, but no
    accessibility focus-changed event ever reached NVDA, which kept
    announcing whatever had focus before Ctrl+G was pressed. Deferring the
    setFocus() to after showEvent (see GotoMeasureDialog.showEvent) fixes
    that; this proves the edit field actually ends up with real Qt focus
    once the dialog is shown, not just tab-order to it."""
    dialog = GotoMeasureDialog(window)
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitExposed(dialog)
    qtbot.waitUntil(lambda: dialog.focusWidget() is dialog.measure_edit)

    assert dialog.focusWidget() is dialog.measure_edit


def test_about_dialog_shows_the_version_number(window):
    from version import __version__

    dialog = AboutDialog(window)
    labels = dialog.findChildren(QLabel)

    assert any(__version__ in label.text() for label in labels)


def test_about_dialog_labels_are_individually_tab_focusable(window):
    """Each piece of the About text (name, version, description) is its own
    Tab stop, so NVDA users can move through them one at a time instead of
    hearing one large label read all at once."""
    dialog = AboutDialog(window)
    labels = dialog.findChildren(QLabel)

    assert len(labels) >= 3
    for label in labels:
        assert label.focusPolicy() == Qt.FocusPolicy.StrongFocus


def test_about_action_opens_without_crashing(window, qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr("main_window.AboutDialog", lambda parent: type(
        "FakeDialog", (), {"exec": lambda self: opened.append(True)}
    )())

    window._show_about_dialog()

    assert opened == [True]


def test_tools_menu_has_keyboard_shortcuts_action_that_opens_the_dialog(window, monkeypatch):
    assert window._actions.keyboard_shortcuts is not None
    assert window._actions.keyboard_shortcuts.text() == "&Keyboard Shortcuts..."

    opened = []
    monkeypatch.setattr(
        "main_window.KeyboardShortcutsDialog",
        lambda parent, controller: type(
            "FakeDialog", (), {"exec": lambda self: opened.append(controller)}
        )(),
    )

    window._show_keyboard_shortcuts_dialog()

    assert opened == [window.shortcuts]


def test_missing_user_guide_reports_an_error_instead_of_doing_nothing(window, monkeypatch):
    """CR8thSept2.txt T1: Help > User Guide used to just print and return when
    the file was absent, so a frozen-build user saw Help do nothing at all."""
    monkeypatch.setattr("main_window.user_guide_html_path", lambda: "/no/such/guide.html")
    monkeypatch.setattr("main_window.QDesktopServices.openUrl",
                        lambda *_: pytest.fail("must not try to open a missing guide"))
    calls = []
    monkeypatch.setattr("main_window.notify_user", lambda level, message: calls.append((level, message)))

    window._show_user_guide()

    assert len(calls) == 1 and calls[0][0] == "error"


def test_missing_quick_start_reports_an_error_instead_of_doing_nothing(window, monkeypatch):
    monkeypatch.setattr("main_window.quick_start_html_path", lambda: "/no/such/guide.html")
    monkeypatch.setattr("main_window.QDesktopServices.openUrl",
                        lambda *_: pytest.fail("must not try to open a missing guide"))
    calls = []
    monkeypatch.setattr("main_window.notify_user", lambda level, message: calls.append((level, message)))

    window._show_quick_start()

    assert len(calls) == 1 and calls[0][0] == "error"


def test_missing_keystrokes_reports_an_error_instead_of_doing_nothing(window, monkeypatch):
    monkeypatch.setattr("main_window.keystrokes_html_path", lambda: "/no/such/guide.html")
    monkeypatch.setattr("main_window.QDesktopServices.openUrl",
                        lambda *_: pytest.fail("must not try to open a missing guide"))
    calls = []
    monkeypatch.setattr("main_window.notify_user", lambda level, message: calls.append((level, message)))

    window._show_keystrokes()

    assert len(calls) == 1 and calls[0][0] == "error"
