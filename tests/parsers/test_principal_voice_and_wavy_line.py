# tests/parsers/test_principal_voice_and_wavy_line.py
"""PerformanceMarkingsImplementationPlanV2.md stage 10: <principal-voice>
is now a real DirectionSpan (previously the other_direction catch-all
point - inventory.csv: "Catch-all point today; length is low priority"),
and <barline>/<wavy-line> is now read at all (previously dropped
silently), as a score-wide WavyLineSpan rendered the same bare-name
start/end way as RepeatSpan/EndingSpan.

tests/fixtures/principal_voice_and_wavy_line.musicxml: one part, a
Hauptstimme bracket spanning bar 1, and a wavy-line crossing the bar
1/bar 2 barline."""
from models import marking_labels
from models.music_data import MusicData
from models.region3_row import MarkingRow

FIXTURE = "tests/fixtures/principal_voice_and_wavy_line.musicxml"


def _marking_row_texts(rows):
    return [r.text for r in rows if isinstance(r, MarkingRow)]


def test_principal_voice_is_a_direction_span_not_the_catch_all():
    md = MusicData(file_path=FIXTURE)
    assert not any(m.kind == "other_direction" for m in md.direction_marks)
    spans = [s for s in md.direction_spans if s.kind == "principal_voice"]
    assert len(spans) == 1
    assert spans[0].label == "Hauptstimme"
    assert spans[0].start_measure == 1
    assert spans[0].end_measure == 1


def test_principal_voice_name_reads_the_symbol():
    md = MusicData(file_path=FIXTURE)
    span = next(s for s in md.direction_spans if s.kind == "principal_voice")
    assert marking_labels.principal_voice_name(span) == "Hauptstimme"


def test_principal_voice_gives_a_note_list_row_at_its_start_and_stop():
    md = MusicData(file_path=FIXTURE)
    texts = []
    for idx, slice_ in enumerate(md.timeline_slices):
        md.active_event_index = idx
        texts.extend(_marking_row_texts(md.get_region_3_rows()))
    assert "Hauptstimme, start" in texts
    assert "Hauptstimme, end" in texts


def test_wavy_line_span_crosses_the_barline():
    md = MusicData(file_path=FIXTURE)
    assert len(md.wavy_line_spans) == 1
    span = md.wavy_line_spans[0]
    assert span.start_measure == 1
    assert span.end_measure == 2


def test_wavy_line_gives_a_score_level_note_list_row():
    md = MusicData(file_path=FIXTURE)
    texts = []
    for idx, slice_ in enumerate(md.timeline_slices):
        md.active_event_index = idx
        texts.extend(_marking_row_texts(md.get_region_3_rows()))
    assert "Wavy line, start" in texts
    assert "Wavy line, end" in texts
