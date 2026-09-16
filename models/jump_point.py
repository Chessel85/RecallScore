# models/jump_point.py
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class JumpPoint:
    """A named song section ([Intro], [Verse 1], [Chorus], [Bridge], ...),
    as a span of measures. Named "jump point" rather than "section" so it
    reads distinctly from the unrelated multi-section MusicXML feature
    (NavigationController.select_section/step_section, "one file holding
    several independent pieces" - UserPlans/MultiSectionScores.md) - the two
    were confusable under one name even though they share nothing but the
    word. A jump point is a span, not a point - the user is inside one for
    many bars, and a span is what makes Region 5's Ctrl+Home/Ctrl+End and
    the change cue meaningful.

    Populated by UgTimelineBuilder from the [Section] labels it walks and by
    GpTimelineBuilder from GP's own <Section> markers (see build_jump_points
    below); the label is passed through verbatim (no normalising, no
    title-casing, homoglyphs included). end_measure is the bar before the
    next jump point starts, or the last bar of the score for the final one.

    MusicXML has no JumpPoint of its own - its equivalent, <rehearsal>
    marks, is already a first-class DirectionMark kind with its own Region
    3/5 rows, Find target and Performance Report line, so
    NavigationController's Ctrl+Alt+Left/Right reads those directly instead
    of duplicating them as JumpPoints (invariant 8: two copies of the same
    fact will diverge)."""

    label: str
    start_measure: int
    end_measure: int


def build_jump_points(measure_labels: List[str], total_measures: int) -> List[JumpPoint]:
    """One JumpPoint per run of consecutive measures sharing a label.
    end_measure is the bar before the next jump point starts (or
    total_measures for the last). Measures before the first label carry ""
    and are not given a jump point.

    Shared by UgTimelineBuilder ([Section] lines) and GpTimelineBuilder (GP's
    <Section> markers) so the two formats can't drift on what "a run of
    measures sharing a label" means."""
    points: List[JumpPoint] = []
    current: Optional[str] = None
    for idx, label in enumerate(measure_labels):
        measure = idx + 1
        if not label:
            continue
        if current is not None and label == current:
            continue
        if points:
            points[-1].end_measure = measure - 1
        points.append(JumpPoint(label=label, start_measure=measure, end_measure=measure))
        current = label
    if points:
        points[-1].end_measure = max(points[-1].start_measure, total_measures)
    return points
