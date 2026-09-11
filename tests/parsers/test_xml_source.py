# tests/parsers/test_xml_source.py
import xml.etree.ElementTree as ET
import zipfile

from parsers.xml_source import (
    read_musicxml_root,
    read_musicxml_root_and_origin,
    timewise_to_partwise,
)

CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container>
  <rootfiles>
    <rootfile full-path="{rootfile_name}"></rootfile>
  </rootfiles>
</container>
"""


def test_read_musicxml_root_handles_plain_musicxml(minimal_score):
    root = read_musicxml_root(minimal_score)
    assert root.tag == "score-partwise"


def test_read_musicxml_root_reads_plain_musicxml_misnamed_mxl(tmp_path, minimal_score):
    """T10: dispatch is on contents, not extension - a plain MusicXML file
    that happens to carry a .mxl extension still loads rather than being
    treated as a (non-existent) zip container."""
    with open(minimal_score, "rb") as f:
        musicxml_bytes = f.read()
    mislabelled = tmp_path / "actually_plain.mxl"
    mislabelled.write_bytes(musicxml_bytes)

    root = read_musicxml_root(str(mislabelled))
    assert root.tag == "score-partwise"


def test_read_musicxml_root_follows_container_manifest_not_a_guessed_name(tmp_path, minimal_score):
    """The container manifest, not a guessed member name (e.g. "score.xml"),
    is what identifies the real score inside a .mxl - this fixture uses a
    deliberately unrelated member name to prove the manifest is actually
    being read rather than a convention being assumed."""
    with open(minimal_score, "rb") as f:
        musicxml_bytes = f.read()

    mxl_path = tmp_path / "renamed.mxl"
    with zipfile.ZipFile(mxl_path, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            CONTAINER_XML.format(rootfile_name="totally_unrelated_member_name.xml"),
        )
        archive.writestr("totally_unrelated_member_name.xml", musicxml_bytes)

    root = read_musicxml_root(str(mxl_path))
    assert root.tag == "score-partwise"


def test_timewise_to_partwise_returns_same_object_for_partwise(minimal_score):
    root = ET.parse(minimal_score).getroot()
    assert timewise_to_partwise(root) is root


TIMEWISE_TWO_PARTS_TWO_MEASURES = """<?xml version="1.0" encoding="UTF-8"?>
<score-timewise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Flute</part-name></score-part>
    <score-part id="P2"><part-name>Cello</part-name></score-part>
  </part-list>
  <measure number="1">
    <part id="P1">
      <note><pitch><step>C</step><octave>5</octave></pitch></note>
    </part>
    <part id="P2">
      <note><pitch><step>C</step><octave>3</octave></pitch></note>
    </part>
  </measure>
  <measure number="2">
    <part id="P1">
      <note><pitch><step>D</step><octave>5</octave></pitch></note>
    </part>
    <part id="P2">
      <note><pitch><step>D</step><octave>3</octave></pitch></note>
    </part>
  </measure>
</score-timewise>
"""


def test_timewise_to_partwise_converts_shape():
    timewise_root = ET.fromstring(TIMEWISE_TWO_PARTS_TWO_MEASURES)
    root = timewise_to_partwise(timewise_root)

    assert root.tag == "score-partwise"
    assert root.attrib == {"version": "4.0"}

    # Header (non-measure) children kept, in original order.
    header_tags = [child.tag for child in root if child.tag != "part"]
    assert header_tags == ["part-list"]

    parts = root.findall("part")
    assert [part.get("id") for part in parts] == ["P1", "P2"]

    flute_measures = parts[0].findall("measure")
    assert [m.get("number") for m in flute_measures] == ["1", "2"]
    assert (
        flute_measures[0].find("note/pitch/step").text == "C"
        and flute_measures[1].find("note/pitch/step").text == "D"
    )

    cello_measures = parts[1].findall("measure")
    assert [m.get("number") for m in cello_measures] == ["1", "2"]
    assert (
        cello_measures[0].find("note/pitch/step").text == "C"
        and cello_measures[1].find("note/pitch/step").text == "D"
    )


TIMEWISE_PART_MISSING_FROM_MEASURE_1 = """<?xml version="1.0" encoding="UTF-8"?>
<score-timewise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Flute</part-name></score-part>
    <score-part id="P2"><part-name>Cello</part-name></score-part>
  </part-list>
  <measure number="1">
    <part id="P1">
      <note><pitch><step>C</step><octave>5</octave></pitch></note>
    </part>
  </measure>
  <measure number="2">
    <part id="P1">
      <note><pitch><step>D</step><octave>5</octave></pitch></note>
    </part>
    <part id="P2">
      <note><pitch><step>D</step><octave>3</octave></pitch></note>
    </part>
  </measure>
</score-timewise>
"""


def test_timewise_to_partwise_keeps_part_missing_from_first_measure():
    timewise_root = ET.fromstring(TIMEWISE_PART_MISSING_FROM_MEASURE_1)
    root = timewise_to_partwise(timewise_root)

    parts = root.findall("part")
    assert [part.get("id") for part in parts] == ["P1", "P2"]

    cello = parts[1]
    cello_measures = cello.findall("measure")
    assert [m.get("number") for m in cello_measures] == ["1", "2"]
    assert len(list(cello_measures[0])) == 0
    assert cello_measures[1].find("note/pitch/step").text == "D"


def test_read_musicxml_root_and_origin_reports_timewise(tmp_path):
    timewise_path = tmp_path / "timewise.musicxml"
    timewise_path.write_text(TIMEWISE_TWO_PARTS_TWO_MEASURES, encoding="utf-8")

    root, was_timewise = read_musicxml_root_and_origin(str(timewise_path))
    assert was_timewise is True
    assert root.tag == "score-partwise"


def test_read_musicxml_root_and_origin_reports_partwise(minimal_score):
    root, was_timewise = read_musicxml_root_and_origin(minimal_score)
    assert was_timewise is False
    assert root.tag == "score-partwise"
