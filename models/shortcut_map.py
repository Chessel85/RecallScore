# models/shortcut_map.py
"""Keyboard shortcut rebinding (UserPlans/KeyboardShortcuts.md): pure logic
on canonical QKeySequence PortableText strings (e.g. "Ctrl+Shift+K"), so it's
trivially unit-testable and stays out of controllers/shortcut_controller.py,
which is the only place that touches Qt.

CLAUDE.md invariant 8 ("two copies of the same fact will diverge") is why
this module never stores default shortcuts itself. ShortcutMap.defaults is a
snapshot the caller takes of whatever MenuBuilder/MainWindow.setup_shortcuts
actually built - the single source of the factory defaults. overrides holds
only the user's differences from that snapshot: an action id missing from
overrides uses its defaults unchanged, "" means "no shortcut", and any other
string is the one sequence in use. Keeping only the diff means a changed
default in a future version still reaches a user who never touched that
action.

stdlib-only, like every other models/ module - see
test_models_package_does_not_import_qt.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


def with_twins(seq: str) -> Tuple[str, ...]:
    """'Alt+Return' or 'Alt+Enter' -> ('Alt+Enter', 'Alt+Return'); a bare
    'Return'/'Enter' likewise; anything else -> (seq,). Enter first, matching
    the existing Voice Control order (menu_builder.py) so the menu shows the
    same text.

    Qt treats numpad Enter and the main Return key as different keys, so
    binding one alone would silently miss the other. Suffix test only (seq
    == 'Return' or seq.endswith('+Return')) - never split on '+', which is
    itself a valid key ('Ctrl++')."""
    if seq == "Return":
        return ("Enter", "Return")
    if seq == "Enter":
        return ("Enter", "Return")
    if seq.endswith("+Return"):
        return (seq[: -len("Return")] + "Enter", seq)
    if seq.endswith("+Enter"):
        return (seq, seq[: -len("Enter")] + "Return")
    return (seq,)


@dataclass
class ShortcutMap:
    """defaults: action id -> default sequences, in display order (a tuple
    because an action such as voice_control has more than one, the Enter/
    Return twins). overrides: action id -> a single sequence, or "" for no
    shortcut. An id absent from overrides is unmodified."""

    defaults: Dict[str, Tuple[str, ...]]
    overrides: Dict[str, str] = field(default_factory=dict)

    def bindings(self) -> Dict[str, Tuple[str, ...]]:
        """Effective shortcuts for every action, in defaults order.

        Walk ids in defaults order. An id with a non-empty override claims
        with_twins(override) first; if two overrides claim the same
        sequence (only possible in a hand-edited settings file), the later
        one wins and the earlier gets (). An id with override "" gets ().
        An id with no override gets its defaults minus any sequence an
        override elsewhere has already claimed - that settles a future
        default colliding with an existing user override in the user's
        favour: the override wins the key and the default-holder loses it."""
        claimed: Dict[str, str] = {}
        result: Dict[str, Tuple[str, ...]] = {}
        for action_id in self.defaults:
            override = self.overrides.get(action_id)
            if override:
                for seq in with_twins(override):
                    claimed.setdefault(seq, action_id)
        for action_id in self.defaults:
            override = self.overrides.get(action_id)
            if override is not None:
                if override == "":
                    result[action_id] = ()
                else:
                    seqs = with_twins(override)
                    result[action_id] = tuple(
                        s for s in seqs if claimed.get(s) == action_id
                    )
            else:
                result[action_id] = tuple(
                    s
                    for s in self.defaults[action_id]
                    if claimed.get(s, action_id) == action_id
                )
        return result

    def owner_of(self, seq: str) -> Optional[str]:
        """The action id currently bound to seq (matching any twin), or
        None."""
        for action_id, seqs in self.bindings().items():
            if seq in seqs:
                return action_id
        return None

    def assign(self, action_id: str, seq: str) -> Optional[str]:
        """Bind seq to action_id, displacing whichever action currently owns
        it (if any). Returns the displaced action id, or None if seq was
        unowned or already belonged to action_id."""
        displaced = self.owner_of(seq)
        if displaced == action_id:
            return None
        self.overrides[action_id] = seq
        if displaced is not None:
            self.overrides[displaced] = ""
        self._normalize()
        return displaced

    def clear(self, action_id: str) -> None:
        self.overrides[action_id] = ""
        self._normalize()

    def restore_defaults(self) -> None:
        self.overrides.clear()

    def _normalize(self) -> None:
        """Drop any override whose effective value equals its default, so a
        round trip back to the factory setting doesn't leave a no-op entry
        in the saved settings file."""
        for action_id in list(self.overrides.keys()):
            override = self.overrides[action_id]
            default = self.defaults.get(action_id, ())
            if override == "":
                if default == ():
                    del self.overrides[action_id]
            elif with_twins(override) == default:
                del self.overrides[action_id]
