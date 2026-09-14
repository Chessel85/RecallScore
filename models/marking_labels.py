# models/marking_labels.py
"""PerformanceMarkingsStrategy.md section 15: the single source of marking
label text. Region 5's one-line range rendering (section 6) and the note
list's start/end rendering (section 5, stage 3) are two views of the same
vocabulary; keeping both here is what stops them drifting apart (CLAUDE.md
invariant 8). Owns no state - pure functions over the measure/beat numbers
callers already have from a span or mark."""
from typing import Optional

from models import vocabulary

bar_word = vocabulary.bar_word


def _beat_str(beat_position: float) -> str:
    return str(int(beat_position)) if float(beat_position).is_integer() else str(beat_position)


def bar_beat_label(
    word: str, measure: int, beat_position: float, beats_in_bar: Optional[int] = None
) -> str:
    """"bar N" on the downbeat; "bar N beat B" otherwise - only markers
    actually falling mid-bar name a beat (user's decision).

    The timeline's own "barline after the last beat" convention
    (`parsers/timeline_builder.py` `_PartState.beat_position`,
    `_flush_open_direction_spans`, the barline fermata's `1.0 + ts_num`)
    represents the barline itself as one unit past the last real beat - a
    position that is internally consistent but reads as nonsense aloud
    ("beat 5" in 4/4). `beats_in_bar`, when supplied, is that bar's time
    signature numerator; a beat_position at or past `beats_in_bar + 1` is
    that barline and is worded "end of <word> N" instead. The fix lives
    here, the single place every report and Region 5 row formats a
    bar/beat pair (CLAUDE.md invariant 8), rather than in the timeline,
    which would have to invent a value with no other use."""
    if beats_in_bar is not None and float(beat_position) >= beats_in_bar + 1:
        return f"end of {word} {measure}"
    if float(beat_position) == 1.0:
        return f"{word} {measure}"
    return f"{word} {measure} beat {_beat_str(beat_position)}"


def start_label(name: str) -> str:
    """Note list span-start wording (strategy section 5): "Repeat start",
    "Crescendo start". Region 5's own range_label is the other rendering of
    the same span."""
    return f"{name} start"


def end_label(name: str) -> str:
    """Note list span-end wording (strategy section 5): "Repeat end"."""
    return f"{name} end"


def label_suffix(label: str) -> str:
    """A point mark's own printed label, appended when it says something
    beyond the default - " A" for a rehearsal mark, " 2" for a second segno,
    nothing for the ordinary unlabelled "1" case. Shared by Region 5 and the
    note list (stage 7) so a numbered point mark reads identically in both
    (invariant 8)."""
    return f" {label}" if label and label != "1" else ""


def repeat_times_suffix(times) -> str:
    """", play N times" when the file's own <repeat>/times="N" attribute is
    present (MusicXMLMarkingInventory.md #7) - reported whatever it says,
    never inferred or suppressed for the ordinary case (invariant 14)."""
    return f", play {times} times" if times is not None else ""


def key_signature_change_label(key_name: str) -> str:
    """Structural change wording (strategy section 7), shared by Region 5's
    one-shot row, the note list's row (stage 6), and the change cue's own
    "is this a structural change" check - one source (invariant 8)."""
    return f"Key signature change: {key_name}"


def time_signature_change_label(numerator: int, denominator: int) -> str:
    return f"Time signature change: {numerator}/{denominator}"


def tempo_change_label(number: str, unit: str) -> str:
    return f"Tempo change: {number} {unit} notes per minute"


def range_label(
    word: str,
    start_measure: int,
    start_beat: float,
    end_measure: int,
    end_beat: float,
    start_beats_in_bar: Optional[int] = None,
    end_beats_in_bar: Optional[int] = None,
) -> str:
    """Region 5's one-line span rendering (section 6): a span contained in
    one bar reads singular and the bar is named once ("bar 12", or "bar 2
    beat 1 to beat 3" when the beats within that bar differ); a span
    crossing a barline reads "bars N to M" when both ends fall on the
    downbeat (repeats, endings, sections - they fall on barlines by
    construction) or the full "bar N beat B to bar M beat C" form otherwise.
    General across every span kind - callers prefix it with their own
    marking name.

    `start_beats_in_bar`/`end_beats_in_bar`, when supplied, are those
    measures' time signature numerators, passed straight to
    `bar_beat_label` so a span running to the barline (a hairpin or line
    that reaches the end of a part hits this on every score) reads "to end
    of bar N" rather than naming a beat past the end (see
    `bar_beat_label`'s docstring)."""
    if start_measure == end_measure:
        if float(start_beat) == float(end_beat):
            return bar_beat_label(word, start_measure, start_beat, start_beats_in_bar)
        end_part = (
            f"end of {word} {end_measure}"
            if end_beats_in_bar is not None and float(end_beat) >= end_beats_in_bar + 1
            else f"beat {_beat_str(end_beat)}"
        )
        return f"{word} {start_measure} beat {_beat_str(start_beat)} to {end_part}"
    if float(start_beat) == 1.0 and float(end_beat) == 1.0:
        return f"{word}s {start_measure} to {end_measure}"
    return (
        f"{bar_beat_label(word, start_measure, start_beat, start_beats_in_bar)} to "
        f"{bar_beat_label(word, end_measure, end_beat, end_beats_in_bar)}"
    )
