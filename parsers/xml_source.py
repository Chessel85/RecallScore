# parsers/xml_source.py
import xml.etree.ElementTree as ET
import zipfile
from typing import Optional, Tuple

from parsers.score_load_error import ScoreLoadError


def timewise_to_partwise(root: ET.Element) -> ET.Element:
    """Converts a <score-timewise> root to an equivalent <score-partwise>
    root, in memory. Returns `root` itself, unchanged, when it is not
    timewise (the tag check is the only work done in that case).

    A timewise document nests parts inside measures; partwise nests measures
    inside parts. The header children (work, identification, defaults,
    credit, part-list, ...) are identical in both shapes and are reused as-is
    (no deep copy - the timewise tree is discarded after conversion).

    Part order is first-appearance order, scanning measures in document
    order - this matches "parts of measure 1" whenever measure 1 contains
    every part, but also keeps a part that is absent from measure 1 instead
    of silently dropping it.

    Measures are matched across parts by position, never by the `number`
    attribute, since multi-section scores restart numbering. Each output
    measure carries a copy of the timewise measure's own attributes
    (`number`, `implicit`, `width`, ...); a timewise measure with no <part>
    for some id still produces an empty measure for that part, so every
    part ends up with the same number of measures and bar indices stay
    aligned.
    """
    if root.tag != "score-timewise":
        return root

    new_root = ET.Element("score-partwise", dict(root.attrib))

    part_ids_in_order = []
    seen_ids = set()
    measures = [child for child in root if child.tag == "measure"]
    for measure in measures:
        for part in measure.findall("part"):
            part_id = part.get("id")
            if part_id not in seen_ids:
                seen_ids.add(part_id)
                part_ids_in_order.append(part_id)

    for child in root:
        if child.tag != "measure":
            new_root.append(child)

    new_parts = {
        part_id: ET.SubElement(new_root, "part", {"id": part_id})
        for part_id in part_ids_in_order
    }

    for measure in measures:
        parts_by_id = {part.get("id"): part for part in measure.findall("part")}
        for part_id in part_ids_in_order:
            new_measure = ET.SubElement(
                new_parts[part_id], "measure", dict(measure.attrib)
            )
            source_part = parts_by_id.get(part_id)
            if source_part is not None:
                for note_or_attr in source_part:
                    new_measure.append(note_or_attr)

    return new_root


def read_musicxml_root_and_origin(file_path: str) -> Tuple[Optional[ET.Element], bool]:
    """Returns `(root, was_timewise)`, where `root` is always a
    <score-partwise> Element - a timewise document is converted in memory by
    `timewise_to_partwise` - and `was_timewise` says whether that conversion
    happened. Exists only so `MusicXMLReader` can hand music21 the converted
    tree (music21 refuses timewise documents outright); everything else
    should call `read_musicxml_root`.
    """
    raw_root = _read_root_as_written(file_path)
    return timewise_to_partwise(raw_root), raw_root.tag == "score-timewise"


def read_musicxml_root(file_path: str) -> Optional[ET.Element]:
    """Returns the root Element for either a plain MusicXML file or a
    compressed .mxl one, always normalised to <score-partwise> - a
    <score-timewise> document is converted in memory (see
    `timewise_to_partwise`) so this is the single normalisation point and
    nothing downstream (parsers, timeline builders, models) ever needs to
    handle timewise.

    Dispatch is on the file's actual contents, not its extension: a plain
    MusicXML document misnamed .mxl still loads, and a zip container is
    unpacked whatever it is called - asking a screen-reader user to go and
    rename a file the reader could have opened is the worse outcome (T10).
    .mxl is a zip container whose member the score lives in is named by
    META-INF/container.xml's rootfile - never the outer file's name, and not
    reliably "score.xml" either (that's just what the encoders creating this
    project's own test files happen to use), so the container manifest has
    to be read rather than guessed.

    Raises ScoreLoadError when the file is not parseable at all (malformed
    XML, a broken .mxl container). Callers must let that propagate rather
    than degrade to an empty score - a file that cannot be read is a failure
    the user needs told about, not a silently blank piece.
    """
    return read_musicxml_root_and_origin(file_path)[0]


def _read_root_as_written(file_path: str) -> Optional[ET.Element]:
    """Returns the root Element exactly as the file encodes it - either
    <score-partwise> or <score-timewise>, unconverted. Callers almost always
    want `read_musicxml_root` (always partwise) instead.
    """
    if not zipfile.is_zipfile(file_path):
        try:
            return ET.parse(file_path).getroot()
        except ET.ParseError as e:
            raise ScoreLoadError(
                "This file is not valid MusicXML - it may be corrupt or the "
                "wrong type of file.",
                cause=e,
            )
        except OSError as e:
            raise ScoreLoadError(
                "This file could not be opened for reading.", cause=e
            )

    try:
        with zipfile.ZipFile(file_path) as archive:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile_el = container.find("./rootfiles/rootfile")
            if rootfile_el is None or "full-path" not in rootfile_el.attrib:
                raise ScoreLoadError(
                    "This compressed MusicXML (.mxl) file is missing its "
                    "container manifest - it may be corrupt."
                )
            return ET.fromstring(archive.read(rootfile_el.attrib["full-path"]))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise ScoreLoadError(
            "This compressed MusicXML (.mxl) file could not be opened - it "
            "may be corrupt or incomplete.",
            cause=e,
        )
