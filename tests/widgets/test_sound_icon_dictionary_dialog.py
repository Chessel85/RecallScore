# tests/widgets/test_sound_icon_dictionary_dialog.py
from audio.sound_catalog import SoundCatalogEntry
from widgets.sound_icon_dictionary_dialog import SoundIconDictionaryDialog


def _entries():
    return [
        SoundCatalogEntry("Boundary cue", "You hit an edge", "At the edge", [(250, 0, 6, 60, 127)]),
        SoundCatalogEntry("Live MIDI input", "Passthrough", "While playing", []),
    ]


def test_lists_one_row_per_entry(qtbot):
    dialog = SoundIconDictionaryDialog(None, entries=_entries())
    qtbot.addWidget(dialog)
    assert dialog.sound_list.count() == 2
    assert "Boundary cue" in dialog.sound_list.item(0).text()


def test_play_button_disabled_for_an_entry_with_no_events(qtbot):
    dialog = SoundIconDictionaryDialog(None, entries=_entries())
    qtbot.addWidget(dialog)
    dialog.sound_list.setCurrentRow(1)
    assert dialog.play_button.isEnabled() is False


def test_play_button_emits_play_index_requested(qtbot):
    dialog = SoundIconDictionaryDialog(None, entries=_entries())
    qtbot.addWidget(dialog)
    dialog.sound_list.setCurrentRow(0)
    received = []
    dialog.play_index_requested.connect(received.append)
    dialog.play_button.click()
    assert received == [0]


def test_help_menu_opens_the_dialog_and_wires_play(window, qtbot, monkeypatch, null_synth):
    opened = {}

    class _FakeDialog:
        def __init__(self, parent, entries=None):
            opened["entries"] = entries
            self._entries = entries
            self.play_index_requested = _Signal()

        def entry_at(self, index):
            return self._entries[index]

        def exec(self):
            self.play_index_requested.fire(0)
            return 0

    class _Signal:
        def __init__(self):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def fire(self, *a):
            for slot in self._slots:
                slot(*a)

    monkeypatch.setattr("main_window.SoundIconDictionaryDialog", _FakeDialog)
    window._show_sound_icon_dictionary_dialog()

    assert opened["entries"]
    assert null_synth.clicks  # the boundary cue (or whichever entry[0] is) sounded
