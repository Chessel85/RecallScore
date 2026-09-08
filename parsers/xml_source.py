# parsers/xml_source.py
import xml.etree.ElementTree as ET
import zipfile
from typing import Optional

from parsers.score_load_error import ScoreLoadError


def read_musicxml_root(file_path: str) -> Optional[ET.Element]:
    """Returns the root <score-partwise>/<score-timewise> Element for either
    a plain MusicXML file or a compressed .mxl one.

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
