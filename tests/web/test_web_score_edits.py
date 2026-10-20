"""Score edits through the browser bridge (RSBV 6.5): Instruments, Key
Signature, Reorder Parts, Link Parts, Region 2's Unlink and Collapse
staves. What each does to MusicData is models/score_edits.py, shared with
the desktop's ScoreEditController; these check the bridge's forms, that
Region 2 is changed in place (mute and solo survive, invariant 11) and that
the result is plain data carrying every region."""
import json
from pathlib import Path

import web_api

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _load_path(path):
    path = Path(path)
    result = web_api.load(path.read_bytes(), path.name)
    assert result["ok"]


def _load(name):
    _load_path(FIXTURES / name)


def _part_rows(result):
    return [row["text"] for row in result["regions"]["2"]]


def _values(form):
    """The Instruments dialog at OK with nothing changed."""
    return [{"name": r["name"], "sound": r["sound"], "percussion": r["percussion"]} for r in form["rows"]]


def test_instruments_form_lists_each_part_with_its_instrument():
    _load("hairpins_two_parts.musicxml")
    md = web_api._music_data
    form = web_api.instruments_form()
    json.dumps(form)
    assert [r["name"] for r in form["rows"]] == [p.name for p in md.parts_info]
    assert all(r["kind"] == "part" and r["toggleable"] for r in form["rows"])
    assert form["rows"][0]["sound"] in form["instruments"]
    assert len(form["instruments"]) == 128
    assert form["auto_correct"] is None  # no percussion: the box is not shown


def test_instruments_ok_with_nothing_changed_changes_nothing():
    _load("hairpins_two_parts.musicxml")
    form = web_api.instruments_form()
    assert web_api.instruments_apply(_values(form)) == {"changed": False}


def test_rename_and_reprogram_keep_region_2_state():
    _load("hairpins_two_parts.musicxml")
    md = web_api._music_data
    first = md.parts_info[0].part_id
    web_api.region2_toggle(f"part_{first}", "mute")
    form = web_api.instruments_form()
    values = _values(form)
    values[0]["name"] = "Lead"
    values[0]["sound"] = "Cello"
    result = web_api.instruments_apply(values)
    json.dumps(result)
    assert result["changed"] is True
    assert md.parts_info[0].name == "Lead"
    assert md.parts_info[0].gmidi_program == 43
    assert _part_rows(result)[0] == "Lead muted"
    assert set(result["regions"]) == {"1", "2", "3", "4", "5", "6"}
    assert result["mixer"] == web_api.mixer_levels()


def test_an_empty_name_or_unknown_sound_keeps_the_old_value():
    _load("hairpins_two_parts.musicxml")
    md = web_api._music_data
    name, program = md.parts_info[0].name, md.parts_info[0].gmidi_program
    form = web_api.instruments_form()
    values = _values(form)
    values[0]["name"] = "   "
    values[0]["sound"] = "Kazoo"
    assert web_api.instruments_apply(values) == {"changed": False}
    assert (md.parts_info[0].name, md.parts_info[0].gmidi_program) == (name, program)


def test_flagging_a_part_percussion_rebuilds_region_2_keeping_mute(gp_ripple):
    _load_path(gp_ripple)
    md = web_api._music_data
    web_api.region2_toggle("part_P0", "mute")
    form = web_api.instruments_form()
    bass = [i for i, r in enumerate(form["rows"]) if r["kind"] == "part"][2]  # P2
    values = _values(form)
    values[bass]["percussion"] = True
    result = web_api.instruments_apply(values)
    assert result["changed"] is True
    assert md.is_percussion_part("P2")
    assert web_api._region_2.node("part_P0").muted is True
    # The kit now lists one row per drum after its part row.
    form = web_api.instruments_form()
    kit = [i for i, r in enumerate(form["rows"]) if r["kind"] == "part"][2]
    assert form["rows"][kit]["percussion"] is True
    assert form["rows"][kit + 1]["kind"] == "item"
    assert form["auto_correct"] is not None


def test_key_signature_form_and_apply():
    _load("hairpins_two_parts.musicxml")
    md = web_api._music_data
    form = web_api.key_signature_form()
    json.dumps(form)
    assert form["options"][0] == "Use the file's own key"
    assert form["current"] == 0
    g_major = form["options"].index("G major")
    result = web_api.key_signature_apply(g_major)
    assert result["changed"] is True
    assert (md.key_signature_override_fifths, md.key_signature_override_mode) == (1, "major")
    assert web_api.key_signature_form()["current"] == g_major
    assert web_api.key_signature_apply(g_major) == {"changed": False}
    assert web_api.key_signature_apply(0)["changed"] is True
    assert md.key_signature_override_fifths is None


def test_reorder_moves_region_2_rows_in_place():
    _load("hairpins_two_parts.musicxml")
    md = web_api._music_data
    ids = [p.part_id for p in md.parts_info]
    web_api.region2_toggle(f"part_{ids[1]}", "solo")
    form = web_api.part_order_form(f"part_{ids[1]}")
    assert [r["id"] for r in form["rows"]] == ids
    assert form["current"] == 1
    result = web_api.part_order_apply(list(reversed(ids)))
    assert result["changed"] is True
    assert [p.part_id for p in md.parts_info] == list(reversed(ids))
    assert [n.part_id for n in web_api._region_2.roots] == list(reversed(ids))
    assert _part_rows(result)[0].endswith("soloed")
    assert web_api.part_order_apply(list(reversed(ids))) == {"changed": False}


def test_link_then_unlink():
    _load("hairpins_two_parts.musicxml")
    md = web_api._music_data
    ids = [p.part_id for p in md.parts_info]
    form = web_api.link_parts_form(f"staff_{ids[1]}_1")
    assert [r["id"] for r in form["rows"]] == ids
    assert form["current"] == 1
    assert web_api.region2_menu(f"part_{ids[0]}")["items"] == []
    assert web_api.link_parts_apply(ids[:1]) == {"changed": False}  # one part is not a group
    result = web_api.link_parts_apply(ids)
    assert result["changed"] is True
    assert all(text.startswith("1. ") for text in _part_rows(result))
    assert web_api.link_parts_form()["rows"] == []  # linked parts are left out
    menu = web_api.region2_menu(f"part_{ids[0]}")
    assert menu["items"] == [{"label": "Unlink"}]
    assert menu["title"] == md.parts_info[0].name
    assert web_api.region2_menu(f"staff_{ids[0]}_1")["items"] == []
    result = web_api.region2_unlink(f"part_{ids[0]}")
    assert result["changed"] is True
    assert not any(text.startswith("1. ") for text in _part_rows(result))


def test_saved_link_groups_number_region_2_on_load():
    _load("hairpins_two_parts.musicxml")
    ids = [p.part_id for p in web_api._music_data.parts_info]
    web_api.link_parts_apply(ids)
    saved = web_api.score_settings_json()
    path = FIXTURES / "hairpins_two_parts.musicxml"
    assert web_api.load(path.read_bytes(), path.name, saved)["ok"]
    assert all(row["text"].startswith("1. ") for row in web_api._region_2_rows())


def test_collapse_staves_rebuilds_region_2_and_speaks():
    _load("guitar_alternate_tab_stave.musicxml")
    assert web_api.staves_state(None) == {"enabled": False, "checked": False}
    assert web_api.staves_state("voice_P1_2_5") == {"enabled": True, "checked": False}
    web_api.region2_toggle("staff_P1_1", "mute")
    result = web_api.staves_toggle("voice_P1_2_5")
    json.dumps(result)
    assert result["changed"] is True
    assert result["announce"] == "Staves collapsed"
    assert web_api._region_2.node("staff_P1_2") is None
    assert result["node"] == "part_P1"  # the row it was on is gone
    assert web_api._region_2.node("staff_P1_1").muted is True
    assert web_api.staves_state("part_P1") == {"enabled": True, "checked": True}
    result = web_api.staves_toggle("staff_P1_1")
    assert result["announce"] == "Staves uncollapsed"
    assert result["node"] == "staff_P1_1"
    assert web_api._region_2.node("staff_P1_2") is not None


def test_no_score_is_refused():
    web_api._music_data = None
    for form in (web_api.instruments_form, web_api.key_signature_form,
                 web_api.part_order_form, web_api.link_parts_form):
        assert "error" in form()
    assert web_api.instruments_apply([]) == {"error": "No score is loaded."}
    assert web_api.part_order_apply([]) == {"changed": False}
    assert web_api.region2_menu("part_P1")["items"] == []
    assert web_api.staves_toggle("part_P1") == {"changed": False}
