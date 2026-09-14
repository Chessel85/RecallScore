# models/directive_mark.py
from dataclasses import dataclass


@dataclass
class DirectiveMark:
    """PerformanceMarkingsStrategy.md section 9 / MusicXMLMarkingInventory.md
    #6: a <direction directive="yes"> - MusicXML's one explicit marker for a
    score-wide instruction ("Play with vigour") rather than a local one, as
    opposed to a written performance direction. Collected wherever it
    appears in the file (any part) since the flag itself, not the part it
    happens to sit in, is what makes it score-level; a duplicate (measure,
    label) pair - the same instruction printed in more than one part - is
    kept once (TimelineBuilder._handle_direction dedupes at append time).

    Listed in Region 1's Directives list in bar order (MusicData.
    get_directive_rows); IN the note list by default (PI tweaks stage 5) as
    a score-level point row at its own position - Ctrl+N on a Region 1
    directive row hides/reshows it there (MusicData.
    toggle_directive_in_note_list), per-score in the .rsc. Populated by
    TimelineBuilder as a side effect of build(); MIDI/GP/UG builders stub
    this empty, like every other MusicXML-only marker list."""

    measure: int
    label: str
    quarters_from_start: float
