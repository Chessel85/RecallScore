# Turn attributes and performance-indicator categories off by default

## Context

Region 3's inline note text and Region 5's note-list marking categories
currently start with a curated set of extras switched **on** by default
(`MusicData.DEFAULT_DISPLAY_ATTRIBUTES` for attributes; an empty
`marking_categories_off` — meaning "every category on" — for performance
markings). The user has changed their mind on this design decision and now
wants a quieter starting point: nothing extra surfaces in the note list until
the user deliberately switches it on, via the existing Region 4
context-menu/Reorder-Attributes-dialog toggles (attributes) or Ctrl+N
(marking categories). Clarified with the user: the plain note name/pitch
("step") stays on — that's the baseline "notes rendered as spoken-friendly
text" accessibility guarantee, not an optional extra — only the additional
attribute kinds and marking categories go off.

The "Show Engraving Details" toggle (`show_engraving_details_enabled`) is
already off by default and needs no change.

## Changes

### 1. `models/music_data.py` — attribute default

Change the constant at `music_data.py:859-862`:

```python
DEFAULT_DISPLAY_ATTRIBUTES = frozenset({
    "step", "dynamic", "articulation", "ornament", "slur",
    "arpeggio", "glissando", "technique", "other notation",
})
```

to:

```python
DEFAULT_DISPLAY_ATTRIBUTES = frozenset({"step"})
```

Rewrite the explanatory comment block above it (`music_data.py:836-858`,
currently justifying the *widened* PI-tweaks-stage-5 default) to instead
explain that only "step" (the plain note name) is on by default now — every
other attribute, including the performance ones previously widened in, is
off until the user switches it on via the Region 4 context menu or the
Reorder Attributes dialog's Add/Remove button.

No change needed to `note_renderer.py` (`attributes_for_voice`,
`apply_display_attribute`) — both already fall back to
`DEFAULT_DISPLAY_ATTRIBUTES` generically, and "keep showing the plain note
name" (the comment at `note_renderer.py:349-351`) is still satisfied by
`{"step"}`.

### 2. `persistence/app_settings.py` — marking category default

Add `from models import marking_categories` to the imports.

Change the dataclass field default at `app_settings.py:80`:
```python
marking_categories_off: List[str] = field(default_factory=list)
```
to default to every category off:
```python
marking_categories_off: List[str] = field(
    default_factory=lambda: list(marking_categories.ALL_CATEGORIES)
)
```

Change the `load()` fallback at `app_settings.py:115` from
`data.get("marking_categories_off", [])` to
`data.get("marking_categories_off", list(marking_categories.ALL_CATEGORIES))`
— this is what makes a settings.json that predates this field (or a freshly
deleted one) pick up "all off" rather than "all on".

Update the doc comment at `app_settings.py:59-63` describing
`marking_categories_off` as "the global default for a score that has never
had its own .rsc written yet" to state the new default is every category
off, not on.

`show_engraving_details_enabled` (`app_settings.py:81`, already `False`) is
unchanged.

No change needed in `main_window.py:876-880` — it already seeds
`music_data.marking_categories_off` straight from `app_settings.load()`, so
it picks up the new default automatically.

### 3. Existing local settings.json (this machine)

`C:\Users\chess\AppData\Local\Recall Score\settings.json` already has
`"marking_categories_off": []` and `"show_engraving_details_enabled": false`
baked in from a previous save, so the code default change alone will not
change this machine's *existing* behaviour (the key is present, so
`load()`'s fallback is never consulted). Update that JSON file's
`marking_categories_off` list directly to contain every entry from
`models.marking_categories.ALL_CATEGORIES` so the new default takes effect
immediately without deleting the rest of the file's settings (recent files,
shortcuts, etc.). This is a local runtime file, not source-controlled, and
fully reversible from within the app (Ctrl+N per category).

### 4. Test updates

Run the full suite after the above changes and fix fallout. Expected shape,
based on inspection:

- `tests/models/test_music_data.py` — several tests build their expected
  value as `MusicData.DEFAULT_DISPLAY_ATTRIBUTES | {"octave"}` /
  `MusicData.DEFAULT_DISPLAY_ATTRIBUTES - {"step"}` (lines ~1364-1437); these
  reference the constant symbolically and should keep passing unchanged, but
  their docstrings (e.g. "PI tweaks stage 5 widened DEFAULT_DISPLAY_ATTRIBUTES
  beyond just step", lines ~1322-1326, ~1429-1431) are now stale and should
  be rewritten to describe the reverted default.
- `tests/test_main_window_attributes.py:197-214` — docstring at line 200-203
  references the old widened default; check this test and any sibling test
  using the `dynamics_articulation_fingering_score` fixture for an assertion
  that assumed "dynamic" reads as already-present (Remove wording) by
  default — that assumption no longer holds and the test/fixture usage needs
  updating to match "dynamic" now being off by default too.
- `tests/models/test_stage5_marking_rows.py`,
  `test_linked_parts_marking_rows.py`, and the `ScoreConfig`-round-trip tests
  in `test_music_data.py` (~3236-3371) all set `marking_categories_off`
  explicitly on the `MusicData`/`ScoreConfig` instance under test rather than
  relying on `AppSettings`'s default, so they should be unaffected — confirm
  with a full test run rather than assuming.
- `tests/persistence/test_app_settings.py` has no existing assertion on the
  `marking_categories_off` default — add one covering `load()` with no
  existing file (or a file missing the key) returning every
  `ALL_CATEGORIES` entry, mirroring how `show_engraving_details_enabled`'s
  off-default would be tested if it were.

## Verification

1. `.venv\Scripts\python.exe -m pytest` — full suite must pass after the
   test updates above.
2. Run the app (`runapp` skill) against a score with dynamics/articulation/
   slurs etc., confirm Region 3 reads only the plain note name by default,
   and that switching an attribute on via Region 4's context menu (or the
   Reorder Attributes dialog) still works and persists to the score's
   `.rsc`.
3. Confirm Region 5 / the note list shows no marking-category rows by
   default on a fresh score, and that Ctrl+N still toggles a category back
   on and persists both to `AppSettings` (global) and the score's `.rsc`.
