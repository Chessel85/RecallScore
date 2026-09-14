# tests/parsers/test_direction_system_attribute.py
"""PerformanceMarkingsImplementationPlanV2.md stage 1: DirectionMark/
DirectionSpan/HairpinSpan carry `system` (directive="yes" folded into
"only-top") and `staff_given`, feeding stage 2's ground rule 1 ("score if
... the <direction> has system="only-top"/"also-top" or directive="yes"")
and ground rule 3 ("stave if ... the element gives <staff>")."""
import xml.etree.ElementTree as ET

from parsers.timeline_builder import _direction_system, _staff_given


def _direction(xml: str):
    return ET.fromstring(xml)


def test_system_only_top_is_read_verbatim():
    elem = _direction('<direction system="only-top"><direction-type/></direction>')
    assert _direction_system(elem) == "only-top"


def test_system_also_top_is_read_verbatim():
    elem = _direction('<direction system="also-top"><direction-type/></direction>')
    assert _direction_system(elem) == "also-top"


def test_directive_yes_is_folded_into_only_top():
    elem = _direction('<direction directive="yes"><direction-type/></direction>')
    assert _direction_system(elem) == "only-top"


def test_directive_takes_priority_over_a_written_system():
    # Shouldn't occur in real files, but directive="yes" already means the
    # instruction is score-wide regardless of whatever system says.
    elem = _direction('<direction system="none" directive="yes"><direction-type/></direction>')
    assert _direction_system(elem) == "only-top"


def test_no_system_or_directive_is_empty_string():
    elem = _direction('<direction><direction-type/></direction>')
    assert _direction_system(elem) == ""


def test_staff_given_true_when_staff_child_present():
    elem = _direction('<direction><staff>2</staff><direction-type/></direction>')
    assert _staff_given(elem) is True


def test_staff_given_false_when_staff_child_absent():
    elem = _direction('<direction><direction-type/></direction>')
    assert _staff_given(elem) is False


def test_staff_given_false_when_staff_child_is_empty():
    elem = _direction('<direction><staff></staff><direction-type/></direction>')
    assert _staff_given(elem) is False


def test_real_file_with_only_top_directions_still_parses():
    """files/etude 1 tablature.mxl carries the plan's own example: an
    ""Allegro"" <words> and a <metronome>, both on <direction
    system="only-top">. Not a vocabulary match for either (so no
    DirectionMark results), so this is a smoke test that a real file
    exercising the attribute still builds cleanly with the new fields."""
    from models.music_data import MusicData

    md = MusicData(file_path="files/etude 1 tablature.mxl")
    assert md.total_measures > 0
