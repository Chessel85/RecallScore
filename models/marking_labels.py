# models/marking_labels.py
"""PerformanceMarkingsStrategy.md section 15: the single source of marking
label text. Region 5's one-line range rendering (section 6) and the note
list's start/end rendering (section 5, stage 3) are two views of the same
vocabulary; keeping both here is what stops them drifting apart (CLAUDE.md
invariant 8). Owns no state - pure functions over the measure/beat numbers
callers already have from a span or mark."""
from models import vocabulary

bar_word = vocabulary.bar_word


def _beat_str(beat_position: float) -> str:
    return str(int(beat_position)) if float(beat_position).is_integer() else str(beat_position)


def bar_beat_label(word: str, measure: int, beat_position: float) -> str:
    """"bar N" on the downbeat; "bar N beat B" otherwise - only markers
    actually falling mid-bar name a beat (user's decision)."""
    if float(beat_position) == 1.0:
        return f"{word} {measure}"
    return f"{word} {measure} beat {_beat_str(beat_position)}"


def range_label(
    word: str,
    start_measure: int,
    start_beat: float,
    end_measure: int,
    end_beat: float,
) -> str:
    """Region 5's one-line span rendering (section 6): a span contained in
    one bar reads singular and the bar is named once ("bar 12", or "bar 2
    beat 1 to beat 3" when the beats within that bar differ); a span
    crossing a barline reads "bars N to M" when both ends fall on the
    downbeat (repeats, endings, sections - they fall on barlines by
    construction) or the full "bar N beat B to bar M beat C" form otherwise.
    General across every span kind - callers prefix it with their own
    marking name."""
    if start_measure == end_measure:
        if float(start_beat) == float(end_beat):
            return bar_beat_label(word, start_measure, start_beat)
        return f"{word} {start_measure} beat {_beat_str(start_beat)} to beat {_beat_str(end_beat)}"
    if float(start_beat) == 1.0 and float(end_beat) == 1.0:
        return f"{word}s {start_measure} to {end_measure}"
    return (
        f"{bar_beat_label(word, start_measure, start_beat)} to "
        f"{bar_beat_label(word, end_measure, end_beat)}"
    )
