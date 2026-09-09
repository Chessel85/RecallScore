# parsers/timeline_builder_factory.py
"""S2: picks the right timeline builder for a score's file format and runs it.

This dispatch used to sit inside MusicData.__post_init__, which meant
models/music_data.py imported all four builders at module scope - a
models -> parsers dependency, and an expensive one: TimelineBuilder and
UgTimelineBuilder both import music21, so merely importing the data model
pulled in ~460ms and ~700 modules of parsing machinery whether or not
anything was ever parsed.

MusicData still supports the documented `MusicData(file_path=...)` shortcut
(the ~1ms ElementTree path timeline tests rely on - see CLAUDE.md); it now
reaches this module through a FUNCTION-LOCAL import, so the dependency is
deferred to the moment a file is actually parsed rather than paid at import
time. That local import is deliberate, not an oversight.

Each builder takes its already-parsed source object when the matching
reader has one (xml_root/midi_source/gp_source/ug_source), so a file is
never walked twice - the shared-source rule described in CLAUDE.md. UG is
the exception with no fallback: a UG import's file_path is a synthetic slug
with nothing fetchable at it, so ug_source must always be supplied.
"""
from typing import List

from models.score_section import ScoreSection
from models.timeline_build import TimelineBuild
from parsers.gp_timeline_builder import GpTimelineBuilder
from parsers.midi_timeline_builder import MidiTimelineBuilder
from parsers.score_sections import split_score_sections
from parsers.timeline_builder import TimelineBuilder
from parsers.ug_timeline_builder import UgTimelineBuilder
from parsers.xml_source import read_musicxml_root


def builder_for(music_data):
    """The timeline builder matching this score's format, unrun.

    Dispatches on MusicData's own is_midi/is_gp/is_ug extension properties
    so the format test lives in exactly one place - MusicXML is the default,
    not a fourth explicit check, because it is the only format identified by
    more than one extension (.xml/.musicxml/.mxl)."""
    if music_data.is_midi:
        return MidiTimelineBuilder(
            music_data.file_path, music_data.parts_info, source=music_data.midi_source
        )
    if music_data.is_gp:
        return GpTimelineBuilder(
            music_data.file_path, music_data.parts_info, source=music_data.gp_source
        )
    if music_data.is_ug:
        return UgTimelineBuilder(
            music_data.file_path, music_data.parts_info, source=music_data.ug_source
        )
    return TimelineBuilder(
        music_data.file_path, music_data.parts_info, root=music_data.xml_root
    )


def build_timeline(music_data) -> TimelineBuild:
    """Run the matching builder and return everything it produced.

    The documented single-build entry point - tests drive it directly and
    it stays as it is. `build_sections` (below) sits beside it for the
    multi-section case and reuses it for every format that only ever has
    one section.
    """
    return TimelineBuild.from_builder(builder_for(music_data))


def build_sections(music_data) -> List[ScoreSection]:
    """One `ScoreSection` per independent piece in the file (see
    `UserPlans/MultiSectionScores.md`).

    A non-MusicXML score, or a MusicXML file with no `<measure number>`
    restart, yields a single section with an empty label whose build is
    exactly `build_timeline(music_data)` - bit-identical to before this
    feature. A multi-section MusicXML file yields one section per sub-root,
    each built by a fresh `TimelineBuilder` over that sub-root as though it
    were the whole file (so `_detect_pickup`, bar numbering and every
    timeline cache are naturally section-local).
    """
    is_musicxml = not (music_data.is_midi or music_data.is_gp or music_data.is_ug)
    if not is_musicxml:
        return [ScoreSection(index=0, label="", build=build_timeline(music_data))]

    root = music_data.xml_root
    if root is None:
        root = read_musicxml_root(music_data.file_path)
    sections_xml = split_score_sections(root)
    if len(sections_xml) <= 1:
        return [ScoreSection(index=0, label="", build=build_timeline(music_data))]

    sections: List[ScoreSection] = []
    for section_xml in sections_xml:
        builder = TimelineBuilder(
            music_data.file_path, music_data.parts_info, root=section_xml.root
        )
        sections.append(
            ScoreSection(
                index=section_xml.index,
                label=section_xml.label,
                build=TimelineBuild.from_builder(builder),
            )
        )
    return sections
