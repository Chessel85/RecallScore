# audio/sound_catalog.py
"""PerformanceMarkingsStrategy.md section 10.1: every sound Recall Score can
make, generated from the same declarations the audio modules use to PLAY
them - never a hand-written second list, which is exactly the "two copies of
the same fact will diverge" class of bug CLAUDE.md invariant 8 warns about.

Backs Help > Sound Icon Dictionary (widgets/sound_icon_dictionary_dialog.py).
A pure data-building module - no Qt - so it's testable and reusable on its
own.
"""
from dataclasses import dataclass, field
from typing import List, Tuple

from audio import barline_patterns
from audio.boundary_cue import boundary_cue_event
from audio.metronome import click_event_for_beat
from audio.performance_cue import performance_cue_event
from audio.position_announcer import announcement_event_for_beat
from audio.voice_confirmation_cue import (
    voice_confirmation_cue_event,
    voice_recognition_started_event,
    voice_recognition_stopped_event,
)

Event = Tuple[int, int, int, int, int]


@dataclass
class SoundCatalogEntry:
    """One row of the dictionary. `events` is the one-or-more-step sequence
    Play sounds, in order (empty for a sound with no fixed pitch to demo,
    like the live MIDI input pass-through - the dialog disables Play for
    those rather than faking a pitch)."""
    name: str
    meaning: str
    when: str
    events: List[Event] = field(default_factory=list)


def build_catalog() -> List[SoundCatalogEntry]:
    entries: List[SoundCatalogEntry] = [
        SoundCatalogEntry(
            "Bar line indicator - plain barline",
            "An ordinary bar line",
            "Bar Line Indicator on, crossing an ordinary bar line with a plain Left/Right step",
            [click_event_for_beat(1.0)],
        ),
    ]
    for kind, spec in barline_patterns.BARLINE_PATTERNS.items():
        entries.append(SoundCatalogEntry(
            f"Bar line indicator - {kind.replace('_', ' ')}",
            spec["meaning"],
            "Bar Line Indicator on, crossing this kind of bar line with a plain Left/Right step",
            barline_patterns.events_for_pattern(kind),
        ))
    entries.append(SoundCatalogEntry(
        "Boundary cue",
        "You tried to move past the start or end of the score",
        "A navigation key would step past the first or last event",
        [boundary_cue_event()],
    ))
    entries.append(SoundCatalogEntry(
        "Structural change cue",
        "A key signature, time signature or immediate tempo change",
        "The cursor lands on an event carrying one of those note-list rows (never at the very start)",
        [performance_cue_event()],
    ))
    entries.append(SoundCatalogEntry(
        "Metronome - accent",
        "Beat 1 of every bar",
        "Metronome on, or the free-running Play Metronome",
        [click_event_for_beat(1.0)],
    ))
    entries.append(SoundCatalogEntry(
        "Metronome - offbeat",
        "Every other beat of the bar",
        "Metronome on, or the free-running Play Metronome",
        [click_event_for_beat(2.0)],
    ))
    announcement = announcement_event_for_beat(1.5)
    entries.append(SoundCatalogEntry(
        "Position announcer",
        'Speaks the current beat position ("and", "e", ...)',
        "Position Announcer on, on every timeline move",
        [announcement] if announcement is not None else [],
    ))
    entries.append(SoundCatalogEntry(
        "Voice control - command recognized",
        "A spoken command was recognized and acted on",
        "Voice control on, after any recognized command",
        [voice_confirmation_cue_event()],
    ))
    entries.append(SoundCatalogEntry(
        "Voice control - listening started",
        "Voice control has started listening",
        "Voice control is turned on",
        [voice_recognition_started_event()],
    ))
    entries.append(SoundCatalogEntry(
        "Voice control - listening stopped",
        "Voice control has stopped listening",
        "Voice control is turned off",
        [voice_recognition_stopped_event()],
    ))
    entries.append(SoundCatalogEntry(
        "Lead-in click",
        "Counting in before playback starts",
        "Space, with a lead-in configured in Play Settings",
        [click_event_for_beat(1.0), click_event_for_beat(2.0)],
    ))
    entries.append(SoundCatalogEntry(
        "Live MIDI input",
        "A connected MIDI keyboard's own notes, sounded as you play them",
        "Live MIDI Input on, on every key press/release",
        [],
    ))
    return entries
