# tests/models/test_marking_classification.py
"""PerformanceMarkingsImplementationPlanV2.md stage 1: table lookups against
models/marking_classification.py - the one place levels/dimensions are
declared, transcribed from UserPlans/inventory.csv."""
import pytest

from models.marking_classification import (
    CLASSIFICATION,
    DIMENSIONS,
    LEVELS,
    classification_for,
)


def test_words_allows_stave_part_and_score_as_a_point():
    c = classification_for("direction", "words")
    assert c.levels == ("stave", "part", "score")
    assert c.dimension == "point"


def test_wedge_is_a_length_at_stave_part_and_score():
    c = classification_for("direction", "wedge")
    assert c.levels == ("stave", "part", "score")
    assert c.dimension == "length"


def test_dashes_and_bracket_inherit_level_from_their_words():
    for element in ("dashes", "bracket"):
        c = classification_for("direction", element)
        assert c.inherits_level_from_words is True
        assert c.dimension == "length"


def test_pedal_is_part_level_length_with_a_point_variant():
    c = classification_for("direction", "pedal")
    assert c.levels == ("part",)
    assert c.dimension == "length"
    assert c.has_point_variant is True


def test_metronome_is_score_only_point():
    c = classification_for("direction", "metronome")
    assert c.levels == ("score",)
    assert c.dimension == "point"


def test_barline_bar_style_regular_is_no_row():
    c = classification_for("barline", "bar-style-regular")
    assert c.levels == ()
    assert c.dimension == "none"


def test_repeats_endings_key_and_time_are_agreement_gated():
    for section, element in (
        ("barline", "repeat-forward"),
        ("barline", "repeat-backward"),
        ("barline", "ending"),
        ("attributes", "key"),
        ("attributes", "time"),
    ):
        c = classification_for(section, element)
        assert c.score_or_part_by_agreement is True
        assert "score" in c.levels and "part" in c.levels


def test_note_fermata_is_a_note_row_plus_an_aggregate():
    c = classification_for("note", "fermata")
    assert c.levels == ("note", "score", "part")
    assert c.note_fermata_aggregate is True


def test_note_attributes_never_carry_a_marking_row_dimension():
    for element in ("tied", "slur", "tuplet", "articulations", "technical", "grace"):
        c = classification_for("note", element)
        assert c.levels == ("note",)
        assert c.dimension == "attribute"


def test_barline_fermata_and_signs_are_barline_level():
    for element in ("fermata", "segno", "coda"):
        c = classification_for("barline", element)
        assert c.levels == ("barline",)


def test_unknown_element_is_not_classified():
    with pytest.raises(KeyError):
        classification_for("direction", "not-a-real-element")


def test_every_entry_uses_only_declared_levels_and_dimensions():
    for classification in CLASSIFICATION.values():
        assert classification.dimension in DIMENSIONS
        for level in classification.levels:
            assert level in LEVELS
