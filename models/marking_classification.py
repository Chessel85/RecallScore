# models/marking_classification.py
"""PerformanceMarkingsImplementationPlanV2.md stage 1: for every element
`UserPlans/inventory.csv` lists, the levels it is allowed to render at and
its dimension (point vs. length), transcribed verbatim from that CSV's
Element/Level/Dimension columns. Qt-free, no parsers/ import.

**This is the only place levels/dimensions are declared** - stage 2's
`MarkingRows.level_of(marking)` reads this table (plus the ground rules in
the plan's section 3) rather than re-deciding per family. An element not
in `CLASSIFICATION` is not surfaced at all (inventory.csv's own rule).

Keyed by `(section, element)` - the inventory's own Section/Element pair -
because a handful of element names repeat across sections with different
rules (`segno`/`coda` appear under Direction, Barline AND Sound; `fermata`
under both Barline and Note).

Two CSV phrasings don't fit a plain level tuple and get their own flag
instead of being force-fit into `levels`:

* "Score when every part agrees, else Part" (ground rule 2: barline
  styles, repeats, endings, key, time) - `levels=("score", "part")` plus
  `score_or_part_by_agreement=True`. Stage 10 implemented the agreement
  comparison for key/time only (KeyChangeMark/TimeChangeMark carry their
  own resolved `is_score_level`, majority-vote, not strict unanimity - see
  models/marking_rows.py's `level_of` and TimelineBuilder.
  _resolve_key_time_levels); barline styles/repeats/endings still stay
  unconditionally score (this flag only records that they're SUBJECT to
  the rule, not that it's implemented for them).
* "Note, plus Score or Part row" (note fermata) - `levels=("note", "score",
  "part")` plus `note_fermata_aggregate=True`, since the aggregation rule
  (one score row if every sounding part has a fermata there, else one part
  row per carrying part) is specific to that one element, spelled out in
  the plan's section 3.

`dashes`/`bracket` carry `inherits_level_from_words=True`: the CSV gives
their level as "Same as the words it extends" - they are classified by
whatever `<words>` shares their `<direction>`, never independently.
"""
from dataclasses import dataclass
from typing import Dict, Tuple

# Allowed values for MarkingClassification.levels.
LEVELS: Tuple[str, ...] = ("score", "part", "stave", "note", "barline")

# Allowed values for MarkingClassification.dimension.
#   point         - one row at one position
#   length        - a start/end pair (or a collapsed bare point when both
#                    ends resolve to the same position - strategy section 11)
#   length_start  - only ever a span's start (a forward repeat)
#   length_end    - only ever a span's end (a backward repeat)
#   attribute     - a Note-section field: never a row of its own, always
#                    read off the note it decorates
#   none          - genuinely nothing (an ordinary <bar-style>regular</>)
DIMENSIONS: Tuple[str, ...] = (
    "point", "length", "length_start", "length_end", "attribute", "none",
)


@dataclass(frozen=True)
class MarkingClassification:
    levels: Tuple[str, ...]
    dimension: str
    score_or_part_by_agreement: bool = False
    note_fermata_aggregate: bool = False
    inherits_level_from_words: bool = False
    # Set only for <pedal>: the element's usual dimension is "length"
    # (start/stop/sostenuto/resume), but type="change" is always a point -
    # inventory.csv's "Length; change is a Point".
    has_point_variant: bool = False


CLASSIFICATION: Dict[Tuple[str, str], MarkingClassification] = {
    # --- Direction ---------------------------------------------------
    ("direction", "words"): MarkingClassification(("stave", "part", "score"), "point"),
    ("direction", "dynamics"): MarkingClassification(("note",), "point"),
    ("direction", "wedge"): MarkingClassification(("stave", "part", "score"), "length"),
    ("direction", "dashes"): MarkingClassification(
        (), "length", inherits_level_from_words=True
    ),
    ("direction", "bracket"): MarkingClassification(
        (), "length", inherits_level_from_words=True
    ),
    ("direction", "pedal"): MarkingClassification(
        ("part",), "length", has_point_variant=True
    ),
    ("direction", "octave-shift"): MarkingClassification(("stave", "part", "score"), "length"),
    ("direction", "metronome"): MarkingClassification(("score",), "point"),
    ("direction", "segno"): MarkingClassification(("score",), "point"),
    ("direction", "coda"): MarkingClassification(("score",), "point"),
    ("direction", "rehearsal"): MarkingClassification(("score",), "point"),
    ("direction", "symbol"): MarkingClassification(("score",), "point"),
    ("direction", "harp-pedals"): MarkingClassification(("stave", "part", "score"), "point"),
    ("direction", "damp"): MarkingClassification(("stave", "part", "score"), "point"),
    ("direction", "damp-all"): MarkingClassification(("stave", "part", "score"), "point"),
    ("direction", "eyeglasses"): MarkingClassification(("part", "score"), "point"),
    ("direction", "string-mute"): MarkingClassification(("stave", "part", "score"), "point"),
    ("direction", "scordatura"): MarkingClassification(("stave", "part", "score"), "point"),
    ("direction", "accordion-registration"): MarkingClassification(
        ("stave", "part", "score"), "point"
    ),
    # Low priority (plan stage 10): classified as a length per the CSV, even
    # though today's parser only ever produces the point catch-all for it.
    ("direction", "principal-voice"): MarkingClassification(("stave", "part"), "length"),
    ("direction", "staff-divide"): MarkingClassification(("stave", "part"), "point"),
    ("direction", "percussion"): MarkingClassification(("stave", "part"), "point"),
    ("direction", "other-direction"): MarkingClassification(("stave", "part", "score"), "point"),

    # --- Barline -------------------------------------------------------
    ("barline", "bar-style-regular"): MarkingClassification((), "none"),
    ("barline", "bar-style-light-light"): MarkingClassification(
        ("score", "part"), "point", score_or_part_by_agreement=True
    ),
    ("barline", "bar-style-light-heavy"): MarkingClassification(
        ("score", "part"), "point", score_or_part_by_agreement=True
    ),
    ("barline", "bar-style-heavy"): MarkingClassification(
        ("score", "part"), "point", score_or_part_by_agreement=True
    ),
    ("barline", "bar-style-dotted-dashed"): MarkingClassification(
        ("score", "part"), "point", score_or_part_by_agreement=True
    ),
    ("barline", "bar-style-tick-short"): MarkingClassification(
        ("score", "part"), "point", score_or_part_by_agreement=True
    ),
    ("barline", "repeat-forward"): MarkingClassification(
        ("score", "part"), "length_start", score_or_part_by_agreement=True
    ),
    ("barline", "repeat-backward"): MarkingClassification(
        ("score", "part"), "length_end", score_or_part_by_agreement=True
    ),
    ("barline", "ending"): MarkingClassification(
        ("score", "part"), "length", score_or_part_by_agreement=True
    ),
    ("barline", "fermata"): MarkingClassification(("barline",), "point"),
    ("barline", "segno"): MarkingClassification(("barline",), "point"),
    ("barline", "coda"): MarkingClassification(("barline",), "point"),
    ("barline", "wavy-line"): MarkingClassification(("barline",), "length"),

    # --- Sound -----------------------------------------------------------
    ("sound", "tempo"): MarkingClassification(("score",), "point"),
    ("sound", "dacapo"): MarkingClassification(("score",), "point"),
    ("sound", "dalsegno"): MarkingClassification(("score",), "point"),
    ("sound", "segno"): MarkingClassification(("score",), "point"),
    ("sound", "coda"): MarkingClassification(("score",), "point"),
    ("sound", "tocoda"): MarkingClassification(("score",), "point"),
    ("sound", "fine"): MarkingClassification(("score",), "point"),

    # --- Note (attributes - never a marking row of their own) -----------
    ("note", "tied"): MarkingClassification(("note",), "attribute"),
    ("note", "slur"): MarkingClassification(("note",), "attribute"),
    ("note", "tuplet"): MarkingClassification(("note",), "attribute"),
    ("note", "glissando"): MarkingClassification(("note",), "attribute"),
    ("note", "slide"): MarkingClassification(("note",), "attribute"),
    ("note", "ornaments"): MarkingClassification(("note",), "attribute"),
    ("note", "articulations"): MarkingClassification(("note",), "attribute"),
    ("note", "breath-mark"): MarkingClassification(("note",), "attribute"),
    ("note", "caesura"): MarkingClassification(("note",), "attribute"),
    ("note", "technical"): MarkingClassification(("note",), "attribute"),
    ("note", "dynamics"): MarkingClassification(("note",), "attribute"),
    ("note", "fermata"): MarkingClassification(
        ("note", "score", "part"), "point", note_fermata_aggregate=True
    ),
    ("note", "arpeggiate"): MarkingClassification(("note",), "attribute"),
    ("note", "non-arpeggiate"): MarkingClassification(("note",), "attribute"),
    ("note", "other-notation"): MarkingClassification(("note",), "attribute"),
    ("note", "grace"): MarkingClassification(("note",), "attribute"),

    # --- Attributes --------------------------------------------------
    ("attributes", "key"): MarkingClassification(
        ("score", "part"), "point", score_or_part_by_agreement=True
    ),
    ("attributes", "time"): MarkingClassification(
        ("score", "part"), "point", score_or_part_by_agreement=True
    ),
    ("attributes", "clef"): MarkingClassification(("stave", "part"), "point"),
    ("attributes", "measure-style"): MarkingClassification(("stave", "part", "score"), "point"),

    # --- Other -------------------------------------------------------
    ("other", "harmony"): MarkingClassification(("stave", "part"), "attribute"),
}


def classification_for(section: str, element: str) -> MarkingClassification:
    """Raises KeyError for any (section, element) not in inventory.csv -
    deliberate, matching the plan's "an element not listed there is not
    surfaced"."""
    return CLASSIFICATION[(section, element)]
