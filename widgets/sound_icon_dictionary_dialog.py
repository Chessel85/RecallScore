# widgets/sound_icon_dictionary_dialog.py
"""Help > Sound Icon Dictionary (PerformanceMarkingsStrategy.md section
10.1): every sound Recall Score can make, as a plain list of short names.
Always enabled, with or without a score loaded (decided in review - this is
a reference, not something tied to the current file).

Rows show just entry.name - no meaning/when text - so the list reads like
the keystroke list, not a paragraph. The sound auto-plays on every arrow-key
move (Ref 9's audition pattern, same as Region 3's timeline), and the Play
button replays the current row on demand.

Pure view (docs/dialog_widget_patterns.md conventions), modelled on
widgets/strumming_dialog.py's list-plus-Play shape: it emits
play_index_requested(index) and MainWindow drives the synth via
PlaybackController.play_event_sequence. Read-only - no Ok/Cancel, just
Close, like widgets/keyboard_shortcuts_dialog.py's Close-only button box."""
from typing import List, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidget, QPushButton, QVBoxLayout

from audio.sound_catalog import SoundCatalogEntry
from widgets.list_focus_helper import focus_list_and_reannounce_current_row


class SoundIconDictionaryDialog(QDialog):
    play_index_requested = Signal(int)

    def __init__(self, parent=None, entries: Optional[List[SoundCatalogEntry]] = None):
        super().__init__(parent)
        self.setWindowTitle("Sound Icon Dictionary")
        self._entries = list(entries or [])

        layout = QVBoxLayout(self)

        self.sound_list = QListWidget(self)
        for entry in self._entries:
            self.sound_list.addItem(entry.name)
        if self.sound_list.count():
            self.sound_list.setCurrentRow(0)
        self.sound_list.currentRowChanged.connect(self._update_play_button)
        self.sound_list.currentRowChanged.connect(self._auto_play_on_navigation)
        layout.addWidget(self.sound_list)

        self.play_button = QPushButton("&Play", self)
        self.play_button.setAutoDefault(False)
        self.play_button.clicked.connect(self._play_current)
        layout.addWidget(self.play_button)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

        self._update_play_button(self.sound_list.currentRow())

    def _current_entry(self) -> Optional[SoundCatalogEntry]:
        row = self.sound_list.currentRow()
        return self._entries[row] if 0 <= row < len(self._entries) else None

    def _update_play_button(self, _row: int) -> None:
        entry = self._current_entry()
        self.play_button.setEnabled(entry is not None and bool(entry.events))

    def _play_current(self) -> None:
        entry = self._current_entry()
        if entry is not None and entry.events:
            self.play_index_requested.emit(self.sound_list.currentRow())

    def _auto_play_on_navigation(self, row: int) -> None:
        entry = self._entries[row] if 0 <= row < len(self._entries) else None
        if entry is not None and entry.events:
            self.play_index_requested.emit(row)

    def entry_at(self, index: int) -> Optional[SoundCatalogEntry]:
        return self._entries[index] if 0 <= index < len(self._entries) else None

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: focus_list_and_reannounce_current_row(self.sound_list))
