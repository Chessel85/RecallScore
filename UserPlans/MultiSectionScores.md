# Plan: multi-section MusicXML scores ("Two Flute Exercises")

Implementation plan for Sonnet. Read `CLAUDE.md`, `docs/architecture.md` and
`docs/parsers.md` before starting. Work through the tasks in order; each one
is separately testable and separately committable.

## The problem

`files/Two flute exercises.musicxml` is one MusicXML document holding **two
independent pieces** in a single `<part id="P1">`:

* bars 1-3, C major, 4/4, preceded by a `<words>` direction "Exercise 1";
* bars **1-2 again** (the `<measure number="...">` counter restarts), G major
  (`<fifths>1</fifths>`), 3/4, preceded by a `<words>` direction "Exercise 2".

Today the app treats this as one five-bar score with two bar 1s and two bar 2s.
That is wrong in every region: `End` runs to the end of exercise 2, Region 1
shows exercise 1's key/time for the whole file, and every by-measure lookup
(`Go to bar`, Find, Region 5 jumps) silently resolves a duplicate bar number to
its first occurrence.

## The decision (from the user)

Treat the file as **N separate scores in one file**. The user picks one
section; every other region then behaves exactly as if that section were the
whole file — `End` in the note list with exercise 1 selected lands on the last
note of *its* bar 3; Region 1 shows *its* key and time signature; the
Performance Report covers *it* only. Section 1 is selected by default on load.

## The chosen architecture — and why

**Build one complete, independent `TimelineBuild` per section, keep them all on
`MusicData`, and make "select a section" mean "apply that section's
`TimelineBuild` to `MusicData`".**

The alternative — one timeline carrying every section, filtered at navigation
time — was rejected. Bar numbers repeat across sections, and the builder keys
`measure_start_quarters`, `measure_ts_fifths` and every `first_*_index_of_measure`
cache by bar number; making those section-aware means touching ~40 display sites
that render `slice.measure` (`models/performance_rows.py`, `note_renderer.py`,
the status bar, Region 3's spoken bar announcement) and inventing an
internal-vs-display bar number distinction. That is exactly the "two copies of
the same fact" trap in invariant 8.

With one build per section, the active timeline always has ascending, unique,
file-accurate bar numbers, so **every existing consumer is correct with no
change at all**. The cost is concentrated in two places instead: splitting the
XML (task 1) and rebinding `MusicData`'s timeline-derived caches (task 3).

MIDI, Guitar Pro and Ultimate Guitar scores always produce exactly one section,
so they take the same code path with a one-element list and no visible change.

---

## Task 1 — Split a MusicXML document into sections (`parsers/`)

New module `parsers/score_sections.py`. Pure ElementTree, no music21, no Qt.

**1a. Detect boundaries.** Walk the **first** `<part>`'s `<measure>` children in
document order (the same first-part convention `_scan_first_part` already
uses). A measure starts a new section when it is not the first measure and its
raw `number` attribute is `1` or `0` while the previous measure's raw number was
greater. Use `parsers.timeline_builder._raw_measure_number` — do not re-parse
the attribute here (invariant 8).

Return a list of `(start_ordinal, end_ordinal)` measure ranges. One range means
"not a multi-section score" and every later task must then behave exactly as
today.

**1b. Label each section.** For each section, the label is the first non-empty
`<direction>/<direction-type>/<words>` text in its first measure, `.strip()`ed
and with internal newlines collapsed to a single space (exercise 2's `<words>`
ends with a newline and is followed by a whitespace-only second `<words>` — both
must be handled). Skip a `<direction>` that also carries `<sound tempo=...>` or
a `<metronome>` child: that is a tempo marking, not a title. Fall back to
`<movement-title>` for section 1 only, then to `"Section {n}"`.

The label is **additive**. The `<words>` direction must still be parsed and
reported exactly as it is today (invariant 14 / `feedback_report_what_is_written`)
— do not consume or suppress it.

**1c. Produce a sub-root per section.** For section *k*, build a new
`<score-partwise>` element that reuses (does not deep-copy) the original's
`<work>`, `<identification>`, `<defaults>`, `<credit>` and `<part-list>`
children, plus one `<part>` per original part holding only that section's
measure elements. Reusing the measure elements is safe — nothing in
`TimelineBuilder` mutates the tree.

**1d. Carry forward the attributes the section does not re-declare.** This is
the one genuinely tricky part. Exercise 2's first measure re-declares
`<divisions>`, `<key>` and `<time>` but **not** `<clef>` — the treble clef was
declared once in exercise 1 bar 1. A naive slice loses it.

Walk the original part's measures from the document start up to (not including)
the section's first measure, accumulating the last-seen `<attributes>` children
per staff: `divisions`, `key`, `time`, `staves`, `part-symbol`, `instruments`,
`clef` (per `number`), `staff-details`, `transpose`. Synthesise an
`<attributes>` element from that state and **prepend it as the section's first
measure's first child**. The measure's own `<attributes>` follows it in document
order and therefore overrides it naturally — no merge logic needed.

Mark the synthesised element with an attribute (`recall-score-carried="yes"`)
and have `TimelineBuilder._handle_attributes` skip emitting `ClefChangeMark` /
`MeasureStyleMark` for a carried element — otherwise every section after the
first reports a spurious mid-part clef change in Region 5, Find and the
Performance Report. For section 0 nothing is carried and nothing is prepended,
which is what keeps single-section behaviour bit-identical.

**Tests** (`tests/parsers/test_score_sections.py`): boundary detection on the
new file and on a single-section fixture; label extraction including the
trailing-newline case; the section-2 sub-root having the carried treble clef;
`<work>`/`<part-list>` present in every sub-root.

---

## Task 2 — A section-aware `TimelineBuild` set (`models/`, `parsers/`)

**2a.** New `models/score_section.py`:

```python
@dataclass
class ScoreSection:
    index: int          # 0-based
    label: str          # "Exercise 1"
    build: Any          # models.timeline_build.TimelineBuild
    credits: Dict[str, str]   # per-section Region 1 overrides (task 5)
```

**2b.** In `parsers/timeline_builder_factory.py`, add
`build_sections(music_data) -> List[ScoreSection]`:

* non-MusicXML formats, or a MusicXML file with one section → a single
  `ScoreSection(index=0, label="", build=build_timeline(music_data), credits={})`;
* otherwise one `ScoreSection` per sub-root, each built by running a *fresh*
  `TimelineBuilder(file_path, parts_info, root=<sub-root>)` through
  `TimelineBuild.from_builder`.

`build_timeline()` stays as it is — it is the documented single-build entry
point and the tests use it. `build_sections` sits beside it.

Note that `_detect_pickup` now runs per section, which is correct: a later
section may open with its own pickup bar and gets bar 0 by Ref 17 like any
other score.

---

## Task 3 — `MusicData` holds the sections and can switch (`models/music_data.py`)

**3a. Extract the rebind.** `__post_init__` currently does
`build_timeline(self).apply_to(self)` and then initialises seven
timeline-derived caches that its own comments describe as "never reassigned
after construction" (`_real_timeline_slices`, `_measure_numbers_cache`,
`_tempo_change_starts_cache`, `_chord_context`, `_lyric_context`,
`_context_quarters`, plus `navigator.invalidate_cache()` /
`_invalidate_visibility_cache()`). Move that whole block into

```python
def _adopt_timeline_build(self, build) -> None:
```

called by `__post_init__` and by `set_active_section`. **Every one of those
caches must be reset there** — a missed one is the failure mode of this task
(a stale `_measure_numbers_cache` makes `Go to bar` in section 2 silently jump
into section 1's slices).

**3b. New fields:**

```python
sections: List[ScoreSection] = field(default_factory=list)   # always >= 1 entry
active_section_index: int = 0
```

`__post_init__` calls `build_sections`, stores the list, and adopts
`sections[0].build`.

```python
@property
def has_multiple_sections(self) -> bool: ...
@property
def active_section(self) -> ScoreSection: ...
def set_active_section(self, index: int) -> bool: ...
```

`set_active_section` must, in this order: bounds-check and no-op on an
unchanged index (returning `False`); set `active_section_index`; call
`_adopt_timeline_build`; set `active_event_index = 0`; re-apply the state that
lives on `MusicData` but was baked into the *old* slices' `NoteData` —
`apply_part_overrides`, `apply_percussion_overrides`,
`apply_key_signature_override`, `_set_percussion_voice_names`, and
`set_metronome_enabled(self.metronome_enabled)` so the beat markers get spliced
into the new timeline. Return `True`.

`active_voice_filter`, `voice_display_attributes` and `mixer` are keyed by
`(part_id, staff, voice)` / part id, which are whole-file facts, so they carry
across a switch untouched — only the caches they feed need dropping, which
`_adopt_timeline_build` does.

**3c. Persistence.** Do **not** persist the selected section in the `.rsc`.
Every load starts at section 1 (`feedback_simplicity_over_stateful_features`).
`last_position_index` is already bounds-checked against `timeline_slices` in
`apply_config`, so a stale index from a differently-sectioned file is dropped,
not misapplied.

**Tests** (`tests/models/test_score_sections.py`, built with
`MusicData(file_path=...)` so they stay on the ~1 ms ElementTree path):

* two sections detected, labelled "Exercise 1"/"Exercise 2";
* section 0: `measure_numbers() == [1, 2, 3]`, `total_measures == 3`, `End`
  lands on the whole-note C5 in bar 3, first slice `time_sig == (4, 4)` and
  `key_fifths == 0`;
* section 1: `measure_numbers() == [1, 2]`, `time_sig == (3, 4)`,
  `key_fifths == 1`, the clef carried forward, `End` lands on the dotted half
  G5;
* switching back to section 0 restores all of the above (proves the caches are
  dropped);
* an existing single-section fixture has `len(sections) == 1` and
  `has_multiple_sections is False`.

---

## Task 4 — Controller wiring (`controllers/`)

The section is score state, so it belongs to `ScoreSession`/a controller, not
to `MainWindow` (invariant 5).

Add to `controllers/navigation_controller.py` (it already owns cursor
movement and the `Go to bar` flow):

```python
def select_section(self, index: int) -> bool
def step_section(self, delta: int) -> bool     # for Left/Right on the Region 1 row
```

`select_section` calls `music_data.set_active_section`, and on `True`:

* refreshes **every** region through `RegionPresenter` — Region 1
  (`refresh_region_1`), Region 3/4/5 via the normal
  `update_timeline_views(...)` path, and the status bar;
* calls `presenter.reset_performance_labels()` first, so Region 5 is not
  diffed against the previous section's rows and the "None" placeholder
  renders correctly;
* announces the new section with `widgets/accessible_announcer.py`
  ("Exercise 2, section 2 of 2") — a `QAccessible` event, never text baked
  into a widget (`feedback_accessible_announcements`);
* leaves the audition to the normal `update_timeline_views` path, so landing
  on the section's first note sounds like any other jump.

---

## Task 5 — Region 1 presents and owns the choice (`widgets/`, `controllers/region_presenter.py`)

Region 1 gains a **`QTabBar`** above its existing property list, one tab per
section, labelled with the section labels ("Exercise 1", "Exercise 2"). A tab
bar is the control that already means "one of N views of the same information",
and NVDA reports it natively — "Exercise 1, tab, 1 of 2" — with Left/Right
switching, so there is no invented key convention and no explanatory row for
the user to read past. The count comes from the control rather than from a
formatted string.

**5a. The widget.** A bare `QTabBar`, **not** a `QTabWidget`. There is one
property list, repopulated on the tab bar's `currentChanged`; a `QTabWidget`
would mean N copies of the same rows and N focus targets. In `main_window.py`,
the existing `_titled_region(self.region_1, "Score information")` box gets a
`QVBoxLayout` holding the tab bar then the list.

Give Region 1 a small container class rather than wiring the bar into
`MainWindow` ad hoc — `widgets/region1_panel.py`, holding the `QTabBar` and the
`Region1ListWidget`, exposing `set_sections(labels, current_index)`,
`refresh_list(data)` and a `section_selected = Signal(int)`. `RegionPresenter`
then still talks to one object for Region 1 (invariant 6), and
`region1_list_widget.py` stays behaviour-free.

**5b. Hidden for a single-section score.** `set_sections` with fewer than two
labels calls `tab_bar.setVisible(False)`, so an ordinary file's Region 1 looks
and behaves exactly as it does today — same rows, same single focus target, no
extra stop in the focus order.

**5c. Focus.** With the bar visible, Region 1 contains two focusable widgets:
the tab bar first, then the list. Three things follow.

* `RegionFocusCycleMixin` is the single owner of Tab/Shift+Tab (invariant 7).
  The tab bar must not swallow Tab — give it the same
  `Qt.FocusPolicy.TabFocus` treatment the regions already get, and confirm the
  region cycle steps Region 1 → Region 2 from *either* child. Test by driving
  `widget.event(...)` and asserting the cycle method runs, not just where focus
  lands.
* `Z` (the direct jump to Region 1, `main_window.py` line ~609/996) must land
  on the tab bar when it is visible, and on the list when it is not.
* Qt's tab bar also answers Ctrl+PageUp/PageDown. Harmless; leave it.

**5d. Switching.** Connect `QTabBar.currentChanged` to
`Region1Panel.section_selected`, and that in `MainWindow` to
`NavigationController.select_section` (wiring in the window is correct; the
logic is not). Note that `currentChanged` fires when *`set_sections` itself*
sets the current tab on load — block signals across that call, or the load path
will re-enter `select_section` and reset the cursor a second time.

`QTabBar`'s own Left/Right arrows stop at the ends rather than wrapping, which
matches Ref 6's boundary behaviour at the ends of the timeline; nothing extra
to implement, and no boundary cue is needed for a control that announces its
own position.

**5e. Per-section Region 1 values.** `credits` is whole-file, parsed once by
`MusicXMLReader`. With multiple sections, override `"Key Signature"` and
`"Time Signature"` from the **first slice of the active section**
(`EventSlice.key_fifths` / `.time_sig`, via
`models.key_signatures.key_signature_display_name` and the existing time
signature formatting), using the same "rebuild live, don't touch the parsed
original" pattern `get_region_1_data` already applies to `Tempo` and the S6 key
override. Title and Composer stay whole-file. If the active section's build has
its own opening tempo different from the file's, override `Tempo` the same way.

No "Section: ..." row is added to the property list — the tab bar is the
display as well as the control, and a row restating it would be the second copy
of the same fact.

**5f. Menu.** Add `Navigation > Select Section...` in `widgets/menu_builder.py`,
next to `goto_measure`, disabled when `has_multiple_sections` is `False`. It is
not redundant with the tab bar: it gives a keyboard route to the choice from
any region without first jumping to Region 1. Implement it as "move focus to
the Region 1 tab bar", not as a modal dialog — with the tab bar present, a
select dialog has nothing left to do.

**5g. The announcement.** Because the tab bar announces itself when focused and
arrowed, the explicit `QAccessible` announcement in task 4 risks doubling up
(the same double-speech trap documented in `RegionPresenter.update_timeline_views`).
Make task 4's announcement conditional: skip it when the change came from the
tab bar itself, keep it when the change came from elsewhere. Live-test which
reads better before settling it.

**Tests**: `tests/test_main_window_navigation.py` — the tab labels for the new
file; `setCurrentIndex(1)` switching section and changing Region 3's content;
the tab bar hidden and the focus order unchanged for a single-section fixture;
the region focus cycle stepping out of Region 1 from both children; loading a
file not double-firing `select_section`.

---

## Task 6 — Sweep the section-unaware corners

With the active-build design, most things are already correct. Verify (with a
test each) rather than assume:

* **Region 2** — `parts_info` is whole-file, so a part appearing in only one
  section still lists. That is acceptable and intended: a part is a property of
  the file. Just confirm the filter still applies after a switch.
* **Playback / `audio/sequencer.py`** — bounded by `sounding_bounds()` over
  `timeline_slices`, which is now the section's, so play-to-end stops at the
  section end. Confirm with a test using `tests/support/null_synth.py`.
* **Find**, **Performance Report**, **Region 5**, **status bar**,
  **`Go to bar`** — all read `MusicData`'s active lists; confirm each is scoped
  to the section, especially that `Go to bar 1` in section 2 lands in section 2.
* **`File > Close` and loading a second file** — `MusicData` is replaced
  wholesale (invariant 3), so `sections` goes with it; confirm nothing caches a
  `ScoreSection`.

---

## Task 7 — Acceptance gate

`parsers/` and `models/` both change, and for every existing single-section
score the change is meant to be **exactly** behaviour-preserving. "The tests
pass" is not evidence for that. Run the fingerprint harnesses per
`tests/manual/README.md`:

```powershell
# from a worktree at the pre-change revision
.venv\Scripts\python.exe tests\manual\parser_fingerprint.py
.venv\Scripts\python.exe tests\manual\model_fingerprint.py
# then, on the branch
.venv\Scripts\python.exe tests\manual\parser_fingerprint.py --check
.venv\Scripts\python.exe tests\manual\model_fingerprint.py --check
```

`files/Two flute exercises.musicxml` is inside the harness corpus, so it will
now fingerprint as section 1 only — that one file is an **expected** diff and
the only one permitted. Every other file must be identical.

Then the suite, and a live run:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe main.py
```

Live check with the real file: open it, hear "Exercise 1" in Region 1, `End` in
Region 3 stops on bar 3's whole note, switch to Exercise 2 from Region 1, hear
the announcement, confirm Region 1 now reads G major / 3/4 and `Home`/`End`
cover only its two bars.

---

## Suggested commit sequence

1. `parsers/score_sections.py` + carried-attributes suppression + its tests.
2. `models/score_section.py`, `build_sections`, `_adopt_timeline_build`,
   `set_active_section` + model tests.
3. Controller + `Region1Panel` tab bar + menu + window tests.
4. Fingerprint baselines re-captured, if and only if step 1-3 diffs are
   confined to the new file.

## Open questions worth confirming with the user before task 5

* Should the section label also appear in the status bar? The plan says no —
  Region 1 owns it, and the status bar is already dense.
