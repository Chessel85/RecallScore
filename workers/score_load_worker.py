# workers/score_load_worker.py
import traceback

from PySide6.QtCore import QThread, Signal

from parsers.gp_reader import GpReader
from parsers.midi_reader import MidiReader
from parsers.musescore_reader import MuseScoreReader
from parsers.musicXML_reader import MusicXMLReader
from parsers.score_load_error import ScoreLoadError
from parsers.ug_reader import UgFileReader
from models.score_formats import family_for_path
from persistence import app_settings

_GENERIC_LOAD_ERROR = (
    "This score could not be opened. It may be corrupt or in a format Recall "
    "Score does not support. See the log file for details."
)


class ScoreLoadThread(QThread):
    """Runs MusicXMLReader.load() off the UI thread.

    A synchronous load blocks on several ElementTree passes plus
    music21.converter.parse (~460ms) - for a screen-reader-first app that is
    silence with no cue, not just a frozen window. loaded/failed are
    Qt-queued back onto whichever thread owns this QThread's parent.
    """

    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        # S4: family_for_path owns the extension lists (models/score_formats.py);
        # MusicXML is the default/catch-all for an unrecognised extension.
        family = family_for_path(self.file_path)
        try:
            if family == "midi":
                data = MidiReader(self.file_path).load()
            elif family == "gp":
                data = GpReader(self.file_path).load()
            elif family == "ug":
                data = UgFileReader(self.file_path).load()
            elif family == "musescore":
                data = MuseScoreReader(
                    self.file_path,
                    configured_exe=app_settings.load().musescore_path,
                ).load()
            else:
                data = MusicXMLReader(self.file_path).load()
        except ScoreLoadError as e:
            # A failure we can explain in plain words - the message is shown
            # verbatim in the accessible error dialog and spoken by the
            # screen reader. Still log the full chain for diagnosis.
            print(f"[ERROR] Score load failed: {e.user_message}")
            traceback.print_exc()
            self.failed.emit(e.user_message)
            return
        except Exception:
            # An unexpected bug, not a bad file - log everything, tell the
            # user something generic rather than a raw traceback.
            print("[ERROR] Unexpected error loading score:")
            traceback.print_exc()
            self.failed.emit(_GENERIC_LOAD_ERROR)
            return
        self.loaded.emit(data)
