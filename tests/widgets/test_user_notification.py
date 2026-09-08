# tests/widgets/test_user_notification.py
"""notify_user(level, message) - the single user-visible error/warning
surface outside score loading (CR8thSept2.txt T1)."""
import pytest
from PySide6.QtWidgets import QMessageBox, QWidget

from widgets import user_notification
from widgets.user_notification import notify_user


class _FakeBox:
    instances = []
    Icon = QMessageBox.Icon
    StandardButton = QMessageBox.StandardButton

    def __init__(self):
        self.text = None
        self.exec_called = False
        _FakeBox.instances.append(self)

    def setIcon(self, *_):
        pass

    def setWindowTitle(self, *_):
        pass

    def setStandardButtons(self, *_):
        pass

    def setText(self, text):
        self.text = text

    def exec(self):
        self.exec_called = True


@pytest.fixture(autouse=True)
def _reset_fake_box():
    _FakeBox.instances = []


def test_error_posts_a_modal_message_box(monkeypatch, capsys, qtbot):
    monkeypatch.setattr(user_notification, "QMessageBox", _FakeBox)

    notify_user("error", "disk full")

    assert len(_FakeBox.instances) == 1
    box = _FakeBox.instances[0]
    assert box.exec_called
    assert "disk full" in box.text
    assert "[ERROR] disk full" in capsys.readouterr().out


def test_warning_announces_against_the_active_window_without_a_box(monkeypatch, capsys, qtbot):
    monkeypatch.setattr(user_notification, "QMessageBox", _FakeBox)
    win = QWidget()
    qtbot.addWidget(win)
    monkeypatch.setattr(user_notification.QApplication, "activeWindow", staticmethod(lambda: win))

    seen = []
    monkeypatch.setattr(user_notification, "announce", lambda w, m: seen.append((w, m)))

    notify_user("warning", "sounds unavailable")

    assert seen == [(win, "sounds unavailable")]
    assert _FakeBox.instances == []  # a warning never steals focus
    assert "[WARN] sounds unavailable" in capsys.readouterr().out


def test_warning_with_no_active_window_is_print_only(monkeypatch, capsys, qtbot):
    monkeypatch.setattr(user_notification.QApplication, "activeWindow", staticmethod(lambda: None))
    monkeypatch.setattr(user_notification, "announce", lambda w, m: pytest.fail("must not announce"))

    notify_user("warning", "nobody listening")

    assert "[WARN] nobody listening" in capsys.readouterr().out


def test_unknown_level_is_rejected():
    with pytest.raises(AssertionError):
        notify_user("info", "nope")
