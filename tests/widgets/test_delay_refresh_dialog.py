"""widgets/delay_refresh_dialog.py - a pure view over RefreshSettings.

Never exec()'d: the dialog is built, driven through its widgets and read
back, the same way test_play_settings_dialog.py drives PlaySettingsDialog.
"""
from models.refresh_settings import RefreshSettings
from widgets.delay_refresh_dialog import DelayRefreshDialog


def test_shows_the_settings_it_was_given(qtbot):
    settings = RefreshSettings(refresh_during_playback=False, delay_ms=-400)
    dialog = DelayRefreshDialog(refresh_settings=settings)
    qtbot.addWidget(dialog)

    assert dialog.refresh_check.isChecked() is False
    assert dialog.delay_spin.value() == -0.4


def test_defaults_when_no_settings_given(qtbot):
    dialog = DelayRefreshDialog()
    qtbot.addWidget(dialog)

    assert dialog.refresh_check.isChecked() is True
    assert dialog.delay_spin.value() == 0.0


def test_spin_box_disabled_when_tickbox_clear(qtbot):
    dialog = DelayRefreshDialog(refresh_settings=RefreshSettings())
    qtbot.addWidget(dialog)

    assert dialog.delay_spin.isEnabled() is True

    dialog.refresh_check.setChecked(False)
    assert dialog.delay_spin.isEnabled() is False

    dialog.refresh_check.setChecked(True)
    assert dialog.delay_spin.isEnabled() is True


def test_edits_round_trip_back_out_including_negative(qtbot):
    dialog = DelayRefreshDialog(refresh_settings=RefreshSettings())
    qtbot.addWidget(dialog)

    dialog.refresh_check.setChecked(False)
    dialog.delay_spin.setValue(-0.35)

    settings = dialog.refresh_settings()

    assert settings.refresh_during_playback is False
    assert settings.delay_ms == -350


def test_edits_round_trip_back_out_positive(qtbot):
    dialog = DelayRefreshDialog(refresh_settings=RefreshSettings())
    qtbot.addWidget(dialog)

    dialog.delay_spin.setValue(0.5)

    settings = dialog.refresh_settings()

    assert settings.refresh_during_playback is True
    assert settings.delay_ms == 500
