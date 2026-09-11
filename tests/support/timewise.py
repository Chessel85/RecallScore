# tests/support/timewise.py
"""Test-only inverse of parsers.xml_source.timewise_to_partwise.

Exists only to manufacture timewise input from partwise fixtures we already
trust, so Task 4 of userPlans/timewiseMusicXML.md can round-trip and
timeline-compare against a genuine (if synthetic) <score-timewise> document.
Not used by application code.
"""
import copy
import xml.etree.ElementTree as ET


def partwise_to_timewise(root: ET.Element) -> ET.Element:
    """Converts a <score-partwise> root to an equivalent <score-timewise>
    root. Deep-copies the input first so the returned tree shares no element
    objects with it - callers may keep using the original root afterwards.

    Header children (everything but <part>) are copied in document order.
    One <measure> is emitted per measure position, carrying the first part's
    measure attributes at that position, holding one <part id="..."> child
    per part with that part's measure children at that position.
    """
    if root.tag != "score-partwise":
        return root

    root = copy.deepcopy(root)
    new_root = ET.Element("score-timewise", dict(root.attrib))

    parts = [child for child in root if child.tag == "part"]
    for child in root:
        if child.tag != "part":
            new_root.append(child)

    measures_by_part = [part.findall("measure") for part in parts]
    measure_count = max((len(m) for m in measures_by_part), default=0)

    for i in range(measure_count):
        attrib_source = next(
            (measures[i] for measures in measures_by_part if i < len(measures)),
            None,
        )
        new_measure = ET.SubElement(
            new_root, "measure", dict(attrib_source.attrib) if attrib_source is not None else {}
        )
        for part, measures in zip(parts, measures_by_part):
            new_part = ET.SubElement(new_measure, "part", {"id": part.get("id")})
            if i < len(measures):
                for note_or_attr in measures[i]:
                    new_part.append(note_or_attr)

    return new_root
