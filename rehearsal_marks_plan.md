# Plan: Surface rehearsal marks

## Progress (2026-09-07)

Committed this plan for continuity across a `/clear`. Work started, uncommitted in the
working tree (`parsers/timeline_builder.py`):

- [x] Step 1 helper: `_rehearsal_stave_text_label()` added after `_is_qualifying_stave_text`.
- [x] Step 2b: `_stave_text_staves_for_part` now also scans `direction-type/rehearsal`
      (added a nested `_staff_of` helper).
- [ ] Step 1 empty-skip + Step 2a stave-text fabrication in `_step_direction_marks`
      (rehearsal branch), plus adding `sink` to its signature and updating the lone call
      site at `_handle_direction` (~line 986/1002 now).
- [ ] Step 3: Region 5 one-shot row in `models/music_data.py`.
- [ ] Tests + fixtures.
- [ ] Manual fingerprint re-baseline.

## Context

`files/Long tune.mxl` contains **three rehearsal marks — A, B, C at bars 12, 24, 36**
(confirmed by reading the file directly). Bar 24's `<direction-type>` also holds a stray
empty `<rehearsal></rehearsal>` sibling (a MuseScore export quirk), which currently
produces a spurious 4th `DirectionMark` with an empty label and a blank line in the
Performance Report.

The user wants rehearsal marks surfaced three ways: searchable in Find, readable in the
note list as stave text, and reachable via Alt+Left/Right stepping. Investigation shows
this is **already largely consistent with the app** and **partly built**:

- Rehearsal marks already parse to `DirectionMark(kind="rehearsal", label=...)` and are
  already a Find marking target (`"rehearsal"` in `MARKING_KINDS`), so they already show
  as `Marking: Rehearsal mark, N occurrences` in the Find dialog, and **Alt+Left/Right
  already steps any armed Find target** (`NavigationController.find_next/find_previous`).
- They already appear in the Performance Report (`Rehearsal marks: N` + per-mark lines).
- They do **not** appear in Region 3 (only `<words>` directions feed the Stave Text voice).
- They have **no Region 5 row**.

User-confirmed decisions:
1. **Jump navigation:** rely on existing Find (no new nav command / keybinding).
2. **Region 5:** add a one-shot row (`Rehearsal mark A: measure 12`), like the existing
   tempo / time-signature one-shot rows.
3. **Stave text label:** `Rehearsal mark A`.

Outcome: navigating onto bar 12/24/36 reads "Rehearsal mark A/B/C" in the note list;
Region 5 shows a one-shot rehearsal row there; Find and the Performance Report report a
clean count of 3 (empty mark dropped).

### Out of scope (noted, not fixed here)
- `files/Long tune.mxl` is plain uncompressed XML with a `.mxl` extension, so it currently
  fails to load (`.mxl` is treated as a zip). The loadable copy is
  `files/mscz/long tune.mxl`. This is a data/packaging issue, separate from this feature.
- User guide (`docs/user_guide.md`) is not touched (no explicit request).

## Implementation

### 1. Drop empty-label rehearsal marks — `parsers/timeline_builder.py`

New module-level helper, right after `_is_qualifying_stave_text` (~line 116):

```python
def _rehearsal_stave_text_label(rehearsal_el) -> Optional[str]:
    """Printed rehearsal text ("A", "12") when it should become a Stave Text
    event, else None (empty after strip, or a pure SMuFL glyph). The same bar
    _is_qualifying_stave_text applies to <words>. Both _stave_text_staves_for_part
    (the reader's voice-creation scan) and TimelineBuilder call this one detector
    so they cannot disagree on which marks count."""
    text = (rehearsal_el.text or "").strip()
    if not text or _is_pure_smufl_glyph_text(rehearsal_el.text):
        return None
    return text
```

In `_step_direction_marks`, the `elif tag == "rehearsal":` branch (~lines 1027-1038):
compute `label = _rehearsal_stave_text_label(dt_child)`, `continue` when `None`, then
append the `DirectionMark` using that `label` (instead of `(dt_child.text or "").strip()`).

The `label = f" {mark.label}" if mark.label else ""` guard in
`get_performance_report_lines` (~1560-1565) becomes dead but harmless — leave it.

### 2. Region 3 stave text + Region 2 voice row

**2a. Fabricate the stave-text note in `_step_direction_marks`.** It already has every
local needed except `sink` (`m_num`, `offset_q`, `beat_pos`, `walker`, `staff`; `NoteData`
and `STAVE_TEXT_VOICE_ID` already imported). Add `sink` to the signature
(`_step_direction_marks(self, elem, part_state, measure_state, sink, measure_start_quarters)`
— mirrors `_handle_direction`'s own order) and update the single call site
(`parsers/timeline_builder.py:986`).

In the rehearsal branch, after appending the `DirectionMark`:

```python
sink.add(
    measure_state.key_for(offset_q),
    NoteData(
        step_name=f"Rehearsal mark {label}", octave=None, midi_pitch=None,
        measure=m_num, beat_position=beat_pos,
        ts_duration=float(walker.ts_num),
        quarter_length=part_state.full_bar_quarters,
        part_id=part_state.part_id, part_name=part_state.part_name,
        staff=staff, voice=STAVE_TEXT_VOICE_ID,
    ),
    walker, overwrite_state=False,
)
```

Per-child loop + the empty-skip handles bar 24 cleanly: only "B" emits a mark + note.
No rendering change needed — `note_renderer.py` already routes `voice == STAVE_TEXT_VOICE_ID`
into the unprefixed `{"text": ...}` path and `_pitch_sort_key` already sorts it first.

**2b. Region 2 voice row — extend `_stave_text_staves_for_part`** (~lines 119-136) to also
scan `direction-type/rehearsal`, adding the `<staff>` of any `<direction>` whose
`_rehearsal_stave_text_label(...)` is non-`None`. No change in `musicXML_reader.py` — it
already loops `_stave_text_staves_for_part(part_elem)` to insert `STAVE_TEXT_VOICE_ID` at
index 0, name it, and set `voice_display_attributes[(part_id, staff, 1000)] = {"text"}`.
Update the helper's docstring to mention `<rehearsal>`.

### 3. Region 5 one-shot row — `models/music_data.py`

In `get_performance_region_rows`, immediately after the `other_direction` loop (~line 1085,
before the "Plain-text dynamics / tempo instructions" block — keeps all `direction_marks`
rows contiguous, in the documented D12 slot):

```python
for mark in self.direction_marks:
    if mark.kind != "rehearsal" or mark.measure != slice_.measure:
        continue
    rows.append(
        PerformanceRegionRow(
            label=f"Rehearsal mark {mark.label}: {bar_word} {mark.measure}",
            jump_target_measure=mark.measure,
        )
    )
```

`bar_word` is already bound (~line 928, lowercase here — `measure`/`bar`). Point-mark gate
(`== slice_.measure`), like `other_direction` / barline rows. No part-name prefix (matches
the Performance Report's rehearsal lines; rehearsal marks are score-level landmarks).
`jump_target_measure` only → Ctrl+Home/Ctrl+End resolve via
`first/last_visible_event_index_of_measure`. `region_presenter.refresh_region_5` needs no
change — its label-list diff picks the row up and fires the change cue once on entry.

## Tests

**Fixtures**
- `tests/fixtures/rehearsal_mark.musicxml` — rewrite the header comment (drop "no Region 5
  row"; note the Stave Text event, the Region 2 voice row, the one-shot Region 5 row). Add
  a bare second part `P2` (two 4/4 bars, no `<direction>`) as the cross-contamination guard.
- `tests/fixtures/rehearsal_mark_empty.musicxml` — new: one part, one bar, a `<direction-type>`
  with `<rehearsal>C</rehearsal><rehearsal></rehearsal>` (the bar-24 shape).
- `tests/conftest.py` — update `rehearsal_mark_score` docstring; add `rehearsal_mark_empty_score`.

**`tests/models/test_timeline_characterisation.py`**
- Extend `test_p3_rehearsal_marks_keep_their_printed_label`: P1 stave-text step names ==
  `["Rehearsal mark A", "Rehearsal mark B"]`; `P2` has none.
- New `test_rehearsal_mark_fabricates_a_stave_text_event` (near the stave-text cluster,
  ~line 1010): silent (`midi_pitch is None`), sorts first in its slice.
- New `test_empty_rehearsal_mark_is_skipped` (uses `rehearsal_mark_empty_score`):
  `direction_marks` == `[("rehearsal", "C", 1)]`, exactly one stave-text note.

**`tests/parsers/test_musicxml_reader.py`**
- New `test_reader_adds_a_stave_text_voice_for_a_rehearsal_only_part` (mirror the existing
  `..._to_the_real_part_that_carries_it`): `p1.staves_voices[1][0] == STAVE_TEXT_VOICE_ID`,
  named, `voice_display_attributes[("P1", 1, STAVE_TEXT_VOICE_ID)] == {"text"}`, and `P2`
  did not get the voice.

**`tests/models/test_music_data.py`**
- `test_p3_rehearsal_marks_findable_and_reported` — stays green.
- New `test_p3_rehearsal_mark_gets_a_region_5_one_shot_row`: at the bar-1 index,
  `"Rehearsal mark A: measure 1"` is in the row labels (lowercase — Region 5 convention);
  bar-2 index gives `"Rehearsal mark B: measure 2"`; row `jump_target_measure` == mark
  measure, `jump_target_quarters is None`.
- New `test_empty_rehearsal_mark_excluded_from_report` (uses `rehearsal_mark_empty_score`):
  `"Rehearsal marks: 1"` present, no blank-label rehearsal line.

**Manual fingerprint re-baseline (acceptance gate, not pytest — see `tests/manual/README.md`)**
Both `tests/manual/parser_fingerprint.py` and `model_fingerprint.py` will legitimately
differ (new stave-text notes, new `staves_voices` entries, new Region 5 rows / report
lines, changed Find occurrence lists) for every rehearsal-bearing score in
`files/`/`examples/`/`tests/fixtures/`. Capture a pre-change baseline via the git-worktree
workflow, then `--check` after and confirm only rehearsal-bearing scores differ, only as
expected. Call this out in the PR description.

## Verification

- `.venv\Scripts\python.exe -m pytest -q` — whole suite green (new + updated tests).
- Manual: run the app (`runapp` skill), open `files/mscz/long tune.mxl`.
  - Navigate to bar 12 → Region 3 note list reads "Rehearsal mark A"; Region 5 shows
    "Rehearsal mark A: measure 12". Repeat for bars 24 (B) and 36 (C).
  - Region 2 shows a "Stave Text" voice row under the part.
  - Ctrl+F → "Marking: Rehearsal mark, 3 occurrences" (not 4); OK jumps to bar 12;
    Alt+Right / Alt+Left step B ↔ A ↔ C.
  - Edit > Performance Report → "Rehearsal marks: 3" with A/B/C lines, no blank line.

## Critical files

- `parsers/timeline_builder.py` — helper, empty-skip, stave-text fabrication, signature
- `parsers/musicXML_reader.py` — no change (verify `_stave_text_staves_for_part` pickup)
- `models/music_data.py` — Region 5 one-shot row
- `tests/fixtures/rehearsal_mark.musicxml` (+ new `rehearsal_mark_empty.musicxml`),
  `tests/conftest.py`, `tests/models/test_timeline_characterisation.py`,
  `tests/parsers/test_musicxml_reader.py`, `tests/models/test_music_data.py`
