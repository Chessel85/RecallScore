# Parsers: per-format detail

Read the section for the format you are touching. The invariants that apply
across all formats are in `CLAUDE.md`; this file is the detail behind them.

## Shared conventions

**One source of truth per format.** Each format has a `*_source.py` module that
turns a path into a typed object, shared by that format's reader and its timeline
builder (`MusicData.xml_root` / `.midi_source` / `.gp_source` / `.ug_source`) so
the two can never independently re-walk the input and drift.

**The R5 bug class.** Two independent reads of the same fact WILL diverge. It
happened for real: a non-ASCII `<part-name>` (a MuseScore export with a Korean
instrument name) was replaced by `_extract_part_structure_etree` with a hardcoded
`"Classical Guitar"` fallback while `TimelineBuilder` kept the real text, and the
Performance Report — which joins `parts_info.name` against `note.part_name` by
exact text — showed "0 notes" for a fully-noted part. Whenever two places need
the same fact, share one function; don't write the fact twice.

**`parsers/timeline_builder_factory.py`** (`builder_for`/`build_timeline`) owns
format dispatch; **`models/timeline_build.py`** (`TimelineBuild`) owns the
contract. `TimelineBuild.apply_to(music_data)` is the single assignment site for
all twelve builder outputs, so a field added to a builder but forgotten here
can't silently read as a default.

**`MusicData.__post_init__` imports the factory function-locally, deliberately.**
That is what keeps the `MusicData(file_path=...)` shortcut (the ~1 ms ElementTree
path timeline tests rely on) working while deferring the parser/music21 cost to
the moment a file is actually parsed. Don't "tidy" that import up to module
scope; it reinstates both the layering inversion and the import cost.

---

## MusicXML

### `parsers/xml_source.py`

`read_musicxml_root(file_path)` — the single place a path becomes a root
`Element`. Handles compressed `.mxl` (a zip container) by reading
`META-INF/container.xml`'s `rootfile` entry rather than guessing a member name:
every real `.mxl` seen internally names that member `score.xml` regardless of the
outer filename, so the manifest has to be read, not assumed.

### `parsers/musicXML_reader.py`

`MusicXMLReader` builds header/metadata: credits, key, time signature, tempo,
per-part structure (staff-to-clef, staff-to-voices, GM program). It parses the
file **twice**: raw `ElementTree` for credits/part-list/clefs, and
`music21.converter.parse` for tempo/key/time, with the ElementTree values as
fallback when music21 returns nothing.

`_extract_part_structure_etree`'s `<part-name>` read populates
`PartStructureInfo.name`, and **`TimelineBuilder` derives `NoteData.part_name`
from that same `parts_info`** (R5, `TimelineBuilder._part_names`) rather than
re-reading the XML. `TimelineBuilder` keeps an ElementTree fallback only for the
no-reader path (`MusicData(file_path=...)` built directly by timeline tests,
which has no `parts_info` at all).

### `TimelineBuilder.build()`'s structure

`build()` is 84 lines showing only the shape of the walk (part, then measure,
then element), dispatching each measure child to the handler that owns it:

* **`_handle_direction`** — dynamics (deferred to a note at the same offset),
  stave text (bucketed immediately), wedges, plain-text dynamics/tempo words.
* **`_handle_harmony`** — the Chords entry plus the sticky chord.
* **`_handle_note`** — the note plus what rides along with it (a lyric, a
  Chords-part stroke), calling **`_read_pitch`** (`<pitch>`/`<unpitched>` to
  name/octave/sounding key/percussion voice override) and **`_read_notations`**.
* **`_flush_pending_grace`** and **`_assemble_slices`** close out.

**Three small state objects** carry what must survive between elements:
**`_PartState`** (divisions/time signature/key carried forward, the sticky
current chord, `harmony_notes_by_key`), **`_MeasureState`** (reset per measure:
the offset walker, `pending_dynamics`, `pending_grace`), and **`_NoteSink`** (the
`(measure, offset)` buckets plus each slice's time signature and key).

**`_NoteSink` is the one place that writes both `buckets` and `slice_state`.** Its
`overwrite_state` flag preserves two distinct conventions: a real note stamps its
slice's state unconditionally, while stave text and harmony entries only
`setdefault` (they are `<measure>` children that can precede the notes they sit
with). `append_only` is for a note riding along with one already bucketed there.

**`_PartState.beat_position`** is the single copy of the "pickup bars start at the
end of a notional bar" calculation (previously duplicated across notes, stave
text and harmony). **`refresh_bar_shape` deliberately does not write back to
`time_sig_num`/`time_sig_den`** — those exist only to seed the next measure's
walker, and `carry_forward` is the single place that sets them. Keeping the two
roles apart is what preserves R17's "mid-measure `<attributes>` affects offsets
after it, but measure *length* comes from the barline" split.

### Synthetic Chords/Lyrics parts from `<harmony>`/`<lyric>`

A real notated MusicXML score with chord symbols and lyrics (e.g. a MuseScore
lead-sheet export) gets the same "an instrument called Chords" / "lyrics are also
a part" UX established for Ultimate Guitar import, but bucketed into the SAME
slices as the real notated part (real measure/beat positions already exist here,
unlike UG's fabricated ones).

Identifiers live in `models/synthetic_parts.py`; `has_harmony_elements(root)` and
`has_lyric_elements(root)` live in `timeline_builder.py` and are imported into
`_extract_part_structure_etree` — one shared source, not two independent reads.
`MusicXMLReader` adds the two `PartStructureInfo` entries **only when the file
actually has the markup**, with one staff and one voice each — **not zero**: a
part with no staff/voice nodes is invisible to
`Region2HierarchyModel.get_active_voice_tuples()`.

**Chord resolution.** A `<harmony>`'s root/kind/bass resolves to MIDI pitches and
a display label ("G7", "F/C") via `music21.harmony.ChordSymbol(root=..., kind=...,
bass=...)`, accepting MusicXML's own `kind` vocabulary directly, with a
bare-root-triad fallback and finally the label alone with no `chord_pitches` — a
malformed `<kind>` shouldn't make the whole bar's chord entry vanish.

**`models/vocabulary.spell_out_minor_chord`.** A chord label's minor abbreviation
is usually a bare trailing "m" ("Am", "Am7") — NVDA reads that as the letter "m",
not the word "minor", while every other abbreviation seen in practice (`Cmaj7`,
`Dsus4`, `C7`, bare `G`) already reads correctly. A regex (root + accidental, "m"
not followed by "aj" so `Amaj7` is untouched, optional extension digits, optional
`/bass`) rewrites just that case. `AmM7` is deliberately left unhandled. It lives
in `models/vocabulary.py` because three independent chord-symbol sources need it
and share no other code: MusicXML `<harmony>`, UG's raw `[ch]` markup, and Guitar
Pro's chord diagram name.

**Lyrics.** A `<lyric>`'s `<text>` becomes a Lyrics-part `NoteData` in the same
`(measure, offset)` bucket as the melody note it came from — silent by design
(`midi_pitch=None`), and simply absent (not a `"No lyrics"` placeholder) where a
note has no `<lyric>` child, since real per-note timing already exists here.

**Arpeggiate on a single note = a strum direction.** A
`<notations/arpeggiate direction="up"/"down">` on a non-chord note has no real
notation meaning, so it is read as a pick/strum-direction indicator reusing
`NoteData.strum`'s "down stroke"/"up stroke" vocabulary.

The mark produces an extra **Chords-part stroke `NoteData`**, never a change to
the melody note — "strumming does not take place on a piano... strumming is for
guitars and would be associated with the chord instrument" (the user's framing).
`TimelineBuilder.build()` tracks a per-part sticky "current chord" (pitches plus
label, updated on each `<harmony>`), and an arpeggiate mark emits a stroke at
that beat carrying the sticky chord's pitches/label plus its own `strum`. A
stroke with no chord known yet is skipped rather than fabricating one.
Sticky-chord state is scoped **per part, not per document** — interleaving across
multiple parts would need cross-part time-ordered measure walking that
`TimelineBuilder` doesn't do.

**Deduplication:** `harmony_notes_by_key` (a `(measure, offset)` to `NoteData`
map, scoped per part) means a stroke landing where a `<harmony>` already sits
sets `.strum` on the SAME `NoteData` instead of appending a near-identical second
row.

`MusicXMLReader.load()` defaults the Chords part's `voice_display_attributes` to
`{"step", "beat position", "strum"}` (audible immediately); the real Piano voice
stays at `{"step"}`. Both synthetic parts sort after every real part in a slice's
pitch order.

**Region 2 collapse for these two parts only.** "Chord chart" and its fake "Voice
1" are exactly the made-up layers the app already hides for GP/UG's synthetic
parts, but a real score's real instruments still deserve their tree. So
`collapse_to_parts` (`Region2HierarchyModel`, `build_from_score`,
`Region2ListWidget.load_score_structure`) is `Union[bool, Set[str]]`: `True`
collapses every part (MIDI, pure UG import), a `Set[str]` collapses only those
part_ids. `MusicData.collapsed_part_ids` is the single computed value both cases
resolve to. The full part/staff/voice tree is still built underneath either way.
The same check trims Region 4's attribute context menu
(`controllers/attribute_controller.py`): a part with no real stave/voice concept
no longer offers "current voice"/"current stave" scopes.

---

## MIDI (Ref 25)

### `parsers/midi_source.py`

`read_midi_source(file_path)` — a hand-rolled binary Standard MIDI File parser
(no `mido`). Produces a typed `MidiSource` (header/division, sorted
`time_signature_changes`/`key_signature_changes`/`tempo_changes`,
`List[MidiTrackData]`) read by both `MidiReader` and `MidiTimelineBuilder`.

Note-on/off pairing uses a per-`(channel, pitch)` FIFO queue (handles overlapping
same-pitch retriggers in performance order). The percussion channel (9,
0-indexed) and pure-percussion/conductor-only (zero-note) tracks are excluded
**before** `part_id`s (`f"P{n}"`) are assigned, so reader and builder agree on
numbering with no cross-talk.

MIDI has only one source of truth (the raw bytes) — no music21 reconciliation
pass.

### `parsers/midi_reader.py` / `parsers/midi_timeline_builder.py`

* **Pickup detection (Ref 17)** uses a single signal only: a declared time
  signature spanning less than the one that follows it (MuseScore's own
  MIDI-export convention). A content-based signal (comparing bar-1 content to the
  declared bar length) was tried and dropped — real scores with staggered entries
  and human note-off timing rarely reach the literal bar end, causing false
  positives. **Accepted gap:** a pickup with no time-signature hint isn't
  detected.
* **Enharmonic spelling** (`models/pitch_spelling.spell_pitch(midi_pitch,
  fifths)`) is a simplification, not full scale-degree spelling: non-negative
  fifths spell every chromatic note sharp, negative fifths flat — the convention
  most quick MIDI-to-notation tools use, not degree-accurate for exotic modes.
  `NoteData.file_key_fifths` records which fifths a note was spelled against so
  `apply_key_signature_override` can re-derive losslessly without a re-parse.
* **Duration naming.** MIDI is unquantized, so `quarter_length_to_display_name`'s
  tolerance is tightened to 0.01 for MIDI. Even then a freehand recording can land
  within 1% of some rare type/dots combination by coincidence (13 types by up to 4
  dots). `models/duration_units.is_simple_duration_match()`
  (whole/half/quarter/eighth/16th/32nd, at most 1 dot) plus a per-track second
  pass in `MidiTimelineBuilder.build()` reverts an ENTIRE track to numeric
  duration display when over 5% of its matched names are "not simple" — a mix of
  sensible and nonsense names reads as inconsistent even where each name is
  individually defensible. Region 3's inline text keeps the "duration" label only
  when `duration_name_us` is a real word; the numeric fallback needs the label,
  since a bare number in a comma list could be mistaken for anything.
* **Untitled tracks.** `MidiReader._build_parts_info` suggests a GM instrument
  name (`models/gm_instruments.py`, the 128-entry GM Level 1 table) from the
  track's own Program Change event instead of a bare "Track N". A naming
  *suggestion* only — a real track name, even an unhelpful one like "Track1",
  always wins; the Instruments dialog is the actual fix for that case.
* **Region 2 collapses to part-only rows** (`collapse_to_parts`, driven by
  `MusicData.is_midi`) — MIDI staff is always fake (`1`) and voice untested beyond
  `1`. **The full part/staff/voice tree is still built underneath**: omitting
  those nodes would make every MIDI part invisible to
  `get_active_voice_tuples()`, not just tidy the display.

---

## Guitar Pro (Ref 25)

### `parsers/gp_source.py`

`read_gp_source(file_path)` unzips the `.gp` container, parses
`Content/score.gpif`, and resolves its id-indirection graph (`MasterBars`, then a
`Bar` id per track, then a `Voice` id list per bar, then a `Beat` id list per
voice, then a rhythm ref plus `Note` id list per beat) into a typed `GpSource`.

Covers the GP7/GP8 zip+XML container — both share one schema (GP8 only adds
optional elements on top of GP7's, never renaming or removing anything, per
alphaTab's format docs). Reads defensively throughout: an absent element is "not
present", never an error, so an older GP7 file (untested — no sample available)
should parse the same way with fewer optional fields populated.

**`iter_track_positions(source, track_index)`** yields `(measure_index,
voice_slot, beat_id)` in performance order, shared by `GpReader` (a lightweight
scan) and `GpTimelineBuilder` (the full note walk). **GP dedupes identical beat
content into one shared `Beat` id** reused from multiple voice positions (a held
chord re-struck with identical content), so callers must treat each yielded
*position* as its own event and never collapse by `beat_id`.

### `parsers/gp_reader.py` / `parsers/gp_timeline_builder.py`

GP gives explicit measure boundaries and exact per-beat rhythm
(`NoteValue` plus dots and tuplet) — no tick-based inference — so pickup
detection (Ref 17) and repeat/ending/hairpin spans (Ref 29) are **out of scope
rather than approximated**: `repeat_spans`/`ending_spans`/`hairpin_spans` stay
permanently empty and measure numbers are never reindexed.

Note spelling prefers GP's own notated `ConcertPitch` (step/accidental/octave)
over deriving one from the raw MIDI pitch, since GP already did that work — so
`apply_key_signature_override` skips GP the same way it skips MusicXML.

**Synthetic "Chords" voice.** For any track with at least one beat carrying a
real chord-name reference or a real `Brush` direction anywhere in the piece
(`GpReader._scan_track`), `GpReader` adds one always-present voice,
`GP_CHORD_VOICE_ID = 1000` (out of range of GP's real 1-4 slots, so it can't
collide), displayed as "Chords".

`GpTimelineBuilder` emits one extra `NoteData` per chord-shaped (2+ note) beat:
`step_name` is the sticky current chord name (falling back to the literal
`"Strum"` before any chord name is seen), `midi_pitch` is a representative pitch
(`max(chord_pitches)`, for sort order only), and `chord_pitches` carries the full
voicing — playback extends the part's pitch group with `chord_pitches` so the
full chord sounds.

`strum` is set **only** on the rare beat where GP records an explicit `Brush`
direction — never inferred, even though the real strike rhythm is far denser than
the marked beats (the user's explicit "leave unstated" decision).

`GpReader.load()` defaults the Chords voice's `voice_display_attributes` to
`{"step", "beat position", "strum"}`. `pitch_sort_key` treats the chord note's
representative pitch as a tie-break only — it always sorts after every real
fretted note for that instrument in the same slice, since it is a strum summary,
not another note in the voicing.

---

## Ultimate Guitar

`parsers/ug_source.py` / `ug_reader.py` (`UgReader`, `UgFileReader`) /
`ug_timeline_builder.py`. File > Import from Ultimate Guitar...
(`widgets/ultimate_guitar_import_dialog.py`) imports chords and lyrics from a UG
chord-tab page.

### Fetching

`read_ug_source(url)` does a plain `urllib.request` GET with a spoofed
desktop-browser `User-Agent` (a generic/non-browser fetch gets back only the
page's `<title>`; there is no explicit bot-block) and regex-extracts the
`<div class="js-store" data-content="...">` element — UG's entire React app state
serialized as JSON, server-rendered into the page. **That is what gets parsed,
never the visible rendered HTML.**

Validates `store.page.data.tab.type == "Chords"` (Pro/Tab/Bass/Ukulele use a
different notation model, out of scope) and that title/artist/content are
non-empty, raising a clear `ValueError` otherwise.

### Bar numbering is fabricated

UG gives no real bar boundaries or time signature — `UgTimelineBuilder` assigns
**one bar per chord change, always** (`EventSlice.time_sig` stays the dataclass
default `(4, 4)`, never inferred). Chosen over a per-line or strumming-grid
heuristic — "songs very often have just one chord per bar" — and is intentionally
simple rather than notation-accurate.

### Chord/lyric alignment

A `[tab]...[/tab]` block's chord line (`[ch]Fmaj7[/ch]` markup) and its paired
lyric line are aligned by literal character column. Two wrinkles, both handled
generically: a line's first chord doesn't always start at column 0 (any lead-in
text is attached to that first chord rather than dropped), and a chord's column
can land mid-word (`_snap_to_word_boundary` gives the whole word to whichever
side holds the majority of its letters, so a word is never split).

Every chord bar gets an explicit Lyrics-part row even with nothing to say
(`"No lyrics"`, for wordless intro/instrumental/outro bars) — without it, "no
lyrics here" and "the feature is broken" looked identical.

### Two synthetic parts

`CHORDS_PART_ID`/`LYRICS_PART_ID`, each with exactly one staff and one voice —
**not zero** (same `get_active_voice_tuples()` gotcha as MIDI). `MusicData.is_ug`
extends `collapse_to_parts` so Region 2 shows them as flat, childless rows. The
Lyrics part is silent by design (`midi_pitch=None` throughout); the Chords part
carries a real voicing via `music21.harmony.ChordSymbol(symbol).pitches` in
`NoteData.chord_pitches`.

**`MusicData._sounding_bounds()` gotcha:** with only the (silent) Lyrics part
visible, the strict `_slice_has_visible_sounding_note` check
(`midi_pitch is not None`) found no bounds at all and the score stopped
responding to Left/Right. It falls back to the looser `_slice_has_visible_notes`
check whenever the strict pass finds nothing.

### Strumming patterns

`tab_view.strummings` is a **list** (6 of the 18 example tabs carry 2-3
patterns) — `UgSource.strum_patterns: List[StrumPattern]`, each keeping its own
`part` name, `denuminator`, `bpm`, `is_triplet` and codes. The score tempo is
`strum_patterns[0].bpm or 120`. `UgSource.capo` (`tab_view.meta.capo`) is read
too.

Region 1's `"Strumming Pattern"` credit is the decoded stroke words for a single
unnamed pattern, else a summary (`"3 patterns: Verse, Chorus, ... (see Edit >
Strumming Patterns)"`); `"Capo"` and `"Tablature blocks: N (not imported)"` are
conditional credits alongside it.

**Per-chord strummed audition was removed** — a UG chord auditions as a plain
chord through the unchanged `play_chord` path (the strum audio was unreadable by
ear, and a multi-pattern song's per-bar choice was arbitrary). The pattern is
instead legible in **Edit > Strumming Patterns...** (`Ctrl+Shift+U`,
`widgets/strumming_dialog.py`) — a pattern combo (hidden when only one) plus a
flat one-row-per-slot list (`StrumPattern.slot_rows()`, `"Bar 1, 1 e: pause"`),
and an `Alt+P` looped demo routing through `SynthEngine.play_strum_pattern`.
Disabled unless `MusicData.ug_strum_patterns` is non-empty.

### Sections (P2)

`[Intro]`/`[Verse 1]`/`[Chorus]` labels become
`UgTimelineBuilder.section_spans: List[SectionSpan]` — label verbatim (homoglyphs
and all), `end_measure` = bar before the next section's start (or
`total_measures`). Surfaced as a Region 5 row pair, a Find marking kind, a
Performance Report block, and `Ctrl+Alt+Left/Right` section stepping
(`NavigationController.next_section`/`previous_section` — a positional jump that
cues `boundary_hit` at the ends and never wraps, unlike Find). Written
generically against `section_spans`, so feeding it from GP section text or
MusicXML rehearsal marks later needs no navigation changes.

### Tablature blocks (P4)

A `[tab]` block whose chord or lyric row is raw ASCII tablature
(`is_ascii_tablature_line`) is skipped from alignment and counted
(`count_tablature_blocks`) for the credit — Summer of 69 opens with two such
riffs the aligner used to chew through as lyrics.

### Save/load

File > Save Ultimate Guitar Import As... (`write_ug_source`) serializes the
*source* the import was built from (title, artist, key, tuning, `content` markup,
`strum_patterns`, `capo`, tagged
`{"format": "recall_score_ug_import", "version": 2}`) to a `.ug` JSON file —
deliberately **not** the derived, bar-numbered timeline, so a future
manual-barline feature can layer on via the existing per-file `ScoreConfig`
override system without the file format changing.

`read_ug_source_file` accepts `version in (1, 2)`: a v1 file
(`files/UG/Half the world away.ug` is the only one) migrates its flat
`strum_codes`/`bpm`/`is_triplet` to a single unnamed
`StrumPattern(denominator=None, ...)` — `denominator=None` is honest (v1 never
stored it) and the dialog degrades to `"slot N"` labels.

File > Open recognises `.ug` directly (`workers/score_load_worker.py`). A saved
file's `file_path` is a real path on disk (unlike a live URL import's synthetic
`ultimate-guitar-<tab_id>.ug` slug, which `os.path.exists` naturally excludes
from `.rsc` persistence and Recent Files), so persistence, window title and Open
Local Folder key off it exactly like any other format.

---

## Percussion (cross-format, wishlist #8)

A MusicXML `<unpitched>` note used to hit `TimelineBuilder`'s
`pitch_el is None: continue` and vanish entirely; a MIDI channel-10 track was
dropped in `midi_source.py`'s note-on loop. `PartStructureInfo.is_percussion` now
flags such a part (a MusicXML percussion clef, or a MIDI track whose
`channels_used == [PERCUSSION_CHANNEL]`) — **`gmidi_program` is meaningless for
it and must never be read.**

### Sources

* **MusicXML:** `_percussion_instrument_map(root)` builds
  `score-instrument id -> (name, midi_unpitched key)` once from `<part-list>`; an
  `<unpitched>` note resolves its own `<instrument id>` through that map for BOTH
  its spoken name and its real sounding key — **never** from
  `<display-step>`/`<display-octave>`, which is only where MuseScore draws the
  notehead, not a real pitch. `_extract_part_structure_etree` sets
  `is_percussion` from `<clef><sign>percussion</sign></clef>`, independently of
  the note-level check (the same "structural fact vs. per-note fact" split
  `is_rest` has).
* **MIDI:** `models/gm_percussion_map.py` supplies the GM Level 1 Percussion Key
  Map (35-87) as `gm_percussion_name(note)`, since raw MIDI has no
  instrument-name text. `MidiTimelineBuilder` leaves a percussion note's
  `file_key_fifths` as `None`, which keeps `apply_key_signature_override`'s
  re-spell loop away from it.

### Playback routing — deliberately NOT a dedicated channel

`MusicData.METRONOME_CLICK_CHANNEL` is the click metronome's own channel, not a
slot real percussion is routed to — a real MusicXML file can carry more than one
percussion part (Hit It.mxl's Drum Kit *and* Tambourine), so a single fixed
channel would make them collide.

`get_channel_for_part` treats a percussion part like any other, and
`get_playback_events_for_indices` appends a **trailing 5th element**, `bank=128`
(`GM_PERCUSSION_BANK`, `program` fixed at `GM_PERCUSSION_PROGRAM = 0`) — the same
"trailing optional field" shape `duration_ms` established, so no existing
4-tuple caller changed. `SynthEngine.set_program(channel, program, bank=0)` gained
`bank`; `play_chord` reads `event[4] if len(event) > 4 else 0`.

Verified against `soundfonts/Airfont_380_final.sf2`'s own `phdr` preset headers:
bank 128/program 0 is a real preset ("Hyper Kit"), so GM's standard
percussion-bank convention actually holds for this soundfont.

### Per-item instrument assignment

MuseScore Studio 4.7.4's export declares every percussion instrument's
`<midi-unpitched>` exactly one key higher than the GM key its own
`<instrument-name>` names (confirmed by parsing the soundfont's real preset zones:
key 43 is a genuine tom sample, not the file's claimed "Closed Hi-Hat"; GM's real
Closed Hi-Hat is 42).

* **`NoteData.percussion_source_key`** is the file's ORIGINAL declared key, set
  once at parse time and never mutated; `midi_pitch` stays the *effective*
  (overridable) playback key — the same "immutable original plus mutable
  effective value" split `file_key_fifths`/`step_name` have.
* **A percussion item's identity is `(part_id, percussion_source_key)`** —
  deliberately NOT its display name, which is renameable; keying by name would
  orphan a sound override the moment the item was renamed.
* **`models/gm_percussion_map.py`** carries the reverse lookup
  `gm_percussion_key_for_name` (**exact match only**) and
  `detect_percussion_key_shift(items)`.
* **A fuzzy per-item name match was tried and rejected.** A short declared name
  like "Snare" or "Bass Drum" is genuinely ambiguous against GM's longer names
  ("Acoustic Snare"/"Electric Snare", "Acoustic Bass Drum"/"Bass Drum 1"), and
  picking the closest match by word count landed on the wrong candidate for "Bass
  Drum". Instead `apply_percussion_overrides` detects **ONE shift per PART** from
  whichever items exactly name-match a GM sound (Hit It.mxl's "Closed Hi-Hat" to
  42 and "Tambourine" to 54 both agree on a uniform -1) and applies it to every
  item in the part, including ambiguous ones — reliable because the quirk is
  per-file/per-exporter, not per-instrument.
* **Priority per item:** an explicit `percussion_item_overrides` entry, then the
  detected shift (only when `percussion_auto_correct_enabled` is on, and only for
  a MusicXML note — a MIDI note's name is *derived from* its key, so it can never
  disagree), then the file's own `percussion_source_key`. A name override is
  applied before shift detection, so renaming an item to a real GM name makes it
  individually auto-correctable.
* **`MusicData._set_percussion_voice_names()`** gives a percussion voice's
  `PartStructureInfo.voice_names` entry its one item's display name ("Closed
  Hi-Hat") instead of "Voice N". Each voice holds exactly one item by
  construction, so this is a straight 1:1 label.

### Region 2 split-out: the pitch defines the instrument

Hit It.mxl's Drum Kit voice 1 held BOTH Closed Hi-Hat and Snare (the real
MusicXML `<voice>` they share), so Region 2 could only mute/solo them together.
The user's framing decided the fix: *"the pitch defines the instrument - that is
the defining feature."*

Both builders now set `NoteData.voice` to the item's own declared key
(`percussion_source_key`) for a percussion note, instead of the notated `<voice>`.
This is the same "fabricate a voice_id so it drops into the existing tree for
free" trick as GP's `GP_CHORD_VOICE_ID` — **zero changes** were needed in
`region2_manager.py`'s mute/solo machinery, `active_voice_filter`, or
`ScoreConfig`'s `voices_muted`/`voices_soloed`, since all of those operate on
`(part_id, staff, voice)` and don't care what a "voice" number means. A 4th tree
level was considered and rejected: it would have needed all of that touched.

`_extract_part_structure_etree` makes the identical substitution when building
`staves_voices`/`voice_names`, sharing `_percussion_instrument_map` with
`TimelineBuilder`. **A rest inside a percussion voice has no `<unpitched>`/item
identity**, so it is skipped entirely when building a percussion part's voice
list (falling through to its raw `<voice>` produced a stray extra "Voice 2" row)
— unlike a pitched part, where a rest's real `<voice>` still matters, since a
whole passage can legitimately be nothing but rests.

`midi_reader._build_parts_info` lists the distinct note numbers actually used
(`{ev.pitch for ev in track.note_events}`), each named via `gm_percussion_name`.

**A MIDI percussion part is not collapsed** in Region 2, unlike every other MIDI
part — it now has real, independently mute/soloable voices to expand into.

### Persistence and dialog

Three `ScoreConfig` fields (`percussion_item_overrides`,
`percussion_item_name_overrides`, `percussion_auto_correct_enabled`), same
best-effort filtering as `part_name_overrides` — an item key that no longer
exists is dropped rather than rejecting the whole config.

`widgets/instrument_dialog.py`: a percussion part contributes its own row (name
only — no single "instrument" concept for a whole kit, so the combo is disabled)
plus one extra row per distinct item, inserted immediately after it
(`get_percussion_items_for_part`). Selecting an item row swaps the combo to
`GM_PERCUSSION_SOUND_NAMES`; the combo shows the key's *actual* GM name, which can
visibly differ from the item's declared name — **that mismatch is the whole
point.** One dialog-level checkbox ("Apply MusicXML offset for percussion"), added
only when the score has a percussion part. `overrides()` returns a 5-tuple.
