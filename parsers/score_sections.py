# parsers/score_sections.py
"""Split one MusicXML document into N independent sections.

A single MusicXML file can hold several unrelated pieces back to back in one
`<part>` - "Two Flute Exercises" is two three- and two-bar studies whose
`<measure number>` counter restarts at 1 for the second. The app treats each
such run as its own score: the user picks one section and every region then
behaves as if that section were the whole file (see
`UserPlans/MultiSectionScores.md`).

This module is the split. Pure `xml.etree.ElementTree`, no music21, no Qt -
it walks the already-parsed root and hands back one `<score-partwise>`
sub-root per section, each a self-contained document a fresh `TimelineBuilder`
can build with no knowledge that it came from a larger file.

A document with only one section (the overwhelmingly common case, and every
MIDI/Guitar Pro/Ultimate Guitar score) yields a one-element list whose single
sub-root IS the original root, so the downstream path is bit-identical to
today.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple

from parsers.timeline_builder import SECTION_CARRIED_MARKER, _raw_measure_number

# Marks a synthesised carry-forward <attributes> block (see
# _synthesise_carried_attributes). TimelineBuilder._handle_attributes reads
# this attribute and suppresses the ClefChangeMark / MeasureStyleMark it
# would otherwise emit for a mid-part clef - the carried clef is not a
# change, it is section 1's clef restated so section 2 does not lose it.
CARRIED_MARKER = SECTION_CARRIED_MARKER

# <attributes> children carried forward into a section that does not
# re-declare them, in MusicXML's canonical child order. clef / staff-details
# / transpose are per-staff (keyed by their `number` attribute); the rest
# are last-seen-wins for the part as a whole.
_CARRIED_SINGLE = ("divisions", "key", "time", "staves", "part-symbol", "instruments")
_CARRIED_PER_STAFF = ("clef", "staff-details", "transpose")

# Header children of <score-partwise> that every section sub-root reuses
# verbatim (not deep-copied - nothing in TimelineBuilder mutates them).
_SHARED_HEADER = (
    "work",
    "movement-number",
    "movement-title",
    "identification",
    "defaults",
)


@dataclass
class ScoreSectionXml:
    """One section of a split MusicXML document.

    `root` is a standalone `<score-partwise>` element - the shared header
    plus one `<part>` per original part holding only this section's
    `<measure>` elements. `measure_range` is the half-open ordinal slice
    `[start, end)` into the first part's measure list that produced it.
    """

    index: int
    label: str
    root: ET.Element
    measure_range: Tuple[int, int]


def detect_section_boundaries(root: ET.Element) -> List[Tuple[int, int]]:
    """Half-open `[start, end)` measure-ordinal ranges, one per section.

    Walks the FIRST `<part>`'s `<measure>` children in document order (the
    "structural facts come from the first part" convention `_detect_pickup`
    and `_scan_first_part` already follow). A measure opens a new section
    when it is not the first measure and its raw `number` attribute is 1 or
    0 while the previous measure's raw number was greater - i.e. the counter
    restarted.

    A file with no such restart returns a single `(0, n)` range: "not a
    multi-section score", and every downstream consumer then behaves exactly
    as it does today.
    """
    first_part = root.find("part")
    if first_part is None:
        return [(0, 0)]

    measures = first_part.findall("measure")
    n = len(measures)
    if n == 0:
        return [(0, 0)]

    starts = [0]
    for i in range(1, n):
        raw = _raw_measure_number(measures[i])
        prev_raw = _raw_measure_number(measures[i - 1])
        if raw in (0, 1) and prev_raw > raw:
            starts.append(i)
    starts.append(n)
    return [(starts[k], starts[k + 1]) for k in range(len(starts) - 1)]


def split_score_sections(root: ET.Element) -> List[ScoreSectionXml]:
    """One `ScoreSectionXml` per section of `root`.

    Single-section documents get a one-element list whose `root` IS the
    passed-in root (no copy, no synthesised attributes) so the build path
    stays identical to today.
    """
    ranges = detect_section_boundaries(root)
    if len(ranges) <= 1:
        start, end = ranges[0] if ranges else (0, 0)
        return [
            ScoreSectionXml(
                index=0,
                label=_section_label(root, _first_part_measure(root, start), 0),
                root=root,
                measure_range=(start, end),
            )
        ]

    parts = root.findall("part")
    sections: List[ScoreSectionXml] = []
    for index, (start, end) in enumerate(ranges):
        sub_root = _build_sub_root(root, parts, start, end)
        label = _section_label(root, _first_part_measure(root, start), index)
        sections.append(
            ScoreSectionXml(
                index=index, label=label, root=sub_root, measure_range=(start, end)
            )
        )
    return sections


def _first_part_measure(root: ET.Element, ordinal: int) -> Optional[ET.Element]:
    first_part = root.find("part")
    if first_part is None:
        return None
    measures = first_part.findall("measure")
    return measures[ordinal] if 0 <= ordinal < len(measures) else None


def _section_label(
    root: ET.Element, first_measure: Optional[ET.Element], index: int
) -> str:
    """The section's title: the first non-empty `<words>` of its first
    measure's first non-tempo `<direction>`, `.strip()`ed with internal
    whitespace collapsed. Falls back to `<movement-title>` for section 1
    only, then to `"Section {n}"`.

    The label is ADDITIVE - the `<words>` direction is still parsed and
    reported by `TimelineBuilder` exactly as written (invariant 14). This
    only reads it, it does not consume it.
    """
    if first_measure is not None:
        for direction in first_measure.findall("direction"):
            if direction.find("sound[@tempo]") is not None:
                continue
            if direction.find("direction-type/metronome") is not None:
                continue
            for words in direction.findall("direction-type/words"):
                collapsed = " ".join((words.text or "").split())
                if collapsed:
                    return collapsed

    if index == 0:
        movement_title = root.findtext("movement-title")
        if movement_title and movement_title.strip():
            return " ".join(movement_title.split())

    return f"Section {index + 1}"


def _build_sub_root(
    root: ET.Element,
    parts: List[ET.Element],
    start: int,
    end: int,
) -> ET.Element:
    """A standalone `<score-partwise>` for measures `[start, end)`.

    Reuses (does not deep-copy) the shared header and `<part-list>`, plus
    one `<part>` per original part holding only this section's measures.
    For a section that does not begin at the document start, a synthesised
    `<attributes>` carrying every state-bearing attribute the section does
    not re-declare (crucially the clef) is prepended to each part's first
    measure - the measure's own `<attributes>` follows it in document order
    and overrides it naturally.
    """
    sub_root = ET.Element("score-partwise", dict(root.attrib))
    for tag in _SHARED_HEADER:
        el = root.find(tag)
        if el is not None:
            sub_root.append(el)
    for credit in root.findall("credit"):
        sub_root.append(credit)
    part_list = root.find("part-list")
    if part_list is not None:
        sub_root.append(part_list)

    for part in parts:
        sub_part = ET.SubElement(sub_root, "part", dict(part.attrib))
        measures = part.findall("measure")
        section_measures = measures[start:end]
        if not section_measures:
            continue

        carried = (
            _synthesise_carried_attributes(measures[:start]) if start > 0 else None
        )
        if carried is not None:
            first = section_measures[0]
            # A fresh <measure> so the original element is never mutated
            # (it may still be walked as part of the whole-file tree).
            new_first = ET.Element("measure", dict(first.attrib))
            new_first.append(carried)
            new_first.extend(list(first))
            sub_part.append(new_first)
            sub_part.extend(section_measures[1:])
        else:
            sub_part.extend(section_measures)

    return sub_root


def _synthesise_carried_attributes(
    preceding_measures: List[ET.Element],
) -> Optional[ET.Element]:
    """An `<attributes>` element holding the last-seen value of every
    state-bearing `<attributes>` child across `preceding_measures`, marked
    with `CARRIED_MARKER`. Returns `None` when nothing was declared before
    the section (in which case nothing is prepended).
    """
    single: dict = {}
    per_staff: dict = {tag: {} for tag in _CARRIED_PER_STAFF}

    for measure in preceding_measures:
        for attrs in measure.findall("attributes"):
            for child in attrs:
                if child.tag in _CARRIED_SINGLE:
                    single[child.tag] = child
                elif child.tag in _CARRIED_PER_STAFF:
                    per_staff[child.tag][child.attrib.get("number", "1")] = child

    if not single and not any(per_staff.values()):
        return None

    out = ET.Element("attributes", {CARRIED_MARKER: "yes"})
    for tag in _CARRIED_SINGLE:
        if tag in single:
            out.append(single[tag])
    for tag in _CARRIED_PER_STAFF:
        for _number, child in sorted(per_staff[tag].items()):
            out.append(child)
    return out
