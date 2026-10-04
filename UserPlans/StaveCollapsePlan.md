# Collapse staves + "playing" code (s2f3g4m)

Step 0 of implementation: before touching any code, capture baseline fingerprints from the current tree (`tests/manual/parser_fingerprint.py` and `model_fingerprint.py`, output to the scratchpad), per `tests/manual/README.md`.

## Context

Classical guitar scores (e.g. `files/The Entertainer - Scott Joplin.mxl`, `files/bach-bourree-tab.mxl`) write every note twice in one part: stave 1 (treble, voice 1) carries the left-hand fingering, stave 2 (TAB, voice 5) carries string and fret. The user has to hop between the two staves to get the full picture of each note, and today playback sounds every note twice.

MusicXML flags the tab stave with `<staff-details number="2"><staff-type>alternate</staff-type>`, which means "the same music as the stave before it, shown differently". It has no note-by-note link, so notes are paired by onset (slice) and pitch.

Agreed UI:
1. Parts menu: a checkable "Collapse staves" item, enabled when Region 2's current row is inside a part with an alternate stave. Checking it hides the alternate stave (row gone from Region 2, notes gone from navigation and playback), and each kept note shows its partner's attributes as well. Unchecking reverses this. Saved per score in the `.rsc`.
2. A new attribute, `playing`, condensed as `s<string>f<fret>g<finger><pluck letters>`, e.g. `s2f3g4m`. Missing pieces are left out (`s2f3`). It is added or removed through the existing Region 4 context menu (voice/stave/part/score scope), with no new menu items. In Region 3 it is spoken unprefixed ("s2f3g4m"). It works on any note with string/fret/fingering/pluck, collapsed or not.

## Design

### Parser: record the alternate stave
* `models/parts_structure.py` `PartStructureInfo`: add `alternate_staves: Dict[int, int]` (alternate staff -> the staff it shadows, i.e. `n -> n-1`).
* `parsers/musicXML_reader.py` (~line 383, beside the clef loop): read `.//attributes/staff-details` with `staff-type` text `alternate`, skipping staff 1.
* Only the MusicXML reader sets it. GP, MIDI and UG leave it empty.

### Model: pairing + collapse state (new collaborator, invariant 4)
* New `models/stave_collapse.py` `StaveCollapse(data)`, which keeps no state about MusicData itself:
  * `collapsible(part_id) -> bool` (part has `alternate_staves`).
  * `partner_for(note) -> Optional[NoteData]`. Builds a lazy map from `id(kept note)` to `alt note` over `data._real_timeline_slices`: in each slice, for each collapsed part, pair kept-stave notes with alternate-stave notes on equal `midi_pitch`, taking the first unused match. Rebuild the map when the collapsed set changes.
* `MusicData`: field `collapsed_stave_parts: Set[str]`, plus one-line delegators `is_stave_collapsible`, `is_staves_collapsed`, `set_staves_collapsed(part_id, on)`, `stave_partner_for`.
* `get_score_structure()` (`models/music_data.py:753`): leave out alternate staves of collapsed parts. Region 2 then has no row for them, so `active_voice_filter` drops those voices, and navigation and playback (`_visible_notes`) follow automatically.
* `export_config` / `apply_config` + `models/score_config_data.py`: new `collapsed_stave_parts: List[str]` field, filtered best-effort against known collapsible parts on restore, like `part_link_groups`.

### Rendering: one choke point
* `models/note_renderer.py` `note_attribute_pairs` feeds Region 3, Region 4 and Find (`find_index.py:143,346`). After building `pairs`:
  * If the note has a partner, add each partner key that is missing from `pairs`, except the identity keys (`step, octave, midi, measure, beat position, duration, part, stave, voice`). This is display-time borrowing: NoteData is never copied into, so there is no second copy of the fact (invariant 8).
  * Then compute `playing` from the merged `string`/`fret`/`fingering`/`pluck` values: `s{string}f{fret}` + `g{f}` for each comma-separated fingering + the pluck letters joined. Fingering `0` is written as is; the user's scores won't contain g0 in practice, and invariant 14 means we report what is written.
* `models/music_data.py:842` `DISPLAY_ATTRIBUTE_ORDER`: insert `"playing"` just before `"string"`. Add `"playing"` to `REGION_3_UNPREFIXED_ATTRIBUTES` (line 908).
* Check that the Attribute Management / Reorder dialog and Find pick the key up with no extra work (per the note_renderer.py:85 comment they should).

### Controller + menu
* `controllers/score_edit_controller.py`: `toggle_staves_collapsed(part_id) -> bool`. It flips the state, clears the pairing map and the Find/visibility caches, calls `presenter.reload_region_2_structure(...)` (keeps mute/solo/links, invariant 11; the same path the percussion flag uses at line 121), then `update_timeline_views(play_all=False)`, then announces "Staves collapsed" / "Staves uncollapsed" through the existing QAccessible announcement path.
* `widgets/menu_builder.py` `_parts_menu`: add checkable `a.collapse_staves` ("Collapse s&taves", checking the mnemonic against `test_no_menu_mnemonic_collisions`) after Link Parts, with no default shortcut.
* Enable and check state: wherever FocusController/MainWindow refreshes Parts-menu enablement for Mute/Solo, also enable `collapse_staves` only when Region 2's current row belongs to a collapsible part, and set it checked from `is_staves_collapsed`. A MainWindow slot does one-line delegation (invariant 5).
* Verify that `load_score_structure` re-emits the Region 2 filter so `active_voice_filter` updates after a rebuild. If it doesn't, push `on_region_2_filter_changed` explicitly.
* Load order: confirm in `controllers/score_persistence.py` that the `.rsc` restore of `collapsed_stave_parts` happens before Region 2 is first built, or rebuild once after.

## Tests
* `tests/models/`: pairing on a small inline MusicXML fixture with an alternate TAB stave (parts_info built directly to avoid the slow path), covering: merged pairs, unmatched note keeps only its own attributes, tie-stop note gives `s2f12` with no g, `playing` formatting (`s2f3g4m`, `s2f3`, multi-pluck), and the collapsed structure dropping the stave.
* Config round-trip for `collapsed_stave_parts`.
* MainWindow test (NullSynth): toggle collapse, assert Region 2 row count, Region 3 text includes fret/string on the treble note, NullSynth records one note per pitch rather than two, and uncollapse restores it.
* Menu enabled/checked follows Region 2's current row.

## Verification
* `.venv\Scripts\python.exe -m pytest` (full suite).
* `tests/manual/parser_fingerprint.py --check` and `model_fingerprint.py --check` against a pre-change baseline. The parser change adds a field, so expect `parts_info` differences only for the 3 alternate-stave files and nothing else.
* Run the app on The Entertainer: Parts > Collapse staves, step through measure 1. In Region 4, add `playing` for the part, and Region 3 should read "E, s1f12g1".
