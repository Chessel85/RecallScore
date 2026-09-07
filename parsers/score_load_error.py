# parsers/score_load_error.py
"""One typed exception for "this file cannot be opened as a score".

Raised by the readers/pre-checks whenever a load fails for a reason worth
telling the user about in plain words - a missing or empty file, a file whose
contents do not match its extension, or a parse that cannot produce a usable
score. The load worker (workers/score_load_worker.py) catches it specifically
and forwards `user_message` to the accessible error dialog; anything that is
NOT a ScoreLoadError is treated as an unexpected bug - full traceback to the
log, generic message to the user.

`user_message` must stay short and plain: it is spoken aloud by a screen
reader. No tracebacks, no stack frames; a file path only when it is the point
(e.g. "File not found").
"""
from typing import Optional


class ScoreLoadError(Exception):
    def __init__(self, user_message: str, *, cause: Optional[BaseException] = None):
        super().__init__(user_message)
        self.user_message = user_message
        if cause is not None:
            self.__cause__ = cause
