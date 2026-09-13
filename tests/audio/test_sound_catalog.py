# tests/audio/test_sound_catalog.py
"""PerformanceMarkingsImplementationPlan.md stage 4: the Sound Icon
Dictionary's declarations (strategy section 10.1) - generated from the same
audio module functions/data the app actually plays from."""
from audio.barline_patterns import BARLINE_PATTERNS
from audio.sound_catalog import build_catalog


def test_catalog_has_one_entry_per_barline_pattern_plus_the_plain_beep():
    entries = build_catalog()
    barline_entries = [e for e in entries if e.name.startswith("Bar line indicator")]
    assert len(barline_entries) == len(BARLINE_PATTERNS) + 1  # + the plain beep


def test_every_entry_has_a_name_meaning_and_when():
    for entry in build_catalog():
        assert entry.name and entry.meaning and entry.when


def test_live_midi_input_has_no_playable_events():
    entry = next(e for e in build_catalog() if e.name == "Live MIDI input")
    assert entry.events == []


def test_every_other_entry_has_at_least_one_playable_event():
    for entry in build_catalog():
        if entry.name == "Live MIDI input":
            continue
        assert entry.events, entry.name
