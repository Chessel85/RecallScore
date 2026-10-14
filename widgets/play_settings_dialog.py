# widgets/play_settings_dialog.py
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from models.music_data import MusicData
from models.play_settings import (
    LOOP_REPEAT_MODES,
    MAX_LEAD_IN_BARS,
    MAX_LEAD_IN_BEATS,
    MAX_LOOP_LENGTH_BARS,
    MIN_LOOP_LENGTH_BARS,
    LOOP_REPEAT_LABELS,
    PLAY_MODE_LABELS,
    PLAY_MODES,
    PlaySettings,
    dialog_enabled_states,
    dialog_labels,
)
from models.vocabulary import bar_word


class PlaySettingsDialog(QDialog):
    """Playback > Play Settings... (Ctrl+Shift+P) - the single
    settings dialog for the one play transport: the absolute playback tempo
    for this piece, the lead-in count-in before Space starts, and whether
    Space loops a fixed window.

    Replaces the old Preview Settings / Tempo Offset dialogs. A pure view,
    like MixerDialog: it edits a working copy and hands it back from
    play_settings() / tempo_display_bpm(); MainWindow decides what to do
    with them on OK. Every control has a QLabel with setBuddy so a screen
    reader announces what it is, and focus is deferred to showEvent for the
    same NVDA reason.

    Bar/measure wording goes through vocabulary.bar_word, never a hardcoded
    literal.
    """

    def __init__(
        self,
        parent=None,
        play_settings: PlaySettings = None,
        current_tempo_display_bpm: float = 120.0,
        uk_terms: bool = True,
        score_has_repeats: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle("Play Settings")
        settings = play_settings.copy() if play_settings is not None else PlaySettings()
        labels = dialog_labels(bar_word(uk_terms))
        # "Repeat handling while looping" only bites when the score actually
        # carries repeat barlines; the combo is disabled otherwise (as it is
        # with looping off).
        self._score_has_repeats = bool(score_has_repeats)

        layout = QVBoxLayout(self)

        self.tempo_spin = QSpinBox(self)
        self.tempo_spin.setRange(MusicData.MIN_TEMPO_BPM, MusicData.MAX_TEMPO_BPM)
        self.tempo_spin.setValue(
            max(
                MusicData.MIN_TEMPO_BPM,
                min(MusicData.MAX_TEMPO_BPM, int(round(current_tempo_display_bpm))),
            )
        )
        self._add_row(layout, labels["tempo"], self.tempo_spin)

        self.lead_in_check = QCheckBox(labels["lead_in_enabled"], self)
        self.lead_in_check.setChecked(settings.lead_in_enabled)
        layout.addWidget(self.lead_in_check)

        self.lead_in_bars_spin = QSpinBox(self)
        self.lead_in_bars_spin.setRange(0, MAX_LEAD_IN_BARS)
        self.lead_in_bars_spin.setValue(settings.lead_in_bars)
        self._add_row(layout, labels["lead_in_bars"], self.lead_in_bars_spin)

        self.lead_in_beats_spin = QSpinBox(self)
        self.lead_in_beats_spin.setRange(0, MAX_LEAD_IN_BEATS)
        self.lead_in_beats_spin.setValue(settings.lead_in_beats)
        self._add_row(layout, labels["lead_in_beats"], self.lead_in_beats_spin)

        # Replaces the old "Repeat (loop) until stopped" tickbox: a three-way
        # choice of how far Space plays. Sits here - right after the lead-in
        # controls and before the loop-length spin - both visually and in
        # the tab order.
        self.play_mode_combo = QComboBox(self)
        self.play_mode_combo.addItems(PLAY_MODE_LABELS)
        try:
            play_mode_index = PLAY_MODES.index(settings.play_mode)
        except ValueError:
            play_mode_index = 0
        self.play_mode_combo.setCurrentIndex(play_mode_index)
        self._add_row(layout, labels["play_mode"], self.play_mode_combo)

        self.loop_length_spin = QSpinBox(self)
        self.loop_length_spin.setRange(MIN_LOOP_LENGTH_BARS, MAX_LOOP_LENGTH_BARS)
        self.loop_length_spin.setValue(settings.loop_length_bars)
        self._add_row(layout, labels["loop_length_bars"], self.loop_length_spin)

        self.loop_repeat_combo = QComboBox(self)
        self.loop_repeat_combo.addItems(LOOP_REPEAT_LABELS)
        try:
            mode_index = LOOP_REPEAT_MODES.index(settings.loop_repeat_mode)
        except ValueError:
            mode_index = 0
        self.loop_repeat_combo.setCurrentIndex(mode_index)
        self._add_row(layout, labels["loop_repeat_mode"], self.loop_repeat_combo)

        self.loop_lead_in_check = QCheckBox(labels["loop_lead_in"], self)
        self.loop_lead_in_check.setChecked(settings.loop_lead_in)
        layout.addWidget(self.loop_lead_in_check)

        self.lead_in_check.toggled.connect(self._update_enabled_states)
        self.play_mode_combo.currentIndexChanged.connect(self._update_enabled_states)
        self._update_enabled_states()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_row(self, layout: QVBoxLayout, text: str, widget) -> None:
        label = QLabel(text, self)
        label.setBuddy(widget)
        layout.addWidget(label)
        layout.addWidget(widget)

    def _update_enabled_states(self, *_args) -> None:
        enabled = dialog_enabled_states(
            self.lead_in_check.isChecked(),
            PLAY_MODES[self.play_mode_combo.currentIndex()],
            self._score_has_repeats,
        )
        self.lead_in_bars_spin.setEnabled(enabled["lead_in_bars"])
        self.lead_in_beats_spin.setEnabled(enabled["lead_in_beats"])
        self.loop_length_spin.setEnabled(enabled["loop_length_bars"])
        self.loop_repeat_combo.setEnabled(enabled["loop_repeat_mode"])
        self.loop_lead_in_check.setEnabled(enabled["loop_lead_in"])

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.tempo_spin.setFocus)

    def play_settings(self) -> PlaySettings:
        """The edited lead-in/looping settings. Clamping is PlaySettings'
        own job, so a value typed straight into a spin box is bounded the
        same way a hand-edited settings file is."""
        return PlaySettings(
            lead_in_enabled=self.lead_in_check.isChecked(),
            lead_in_bars=self.lead_in_bars_spin.value(),
            lead_in_beats=self.lead_in_beats_spin.value(),
            play_mode=PLAY_MODES[self.play_mode_combo.currentIndex()],
            loop_length_bars=self.loop_length_spin.value(),
            loop_lead_in=self.loop_lead_in_check.isChecked(),
            loop_repeat_mode=LOOP_REPEAT_MODES[self.loop_repeat_combo.currentIndex()],
        )

    def tempo_display_bpm(self) -> int:
        """The absolute playback tempo, in time-signature-denominator beats
        per minute."""
        return self.tempo_spin.value()
