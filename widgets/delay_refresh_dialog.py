# widgets/delay_refresh_dialog.py
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLabel,
    QVBoxLayout,
)

from models.refresh_settings import RefreshSettings


class DelayRefreshDialog(QDialog):
    """Playback > Delay Refresh... (Ctrl+Shift+D) - whether the regions and
    status bar refresh while playback runs, and how far that refresh is
    offset from the sounding note. See UserPlans/DelayRefresh.md for why
    this feature exists.

    A pure view, like PlaySettingsDialog: it edits a working copy and hands
    it back from refresh_settings(); MainWindow decides what to do with it
    on OK. Seconds in this dialog, milliseconds in the model - the
    conversion happens at this class's boundary only.
    """

    def __init__(self, parent=None, refresh_settings: RefreshSettings = None):
        super().__init__(parent)
        self.setWindowTitle("Delay Refresh")
        settings = refresh_settings.copy() if refresh_settings is not None else RefreshSettings()

        layout = QVBoxLayout(self)

        self.refresh_check = QCheckBox("&Refresh text on playback", self)
        self.refresh_check.setChecked(settings.refresh_during_playback)
        layout.addWidget(self.refresh_check)

        self.delay_spin = QDoubleSpinBox(self)
        self.delay_spin.setRange(-1.00, 1.00)
        self.delay_spin.setSingleStep(0.05)
        self.delay_spin.setDecimals(2)
        self.delay_spin.setSuffix(" seconds")
        self.delay_spin.setValue(settings.delay_ms / 1000.0)
        self._add_row(layout, "Refresh &delay (seconds):", self.delay_spin)

        self.refresh_check.toggled.connect(self._update_enabled_states)
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
        self.delay_spin.setEnabled(self.refresh_check.isChecked())

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh_check.setFocus)

    def refresh_settings(self) -> RefreshSettings:
        """The edited settings. Clamping is the model's job, not the
        dialog's."""
        return RefreshSettings(
            refresh_during_playback=self.refresh_check.isChecked(),
            delay_ms=round(self.delay_spin.value() * 1000),
        )
