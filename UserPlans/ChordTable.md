# Chord table without music21 (RSBV task 1.4)

Written 2026-10-08. Sub-plan for task 1.4 in `UserPlans/RSBV.md`. Opus.
Status: done 2026-10-08. User answers: commit 1.1 first (yes), UG keeps
music21 (yes), compressed table, full sweep in pytest too. As built, the
table also covers music21's own kind names (55 kinds, 145 KB file), since a
file could carry one and music21 accepted it.

## Goal

`_resolve_harmony` (`parsers/timeline_builder.py`) turns a MusicXML
`<harmony>` into MIDI pitches and a label. Today it asks
`music21.harmony.ChordSymbol`. Replace that with a pure-Python table in
`models/chord_kinds.py`, so:

* the browser gets chord symbols with sound (today they vanish without music21);
* desktop chords keep exactly the same pitches, in the same order, and the
  same labels.

## What music21 actually does (measured, music21 10.5.0)

Probed every input `_resolve_harmony` can pass it: 35 root spellings (7 steps
times alter -2 to +2) times the 33 MusicXML `<kind>` values times 36 bass
options (none, or any of the 35 spellings). 41,580 combinations, about 90 s.

* No combination raises and none returns empty pitches, so both fallbacks in
  `_resolve_harmony` are dead code for these inputs.
* The voicing is not "root plus intervals". music21 runs a figured-bass
  realisation, octave bumps for 9th/11th/13th chords, inversion detection,
  and "pull down if above middle C, push up if below A1" passes. Results
  depend on the root letter, e.g. C major is C3 E3 G3 but G major is G3 B3 D4.
  About a quarter of results are not in ascending order (E/G gives
  55, 44, 47, 52), and some repeat a pitch. Porting that algorithm and
  matching every quirk is fragile.
* An unknown kind (any string not in music21's list, e.g. "foo" or "Major")
  behaves like `other`: the root alone.
* The label is fully predictable: root spelling + a fixed suffix per kind
  (major "", minor "m", dominant "7", half-diminished "ø7", suspended-fourth
  "sus", ...) + "/bass" when a bass is given and differs from the root. Zero
  mismatches across all 41,580.
* The packed pitch lists are 246 KB raw, 82 KB after zlib and base64.

So the plan is a generated lookup table, not a port of the algorithm.

## Design

1. `tools/gen_chord_kinds.py` (run by hand, needs music21, imports nothing
   from the app, writes one file). Enumerates the full domain above, asserts
   the label rule holds for every entry, and writes
   `models/chord_kinds.py`. A `--check` flag regenerates in memory and fails
   if the committed file differs (use after a music21 upgrade). Note: the
   `tools/` rule says stdlib only; this script needs music21 as a third-party
   library but still imports nothing from the app. The RSBV plan already
   allows this.

2. `models/chord_kinds.py`, generated, with a "do not edit" header:
   * `KIND_SUFFIX`: readable dict, MusicXML kind to label suffix.
   * `_PACKED`: the pitch lists as a zlib + base64 string (about 82 KB),
     decoded lazily on first use (stdlib `zlib`, which Pyodide has).
   * `chord_symbol(root_step, root_alter, kind, bass_step=None, bass_alter=0)`
     returning `(pitches, label)` exactly as music21 would. Unknown kind maps to
     the `other` row. Alter is normalised the way `_pitch_name` does now
     (`int(float(text))`, anything outside -2 to +2 becomes natural). Unknown
     root step returns `([], "")` so the chord is skipped, as today.
   * Qt-free and parsers-free (invariants 1 and 2).

3. `_resolve_harmony` calls `chord_symbol` and keeps `spell_out_minor_chord`
   on the label. The music21 import, both dead fallbacks and `_pitch_name`
   go. `<degree>`, `<inversion>` and `<kind text="...">` stay ignored, as
   today; reading them would change desktop output and is a separate decision.

4. `tests/parsers/test_musicxml_without_music21.py`: flip the harmony case.
   With music21 blocked, chords must now be present with pitches.

5. Docs: `docs/parsers.md` harmony section, `docs/architecture.md` models
   list, and the 1.4 entry in `UserPlans/RSBV.md`.

## Out of scope

Ultimate Guitar keeps music21. `_chord_symbol_to_pitches` parses free-text
symbols ("C7b9", "Cadd9/G") with music21's figure parser, which is far bigger
than a kind table, and UG import is left out of the web version anyway.
music21 also stays on desktop for tempo, key and time in `MusicXMLReader`.

## Tests and gate

* Before editing: capture `parser_fingerprint.py` and `model_fingerprint.py`
  baselines into the scratchpad. After: `--check`, both must match.
* The corpus is thin evidence here: the uncompressed files hold only about 22
  `<harmony>` elements using 3 kinds (major, minor, minor-seventh). The real
  evidence is the comparison against music21:
  * `tests/models/test_chord_kinds.py`, marked `slow`: every kind times every
    root, with no bass, each natural bass and a few accidental basses (a few
    thousand cases, a few seconds), plus two unknown kind strings. Compares
    pitches, order and label with music21.
  * The full 41,580 sweep runs in `gen_chord_kinds.py` itself (at generation
    and with `--check`), not in pytest, so the suite stays about a minute.
  * A fast, non-slow test of a handful of hand-written cases (C major,
    G major, E/G order, F#m7, an unknown kind).
* Full pytest run.

## Questions for the user

1. Task 1.1 is still uncommitted. Commit it on its own first? (Recommended.)
2. Ultimate Guitar keeps music21 for chords, as above. Agree?
3. Table format: compressed blob of about 82 KB (recommended), or a readable
   Python literal of roughly 300 to 500 KB?
4. Full sweep in the generator, sampled comparison in pytest. Or do you want
   the full 90-second sweep in pytest too, as a slow test?
