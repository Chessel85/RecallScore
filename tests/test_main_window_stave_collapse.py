# tests/test_main_window_stave_collapse.py
"""Parts > Collapse staves, driven through MainWindow with NullSynth:
Region 2 loses the alternate TAB stave's row, Region 3/4 show the TAB
partner's string/fret on the treble note, each pitch sounds once rather
than twice, and unchecking puts everything back."""
from PySide6.QtCore import Qt

from tests.support.main_window_helpers import load_and_wait
from tests.test_main_window_region2 import _capture_announcements


def _region_2_staff_rows(window):
    window.region_2.select_node("staff_P1_1")
    return [t for t in window.region_2.visible_item_texts() if "stave" in t.lower()]


def _sounded_at_chord(window, qtbot, null_synth):
    """The MIDI pitches heard when stepping onto the C4/E4/A4 chord from
    the first note."""
    window.navigate_timeline_home()
    window.region_3.setFocus()
    null_synth.played.clear()
    qtbot.keyClick(window.region_3, Qt.Key.Key_Right)
    return sorted(p for event in null_synth.played for p in event["midi_notes"])


def test_collapse_staves_hides_the_tab_stave_and_borrows_its_attributes(
    window, qtbot, null_synth, guitar_alternate_tab_stave_score, monkeypatch
):
    load_and_wait(window, qtbot, guitar_alternate_tab_stave_score)
    assert len(_region_2_staff_rows(window)) == 2
    assert _sounded_at_chord(window, qtbot, null_synth) == [60, 60, 64, 64, 69]

    messages = _capture_announcements(monkeypatch)
    window.region_2.select_node("part_P1")
    window.toggle_staves_collapsed_current_part()

    assert messages[-1] == "Staves collapsed"
    assert window._actions.collapse_staves.isChecked()
    assert window.region_2.current_node().node_id == "part_P1"
    assert len(_region_2_staff_rows(window)) == 1
    assert _sounded_at_chord(window, qtbot, null_synth) == [60, 64, 69]

    window._music_data.set_display_attribute_for_voice("playing", "part", "P1", 1, 1, True)
    window.presenter.update_timeline_views(play_all=False)
    texts = [window.region_3.item(i).text() for i in range(window.region_3.count())]
    assert texts == ["A, g1", "E, s4f2g2", "C, s5f3g3"]

    window.region_2.select_node("part_P1")
    window.toggle_staves_collapsed_current_part()

    assert messages[-1] == "Staves uncollapsed"
    assert not window._actions.collapse_staves.isChecked()
    assert len(_region_2_staff_rows(window)) == 2
    assert _sounded_at_chord(window, qtbot, null_synth) == [60, 60, 64, 64, 69]


def test_collapsing_keeps_a_muted_row_muted(
    window, qtbot, guitar_alternate_tab_stave_score
):
    """Invariant 11: the rebuild carries mute state across."""
    load_and_wait(window, qtbot, guitar_alternate_tab_stave_score)
    window.region_2.select_node("staff_P1_1")
    window.toggle_mute_current_region2_row()

    window.toggle_staves_collapsed_current_part()

    assert window.region_2.current_node().node_id == "staff_P1_1"
    assert window.region_2.model_manager.node("staff_P1_1").muted


def test_collapse_staves_menu_follows_region_2s_current_part(
    window, qtbot, guitar_alternate_tab_stave_score, score_duet
):
    action = window._actions.collapse_staves
    window.refresh_collapse_staves_action()
    assert not action.isEnabled()

    load_and_wait(window, qtbot, guitar_alternate_tab_stave_score)
    window.region_2.select_node("staff_P1_2")
    window.refresh_collapse_staves_action()
    assert action.isEnabled()
    assert not action.isChecked()

    load_and_wait(window, qtbot, score_duet)
    window.refresh_collapse_staves_action()
    assert not action.isEnabled()
    assert not action.isChecked()


def test_collapsed_staves_persist_per_score(
    window, qtbot, guitar_alternate_tab_stave_score, score_duet
):
    load_and_wait(window, qtbot, guitar_alternate_tab_stave_score)
    window.region_2.select_node("part_P1")
    window.toggle_staves_collapsed_current_part()

    load_and_wait(window, qtbot, score_duet)
    load_and_wait(window, qtbot, guitar_alternate_tab_stave_score)

    assert window._music_data.is_staves_collapsed("P1")
    assert len(_region_2_staff_rows(window)) == 1
