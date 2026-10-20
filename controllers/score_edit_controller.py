# controllers/score_edit_controller.py
"""S5: applying a user's edits to the loaded score.

The counterpart of PlaybackController for score DATA rather than transport:
the Instruments dialog's name/instrument/percussion overrides (S5), the Key
Signature dialog's whole-piece override (S6), and Reorder Parts. Each of
these arrived as a block of merging-and-refreshing logic inside
MainWindow's own _show_*_dialog method, which contradicted the shell's
stated job (build widgets, own controllers, wire them together).

The split this keeps: MainWindow still CONSTRUCTS each dialog and calls
exec() - tests monkeypatch main_window.<DialogClass>, and dialog lifetime
is a view concern - then hands the result here. Controllers own the logic
behind a dialog, not its lifecycle.

What each edit does to MusicData is models/score_edits.py, shared with the
web bridge; this controller adds the desktop's refreshes.

Touches no widgets itself. Region 2's labels and row order are updated
through RegionPresenter, which stays the only controller that talks to
them; that is also why every method here ends by asking the presenter to
refresh rather than poking regions 3/4/5 directly.

Reads session.music_data per call and never caches it - MusicData is
replaced wholesale on every load (see ScoreSession).
"""
from typing import Dict, List, Optional, Tuple

from models import score_edits


class ScoreEditController:
    def __init__(self, session, presenter):
        self.session = session
        self.presenter = presenter

    @property
    def music_data(self):
        return self.session.music_data

    # --- Instruments dialog (S5, wishlist #8) --------------------------

    def instrument_rows(self) -> List[Tuple[str, str, int]]:
        return score_edits.instrument_rows(self.music_data)

    def percussion_part_ids(self) -> List[str]:
        return score_edits.percussion_part_ids(self.music_data)

    def percussion_toggle_part_ids(self) -> List[str]:
        return score_edits.percussion_toggle_part_ids(self.music_data)

    def percussion_rows(self) -> Dict[str, list]:
        return score_edits.percussion_rows(self.music_data)

    def apply_instrument_overrides(
        self,
        name_overrides: Dict[str, str],
        program_overrides: Dict[str, int],
        item_name_overrides: Dict[Tuple[str, int], str],
        item_sound_overrides: Dict[Tuple[str, int], int],
        auto_correct_enabled: bool,
        part_percussion_changes: Optional[Dict[str, bool]] = None,
    ) -> bool:
        """Apply the Instruments dialog's five results. Returns whether
        anything actually changed, so a dialog dismissed with no edits
        doesn't trigger a pointless rebuild.

        Region 2's part and voice labels are updated IN PLACE
        (rename_part/rename_voice), never via load_score_structure - that
        resets every node back to enabled, discarding whatever mute/solo
        toggles and expand state the user had set.
        """
        music_data = self.music_data
        edit = score_edits.apply_instrument_overrides(
            music_data, name_overrides, program_overrides, item_name_overrides,
            item_sound_overrides, auto_correct_enabled, part_percussion_changes,
        )
        if not edit.changed:
            return False
        for part_id, name in edit.renamed_parts.items():
            self.presenter.rename_part(part_id, name)
        if edit.structure_changed:
            # Region 2's voice rows change shape (a kit has one voice per
            # drum), so its tree is rebuilt - with every mute/solo/link the
            # user had carried across (invariant 11).
            self.presenter.reload_region_2_structure(
                music_data.get_score_structure(), music_data.collapsed_part_ids,
                self.link_group_numbers(),
            )
        elif edit.percussion_changed:
            for part_id, staff_id, voice_id, label in edit.voice_renames(music_data):
                self.presenter.rename_voice(part_id, staff_id, voice_id, label)
        self.presenter.update_timeline_views(play_all=False)
        return True

    # --- Key Signature dialog (S6) -------------------------------------

    def current_key_override(self) -> Tuple[Optional[int], Optional[str]]:
        return score_edits.current_key_override(self.music_data)

    def apply_key_signature_override(
        self, fifths: Optional[int], mode: Optional[str]
    ) -> bool:
        """Set or clear the whole-piece key override. Returns whether it
        changed.

        Region 1 and the status bar need their own explicit refresh: the
        displayed key isn't part of update_timeline_views' normal scope.
        """
        if not score_edits.apply_key_signature_override(self.music_data, fifths, mode):
            return False
        self.presenter.update_timeline_views(play_all=False)
        self.presenter.refresh_region_1()
        self.presenter.update_status_bar()
        return True

    # --- Reorder Parts dialog ------------------------------------------

    def part_rows(self) -> List[Tuple[str, str]]:
        return score_edits.part_rows(self.music_data)

    def current_part_order(self) -> List[str]:
        return score_edits.current_part_order(self.music_data)

    def reorder_parts(self, new_order: List[str]) -> bool:
        """Apply a new part order. Returns whether it changed.

        Region 2's rows are moved rather than rebuilt - same "never
        load_score_structure" reasoning as rename_part above.
        """
        if not score_edits.reorder_parts(self.music_data, new_order):
            return False
        self.presenter.reorder_parts(new_order)
        self.presenter.update_timeline_views(play_all=False)
        return True

    # --- Link Parts dialog (stage 9) ------------------------------------
    #
    # Redesigned (user-requested, 2026-09-16): the dialog now only ever
    # CREATES one new group - a part already in a group can't join another,
    # so link_dialog_rows omits it rather than showing it as a checkbox the
    # user could tick and have refused. Dissolving a group is a separate,
    # single-part action now reached from Region 2's own context menu
    # (Unlink), not from inside this dialog - see unlink_part below and
    # MainWindow.show_region_2_context_menu.

    def link_dialog_rows(self) -> List[Tuple[str, str]]:
        return score_edits.link_dialog_rows(self.music_data)

    def link_group_numbers(self) -> Dict[str, int]:
        return score_edits.link_group_numbers(self.music_data)

    def link_new_group(self, part_ids: List[str]) -> bool:
        """Apply the Link Parts dialog's result. Returns whether it changed
        anything."""
        if not score_edits.link_new_group(self.music_data, part_ids):
            return False
        self.presenter.apply_link_groups(self.link_group_numbers())
        self.presenter.update_timeline_views(play_all=False)
        return True

    def unlink_part(self, part_id: str) -> bool:
        """Region 2's context menu Unlink action. Returns whether anything
        changed."""
        if not score_edits.unlink_part(self.music_data, part_id):
            return False
        self.presenter.apply_link_groups(self.link_group_numbers())
        self.presenter.update_timeline_views(play_all=False)
        return True

    # --- Parts > Collapse staves ---------------------------------------

    def collapse_staves_state(self, part_id: Optional[str]) -> Tuple[bool, bool]:
        return score_edits.collapse_staves_state(self.music_data, part_id)

    def toggle_staves_collapsed(self, part_id: str) -> bool:
        """Collapse or uncollapse `part_id`'s alternate stave. Returns
        whether anything changed (False for a part with none).

        Region 2 is rebuilt, carrying mute/solo/links across (invariant 11
        - same path as flagging a part percussion), because the alternate
        stave's rows come and go. The rebuild re-emits Region 2's filter,
        which is what drops (or restores) that stave's notes in navigation
        and playback."""
        music_data = self.music_data
        collapsed = score_edits.toggle_staves_collapsed(music_data, part_id)
        if collapsed is None:
            return False
        self.presenter.reload_region_2_structure(
            music_data.get_score_structure(), music_data.collapsed_part_ids,
            self.link_group_numbers(),
        )
        self.presenter.update_timeline_views(play_all=False)
        self.presenter.announce_staves_collapsed(collapsed)
        return True
