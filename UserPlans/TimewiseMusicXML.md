# Plan: load timewise MusicXML

Read `CLAUDE.md` and the MusicXML section of `docs/parsers.md` before
starting. Tasks are in order; each is separately testable. Do not commit
unless the user says so, and when they do, stage only the files this plan
touches - the working tree may hold the user's own uncommitted edits.

## What was found (2026-09-11)

* MusicXML has two equivalent document shapes. `<score-partwise>` nests
  measures inside parts; `<score-timewise>` nests parts inside measures:

      <score-timewise>
        ...header (work, identification, defaults, credit, part-list)...
        <measure number="1">
          <part id="P1"> ...notes/attributes/directions... </part>
          <part id="P2"> ... </part>
        </measure>
        <measure number="2"> ... </measure>
      </score-timewise>

  The header children are identical in both shapes. The content of a
  timewise `<measure>/<part>` is exactly the content of a partwise
  `<part>/<measure>`. The MusicXML distribution ships an official XSLT
  (`timepart.xsl`) that converts one to the other purely structurally.
* Every ElementTree consumer in this app assumes partwise (`root.findall("part")`,
  `root.find("part")`, `.//part/measure` in `musicXML_reader.py`,
  `score_sections.py`, `timeline_builder.py`).
* All three places that turn a path into a root go through
  `parsers/xml_source.py::read_musicxml_root` (`musicXML_reader.py:127`,
  `timeline_builder.py:899`, `timeline_builder_factory.py:88`). That is the
  single choke point.
* music21 refuses timewise outright (`xmlToM21.py:792`, "Cannot parse
  MusicXML files not in score-partwise"). `MusicXMLReader.load()` calls
  `music21.converter.parse(self.file_path)`. `MusicData.score` is not read
  anywhere outside the reader; music21 only supplies tempo, key and time
  signature, each of which has an ElementTree fallback.
* `parsers/file_signature.py` sniffs only for a leading `<`, so a timewise
  file already passes the precheck.

## Design (decided)

Normalise at the choke point. `read_musicxml_root` converts a timewise root
to an in-memory partwise root before returning it, so nothing downstream ever
sees timewise and there is no second code path to maintain. A partwise file
must go through completely unchanged (same element objects, no copy, no
re-serialisation).

Conversion rules:

* New root `Element("score-partwise", dict(timewise_root.attrib))` (keeps
  `version`).
* Every root child that is not `<measure>` is appended to the new root in
  its original order (these are the header elements). Reuse the existing
  element objects; no deep copy is needed because the timewise tree is
  discarded.
* Part order is the order in which each part id first appears, scanning the
  measures in document order. (This equals the XSLT's "parts of measure 1"
  order whenever measure 1 contains every part, and does not silently drop a
  part that is absent from measure 1.)
* For each part id, create `<part id="...">`. For each timewise `<measure>`,
  in document order, append a new `<measure>` carrying a copy of the
  timewise measure's attributes (`number`, `implicit`, `width`, ...) whose
  children are the children of that measure's `<part>` with this id.
* If a timewise measure has no `<part>` for some id, still append the
  `<measure>` (attributes only, no children) so every part has the same
  number of measures and bar indices stay aligned.
* Measures are matched by position, never by `number` - multi-section
  scores restart the numbering (`tests/fixtures/two_sections.musicxml`).
* Any root tag other than `score-timewise` is returned untouched (the
  current behaviour for partwise, and for anything malformed, is not this
  plan's concern).

music21: give it the converted tree, but only for timewise files, so the
partwise path is byte-for-byte what it is today.

---

## Task 1 - Convert in `parsers/xml_source.py`

* Rename the current body of `read_musicxml_root` to a private
  `_read_root_as_written(file_path)` (unchanged, including every
  `ScoreLoadError`).
* Add a pure function `timewise_to_partwise(root: ET.Element) -> ET.Element`
  implementing the rules above. It returns `root` itself (the same object)
  when `root.tag != "score-timewise"`.
* Add `read_musicxml_root_and_origin(file_path) -> tuple[ET.Element, bool]`
  returning `(timewise_to_partwise(raw), raw.tag == "score-timewise")`.
* `read_musicxml_root(file_path)` becomes
  `return read_musicxml_root_and_origin(file_path)[0]`. Keep its docstring;
  add a paragraph saying it always returns a partwise root and why (one
  normalisation point, nothing downstream handles timewise).
* stdlib only - this module must not import music21 or Qt.

Tests, in `tests/parsers/test_xml_source.py`:

* A partwise file returns the very same element `timewise_to_partwise` was
  given (`is`, not `==`).
* A small inline timewise tree (two parts, two measures) converts to the
  expected partwise shape: header order kept, parts in first-appearance
  order, each part has two measures carrying the timewise measure
  attributes, note children in the right place.
* A part missing from measure 1 but present in measure 2 is kept, appears
  after the parts of measure 1, and gets an empty measure 1.
* `read_musicxml_root_and_origin` reports `True` for a timewise file and
  `False` for `minimal_score`.

## Task 2 - Give music21 the converted tree (`parsers/musicXML_reader.py`)

* `_parse_xml_root` calls `read_musicxml_root_and_origin`, stores the flag
  as `self._was_timewise`, and returns the root. Update its docstring.
* In `load()`:

      if self._was_timewise:
          score = music21.converter.parseData(
              ET.tostring(root, encoding="unicode"), format="musicxml"
          )
      else:
          score = music21.converter.parse(self.file_path)

  inside the existing `try/except`, so a music21 failure still degrades to
  the ElementTree fallbacks exactly as today. Initialise
  `self._was_timewise = False` in `__init__`.
* `parseData` exists in the installed music21 (`converter/__init__.py:1260`).
  Confirm the string form actually parses by running Task 4's slow test,
  rather than assuming.

## Task 3 - Acceptance gate: partwise output unchanged

This change must not alter anything for existing (partwise) files. Run both
fingerprint harnesses against a baseline from `HEAD`, following
`tests/manual/README.md` exactly (git worktree, copy the scripts in, capture
`before`, then `--check` on the working tree).

* `parser_fingerprint.py` and `model_fingerprint.py` must both print
  `MATCH`. Any difference is a regression - fix it; do not re-baseline.
* Do this before Task 4 adds a fixture, otherwise the new file shows up as
  a difference (the baseline tree has no such file).
* Also run the full suite: `.venv\Scripts\python.exe -m pytest`.

## Task 4 - Prove timewise loads identically

A. Test-only inverse, `tests/support/timewise.py`: a function
   `partwise_to_timewise(root) -> ET.Element` (header children copied in
   order, then one `<measure>` per measure position, carrying the first
   part's measure attributes, holding one `<part id>` per part with that
   part's measure children). It exists only to manufacture timewise input
   from fixtures we already trust. Use `copy.deepcopy` of the parsed root
   first so it never mutates a shared tree.

B. `tests/parsers/test_timewise.py`, parametrised over every
   `*.musicxml` in `tests/fixtures/` (glob it, don't hand-list):

   * Structural round trip: `timewise_to_partwise(partwise_to_timewise(r))`
     equals `r` under a canonical comparison that recurses over
     `(tag, attrib, (text or "").strip(), children)` - whitespace-only text
     and tails differ because the part/measure elements are newly built.
   * Timeline equality: write the timewise version to `tmp_path`, build
     `MusicData(file_path=original)` and `MusicData(file_path=timewise_copy)`
     (the fast ~1 ms path - do NOT go through `MusicXMLReader`) and assert
     `timeline_slices`, `total_measures`, `tempo_changes`, `repeat_spans`,
     `ending_spans`, `hairpin_spans`, `segno_marks`, `coda_marks`,
     `to_coda_marks`, `fine_marks` and `navigation_jumps` are equal. If
     dataclass `==` turns out unsuitable for any of these, compare `repr`
     instead and say why in a comment.

C. One `@pytest.mark.slow` test through `MusicXMLReader(path).load()` on
   `key_change.musicxml` and `tempo_change.musicxml` (original vs timewise
   copy): `credits` (includes Key/Time Signature and Tempo), `tempo_bpm` and
   `parts_info` are equal. This is what proves music21 is given the
   converted tree; without Task 2 the key/time/tempo come from the
   ElementTree fallback instead and may render differently.

D. One hand-written fixture, `tests/fixtures/timewise_two_parts.musicxml`,
   so there is a genuine on-disk timewise file that does not depend on our
   own inverse (a symmetric bug in both directions would pass B). Content:

       <?xml version="1.0" encoding="UTF-8"?>
       <score-timewise version="4.0">
         <part-list>
           <score-part id="P1"><part-name>Flute</part-name></score-part>
           <score-part id="P2"><part-name>Cello</part-name></score-part>
         </part-list>
         <measure number="1">
           <part id="P1">
             <attributes><divisions>1</divisions><key><fifths>0</fifths></key>
               <time><beats>4</beats><beat-type>4</beat-type></time>
               <clef><sign>G</sign><line>2</line></clef></attributes>
             <note><pitch><step>C</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type></note>
             <note><pitch><step>D</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type></note>
             <note><pitch><step>E</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type></note>
             <note><pitch><step>F</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type></note>
           </part>
           <part id="P2">
             <attributes><divisions>1</divisions><key><fifths>0</fifths></key>
               <time><beats>4</beats><beat-type>4</beat-type></time>
               <clef><sign>F</sign><line>4</line></clef></attributes>
             <note><pitch><step>C</step><octave>3</octave></pitch><duration>4</duration><type>whole</type></note>
           </part>
         </measure>
         <measure number="2">
           <part id="P1">
             <note><pitch><step>G</step><octave>5</octave></pitch><duration>4</duration><type>whole</type></note>
           </part>
           <part id="P2">
             <note><pitch><step>G</step><octave>2</octave></pitch><duration>2</duration><type>half</type></note>
             <note><pitch><step>C</step><octave>3</octave></pitch><duration>2</duration><type>half</type></note>
           </part>
         </measure>
       </score-timewise>

   Add a `timewise_two_parts_score` fixture to `tests/conftest.py` in the
   same style as its neighbours, and a fast test asserting:
   `total_measures == 2`; the first slice is measure 1 beat 1 holding both
   the flute C5 and the cello C3; the flute's four measure-1 notes are
   C, D, E, F in that order; measure 2 has slices on beat 1 (G5 + G2) and
   beat 3 (C3). Check the actual beat-position units against
   `docs/architecture.md` (they are relative to the time-signature
   denominator, Ref 18) rather than guessing.

   Note that the fixture is also picked up by Part B's glob; Part B's
   inverse must then no-op or be skipped for it (skip any fixture whose
   root is already timewise).

## Task 5 - Documentation

* `docs/parsers.md`, `### parsers/xml_source.py`: add a paragraph - the
  root is always returned partwise; a timewise file is converted in memory
  by `timewise_to_partwise` (positional measure matching, first-appearance
  part order, empty measure for a missing part); downstream code may assume
  partwise. Mention that `read_musicxml_root_and_origin` exists only so
  `MusicXMLReader` can hand music21 the converted tree.
* `docs/parsers.md`, `### parsers/musicXML_reader.py`: one sentence that a
  timewise file's music21 parse is fed the converted tree via `parseData`.
* Do not edit `docs/user_guide.md`/`.html`, `docs/release_notes.md`,
  `version.txt` or `wishlist.txt` - the user maintains those.

## Done means

* Full pytest suite green, including the slow tests.
* Both fingerprint harnesses print `MATCH` against `HEAD` (Task 3).
* A summary for the user that states the fingerprint results and lists the
  files changed. Keep it short and use plain `*` bullets, no bold - the user
  reads it through a screen reader.
