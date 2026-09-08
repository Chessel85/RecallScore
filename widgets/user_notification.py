# widgets/user_notification.py
"""notify_user(level, message) - the app's user-visible surface for an error
or warning that happens *outside* score loading (which has its own
MainWindow._show_load_error dialog, Ref 25 / NFR-06).

Everything else - a failed .rsc save, a missing SoundFont, a missing user
guide - used to be a bare ``print`` that, in a frozen build, goes to a log
file the user never opens. This routes those to something a screen-reader
user actually perceives:

* ``level="error"`` posts a modal QMessageBox. It takes focus and is read
  aloud by NVDA and VoiceOver unaided, and it blocks until acknowledged -
  right for "the thing you asked for did not happen".
* ``level="warning"`` goes through accessible_announcer.announce against the
  active window: a screen-reader side channel that neither steals focus nor
  blocks, for a non-fatal degradation the user should still hear about.

The message is always printed too, so the log keeps every diagnostic. Both
paths fall back to print-only when there is no QApplication yet or no window
to announce against (early startup, headless test run), so this is safe to
call from anywhere on the main thread.
"""
from PySide6.QtWidgets import QApplication, QMessageBox

from widgets.accessible_announcer import announce

_VALID_LEVELS = ("error", "warning")


def notify_user(level: str, message: str) -> None:
    assert level in _VALID_LEVELS, f"level must be one of {_VALID_LEVELS}, got {level!r}"

    print(f"[{'ERROR' if level == 'error' else 'WARN'}] {message}")

    if QApplication.instance() is None:
        return

    if level == "error":
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Recall Score")
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
        return

    target = QApplication.activeWindow()
    if target is not None:
        announce(target, message)
