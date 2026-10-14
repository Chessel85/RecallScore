"""Drift guard (task 2.7): a web command that claims a desktop equivalent
must use the desktop's key, or say in `difference` why it deliberately does
not. Builds the real desktop menus offscreen via the `window` fixture."""
import dataclasses

import pytest
from PySide6.QtGui import QKeySequence

from tests.web.test_keymap_table import load_keymap
from widgets.menu_builder import Actions

CLAIMING = [row for row in load_keymap() if row["desktopAction"]]


def _desktop_keys(action) -> set:
    """The action's shortcuts in the web's key names (Return is Enter)."""
    keys = set()
    for sequence in action.shortcuts():
        text = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        keys.add(text.replace("Return", "Enter"))
    return keys


def test_every_claimed_action_exists_on_the_desktop():
    fields = {field.name for field in dataclasses.fields(Actions)}
    for row in CLAIMING:
        assert row["desktopAction"] in fields, f"{row['id']}: no desktop action {row['desktopAction']!r}"


@pytest.mark.parametrize("row", [r for r in CLAIMING if not r["difference"]], ids=lambda r: r["id"])
def test_web_keys_match_the_desktops(window, row):
    action = getattr(window._actions, row["desktopAction"])
    assert action is not None, row["desktopAction"]
    desktop = _desktop_keys(action)
    assert set(row["keys"]) <= desktop, (
        f"{row['id']}: web {row['keys']} is not among the desktop's {sorted(desktop)}. "
        "Match the key, or explain the difference in the row's `difference` field."
    )


@pytest.mark.parametrize("row", [r for r in load_keymap() if r["difference"]], ids=lambda r: r["id"])
def test_a_deliberate_difference_is_a_real_sentence(row):
    assert len(row["difference"].split()) >= 4, row["id"]
