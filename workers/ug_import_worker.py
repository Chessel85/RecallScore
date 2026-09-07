# workers/ug_import_worker.py
import traceback

from PySide6.QtCore import QThread, Signal

from parsers.score_load_error import ScoreLoadError
from parsers.ug_reader import UgReader

_GENERIC_IMPORT_ERROR = (
    "The Ultimate Guitar tab could not be imported. See the log file for "
    "details."
)


class UgImportThread(QThread):
    """Runs UgReader.load() off the UI thread - the URL counterpart of
    ScoreLoadThread. A network fetch plus JSON parse is no faster than a
    local file load's ~460ms music21 pass, and can be much slower (or hang)
    on a bad connection, so this stays off the UI thread for the same
    reason: silence with no cue is worse than a frozen window for a
    screen-reader-first app.

    Same loaded/failed Signal contract as ScoreLoadThread, so
    ScoreSession.import_from_url can share _on_loaded/_on_thread_finished
    and main_window.py's _on_score_loaded/_on_score_load_failed wiring
    needs no changes at all.
    """

    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            data = UgReader(self.url).load()
        except (ScoreLoadError, ValueError) as e:
            # read_ug_source raises ValueError with user-readable text for
            # every expected failure (bad URL, unreachable, unsupported tab
            # type, no chord content). Show it verbatim; log the full chain.
            message = getattr(e, "user_message", None) or str(e)
            print(f"[ERROR] Ultimate Guitar import failed: {message}")
            traceback.print_exc()
            self.failed.emit(message)
            return
        except Exception:
            print("[ERROR] Unexpected error importing Ultimate Guitar tab:")
            traceback.print_exc()
            self.failed.emit(_GENERIC_IMPORT_ERROR)
            return
        self.loaded.emit(data)
