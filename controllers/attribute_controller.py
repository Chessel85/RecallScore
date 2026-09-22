# controllers/attribute_controller.py
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMenu

from models.vocabulary import attribute_label
from widgets.region2_manager import voice_tuples_for_node
from widgets.user_notification import notify_user


class AttributeController:
    """Ref 15 AC4's attribute-display system: Region 4's add/remove context
    menu (which attributes show against a note) and the reorder dialog
    (what order they render in).

    Both halves write to MusicData and then ask the presenter to re-render,
    so the two regions can never disagree about which attributes exist or
    in what sequence.

    Dialog construction stays in MainWindow, as it does for every other
    dialog - this owns the logic behind it (which attributes are in scope,
    what a move does), not its lifecycle.
    """

    def __init__(self, session, presenter, window):
        self.session = session
        self.presenter = presenter
        # Needed as the parent for QMenu/QDialog, and for focusWidget().
        self._window = window

    @property
    def music_data(self):
        return self.session.music_data

    # --- shared scope-menu building ------------------------------------

    @staticmethod
    def _scope_action_labels(already_present: bool) -> list:
        """(scope, label) pairs for the four fan-out scopes, worded for
        either direction of the toggle. D-15: "stave" is deliberately not
        dialect-translated here. Shared by Region 4's context menu and the
        Reorder Attributes dialog's Add/Remove button, so the two can't
        drift onto different wording for the same action."""
        if already_present:
            return [
                ("voice", "Remove for notes in current voice"),
                ("stave", "Remove for notes in current stave"),
                ("part", "Remove for notes in current part"),
                ("score", "Remove for notes in the whole score"),
            ]
        return [
            ("voice", "Add to notes for this voice"),
            ("stave", "Add to notes in same stave"),
            ("part", "Add to notes in the same part"),
            ("score", "Add to notes in the whole score"),
        ]

    # Broader-or-equal-to-node-level check for the Reorder Attributes
    # dialog's Add/Remove button (_filter_scopes_for_node_level below) -
    # Region2Node.node_type spells the middle level "staff", the attribute-
    # scope vocabulary spells it "stave" (D-15's own dialect-free choice);
    # these two dicts are the one place that difference has to be bridged.
    _SCOPE_LEVEL = {"voice": 0, "stave": 1, "part": 2, "score": 3}
    _NODE_TYPE_LEVEL = {"voice": 0, "staff": 1, "part": 2}

    def _filter_scopes_for_node_level(self, scopes: list, node_type: str) -> list:
        """Reported: the Reorder Attributes dialog can be opened at any
        Region 2 level (voice/staff/part), but every scope was always
        offered regardless - "Add to notes for this voice" from a STAVE-
        level dialog with two voices underneath is genuinely ambiguous
        (which voice?). Only scopes at or broader than the dialog's own
        node level are unambiguous: a stave-level dialog offers stave/
        part/score; a part-level dialog offers only part/score. A voice-
        level dialog (the common case) is unaffected - every scope is
        still offered, same as before this fix."""
        floor = self._NODE_TYPE_LEVEL.get(node_type, 0)
        return [(scope, label) for scope, label in scopes if self._SCOPE_LEVEL[scope] >= floor]

    def _filter_scopes_for_part(self, scopes: list, part_id: str) -> list:
        """Reported: a part with no real stave/voice concept underneath it
        (a MIDI track, a pure Ultimate Guitar import, or one of the
        synthetic Chords/Lyrics parts a MusicXML file's own <harmony>/
        <lyric> markup can add - see MusicData.collapsed_part_ids, the
        same check Region 2 uses to decide whether to show a fake
        staff/voice tree underneath that part) offered "current voice"/
        "current stave" scopes that acted on exactly the same notes as
        "current part" - not wrong, just redundant menu clutter with
        nothing real behind it. Those two scopes are dropped for such a
        part; "part" and "score" still apply normally."""
        collapsed = self.music_data.collapsed_part_ids
        if collapsed is True or part_id in collapsed:
            return [(scope, label) for scope, label in scopes if scope not in ("voice", "stave")]
        return scopes

    # --- Region 4 context menu ---------------------------------------

    def menu_actions(self, row: int) -> list:
        """(label, callback) pairs for the context menu, empty if there's
        nothing to act on. Split from show_menu so it's testable without
        driving a blocking QMenu.exec()."""
        if not self.music_data:
            return []

        selected_indices = self.presenter.selected_region_3_indices()
        targets = self.music_data.get_region_4_row_targets(selected_indices)
        if not (0 <= row < len(targets)):
            return []

        attribute_key, anchor_note = targets[row]
        selected_notes = self.music_data.notes_for_indices(selected_indices)
        already_present = self.music_data.note_has_display_attribute(anchor_note, attribute_key)

        scopes = self._scope_action_labels(already_present)
        scopes = self._filter_scopes_for_part(scopes, anchor_note.part_id)

        return [
            (
                label,
                # checked=False absorbs the bool QAction.triggered passes
                # to any slot that accepts a positional arg. Without it that
                # bool lands in `scope`'s slot instead, silently replacing
                # e.g. "voice" with False.
                lambda checked=False, scope=scope: self.apply_change(
                    attribute_key, scope, selected_notes, add=not already_present
                ),
            )
            for scope, label in scopes
        ]

    def build_menu(self, row: int):
        """Builds the wired QMenu without exec()ing it, so tests can inspect
        it without a blocking modal loop. The exec() call must be kept OUT
        of the tested method rather than monkeypatched around: QMenu.exec is
        Shiboken-wrapped and overloaded, and patching it hangs indefinitely
        rather than raising."""
        actions = self.menu_actions(row)
        if not actions:
            return None
        menu = QMenu(self._window)
        for label, callback in actions:
            menu.addAction(label).triggered.connect(callback)
        return menu

    def show_menu(self, row: int, global_pos) -> None:
        """Called by Region4ListWidget on right-click or the Menu key.

        Reported: NVDA announces nothing when the menu first appears - the
        screen reader still treats Region 4's list item as focused (NVDA+Tab
        confirms this) until an arrow key is pressed, costing the user one
        keypress just to hear the first item.

        A prior attempt highlighted the first action via exec(at=...), with
        or without a synthetic Key_Down, both applied *before* the menu
        became visible - NVDA still read "blank". This one instead defers
        setActiveAction() to a zero-delay QTimer queued just before exec()
        blocks, so it actually fires after the menu's own event loop has
        started and the menu is on screen - the same ordering a real arrow
        press has, just automatic. QMenu.exec() pumps the event loop it
        blocks in, so the queued timer still runs."""
        menu = self.build_menu(row)
        if menu is None:
            return
        actions = menu.actions()
        if actions:
            QTimer.singleShot(0, lambda: menu.setActiveAction(actions[0]))
        menu.exec(global_pos)
        self.restore_focus_after_menu(row)

    def restore_focus_after_menu(self, row: int) -> None:
        """Restores the row the menu was opened from, whether an action
        fired or Escape cancelled.

        Needed because QAction.triggered fires BEFORE exec() returns, so the
        rebuild the callback causes resets the list's current row while the
        menu is still up. (Escape, triggering no callback and no rebuild,
        lands correctly without this; Enter does not.)"""
        region_4 = self.presenter.region_4
        if 0 <= row < region_4.count():
            region_4.setCurrentRow(row)
        region_4.setFocus()

    def apply_change(self, attribute_key: str, scope: str, notes: list, add: bool) -> None:
        self.music_data.set_display_attribute(attribute_key, scope, notes, add)
        self.presenter.refresh_region_3_labels()

    # --- Attribute Management dialog (order + hide, always part-scoped) --
    # UserPlans/hideAttributes.md: "The Hide and reorder dialogue needs to
    # be part specific... Attribute ordering is always per part. never
    # score, stave or voice level." Whatever Region 2 node was current when
    # the dialog opens, it is resolved to that node's own part once
    # (scope_node/_show_attribute_order_dialog) and everything below - the
    # list, Up/Down, Hide, Hide for All - acts at that part's granularity.
    # Add/&Remove keeps its own node-based scope fan-out (order_menu_actions
    # below), untouched by this collapse.

    def order_pairs_for_part(self, part_id: str) -> list:
        """(attribute_key, label, elevated, hidden_state) rows in current
        order, for every attribute present anywhere in `part_id`. Labels
        arrive already dialect-translated so the dialog itself stays
        dialect-agnostic. `elevated` is part-local (any of the four
        add/remove scopes, anywhere under this part - user decision:
        "because the dialogue is scoped to the part, it must prefix with an
        asterisk regardless of the level"). `hidden_state` is "all" / "part"
        / "visible" - see AttributeOrderDialog._row_text."""
        md = self.music_data
        keys = md.attribute_keys_for_part(part_id)
        rows = []
        for key in keys:
            rows.append((
                key,
                attribute_label(key, md.uk_terms),
                md.attribute_elevated_for_part(key, part_id),
                self._hidden_state(part_id, key),
            ))
        return rows

    def _hidden_state(self, part_id: str, attribute_key: str) -> str:
        md = self.music_data
        if attribute_key in md.hidden_attributes_for_all:
            return "all"
        if attribute_key in md.hidden_attributes_by_part.get(part_id, set()):
            return "part"
        return "visible"

    def _part_name(self, part_id: str) -> str:
        for p in self.music_data.parts_info:
            if p.part_id == part_id:
                return p.name
        return part_id

    def part_scope_description(self, part_id: str) -> str:
        """The Attribute Management dialog's own scope label - just the
        part's name, since the dialog is always part-scoped regardless of
        which Region 2 node (voice/stave/part) it was opened from."""
        return self._part_name(part_id)

    def scope_node(self):
        """The Region 2 node the Attribute Management dialog resolves to a
        part from, or None."""
        if not self.music_data:
            return None
        return self.presenter.region_2.current_node()

    def current_region_4_attribute_key(self):
        """The attribute_key of Region 4's current row (its own current
        item, which QListWidget keeps regardless of which region has
        keyboard focus - so this reads as "last selected" too), or None if
        Region 4 has no rows. Lets the reorder dialog open with that same
        attribute already selected instead of nothing; AttributeOrderDialog
        falls back to its first row itself when the key doesn't turn up in
        this dialog's own scope."""
        item = self.presenter.region_4.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def apply_order(self, part_id: str, new_order: list) -> None:
        """Commits the Attribute Management dialog's staged order (read via
        dialog.ordered_keys() after exec() returns Accepted) into `part_id`'s
        own live order and pushes the result to Region 3/4. `within` is
        recomputed the same way order_pairs_for_part did when the dialog
        was opened, so the commit lands on the same subset of slots."""
        if not self.music_data:
            return
        within = self.music_data.attribute_keys_for_part(part_id)
        self.music_data.set_attribute_order_within_part(part_id, new_order, within)
        self.presenter.refresh_region_3_labels()
        self.presenter.on_region_3_selection_changed()

    # --- Hide / Hide for All (Attribute Management) --------------------

    def toggle_hidden_for_part(self, dialog, part_id: str, attribute_key: str) -> None:
        """&Hide/Un&hide button: toggles `attribute_key`'s hidden-for-
        `part_id` state, immediate-apply like Add/Remove. Direction (hide
        vs unhide) is read off MusicData's own live state, not the
        dialog's button label, so this can never drift out of sync with it.
        A blocked hide (elevated in this part, or already hidden for all -
        though the dialog disables the button outright for that second
        case) pops the confirmed message and leaves the model untouched."""
        md = self.music_data
        if md is None:
            return
        currently_hidden = attribute_key in md.hidden_attributes_by_part.get(part_id, set())
        if currently_hidden:
            md.set_attribute_hidden_for_part(attribute_key, part_id, False)
        elif not md.set_attribute_hidden_for_part(attribute_key, part_id, True):
            label = attribute_label(attribute_key, md.uk_terms)
            notify_user(
                "error",
                f"{label} can't be hidden while it's shown in the note list.",
            )
            return
        self._refresh_dialog_row(dialog, part_id, attribute_key)
        self.presenter.refresh_region_3_labels()

    def toggle_hidden_for_all(self, dialog, part_id: str, attribute_key: str) -> None:
        """Hide for &All/Unhide for &All button: toggles `attribute_key`'s
        score-wide hidden state - see toggle_hidden_for_part, same shape. A
        blocked hide names every part it's elevated in."""
        md = self.music_data
        if md is None:
            return
        currently_hidden = attribute_key in md.hidden_attributes_for_all
        if currently_hidden:
            md.set_attribute_hidden_for_all(attribute_key, False)
        elif not md.set_attribute_hidden_for_all(attribute_key, True):
            label = attribute_label(attribute_key, md.uk_terms)
            part_names = ", ".join(
                self._part_name(p) for p in md.attribute_elevated_parts(attribute_key)
            )
            notify_user(
                "error",
                f"{label} can't be hidden for the whole score while it's "
                f"shown in the note list for: {part_names}.",
            )
            return
        self._refresh_dialog_row(dialog, part_id, attribute_key)
        self.presenter.refresh_region_3_labels()

    def _refresh_dialog_row(self, dialog, part_id: str, attribute_key: str) -> None:
        elevated = self.music_data.attribute_elevated_for_part(attribute_key, part_id)
        dialog.set_row_state(attribute_key, elevated, self._hidden_state(part_id, attribute_key))

    # --- reorder dialog's Add/Remove button ----------------------------
    # User-requested: Reorder Attributes already lists every attribute
    # present in the dialog's scope regardless of on/off state (below), so
    # a user who spots a rare one there had no way to actually switch it
    # on without first finding a note that already shows it in Region 4.
    # Reuses Region 4's own scope wording/logic (_scope_action_labels/
    # _filter_scopes_for_part above) so the two can't drift onto different
    # behaviour for the same action - the only real difference is that this
    # one fans out from the dialog's own Region 2 node position instead of
    # a selected note, since the dialog has no note selection of its own.

    def order_menu_actions(self, node, attribute_key: str) -> list:
        """(label, callback) pairs for the Add/Remove button's dropdown,
        empty if there's nothing to act on. "Already present" is read off
        one representative voice under `node` (the lowest-sorted one) -
        node is usually a single voice already; for a wider staff/part
        selection this is the same "one anchor decides the wording"
        simplification note_has_display_attribute makes for a chord."""
        if not self.music_data:
            return []
        voice_tuples = voice_tuples_for_node(node)
        if not voice_tuples:
            return []
        part_id, staff, voice = sorted(voice_tuples)[0]
        already_present = self.music_data.display_attribute_present_for_voice(
            attribute_key, part_id, staff, voice
        )

        scopes = self._scope_action_labels(already_present)
        scopes = self._filter_scopes_for_node_level(scopes, node.node_type)
        scopes = self._filter_scopes_for_part(scopes, part_id)

        return [
            (
                label,
                lambda checked=False, scope=scope: self.apply_order_change(
                    attribute_key, scope, part_id, staff, voice, add=not already_present
                ),
            )
            for scope, label in scopes
        ]

    def show_order_menu(self, dialog, node, attribute_key: str) -> None:
        """Called by MainWindow on the Reorder Attributes dialog's Add/
        Remove button. The dialog stays open throughout - toggling on/off
        changes neither which attributes are listed (presence-based) nor
        their order, so unlike an OK-committed Up/Down move there's nothing
        to refresh in the dialog itself, only Region 3."""
        actions = self.order_menu_actions(node, attribute_key)
        if not actions:
            return
        menu = QMenu(self._window)
        for label, callback in actions:
            menu.addAction(label).triggered.connect(callback)
        button = dialog.add_remove_button
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        dialog.attribute_list.setFocus()

    def apply_order_change(
        self, attribute_key: str, scope: str, part_id: str, staff: int, voice: int, add: bool
    ) -> None:
        self.music_data.set_display_attribute_for_voice(attribute_key, scope, part_id, staff, voice, add)
        self.presenter.refresh_region_3_labels()
