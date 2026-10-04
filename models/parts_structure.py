# parts_structure.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PartStructureInfo:
    part_id: str = ""
    name: str = "Classical Guitar"
    gmidi_program: int = 25
    staves_clefs: Dict[int, str] = field(default_factory=dict)
    staves_voices: Dict[int, List[int]] = field(default_factory=dict)
    # (staff_id, voice_id) -> display name override for Region 2's voice
    # row, e.g. Guitar Pro's synthetic chord/strum voice showing as
    # "Chords" instead of the default "Voice N". Absent entries keep
    # today's f"Voice {v}" default - no behaviour change for MusicXML/MIDI.
    voice_names: Dict[Tuple[int, int], str] = field(default_factory=dict)
    # Wishlist #8: a percussion-clef MusicXML part or a MIDI channel-10
    # track. gmidi_program is meaningless here (percussion selects sound by
    # NOTE NUMBER on a dedicated bank, not by GM program) - MusicData routes
    # playback for such a part to the GM percussion bank instead of reading
    # gmidi_program at all. See CLAUDE.md's percussion-support entry.
    is_percussion: bool = False
    # Set only while the user has flagged this part as percussion: the
    # (staves_voices, voice_names) it had before, restored on un-flagging.
    pre_percussion_structure: Optional[
        Tuple[Dict[int, List[int]], Dict[Tuple[int, int], str]]
    ] = None
    # Classical guitar: <staff-details number="n"><staff-type>alternate
    # </staff-type> marks stave n as "the same music as the stave before
    # it, shown differently" (a TAB stave under the treble). Maps that
    # alternate staff -> the staff it shadows (n -> n-1). Only the MusicXML
    # reader sets it; drives Parts > Collapse staves (models/
    # stave_collapse.py).
    alternate_staves: Dict[int, int] = field(default_factory=dict)
