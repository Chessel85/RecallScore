"""web/app/js/keymap.js: the page's single key table must stay strict JSON
between its markers, so Python can read it (task 2.7's desktop drift guard
builds on this)."""
import json
import re
from pathlib import Path

KEYMAP_JS = Path(__file__).resolve().parents[2] / "web" / "app" / "js" / "keymap.js"
SCOPES = {"region1", "region2", "region3", "region4", "region5", "region6", "list", "cycle", "global"}
FIELDS = {"id", "keys", "scope", "label", "desktopAction", "difference"}


def load_keymap():
    text = KEYMAP_JS.read_text(encoding="utf-8")
    match = re.search(r"/\* KEYMAP-BEGIN \*/(.*?)/\* KEYMAP-END \*/", text, re.S)
    assert match, "keymap.js lost its KEYMAP markers"
    return json.loads(match.group(1))


def test_rows_are_well_formed():
    rows = load_keymap()
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids))
    for row in rows:
        assert set(row) == FIELDS, row["id"]
        assert row["scope"] in SCOPES, row["id"]
        assert row["keys"] and all(isinstance(k, str) and k for k in row["keys"]), row["id"]


def test_scopes_match_the_dispatcher():
    text = KEYMAP_JS.read_text(encoding="utf-8")
    listed = re.search(r"export const SCOPES = (\[.*?\]);", text).group(1)
    assert set(json.loads(listed)) == SCOPES


def test_no_key_is_bound_twice_in_one_scope():
    seen = {}
    for row in load_keymap():
        for key in row["keys"]:
            other = seen.setdefault((row["scope"], key), row["id"])
            assert other == row["id"], f"{key} in {row['scope']}: {other} and {row['id']}"


def test_escape_is_never_bound():
    """NVDA uses Escape to leave focus mode; the page may never see it."""
    for row in load_keymap():
        assert not any(k.split("+")[-1] == "Escape" for k in row["keys"]), row["id"]
