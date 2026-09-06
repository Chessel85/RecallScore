# tests/widgets/test_metronome_player_dialog.py
"""Pure widget-state tests for MetronomePlayerDialog - it never touches
MusicData/PlaybackController/SynthEngine, only emits signals, so it can be
driven directly with no MainWindow/score involved (like test_strumming_dialog)."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from widgets.metronome_player_dialog import MetronomePlayerDialog


def _dialog(qtbot, **kwargs):
    kwargs.setdefault("numerator", 4)
    kwargs.setdefault("denominator", 4)
    kwargs.setdefault("pattern", "ABBB")
    kwargs.setdefault("tempo_bpm", 120)
    dialog = MetronomePlayerDialog(**kwargs)
    qtbot.addWidget(dialog)
    return dialog


def test_seeds_every_control_from_the_constructor(qtbot):
    dialog = _dialog(qtbot, numerator=7, denominator=8, pattern="ABBCDDD", tempo_bpm=140)
    assert dialog.numerator() == 7
    assert dialog.denominator() == 8
    assert dialog.pattern() == "ABBCDDD"
    assert dialog.tempo_bpm() == 140


def test_denominator_snaps_to_four_when_unrepresentable(qtbot):
    dialog = _dialog(qtbot, denominator=3)
    assert dialog.denominator() == 4


def test_tempo_is_clamped_to_the_allowed_range(qtbot):
    assert _dialog(qtbot, tempo_bpm=9999).tempo_bpm() == 300
    assert _dialog(qtbot, tempo_bpm=1).tempo_bpm() == 5


def test_validator_rejects_stray_characters_but_keeps_the_pattern_alphabet(qtbot):
    dialog = _dialog(qtbot)
    validator = dialog.pattern_edit.validator()
    assert validator.validate("x", 1)[0] == QValidator.State.Invalid
    assert validator.validate("A.bCd", 5)[0] != QValidator.State.Invalid


def test_changing_the_numerator_rewrites_the_pattern_to_the_new_default(qtbot):
    dialog = _dialog(qtbot, numerator=4, pattern="ABBB")
    dialog.numerator_spin.setValue(5)
    assert dialog.pattern() == "ABBBB"
    dialog.numerator_spin.setValue(2)
    assert dialog.pattern() == "AB"


def test_play_with_a_mismatched_pattern_warns_and_does_not_start(qtbot, monkeypatch):
    dialog = _dialog(qtbot, numerator=5, pattern="ABBB")
    calls = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: calls.append(a))
    dialog._toggle()
    assert calls, "a mismatch shows QMessageBox.warning"
    assert dialog.is_running() is False
    assert not dialog._timer.isActive()


def test_play_with_a_matching_pattern_starts_the_timer_and_clicks_in_order(qtbot):
    dialog = _dialog(qtbot, numerator=4, pattern="A.CB", tempo_bpm=120)
    heard = []
    dialog.click_requested.connect(heard.append)

    dialog._toggle()  # Play
    assert dialog.is_running() is True
    assert dialog.play_button.text() == "&Pause"
    # _start fires beat 0 immediately; the rest are re-armed off the timer.
    for _ in range(5):
        dialog._fire_beat()

    # beats: A . C B A .  -> the '.' positions emit nothing
    assert heard == ["A", "C", "B", "A"]


def test_beat_interval_is_sixty_thousand_over_bpm(qtbot):
    dialog = _dialog(qtbot, tempo_bpm=144)
    assert dialog._beat_interval_ms() == round(60000 / 144)


def test_stop_button_stops_the_timer_and_emits_stopped(qtbot):
    dialog = _dialog(qtbot, numerator=2, pattern="AB")
    dialog._toggle()  # Play
    with qtbot.waitSignal(dialog.stopped):
        dialog._toggle()  # Stop
    assert dialog.is_running() is False
    assert dialog.play_button.text() == "&Play"


def test_reject_and_close_each_stop_the_click(qtbot):
    for closer in ("reject", "close"):
        dialog = _dialog(qtbot, numerator=2, pattern="AB")
        dialog._toggle()  # Play
        with qtbot.waitSignal(dialog.stopped):
            getattr(dialog, closer)()
        assert dialog.is_running() is False


def test_spacebar_toggles_play_from_every_input_control(qtbot):
    dialog = _dialog(qtbot, numerator=2, pattern="AB")
    for widget in (
        dialog.numerator_spin, dialog.denominator_combo,
        dialog.pattern_edit, dialog.tempo_spin,
    ):
        widget.setFocus()
        before = dialog.is_running()
        qtbot.keyClick(widget, Qt.Key.Key_Space)
        assert dialog.is_running() is (not before), widget


def test_spacebar_on_the_close_button_still_closes_the_dialog(qtbot):
    dialog = _dialog(qtbot, numerator=2, pattern="AB")
    dialog._toggle()  # running
    close_button = dialog.close_box.button(QDialogButtonBox.StandardButton.Close)
    close_button.setFocus()
    with qtbot.waitSignal(dialog.stopped):
        qtbot.keyClick(close_button, Qt.Key.Key_Space)
    assert dialog.is_running() is False
