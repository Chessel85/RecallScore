# widgets/metronome_player_dialog.py
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from models.music_data import MusicData
from models.metronome_pattern import (
    PATTERN_REGEX,
    default_pattern,
    normalise_pattern,
    pattern_length_matches,
)
from widgets.range_spin_box import RangeSpinBox


class MetronomePlayerDialog(QDialog):
    """Tools > Metronome Player... (Ctrl+Shift+M) - a modal practice
    metronome, independent of any loaded score. The user picks a time
    signature, a per-beat click pattern (A/B/C/D pick one of four click
    sounds, '.' is a silent beat) and a tempo, then the Play/Pause button
    (Alt+P, or Spacebar from any input control) toggles a free-running
    click.

    Pure view (docs/dialog_widget_patterns.md conventions), mirroring
    widgets/strumming_dialog.py: it owns a re-armed single-shot QTimer and
    emits click_requested / stopped; MainWindow drives the synth. The caller
    seeds every value (numerator/denominator/pattern/tempo already snapped).
    Closing the dialog - the Close button, Escape or the title-bar X - stops
    the click.
    """

    click_requested = Signal(str)  # pattern symbol for this beat ('A'..'D')
    stopped = Signal()             # metronome stopped (button / close / escape)

    def __init__(
        self,
        parent=None,
        numerator: int = 4,
        denominator: int = 4,
        pattern: str = "ABBB",
        tempo_bpm: int = 120,
    ):
        super().__init__(parent)
        self.setWindowTitle("Metronome Player")

        self._pattern = ""   # the normalised pattern in use while running
        self._index = 0      # position into self._pattern

        layout = QVBoxLayout(self)

        num_label = QLabel("Time &signature:", self)
        self.numerator_spin = RangeSpinBox(self)
        self.numerator_spin.setRange(1, 12)
        self.numerator_spin.setValue(max(1, min(12, int(numerator))))
        num_label.setBuddy(self.numerator_spin)
        layout.addWidget(num_label)
        layout.addWidget(self.numerator_spin)

        # A bare "/" reads as the musical "n / m" between the two fields.
        den_label = QLabel("/", self)
        self.denominator_combo = QComboBox(self)
        self.denominator_combo.addItems(["2", "4", "8", "16"])
        start_den = str(int(denominator))
        if self.denominator_combo.findText(start_den) >= 0:
            self.denominator_combo.setCurrentText(start_den)
        else:
            self.denominator_combo.setCurrentText("4")
        den_label.setBuddy(self.denominator_combo)
        layout.addWidget(den_label)
        layout.addWidget(self.denominator_combo)

        pattern_label = QLabel("&Beat pattern:", self)
        self.pattern_edit = QLineEdit(self)
        self.pattern_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression(PATTERN_REGEX), self)
        )
        self.pattern_edit.setText(str(pattern))
        pattern_label.setBuddy(self.pattern_edit)
        pattern_help = (
            "One character per beat: A, B, C and D each play a different "
            "click sound; a full stop is a silent beat."
        )
        self.pattern_edit.setStatusTip(pattern_help)
        self.pattern_edit.setAccessibleDescription(pattern_help)
        layout.addWidget(pattern_label)
        layout.addWidget(self.pattern_edit)

        tempo_label = QLabel("&Tempo:", self)
        self.tempo_spin = RangeSpinBox(self)
        self.tempo_spin.setRange(MusicData.MIN_TEMPO_BPM, MusicData.MAX_TEMPO_BPM)
        self.tempo_spin.setKeyboardTracking(False)
        self.tempo_spin.setValue(
            max(MusicData.MIN_TEMPO_BPM,
                min(MusicData.MAX_TEMPO_BPM, int(tempo_bpm)))
        )
        tempo_label.setBuddy(self.tempo_spin)
        layout.addWidget(tempo_label)
        layout.addWidget(self.tempo_spin)

        self.play_button = QPushButton("&Play", self)
        self.play_button.setAutoDefault(False)
        self.play_button.clicked.connect(self._toggle)
        layout.addWidget(self.play_button)

        self.close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.close_box.rejected.connect(self.reject)
        layout.addWidget(self.close_box)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._fire_beat)

        # Keep the pattern valid-by-default as the bar length changes; the
        # user can still edit it and will get the mismatch message box on
        # Play if it no longer matches. Denominator changes don't touch it.
        self.numerator_spin.valueChanged.connect(self._on_numerator_changed)

        # Spacebar is a second Play/Pause toggle (alongside Alt+P), working
        # from any of the input controls. It is filtered on those widgets
        # only, so Space on the Close button still closes the dialog; on the
        # pattern field Space types nothing anyway (the validator blocks it),
        # and losing "Space opens the popup" on the denominator combo is the
        # deliberate trade (Alt+Down / arrows still open it).
        for widget in (
            self.numerator_spin, self.denominator_combo,
            self.pattern_edit, self.tempo_spin,
        ):
            widget.installEventFilter(self)

    # --- getters for tests -------------------------------------------------

    def numerator(self) -> int:
        return self.numerator_spin.value()

    def denominator(self) -> int:
        return int(self.denominator_combo.currentText())

    def pattern(self) -> str:
        return self.pattern_edit.text()

    def tempo_bpm(self) -> int:
        return self.tempo_spin.value()

    def is_running(self) -> bool:
        return self._timer.isActive()

    # --- behaviour -------------------------------------------------------

    def _on_numerator_changed(self, value: int) -> None:
        self.pattern_edit.setText(default_pattern(value))

    def _beat_interval_ms(self) -> int:
        """One pattern position = one denominator note; the tempo is already
        denominator-relative, so this is a flat 60000 / BPM. Re-read each
        beat so a tempo edit while running is picked up."""
        return max(1, round(60000.0 / self.tempo_spin.value()))

    def _toggle(self) -> None:
        if self.is_running():
            self._stop()
            return
        numerator = self.numerator_spin.value()
        pattern = normalise_pattern(self.pattern_edit.text())
        if not pattern_length_matches(pattern, numerator):
            QMessageBox.warning(
                self,
                "Pattern does not match the time signature",
                f"The pattern has {len(pattern)} beat(s) but the time "
                f"signature has {numerator} beat(s) per bar. Edit the "
                f"pattern or the time signature so they match, then press Play.",
            )
            return
        self._start(pattern)

    def _start(self, pattern: str) -> None:
        self._pattern = pattern
        self._index = 0
        # "&Pause", not "&Stop", so Alt+P works for both starting and
        # stopping the click (the mnemonic stays on P either way).
        self.play_button.setText("&Pause")
        self._fire_beat()

    def _fire_beat(self) -> None:
        if not self._pattern:
            return
        symbol = self._pattern[self._index]
        if symbol != ".":
            self.click_requested.emit(symbol)
        self._index = (self._index + 1) % len(self._pattern)
        self._timer.start(self._beat_interval_ms())

    def _stop(self) -> None:
        if not self._timer.isActive():
            return
        self._timer.stop()
        self.play_button.setText("&Play")
        self.stopped.emit()

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
        ):
            self._toggle()
            return True
        return super().eventFilter(obj, event)

    def reject(self):
        self._stop()
        super().reject()

    def closeEvent(self, event):
        self._stop()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.pattern_edit.setFocus)
