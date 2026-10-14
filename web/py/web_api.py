"""The browser bridge: the web version's controller layer, run inside Pyodide.

Holds the current MusicData (replaced wholesale on every load, CLAUDE.md
invariant 3) and returns only plain dicts, so JavaScript never holds Python
objects. A failure comes back as {"error": message}, never an exception.

The logic is the desktop's: rows come from MusicData (NoteRenderer,
PerformanceRows, get_status_bar_fields), Region 2 from the shared
Region2HierarchyModel, and every spoken message from models/announcements.py.
What lives here is only the sequencing the desktop controllers do between
those calls (NavigationController, RegionPresenter, MainWindow._on_score_loaded).

Region numbers in the returned dicts are string keys "1" to "6"; Region 6 is
the desktop status bar.
"""
import os
import tempfile
from typing import Any, Dict, List, Optional

from audio.barline_patterns import STEP_MS
from audio.boundary_cue import BOUNDARY_CUE_CHANNEL, boundary_cue_event
from audio.free_metronome import free_metronome_beat
from audio.grace_note_schedule import effective_grace_duration_ms
from audio.metronome import METRONOME_CHANNEL
from audio.navigation_cues import (
    barline_indicator_events, count_in_cues, position_cues, position_cues_at,
)
from audio.performance_cue import PERFORMANCE_CUE_CHANNEL
from audio.position_announcer import POSITION_ANNOUNCER_CHANNEL
from models import announcements
from models.mixer_settings import ANNOUNCER, CENTRE_PAN, CLICK, CUE, default_pan_for
from models.app_settings_data import AppSettings
from models.attribute_scopes import region_4_scope_menu
from models.marking_categories import ALL_CATEGORIES
from models.music_data import MusicData
from models.play_plan import PlayTimeline, TimelineEntry
from models.play_settings import (
    LOOP_REPEAT_LABELS, LOOP_REPEAT_MODES, MAX_LEAD_IN_BARS, MAX_LEAD_IN_BEATS,
    MAX_LOOP_LENGTH_BARS, MIN_LOOP_LENGTH_BARS, PLAY_MODE_LABELS, PLAY_MODES,
    PlaySettings, dialog_enabled_states, dialog_labels,
)
from models.region2_manager import Region2HierarchyModel, Region2Node, node_status_label
from models.region3_row import NoteRow
from models.vocabulary import bar_word
from parsers.musicxml_metadata import load_musicxml_without_music21

SUPPORTED_SUFFIXES = (".musicxml", ".xml", ".mxl")

_music_data: Optional[MusicData] = None
_region_2 = Region2HierarchyModel()
_uk_terms = False
_pending_digits = ""
_pending_cleared = False


def set_uk_terms(uk_terms: bool) -> None:
    """bar/measure, crotchet/quarter... Carried onto every later load, like
    ScoreSession.set_uk_terms on the desktop."""
    global _uk_terms
    _uk_terms = bool(uk_terms)
    if _music_data is not None:
        _music_data.uk_terms = _uk_terms


def load(data: bytes, filename: str) -> Dict[str, Any]:
    """Parse an uploaded score. The reader takes a path, so the bytes are
    written to a temp file that keeps the original suffix (.mxl is a zip).

    On success returns {"ok", "summary", "view"}, "view" being every region
    (see view()). On failure the previous score stays loaded."""
    global _music_data
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return {"error": f"{filename or 'This file'} is not a supported score. "
                         f"Supported types: {', '.join(SUPPORTED_SUFFIXES)}."}
    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(bytes(data))
            path = handle.name
        loaded = load_musicxml_without_music21(path)
    except Exception as exc:  # noqa: BLE001 - every failure must reach the user
        return {"error": f"Could not open {filename}: {exc}"}
    finally:
        if path and os.path.exists(path):
            os.remove(path)
    _adopt(loaded)
    return {"ok": True, "summary": score_summary(), "view": view()}


def _adopt(music_data: MusicData) -> None:
    """MainWindow._on_score_loaded's order, minus what the web has not built
    yet (saved per-score config, Phase 5): global defaults first, then
    Region 2's tree, whose voice filter must be in effect before any row is
    rendered."""
    global _music_data, _pending_digits
    _pending_digits = ""
    _end_playback()
    defaults = AppSettings()
    music_data.uk_terms = _uk_terms
    music_data.marking_categories_off = set(defaults.marking_categories_off) & set(ALL_CATEGORIES)
    music_data.show_engraving_details_enabled = defaults.show_engraving_details_enabled
    _region_2.build_from_score(
        music_data.get_score_structure(), collapse_to_parts=music_data.collapsed_part_ids
    )
    music_data.set_active_voice_filter(_region_2.get_active_voice_tuples())
    _music_data = music_data


def score_summary() -> Dict[str, Any]:
    """Region 1's text plus the counts a loading message needs."""
    if _music_data is None:
        return {"error": "No score is loaded."}
    return {
        "credits": dict(_music_data.get_region_1_data()),
        "parts": [{"part_id": p.part_id, "name": p.name} for p in _music_data.parts_info],
        "slices": len(_music_data.timeline_slices),
    }


# --- region rows -------------------------------------------------------------

def region_rows(region: int, selection: Optional[List[int]] = None) -> Any:
    """One region's rows. `selection` is Region 3's selected row indices and
    only matters for Region 4; None means "every row", which is what Region 3
    selects after every move (invariant 10's intent)."""
    if _music_data is None:
        return {"error": "No score is loaded."}
    builders = {
        1: _region_1_rows,
        2: _region_2_rows,
        3: _region_3_rows,
        4: lambda: _region_4_rows(selection),
        5: _region_5_rows,
        6: _region_6_rows,
    }
    builder = builders.get(int(region))
    if builder is None:
        return {"error": f"There is no region {region}."}
    return builder()


def view() -> Dict[str, Any]:
    """Every region, for a load or a section switch."""
    if _music_data is None:
        return {"error": "No score is loaded."}
    regions = {"1": _region_1_rows(), "2": _region_2_rows()}
    regions.update(_position_regions())
    return {"regions": regions, "selection": _select_all()}


def _position_regions() -> Dict[str, Any]:
    """The regions a cursor move changes: 3 to 6. Regions 1 and 2 describe
    the whole score, so a move never re-sends them."""
    return {
        "3": _region_3_rows(),
        "4": _region_4_rows(None),
        "5": _region_5_rows(),
        "6": _region_6_rows(),
    }


def _select_all() -> List[int]:
    return list(range(len(_music_data.get_region_3_rows())))


def _region_1_rows() -> List[Dict[str, Any]]:
    """Score information as "label: value" rows, like Region1ListWidget. A
    multi-section file gets a first "section" row standing in for the
    desktop's tab bar; section(delta) steps it."""
    md = _music_data
    rows: List[Dict[str, Any]] = []
    if md.has_multiple_sections:
        rows.append({"text": _section_label(md), "kind": "section"})
    rows.extend(
        {"text": f"{key}: {value}", "kind": "info"} for key, value in md.get_region_1_data().items()
    )
    return rows


def _section_label(md: MusicData) -> str:
    return announcements.section_change(md).rstrip(".")


def _region_2_rows() -> List[Dict[str, Any]]:
    """The parts/staves/voices tree, every level included. Expand state is
    the page's: the desktop starts every node collapsed and never persists
    it. A collapsed-to-parts part (MIDI, Ultimate Guitar, synthetic chord or
    lyric parts) has no children to show."""
    return [_node_dict(part) for part in _region_2.roots]


def _node_dict(node: Region2Node) -> Dict[str, Any]:
    collapsed = node.node_type == "part" and _region_2.part_is_collapsed(node.part_id)
    return {
        "id": node.node_id,
        "text": node_status_label(node),
        "type": node.node_type,
        "children": [] if collapsed else [_node_dict(child) for child in node.children],
    }


def _region_3_rows() -> List[Dict[str, Any]]:
    return [
        {"text": row.text, "kind": "note" if isinstance(row, NoteRow) else "marking"}
        for row in _music_data.get_region_3_rows()
    ]


def _region_4_rows(selection: Optional[List[int]]) -> List[Dict[str, Any]]:
    """Region 4 follows Region 3's selection, not the slice. `key` is the
    attribute key, so the page can keep focus on the same attribute across
    a rebuild the way Region4ListWidget.refresh_list does."""
    indices = _select_all() if selection is None else [int(i) for i in selection]
    return [
        {"text": f"{display_key}: {value}", "key": attribute_key}
        for display_key, attribute_key, value
        in _music_data.get_region_4_rows_for_region_3_selection(indices)
    ]


def _region_5_rows() -> List[Dict[str, Any]]:
    """Context rows (section, chord, lyric) first, then the performance
    markings active at the cursor; "None" when there are neither, as
    Region5ListWidget shows."""
    md = _music_data
    rows = list(md.get_performance_context_rows()) + list(md.get_performance_region_rows())
    if not rows:
        return [{"text": "None", "category": None}]
    return [{"text": row.label, "category": row.category} for row in rows]


def _region_6_rows() -> List[Dict[str, Any]]:
    """The desktop status bar's eight fields, in its Tab order."""
    md = _music_data
    fields = md.get_status_bar_fields()
    if _pending_digits:
        fields[0] = announcements.pending_digits(_pending_digits, _uk_terms)
    fields += [
        _playback_status(),
        announcements.metronome_status(md.metronome_enabled),
        announcements.position_announcer_status(md.position_announcer_enabled),
        announcements.loop_length_status(md.play_settings.loop_length_bars, _uk_terms),
    ]
    return [{"text": text} for text in fields]


# --- sound -------------------------------------------------------------------
#
# A sound plan is what SynthEngine would be asked to do, as data, so the
# page's audio.js stays a thin synth driver (GM programs are already
# 0-indexed here, invariant 9):
#   stop      release everything still sounding first (play_chord's
#             retrigger=True, discrete audition)
#   notes     [{channel, program, bank, pitches, ms}] - each group rings for
#             its own ms; program None leaves the channel's program alone
#   grace     [{channel, program, pitches}] sounded first for grace_ms, then
#             the notes (play_chord_with_grace); empty for most slices
#   oneshots  [{slot, event: [channel, bank, program, pitch, velocity],
#             delay_ms}] on the app SoundFont, never released early except
#             by the next one-shot in the same slot or by stop. Slots are
#             SynthEngine's: "click" (metronome and bar line indicator share
#             play_click's), "word" (position announcer), "boundary".

def synth_setup() -> Dict[str, Any]:
    """What audio.js applies once the synth exists, before any score: the
    app-sound channels' pans (SynthEngine._load_click_soundfont, through the
    Mixer's own defaults) as [channel, cc value] pairs. The click is hard
    right and the spoken position hard left so the two are told apart."""
    return {"pans": [
        [METRONOME_CHANNEL, default_pan_for(CLICK)],
        [POSITION_ANNOUNCER_CHANNEL, default_pan_for(ANNOUNCER)],
        [PERFORMANCE_CUE_CHANNEL, default_pan_for(CUE)],
        [BOUNDARY_CUE_CHANNEL, CENTRE_PAN],
    ]}


def _oneshot(slot: str, event, delay_ms: int = 0) -> Dict[str, Any]:
    return {"slot": slot, "event": list(event), "delay_ms": int(delay_ms)}


def _sound_plan(events, grace, stop: bool) -> Dict[str, Any]:
    """SynthEngine.play_chord / play_chord_with_grace as a plan: each group
    with its own ring time, grace notes first when there are any."""
    return {
        "stop": stop,
        "notes": [
            {"channel": e[0], "program": e[1], "bank": e[4] if len(e) > 4 else 0,
             "pitches": list(e[2]), "ms": int(e[3])}
            for e in events if e[2]
        ],
        "grace": [
            {"channel": g[0], "program": g[1], "pitches": list(g[2])} for g in grace if g[2]
        ] if events else [],
        "grace_ms": effective_grace_duration_ms(events) if events and grace else 0,
        "oneshots": [],
    }


def _add_cues(sound: Dict[str, Any], click, word) -> Dict[str, Any]:
    if click is not None:
        sound["oneshots"].append(_oneshot("click", click))
    if word is not None:
        sound["oneshots"].append(_oneshot("word", word))
    return sound


def _audition_sound(selection: List[int], with_position_cues: bool = True) -> Dict[str, Any]:
    """PlaybackController.audition_selection: the selected Region 3 rows,
    then the click and spoken beat position if they are on."""
    md = _music_data
    note_indices = md.note_indices_from_selection([int(i) for i in selection])
    events = md.get_playback_events_for_indices(note_indices)
    grace = md.get_grace_note_events_for_indices(note_indices)
    sound = _sound_plan(events, grace, True)
    if with_position_cues:
        _add_cues(sound, *position_cues(md))
    return sound


def _boundary_sound() -> Dict[str, Any]:
    """Sounds INSTEAD of moving (PlaybackController.play_boundary_cue)."""
    return {"stop": False, "notes": [], "grace": [], "grace_ms": 0,
            "oneshots": [_oneshot("boundary", boundary_cue_event())]}


def audition(selection: Optional[List[int]] = None, with_position_cues: bool = False) -> Dict[str, Any]:
    """Sound Region 3's selection without moving: an in-slice Up/Down (notes
    only, MainWindow.on_region_3_vertical_move) or Ctrl+A (with the position
    cues, RegionPresenter.select_all_region_3)."""
    if _music_data is None:
        return {"sound": None}
    indices = _select_all() if selection is None else selection
    return {"sound": _audition_sound(indices, bool(with_position_cues))}


def toggle(kind: str) -> Dict[str, Any]:
    """Ctrl+M metronome, Ctrl+P position announcer, Ctrl+B bar line
    indicator: flip it, say the new state, re-send Region 6. Only the status
    region is re-sent, as the desktop updates only its status bar (no note
    list redraw to talk over the announcement)."""
    md = _music_data
    if md is None:
        return {"error": "No score is loaded."}
    if kind == "metronome":
        md.toggle_metronome()
        said = announcements.metronome_toggled(md.metronome_enabled)
    elif kind == "position_announcer":
        md.toggle_position_announcer()
        said = announcements.position_announcer_toggled(md.position_announcer_enabled)
    elif kind == "bar_line_indicator":
        md.toggle_bar_line_indicator()
        said = announcements.bar_line_indicator_toggled(md.bar_line_indicator_enabled)
    else:
        return {"error": f"Unknown toggle {kind!r}."}
    return {"announce": said, "regions": {"6": _region_6_rows()}}


# --- navigation --------------------------------------------------------------
#
# Each returns a move result:
#   moved     the cursor moved
#   boundary  the boundary ("doh") cue should sound
#   announce  text to speak BEFORE the note list re-renders (the desktop's
#             RegionPresenter._announce_measure_change order), or None
#   barline   [before, after] measures when a plain step crossed a bar line
#             (the bar line indicator, Ctrl+B), else None
#   regions   the changed regions when moved; "selection" is Region 3's
#             select-all after the move
#   sound     the sound plan (see above): the new slice's audition and
#             position cues, then any bar line indicator steps, the
#             desktop's order (audition first, or its stop would cut the
#             cue off); the boundary cue alone on a refused move; else None

def _result(moved: bool, announce_measure: bool = False, barline=None,
            boundary: Optional[bool] = None, whole_view: bool = False,
            announce: Optional[str] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "moved": moved,
        "boundary": (not moved) if boundary is None else boundary,
        "announce": announce,
        "barline": barline,
        "sound": None,
    }
    global _pending_cleared
    if moved and _paused_seq is not None:
        # PlaybackController.revert_pause_on_move: the paused position is
        # stale once the cursor moves, so drop to Stopped where it now is.
        _end_playback()
        result["transport"] = "stopped"
    if not moved and _pending_cleared:
        result["regions"] = {"6": _region_6_rows()}  # the half-typed number is gone
    _pending_cleared = False
    if moved:
        current = _music_data.get_current_slice()
        if announce_measure and current is not None:
            result["announce"] = announcements.measure_change(current.measure, _uk_terms)
        if whole_view:
            result.update(view())
        else:
            result["regions"] = _position_regions()
            result["selection"] = _select_all()
        sound = _audition_sound(_select_all())
        before, after = barline if barline else (None, None)
        if barline:
            for i, event in enumerate(barline_indicator_events(_music_data, before, after)):
                sound["oneshots"].append(_oneshot("click", event, i * STEP_MS))
        result["sound"] = sound
    elif result["boundary"]:
        result["sound"] = _boundary_sound()
    return result


def _clear_pending() -> None:
    """Any movement cancels a half-typed bar number
    (NavigationController.clear_pending_digits)."""
    global _pending_digits, _pending_cleared
    if _pending_digits:
        _pending_digits = ""
        _pending_cleared = True


def _no_score() -> Dict[str, Any]:
    return {"moved": False, "boundary": False, "announce": None, "barline": None, "sound": None}


def _current_measure() -> Optional[int]:
    current = _music_data.get_current_slice()
    return current.measure if current is not None else None


def move(direction: str) -> Dict[str, Any]:
    """The cursor moves, NavigationController's semantics:
    left/right            Left/Right, one note or chord; reports a crossed bar line
    bar_left/bar_right    Ctrl+Left/Right, by bar; speaks the new bar
    first/last            Ctrl+Home/End, first/last sounding note; speaks the
                          bar and never sounds the boundary cue
    """
    md = _music_data
    if md is None:
        return _no_score()
    _clear_pending()
    if direction in ("left", "right"):
        before = _current_measure()
        moved = md.move_timeline_left() if direction == "left" else md.move_timeline_right()
        after = _current_measure()
        crossed = moved and before is not None and after is not None and before != after
        return _result(moved, barline=[before, after] if crossed else None)
    if direction in ("bar_left", "bar_right"):
        moved = (md.move_timeline_left_by_measure() if direction == "bar_left"
                 else md.move_timeline_right_by_measure())
        return _result(moved, announce_measure=True)
    if direction in ("first", "last"):
        if direction == "first":
            md.move_timeline_home()
        else:
            md.move_timeline_end()
        return _result(True, announce_measure=True)
    return {"error": f"Unknown direction {direction!r}."}


def goto_bar(measure: int) -> Dict[str, Any]:
    """Ref 6: typed bar number then Enter, or Ctrl+G. An unknown bar does
    not move and sounds the boundary cue."""
    if _music_data is None:
        return _no_score()
    _clear_pending()
    return _result(_music_data.jump_to_measure(int(measure)), announce_measure=True)


def jump_point(direction: int) -> Dict[str, Any]:
    """Ctrl+Alt+Right/Left: next/previous song jump point or rehearsal mark."""
    if _music_data is None:
        return _no_score()
    _clear_pending()
    return _result(_music_data.move_to_jump_point(int(direction)))


def section(delta: int) -> Dict[str, Any]:
    """Left/Right on Region 1's section row: step sections, clamped at the
    ends with the boundary cue (NavigationController.step_section). A switch
    re-sends every region and is spoken, "Exercise 2, section 2 of 2.", as
    the desktop does when the switch did not come from its tab bar."""
    md = _music_data
    if md is None:
        return _no_score()
    _clear_pending()
    target = md.active_section_index + int(delta)
    if not (0 <= target < len(md.sections)) or not md.set_active_section(target):
        return _result(False)
    return _result(True, whole_view=True, announce=announcements.section_change(md))


def selection_changed(selection: List[int]) -> Dict[str, Any]:
    """Region 3's selection changed (Up/Down, Shift+arrows, Ctrl+A): Region 4
    follows it."""
    if _music_data is None:
        return {"error": "No score is loaded."}
    return {"regions": {"4": _region_4_rows(selection)}}


def attribute_announcement(number: int, selection: Optional[List[int]] = None) -> Optional[str]:
    """Ctrl+1 to 9: Region 4's Nth row as currently displayed, or None."""
    if _music_data is None:
        return None
    indices = _select_all() if selection is None else [int(i) for i in selection]
    rows = _music_data.get_region_4_rows_for_region_3_selection(indices)
    return announcements.attribute_by_number(rows, int(number))


# --- Region 4 scope menu (Shift+F10, Ref 15 AC4) -------------------------------

def _scope_menu(row: int, selection: Optional[List[int]]):
    indices = _select_all() if selection is None else [int(i) for i in selection]
    return region_4_scope_menu(_music_data, indices, int(row))


def region4_menu(row: int, selection: Optional[List[int]] = None) -> Dict[str, Any]:
    """What Region 4's context menu offers for its row `row` while Region 3
    has `selection` selected: {"title": the attribute's name as the row
    shows it, "items": [{scope, label}]}. No items when there is nothing to
    act on (the desktop then opens no menu)."""
    menu = _scope_menu(row, selection) if _music_data is not None else None
    if menu is None:
        return {"title": "", "items": []}
    indices = _select_all() if selection is None else [int(i) for i in selection]
    display_key = _music_data.get_region_4_rows_for_region_3_selection(indices)[int(row)][0]
    return {
        "title": display_key,
        "items": [{"scope": scope, "label": label} for scope, label in menu.scopes],
    }


def region4_apply(row: int, selection: Optional[List[int]], scope: str) -> Dict[str, Any]:
    """A scope chosen from Region 4's menu (AttributeController.apply_change):
    add or remove the row's attribute across that scope, then re-send Regions
    3 and 4. Region 3's text changes in place (refresh_region_3_labels): the
    page keeps its selection and nothing is sounded or spoken."""
    if _music_data is None:
        return {"error": "No score is loaded."}
    menu = _scope_menu(row, selection)
    if menu is None or scope not in [s for s, _ in menu.scopes]:
        return {"error": "That attribute can no longer be changed from here."}
    _music_data.set_display_attribute(menu.attribute_key, scope, menu.notes, menu.add)
    return {"regions": {"3": _region_3_rows(), "4": _region_4_rows(selection)}}


# --- typed bar number (Ref 6) and Go to bar ------------------------------------

def goto_info() -> Dict[str, Any]:
    """What the Go to bar dialog needs: the dialect's word ("measure"/"bar",
    capitalised for a title) and the current bar number to pre-fill."""
    word = bar_word(_uk_terms)
    current = _current_measure() if _music_data is not None else None
    return {"word": word.capitalize(), "current": current}


def append_digit(digit: str) -> Dict[str, Any]:
    """A bare digit key: it accumulates, and Region 6's first field shows
    "Go to measure: 12" (NavigationController.append_pending_digit)."""
    global _pending_digits
    if _music_data is None or not str(digit).isdigit() or len(str(digit)) != 1:
        return _no_score()
    _pending_digits += str(digit)
    return {"regions": {"6": _region_6_rows()}}


def commit_digits() -> Dict[str, Any]:
    """Enter: jump to the typed bar. {"pending": False} when nothing was
    typed, so the key can fall through to the browser."""
    global _pending_digits, _pending_cleared
    if _music_data is None or not _pending_digits:
        return {"pending": False}
    digits, _pending_digits = _pending_digits, ""
    _pending_cleared = False
    result = _result(_music_data.jump_to_measure(int(digits)), announce_measure=True)
    if not result["moved"]:
        result["regions"] = {"6": _region_6_rows()}
    result["pending"] = True
    return result


def clear_digits() -> Dict[str, Any]:
    """Backspace: cancel a half-typed number. The desktop uses Escape, which
    the web never binds."""
    global _pending_digits
    if _music_data is None or not _pending_digits:
        return {"pending": False}
    _pending_digits = ""
    return {"pending": True, "regions": {"6": _region_6_rows()}}


# --- Region 2 mute and solo (F8, F9, Alt+F8, Alt+F9) ------------------------------

def _filter_changed() -> Dict[str, Any]:
    """Region2's filter changed: tell MusicData, then re-send every region
    that follows it (RegionPresenter.on_region_2_filter_changed). The tree is
    re-sent too because the row text carries "muted"/"soloed"."""
    _music_data.set_active_voice_filter(_region_2.get_active_voice_tuples())
    regions = {"2": _region_2_rows()}
    regions.update(_position_regions())
    return {"regions": regions, "selection": _select_all()}


def region2_toggle(node_id: str, kind: str) -> Dict[str, Any]:
    """F8 (kind "mute") or F9 (kind "solo") on the focused Region 2 row.
    Nothing is spoken: the row's own text says "muted"/"soloed"."""
    if _music_data is None:
        return {"error": "No score is loaded."}
    if _region_2.node(node_id) is None:
        return {"error": "That row is not in the parts list."}
    if kind == "mute":
        _region_2.toggle_mute(node_id)
    elif kind == "solo":
        _region_2.toggle_solo(node_id)
    else:
        return {"error": f"Unknown toggle {kind!r}."}
    return _filter_changed()


def region2_clear(kind: str) -> Dict[str, Any]:
    """Alt+F8 (kind "mute", Unmute All) or Alt+F9 (kind "solo", Unsolo All).
    Spoken, as on the desktop."""
    if _music_data is None:
        return {"error": "No score is loaded."}
    if kind == "mute":
        _region_2.clear_all_mute()
        said = "unmuted all"
    elif kind == "solo":
        _region_2.clear_all_solo()
        said = "unsoloed all"
    else:
        return {"error": f"Unknown clear {kind!r}."}
    result = _filter_changed()
    result["announce"] = said
    return result



# --- playback (Space, Ctrl+Space) ---------------------------------------------
#
# The whole run is planned here (models/play_plan.py's PlayTimeline: the
# desktop PlaybackController's sequencing on a virtual clock) and handed to
# the page a chunk at a time. scheduler.js puts each entry's sound on the
# synth's own sequencer ahead of time and moves the cursor when it is heard.
# Each entry is {at, kind, seq, cursor, sound}:
#   at      ms after playback started (or resumed)
#   kind    "count", "step", "restart" or "end" (see TimelineEntry)
#   cursor  the timeline index the cursor shows from then on, or None
#   sound   a sound plan (see "sound" above), or None
# `session` numbers each start and resume, so a stale call is ignored.

_timeline: Optional[PlayTimeline] = None
_session = 0
_paused_seq: Optional[int] = None


def _playback_status() -> str:
    # The free metronome is not playback: the desktop's field says Stopped.
    playing = _timeline is not None and not isinstance(_timeline, _FreeMetronome)
    run = _timeline.run if playing else None
    paused = _paused_seq is not None
    return announcements.playback_status(run, paused, playing and not paused)


def _end_playback() -> None:
    global _timeline, _paused_seq, _session
    _timeline = None
    _paused_seq = None
    _session += 1


def _entry_dict(entry: TimelineEntry) -> Dict[str, Any]:
    md = _music_data
    sound = None
    if entry.kind == "count":
        sound = _add_cues(_sound_plan([], [], False), *count_in_cues(md, entry.beat))
    elif entry.kind == "step":
        events = md.get_playback_events_at_index(entry.index)
        grace = md.get_grace_note_events_at_index(entry.index)
        # A jump's retrigger acts only through the notes (sound_events does
        # nothing for a step without any); a run's start always stops.
        stop = entry.stop or (entry.retrigger and bool(events))
        sound = _add_cues(_sound_plan(events, grace, stop), *position_cues_at(md, entry.index))
    return {"at": entry.at_ms, "kind": entry.kind, "seq": entry.seq, "cursor": entry.index,
            "sound": sound}


def _cursor_view() -> Dict[str, Any]:
    return {"regions": _position_regions(), "selection": _select_all()}


def play_toggle() -> Dict[str, Any]:
    """Space (PlaybackController.toggle_play_stop): start from the cursor,
    stop (the cursor goes back where it started), or resume a paused plain
    run. A paused lead-in or looping run stops, as on the desktop. From the
    last note it sounds the boundary cue instead: nothing is ahead to play.

    {"action": "start" | "resume", "session", "regions"}, then play_plan;
    {"action": "stop", "regions", "selection"}; {"action": "boundary",
    "sound"}; {"action": "none"} with no score."""
    global _timeline, _paused_seq, _session
    md = _music_data
    if md is None:
        return {"action": "none"}
    _clear_pending()
    if isinstance(_timeline, _FreeMetronome):
        # Space stops everything sounding: a running click track is what it
        # stops here, and nothing starts (toggle_play_stop).
        _end_playback()
        return {"action": "stop", "regions": {"6": _region_6_rows()}}
    if _timeline is not None:
        if _paused_seq is not None and _timeline.run is None:
            _timeline.resume_from(_paused_seq)
            _paused_seq = None
            _session += 1
            return {"action": "resume", "session": _session, "regions": {"6": _region_6_rows()}}
        md.active_event_index = _timeline.restore_index
        _end_playback()
        return {"action": "stop", **_cursor_view()}
    if md.next_visible_event_index(md.active_event_index) is None:
        return {"action": "boundary", "sound": _boundary_sound()}
    _end_playback()
    _timeline = PlayTimeline(md, md.play_settings)
    return {"action": "start", "session": _session, "regions": {"6": _region_6_rows()}}


def play_plan(session: int, until_ms: int) -> Dict[str, Any]:
    """The entries due before until_ms not handed out yet. {"stale": True}
    once that session is over or paused."""
    if _timeline is None or int(session) != _session or _paused_seq is not None:
        return {"stale": True}
    if isinstance(_timeline, _FreeMetronome):
        return {"entries": _timeline.plan(int(until_ms))}
    return {"entries": [_entry_dict(e) for e in _timeline.plan(int(until_ms))]}


def play_cursor(session: int, index: int) -> Dict[str, Any]:
    """A step or a loop restart is heard: the cursor follows it, as the
    desktop's Note region does during playback (Ref 10 AC4). Region 6 comes
    with it, so the Lead-in/Playing field keeps up."""
    if _timeline is None or int(session) != _session or _music_data is None:
        return {"stale": True}
    _music_data.active_event_index = int(index)
    return _cursor_view()


def play_ended(session: int) -> Dict[str, Any]:
    """The run finished on its own: the cursor goes back to where it
    started (Ref 10 AC5: "stopping reverts" includes reaching the end)."""
    if _timeline is None or int(session) != _session:
        return {"stale": True}
    _music_data.active_event_index = _timeline.restore_index
    _end_playback()
    return _cursor_view()


def play_pause(session: int, seq: int) -> Dict[str, Any]:
    """Ctrl+Space (toggle_pause_resume): pauses only, and only once the
    notes are under way; `seq` is the last entry heard. The cursor stays on
    the paused step. Resuming is Space's job. {"paused": bool, ...}."""
    global _paused_seq
    if (_timeline is None or int(session) != _session or _paused_seq is not None
            or not _timeline.can_pause_at(int(seq))):
        return {"paused": False}
    _paused_seq = int(seq)
    # The desktop flushes the cursor on pause, so it is on the paused step
    # even when its redraw had not caught up yet.
    _music_data.active_event_index = _timeline.step_index_at(_paused_seq)
    return {"paused": True, **_cursor_view()}


def play_stop() -> Dict[str, Any]:
    """Stop whatever is playing, cursor put back (a load, or anything else
    that must stop playback first). {"stopped": False} if nothing was."""
    if _timeline is None or _music_data is None:
        return {"stopped": False}
    _music_data.active_event_index = _timeline.restore_index
    _end_playback()
    return {"stopped": True, **_cursor_view()}


# --- free metronome (Ctrl+Alt+Space) -------------------------------------------

class _FreeMetronome:
    """Playback > Play Metronome as a play timeline the scheduler plans like
    any other: one click entry per beat, from audio/free_metronome.py (the
    desktop's own beat logic), so tempo and time signature are re-read each
    beat as it is planned. It never moves the cursor and cannot pause.
    Entries are already dicts, kind "click" (see the playback section)."""

    run = None

    def __init__(self, music_data: MusicData):
        self._md = music_data
        self._beat = 1
        self._next_at = 0
        self._seq = 0

    def plan(self, until_ms: int) -> List[Dict[str, Any]]:
        entries = []
        while self._next_at < until_ms:
            click, self._beat, beat_ms = free_metronome_beat(self._md, self._beat)
            sound = _add_cues(_sound_plan([], [], False), click, None)
            entries.append({"at": self._next_at, "kind": "click", "seq": self._seq,
                            "cursor": None, "sound": sound})
            self._seq += 1
            self._next_at += beat_ms
        return entries

    def can_pause_at(self, seq: int) -> bool:
        return False


def _playback_going() -> bool:
    """Playing, paused or counting in: a play run, not the free metronome
    (PlaybackController.is_playback_active)."""
    return _timeline is not None and not isinstance(_timeline, _FreeMetronome)


def disabled_commands() -> List[str]:
    """Keymap ids the Menu shows as unavailable right now, as the desktop
    greys out their actions: Play Metronome while playback is going (a click
    with the music is Ctrl+M's job)."""
    return ["play.metronome"] if _playback_going() else []


def play_metronome() -> Dict[str, Any]:
    """Ctrl+Alt+Space (toggle_play_metronome): start or stop the free
    click track. Does nothing while playback is going, as the desktop's
    greyed-out action: {"action": "none"}. Otherwise the shapes of
    play_toggle's start and stop."""
    global _timeline
    md = _music_data
    if md is None or _playback_going():
        return {"action": "none"}
    if isinstance(_timeline, _FreeMetronome):
        _end_playback()
        return {"action": "stop", "regions": {"6": _region_6_rows()}}
    _end_playback()
    _timeline = _FreeMetronome(md)
    return {"action": "start", "session": _session, "regions": {"6": _region_6_rows()}}


# --- tempo and play settings (F, S, D, Ctrl+L, Ctrl+I, Ctrl+R, loop length) ------
#
# Each returns {"announce", "regions": {"6": ...}}: the new value is spoken
# (nothing where focus is shows it) and Region 6 redrawn. All of them apply
# to the next play run; a running one keeps its own snapshot, except the
# tempo, which a run reads as it plans (the desktop's per-chunk reading).

def _setting_changed(said: str) -> Dict[str, Any]:
    return {"announce": said, "regions": {"6": _region_6_rows()}}


def tempo(kind: str) -> Dict[str, Any]:
    """F faster, S slower (10 on the displayed tempo), D back to the
    score's own (Ref 12). The new number is spoken."""
    md = _music_data
    if md is None:
        return {"error": "No score is loaded."}
    if kind == "faster":
        md.nudge_playback_tempo(10)
    elif kind == "slower":
        md.nudge_playback_tempo(-10)
    elif kind == "reset":
        md.reset_playback_tempo()
    else:
        return {"error": f"Unknown tempo change {kind!r}."}
    return _setting_changed(announcements.tempo(md))


def play_setting(command: str) -> Dict[str, Any]:
    """play_mode     Ctrl+L, cycle the play mode
    lead_in       Ctrl+I, lead-in on or off
    loop_repeat   Ctrl+R, cycle repeat handling while looping (says why
                  not when looping is off or the score has no repeats)
    loop_longer   Alt+PageUp, loop length one bar longer
    loop_shorter  Alt+PageDown, one bar shorter"""
    md = _music_data
    if md is None:
        return {"error": "No score is loaded."}
    settings = md.play_settings
    if command == "play_mode":
        md.play_settings = settings.with_play_mode(settings.next_play_mode())
        said = announcements.play_mode(md.play_settings.play_mode)
    elif command == "lead_in":
        md.play_settings = settings.with_lead_in_enabled(not settings.lead_in_enabled)
        said = announcements.lead_in_toggled(md.play_settings.lead_in_enabled)
    elif command == "loop_repeat":
        if not settings.loop_enabled:
            return {"announce": announcements.LOOPING_OFF}
        if not md.repeat_spans:
            return {"announce": announcements.NO_REPEATS}
        md.play_settings = settings.with_loop_repeat_mode(settings.next_loop_repeat_mode())
        said = announcements.loop_repeat_mode(md.play_settings.loop_repeat_mode)
    elif command in ("loop_longer", "loop_shorter"):
        delta = 1 if command == "loop_longer" else -1
        md.play_settings = settings.with_loop_length_bars(settings.loop_length_bars + delta)
        said = announcements.loop_length(md.play_settings.loop_length_bars, _uk_terms)
    else:
        return {"error": f"Unknown play setting {command!r}."}
    return _setting_changed(said)


def commit_loop_length() -> Dict[str, Any]:
    """Ctrl+Enter: the typed number becomes the loop length instead of a
    bar to go to (MainWindow.commit_loop_length). With looping off it says
    so and drops the number. {"pending": False} when nothing was typed."""
    global _pending_digits
    md = _music_data
    if md is None or not _pending_digits:
        return {"pending": False}
    digits, _pending_digits = _pending_digits, ""
    if not md.play_settings.loop_enabled:
        said = announcements.LOOPING_OFF
    else:
        md.play_settings = md.play_settings.with_loop_length_bars(int(digits))
        said = announcements.loop_length(md.play_settings.loop_length_bars, _uk_terms)
    result = _setting_changed(said)
    result["pending"] = True
    return result


# --- Play Settings dialog (Ctrl+Alt+P) -------------------------------------------

def _label(text: str) -> str:
    """The desktop's mnemonic "&" means nothing on the web."""
    return text.replace("&", "")


def play_settings_form() -> Dict[str, Any]:
    """The Play Settings dialog's fields in tab order, with the desktop
    dialog's labels, ranges and current values: {"title", "fields": [{name,
    type ("number", "checkbox" or "select"), label, value, min, max,
    options}], "enabled": play_settings_enabled(...)}."""
    md = _music_data
    if md is None:
        return {"error": "No score is loaded."}
    s = md.play_settings
    labels = dialog_labels(bar_word(_uk_terms))
    tempo_now = max(MusicData.MIN_TEMPO_BPM,
                    min(MusicData.MAX_TEMPO_BPM, int(round(md.playback_tempo_display_bpm()))))

    def number(name, value, low, high):
        return {"name": name, "type": "number", "label": _label(labels[name]),
                "value": value, "min": low, "max": high}

    def checkbox(name, value):
        return {"name": name, "type": "checkbox", "label": _label(labels[name]), "value": value}

    def select(name, value, values, texts):
        return {"name": name, "type": "select", "label": _label(labels[name]), "value": value,
                "options": [{"value": v, "label": t} for v, t in zip(values, texts)]}

    fields = [
        number("tempo", tempo_now, MusicData.MIN_TEMPO_BPM, MusicData.MAX_TEMPO_BPM),
        checkbox("lead_in_enabled", s.lead_in_enabled),
        number("lead_in_bars", s.lead_in_bars, 0, MAX_LEAD_IN_BARS),
        number("lead_in_beats", s.lead_in_beats, 0, MAX_LEAD_IN_BEATS),
        select("play_mode", s.play_mode, PLAY_MODES, PLAY_MODE_LABELS),
        number("loop_length_bars", s.loop_length_bars, MIN_LOOP_LENGTH_BARS, MAX_LOOP_LENGTH_BARS),
        select("loop_repeat_mode", s.loop_repeat_mode, LOOP_REPEAT_MODES, LOOP_REPEAT_LABELS),
        checkbox("loop_lead_in", s.loop_lead_in),
    ]
    return {"title": "Play Settings", "fields": fields,
            "enabled": play_settings_enabled(s.lead_in_enabled, s.play_mode)}


def play_settings_enabled(lead_in: bool, play_mode: str) -> Dict[str, bool]:
    """Which fields are live for the dialog's current lead-in tick and play
    mode, asked again on every change. A field not listed stays enabled."""
    has_repeats = bool(_music_data is not None and _music_data.repeat_spans)
    return dialog_enabled_states(bool(lead_in), str(play_mode), has_repeats)


def apply_play_settings(values) -> Dict[str, Any]:
    """The dialog's OK: `values` maps each field name to what was entered.
    Clamping is PlaySettings' and MusicData's own job, as on the desktop.
    Re-sends Region 6 (tempo and loop length are shown there)."""
    md = _music_data
    if md is None:
        return {"error": "No score is loaded."}
    if hasattr(values, "to_py"):
        values = values.to_py()
    md.play_settings = PlaySettings(
        lead_in_enabled=bool(values.get("lead_in_enabled")),
        lead_in_bars=values.get("lead_in_bars"),
        lead_in_beats=values.get("lead_in_beats"),
        play_mode=values.get("play_mode"),
        loop_length_bars=values.get("loop_length_bars"),
        loop_lead_in=bool(values.get("loop_lead_in")),
        loop_repeat_mode=values.get("loop_repeat_mode"),
    )
    try:
        md.set_playback_tempo_display_bpm(float(values.get("tempo")))
    except (TypeError, ValueError):
        pass  # an empty or garbled tempo keeps the current one
    return {"regions": {"6": _region_6_rows()}}
