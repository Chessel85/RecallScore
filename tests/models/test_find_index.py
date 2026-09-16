# tests/models/test_find_index.py
"""P0 - value-level Find (models/find_index.py, models/find_target.py).

Covers FindTarget.value refinement (D1), the VALUE_EXPANDED_KEYS allow-list
(D2), per-row occurrence counts (D13) and the attribute-target cache (D10).
"""
from models.find_target import VALUE_EXPANDED_KEYS, FindTarget, occurrence_label


def _target(md, key, value=None, category="attribute"):
    return next(
        t for t in md.available_find_targets()
        if t.category == category and t.key == key and t.value == value
    )


# --- occurrence_label wording (D13) -----------------------------------

def test_occurrence_label_singular_and_plural():
    assert occurrence_label(1) == "1 occurrence"
    assert occurrence_label(0) == "0 occurrences"
    assert occurrence_label(78) == "78 occurrences"


# --- value targets: which keys expand (D2) --------------------------

def test_value_expanded_key_offers_an_any_target_plus_one_per_distinct_value(
    timeline, dynamics_articulation_fingering_score
):
    md = timeline(dynamics_articulation_fingering_score)

    articulation = [
        t for t in md.available_find_targets()
        if t.category == "attribute" and t.key == "articulation"
    ]

    # Stage 10: the trill moved out into its own `ornament` key.
    assert [t.value for t in articulation] == [None, "staccato"]
    assert articulation[0].label == "articulation (any)"
    assert all(t.label == "articulation" for t in articulation[1:])


def test_key_outside_the_allow_list_offers_only_an_any_target(
    timeline, dynamics_articulation_fingering_score
):
    """fingering has two distinct values here (1 and 5) but is deliberately
    not value-expanded (D2) - the user's "potential for overwhelming"
    case."""
    md = timeline(dynamics_articulation_fingering_score)
    assert "fingering" not in VALUE_EXPANDED_KEYS

    fingering = [
        t for t in md.available_find_targets()
        if t.category == "attribute" and t.key == "fingering"
    ]

    assert [t.value for t in fingering] == [None]
    assert fingering[0].label == "fingering"  # no "(any)" suffix


# --- value targets: matching (D1) ----------------------------------

def test_a_value_target_matches_only_its_own_value(
    timeline, dynamics_articulation_fingering_score
):
    md = timeline(dynamics_articulation_fingering_score)
    staccato = _target(md, "articulation", "staccato")
    trill = _target(md, "ornament", "trill")

    staccato_idx = md.find_index.sorted_candidate_indices(staccato)
    trill_idx = md.find_index.sorted_candidate_indices(trill)

    assert [md.timeline_slices[i].beat_position for i in staccato_idx] == [2.0]
    assert [md.timeline_slices[i].beat_position for i in trill_idx] == [3.0]


def test_a_comma_joined_multi_value_note_matches_each_of_its_values(
    timeline, multi_value_technical_score
):
    """The one note carries pluck "i, m, a" - a value target for any one of
    the three must match it (membership over the split list, never == on the
    whole string)."""
    md = timeline(multi_value_technical_score)

    for value in ("i", "m", "a"):
        target = FindTarget("attribute", "pluck", "pluck", value)
        idx = md.find_index.sorted_candidate_indices(target)
        assert idx == [0], f"pluck value {value!r} should match the note at slice 0"

    absent = FindTarget("attribute", "pluck", "pluck", "p")
    assert md.find_index.sorted_candidate_indices(absent) == []


# --- occurrence counts (D13) -------------------------------------

def test_available_targets_with_counts_reports_position_counts(
    timeline, dynamics_articulation_fingering_score
):
    md = timeline(dynamics_articulation_fingering_score)
    counts = dict(md.available_find_targets_with_counts())

    # Stage 10: the trill is now `ornament`, not `articulation`.
    any_articulation = _target(md, "articulation")
    assert counts[any_articulation] == 1  # staccato slice only


def test_a_chord_of_all_staccato_notes_counts_as_one_occurrence(
    timeline, chord_all_staccato_score
):
    md = timeline(chord_all_staccato_score)
    counts = dict(md.available_find_targets_with_counts())

    any_articulation = _target(md, "articulation")
    # Three chord notes + one single note = 4 notes, but only 2 positions.
    assert counts[any_articulation] == 2


def test_no_offered_row_ever_reads_zero_occurrences(
    timeline, dynamics_articulation_fingering_score
):
    md = timeline(dynamics_articulation_fingering_score)
    for target, count in md.available_find_targets_with_counts():
        assert count >= 1, f"{target!r} was offered with {count} occurrences"


def test_the_count_equals_the_number_of_alt_right_presses_to_wrap(
    timeline, dynamics_articulation_fingering_score
):
    # Stage 10 split articulation/ornament into two single-occurrence keys
    # (staccato, trill) - fingering (two distinct positions, G5 and C3) is
    # what still gives this test a real multi-step wrap to exercise.
    md = timeline(dynamics_articulation_fingering_score)
    target = _target(md, "fingering")  # any: 2 occurrences
    (count,) = [c for t, c in md.available_find_targets_with_counts() if t == target]
    assert count == 2

    first = md.find_occurrence(target, from_index=md.active_event_index, direction=1)
    index = first
    for _ in range(count - 1):
        index = md.find_occurrence(target, from_index=index, direction=1)
    wrapped = md.find_occurrence(target, from_index=index, direction=1)

    assert wrapped == first, "pressing Alt+Right `count` times returns to the first occurrence"


# --- caching (D10) ---------------------------------------------

def test_sorted_candidate_indices_is_cached_per_key_and_value(
    timeline, dynamics_articulation_fingering_score, monkeypatch
):
    md = timeline(dynamics_articulation_fingering_score)
    any_target = FindTarget("attribute", "articulation", "articulation")
    staccato = FindTarget("attribute", "articulation", "articulation", "staccato")

    calls = []
    real = md.find_index._compute_sorted_candidates
    monkeypatch.setattr(
        md.find_index, "_compute_sorted_candidates",
        lambda t: calls.append((t.key, t.value)) or real(t),
    )

    md.find_index.sorted_candidate_indices(any_target)
    md.find_index.sorted_candidate_indices(any_target)
    md.find_index.sorted_candidate_indices(staccato)
    md.find_index.sorted_candidate_indices(staccato)

    # One scan per distinct (key, value) - the repeats are cache hits.
    assert calls == [("articulation", None), ("articulation", "staccato")]


def test_the_attribute_cache_is_dropped_when_the_voice_filter_changes(
    timeline, dynamics_articulation_fingering_score
):
    """D10: invalidate_cache() stays wired to _invalidate_visibility_cache -
    "pluck" occurs only on the guitar (P2)."""
    md = timeline(dynamics_articulation_fingering_score)
    target = FindTarget("attribute", "pluck", "pluck", "i")

    assert md.find_index.sorted_candidate_indices(target) == [0]

    md.set_active_voice_filter({("P1", 1, 1)})

    assert md.find_index.sorted_candidate_indices(target) == []


# --- marking targets respect the active parts/staves filter (Ref 7) -----

def test_marking_targets_are_limited_to_the_active_parts(
    timeline, hairpins_two_parts_score
):
    """Guitar (P1) has a diminuendo, Cello (P2) a crescendo. Muting P1
    entirely must drop its hairpin from Find's catalog and from the
    diminuendo target's own occurrence list, while leaving the crescendo
    (P2) target untouched - the same live, uncached read find_occurrence
    already gives attribute targets."""
    md = timeline(hairpins_two_parts_score)

    diminuendo_start = FindTarget("marking", "diminuendo_start", "Diminuendo, start")
    crescendo_start = FindTarget("marking", "crescendo_start", "Crescendo, start")
    assert md.find_index.sorted_candidate_indices(diminuendo_start) != []
    assert md.find_index.sorted_candidate_indices(crescendo_start) != []

    md.set_active_voice_filter({("P2", 1, 1)})

    assert md.find_index.sorted_candidate_indices(diminuendo_start) == []
    assert md.find_index.sorted_candidate_indices(crescendo_start) != []

    keys = [(t.category, t.key) for t in md.available_find_targets()]
    assert ("marking", "diminuendo_start") not in keys
    assert ("marking", "diminuendo_any") not in keys
    assert ("marking", "crescendo_start") in keys


def test_find_occurrence_sounds_the_boundary_cue_once_the_armed_target_is_hidden(
    timeline, hairpins_two_parts_score
):
    """The scenario in the user's request: arm a target, close the dialog,
    then mute the part it lives on via Region 2 - find_next/find_previous
    must not move (find_occurrence returns None), which is what makes
    NavigationController._find sound the boundary cue instead."""
    md = timeline(hairpins_two_parts_score)
    diminuendo_start = FindTarget("marking", "diminuendo_start", "Diminuendo, start")
    assert md.find_occurrence(diminuendo_start, from_index=0, direction=1) is not None

    md.set_active_voice_filter({("P2", 1, 1)})

    assert md.find_occurrence(diminuendo_start, from_index=0, direction=1) is None


def test_score_wide_marking_targets_are_never_filtered(
    timeline, hairpins_two_parts_score
):
    """A P1-owned hairpin is hidden once P1 is muted, but a marking type
    with no part_id field at all (RepeatSpan, EndingSpan, JumpPoint,
    BarlineMark, SegnoMark/CodaMark/ToCodaMark/FineMark, NavigationJump)
    is unaffected by any parts/staves filter - the generic hasattr guard in
    _is_marking_visible, not a hairpin-specific rule."""
    from models.repeat_span import RepeatSpan

    md = timeline(hairpins_two_parts_score)
    md.set_active_voice_filter({("P2", 1, 1)})

    p1_span = next(s for s in md.hairpin_spans if s.part_id == "P1")
    assert not md.find_index._is_marking_visible(p1_span)

    assert md.find_index._is_marking_visible(RepeatSpan(start_measure=1, end_measure=2))
