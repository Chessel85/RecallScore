# models/stave_collapse.py
"""Parts > Collapse staves: one part's alternate stave folded into the stave
it shadows.

Classical guitar scores write every note twice in one part - the treble
stave carries left-hand fingering, the TAB stave beneath it (MusicXML
<staff-type>alternate</staff-type>, see PartStructureInfo.alternate_staves)
carries string and fret. Collapsing hides the alternate stave (MusicData.
get_score_structure leaves it out, so Region 2 has no row for it and the
voice filter drops its notes from navigation and playback) and lets each
kept note show its partner's attributes too (NoteRenderer.
note_attribute_pairs).

MusicXML has no note-by-note link between the two staves, so notes are
paired by onset (the slice) and pitch: within one slice, each kept-stave
note takes the first unused alternate-stave note of equal midi_pitch.

The partner is read at display time, never copied onto the kept NoteData,
so the alternate stave's string/fret stay one fact in one place
(invariant 8). The collapsed set itself is MusicData.collapsed_stave_parts
(persisted per score); only the derived pairing map is cached here.
"""
from typing import Dict, Optional

from models.note_data import NoteData


class StaveCollapse:
    def __init__(self, data):
        self.data = data
        # id(kept note) -> its alternate-stave partner, or None until first
        # needed. Dropped whenever the collapsed set or the timeline changes.
        self._partners: Optional[Dict[int, NoteData]] = None

    def invalidate_cache(self) -> None:
        self._partners = None

    def _part(self, part_id: str):
        return next((p for p in self.data.parts_info if p.part_id == part_id), None)

    def collapsible(self, part_id: str) -> bool:
        part = self._part(part_id)
        return part is not None and bool(part.alternate_staves)

    def is_collapsed(self, part_id: str) -> bool:
        return part_id in self.data.collapsed_stave_parts

    def set_collapsed(self, part_id: str, on: bool) -> bool:
        """Collapse or uncollapse `part_id`'s alternate stave(s). Returns
        whether anything changed - False for a part with no alternate stave
        or one already in the requested state."""
        if not self.collapsible(part_id) or self.is_collapsed(part_id) == on:
            return False
        if on:
            self.data.collapsed_stave_parts.add(part_id)
        else:
            self.data.collapsed_stave_parts.discard(part_id)
        self.invalidate_cache()
        return True

    def hidden_staves(self, part_id: str):
        """The alternate staves left out of Region 2 for `part_id` - every
        one it has while collapsed, none otherwise."""
        if not self.is_collapsed(part_id):
            return set()
        part = self._part(part_id)
        return set(part.alternate_staves) if part is not None else set()

    def partner_for(self, note: NoteData) -> Optional[NoteData]:
        if not self.data.collapsed_stave_parts:
            return None
        if self._partners is None:
            self._partners = self._build_partners()
        return self._partners.get(id(note))

    def _build_partners(self) -> Dict[int, NoteData]:
        alternates = {
            p.part_id: p.alternate_staves
            for p in self.data.parts_info
            if p.part_id in self.data.collapsed_stave_parts and p.alternate_staves
        }
        partners: Dict[int, NoteData] = {}
        if not alternates:
            return partners
        for event_slice in self.data._real_timeline_slices:
            # (part_id, kept staff) -> that slice's alternate-stave notes
            # still unclaimed, in score order.
            unclaimed: Dict[tuple, list] = {}
            for note in event_slice.notes:
                alt = alternates.get(note.part_id)
                if alt and note.staff in alt:
                    unclaimed.setdefault((note.part_id, alt[note.staff]), []).append(note)
            if not unclaimed:
                continue
            for note in event_slice.notes:
                candidates = unclaimed.get((note.part_id, note.staff))
                if not candidates or note.midi_pitch is None:
                    continue
                for i, candidate in enumerate(candidates):
                    if candidate.midi_pitch == note.midi_pitch:
                        partners[id(note)] = candidates.pop(i)
                        break
        return partners
