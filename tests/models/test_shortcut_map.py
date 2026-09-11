# tests/models/test_shortcut_map.py
"""Pure-logic tests for models/shortcut_map.py (UserPlans/KeyboardShortcuts.md)
- stdlib only, no Qt, no fixtures needed."""
from models.shortcut_map import ShortcutMap, with_twins


# --- with_twins ----------------------------------------------------------

def test_with_twins_expands_alt_return_to_both_enter_and_return():
    assert with_twins("Alt+Return") == ("Alt+Enter", "Alt+Return")


def test_with_twins_expands_alt_enter_to_both_enter_and_return():
    assert with_twins("Alt+Enter") == ("Alt+Enter", "Alt+Return")


def test_with_twins_expands_bare_return_and_enter():
    assert with_twins("Return") == ("Enter", "Return")
    assert with_twins("Enter") == ("Enter", "Return")


def test_with_twins_leaves_other_sequences_alone():
    assert with_twins("Ctrl+Shift+K") == ("Ctrl+Shift+K",)
    assert with_twins("Ctrl++") == ("Ctrl++",)


# --- bindings() ------------------------------------------------------------

def test_bindings_pass_through_defaults_with_no_overrides():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",), "b": ("Ctrl+B",)})
    assert m.bindings() == {"a": ("Ctrl+A",), "b": ("Ctrl+B",)}


def test_bindings_apply_an_override_in_place_of_the_default():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",)}, overrides={"a": "Ctrl+Z"})
    assert m.bindings() == {"a": ("Ctrl+Z",)}


def test_bindings_empty_override_means_no_shortcut():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",)}, overrides={"a": ""})
    assert m.bindings() == {"a": ()}


def test_bindings_default_holder_loses_a_key_an_override_has_claimed():
    """A future-version default colliding with an existing user override:
    the override wins the key and the original default-holder gets ()."""
    m = ShortcutMap(
        defaults={"a": ("Ctrl+K",), "b": ("Ctrl+K",)},
        overrides={"a": "Ctrl+K"},
    )
    bindings = m.bindings()
    assert bindings["a"] == ("Ctrl+K",)
    assert bindings["b"] == ()


def test_bindings_enter_return_twins_bind_both():
    m = ShortcutMap(defaults={"a": ()}, overrides={"a": "Alt+Return"})
    assert m.bindings()["a"] == ("Alt+Enter", "Alt+Return")


def test_bindings_unknown_override_ids_are_ignored():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",)}, overrides={"ghost": "Ctrl+Z"})
    assert m.bindings() == {"a": ("Ctrl+A",)}


# --- owner_of ----------------------------------------------------------

def test_owner_of_finds_the_action_holding_a_sequence():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",), "b": ("Ctrl+B",)})
    assert m.owner_of("Ctrl+B") == "b"
    assert m.owner_of("Ctrl+Z") is None


def test_owner_of_matches_any_twin():
    m = ShortcutMap(defaults={"a": ()}, overrides={"a": "Alt+Return"})
    assert m.owner_of("Alt+Enter") == "a"
    assert m.owner_of("Alt+Return") == "a"


# --- assign --------------------------------------------------------------

def test_assign_displaces_the_current_owner():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",), "b": ("Ctrl+B",)})
    displaced = m.assign("a", "Ctrl+B")
    assert displaced == "b"
    bindings = m.bindings()
    assert bindings["a"] == ("Ctrl+B",)
    assert bindings["b"] == ()


def test_assign_to_an_unowned_sequence_displaces_nobody():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",)})
    assert m.assign("a", "Ctrl+Z") is None
    assert m.bindings()["a"] == ("Ctrl+Z",)


def test_assign_an_actions_own_current_sequence_is_a_no_op():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",)})
    assert m.assign("a", "Ctrl+A") is None
    assert m.overrides == {}


def test_assign_dropping_an_override_that_restores_the_default_normalizes_away():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",), "b": ("Ctrl+B",)})
    m.assign("a", "Ctrl+Z")
    assert m.overrides == {"a": "Ctrl+Z"}
    m.assign("a", "Ctrl+A")
    assert m.overrides == {}


# --- clear / restore_defaults ------------------------------------------

def test_clear_removes_the_shortcut():
    m = ShortcutMap(defaults={"a": ("Ctrl+A",)})
    m.clear("a")
    assert m.bindings()["a"] == ()
    assert m.overrides == {"a": ""}


def test_clear_on_an_action_with_no_default_normalizes_to_no_override():
    m = ShortcutMap(defaults={"a": ()})
    m.clear("a")
    assert m.overrides == {}


def test_restore_defaults_clears_every_override():
    m = ShortcutMap(
        defaults={"a": ("Ctrl+A",), "b": ("Ctrl+B",)},
        overrides={"a": "Ctrl+Z", "b": ""},
    )
    m.restore_defaults()
    assert m.overrides == {}
    assert m.bindings() == {"a": ("Ctrl+A",), "b": ("Ctrl+B",)}
