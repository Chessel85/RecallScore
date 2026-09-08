# widgets/voice_control_test_dialog.py
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QDialog,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from audio.voice_recognition import UNKNOWN_TOKEN

_IDLE_STATUS = "Press Start Test, then speak one of the voice commands."


class VoiceControlTestDialog(QDialog):
    """Options > Voice Control Settings... > Test... (Ref 19) - lets the
    user practice speaking commands and check their microphone/threshold
    setup without triggering any real navigation or playback.

    Pure view: it owns NO recognizer and spawns NO process. Start/Stop emit
    start_requested/stop_requested; VoiceControlController runs a diagnostic
    session on its single, shared VoiceRecognitionManager and calls back
    report_start_result / report_diagnostic (main_window.py's
    _show_voice_control_test_dialog wires the two together). The controller
    suppresses real command dispatch for the session's duration, so speaking
    "stop" here never stops real playback - this dialog is feedback-only.

    Threading is entirely the controller's problem now: report_start_result/
    report_diagnostic are already marshaled onto the Qt main thread before
    they reach here.
    """

    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None, *, confidence_threshold: float = 70.0):
        super().__init__(parent)
        self.setWindowTitle("Voice Control Test")
        self._running = False

        self.hint_label = QLabel(
            "Try saying, for example, \"stop\" or \"next bar\". "
            "The full list of commands is in the User Guide. "
            f"Confidence threshold for this test: {confidence_threshold:.0f}%.",
            self,
        )
        self.hint_label.setWordWrap(True)

        self.status_label = QLabel(_IDLE_STATUS, self)

        self.start_button = QPushButton("&Start Test", self)
        self.start_button.clicked.connect(self._toggle_listening)

        self.results_list = QListWidget(self)
        self.results_list.setAccessibleName("Recognition results")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.start_button)
        layout.addWidget(self.results_list)
        layout.addWidget(buttons)

    def _toggle_listening(self) -> None:
        if self._running:
            self._set_idle()
            self.stop_requested.emit()
            return
        self.start_requested.emit()

    def _set_idle(self) -> None:
        self._running = False
        self.status_label.setText(_IDLE_STATUS)
        self.start_button.setText("&Start Test")

    # --- called by VoiceControlController (Qt main thread) --------------

    def report_start_result(self, started: bool) -> None:
        """The controller's answer to start_requested: whether the
        diagnostic worker was actually launched."""
        self._running = started
        if started:
            self.status_label.setText("Listening - speak a voice command.")
            self.start_button.setText("St&op Test")
        else:
            self.status_label.setText(
                "Could not start voice recognition. See the console for details."
            )
            self.start_button.setText("&Start Test")

    def report_diagnostic(self, heard_text: str, confidence: float, accepted: bool) -> None:
        """One row per final result. Never dispatches anything - this dialog
        is feedback-only (see class docstring).

        Silence is dropped rather than listed - audio/voice_recognition.py
        reports it as heard_text="(silence)" (see its own _handle_final_
        result), and listing one row per silent gap made the results list
        hard to navigate for no useful information (reported).

        Vosk's own catch-all UNKNOWN_TOKEN ("[unk]") means "something was
        said that isn't in the vocabulary" - shown with a plain-language
        message instead of the raw "[unk]" token, which read as unclear
        jargon in testing (reported)."""
        if heard_text == "(silence)":
            return
        if heard_text == UNKNOWN_TOKEN:
            self.results_list.addItem("Word not in dictionary - rejected")
            self.results_list.scrollToBottom()
            return
        verdict = "accepted" if accepted else "rejected"
        self.results_list.addItem(f"Heard: '{heard_text}' - confidence {confidence:.0f}% ({verdict})")
        self.results_list.scrollToBottom()

    # --- teardown -----------------------------------------------------

    def reject(self):
        if self._running:
            self._set_idle()
            self.stop_requested.emit()
        super().reject()

    def closeEvent(self, event):
        if self._running:
            self._set_idle()
            self.stop_requested.emit()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.start_button.setFocus)
