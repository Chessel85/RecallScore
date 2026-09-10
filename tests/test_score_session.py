# tests/test_score_session.py
"""ScoreSession refuses a score with more parts than there are plain MIDI
channels for (ManyParts task 3). One channel goes to each part and the six
Recall Score channels sit just above MAX_PARTS, so a larger score has
nowhere to put its parts and is rejected at the single load choke point."""
import types

from controllers.score_session import ScoreSession
from models.music_data import MusicData


def _session():
    return ScoreSession(synth=object(), uk_terms=False)


def _music_data(part_count: int):
    return types.SimpleNamespace(
        parts_info=[object()] * part_count, uk_terms=None
    )


def test_too_many_parts_is_refused_and_previous_score_kept():
    session = _session()
    sentinel = object()
    session.music_data = sentinel

    failures = []
    session.load_failed.connect(failures.append)
    loaded = []
    session.score_loaded.connect(loaded.append)

    session._on_loaded(_music_data(MusicData.MAX_PARTS + 1))

    assert session.music_data is sentinel
    assert not loaded
    assert len(failures) == 1
    assert str(MusicData.MAX_PARTS + 1) in failures[0]
    assert str(MusicData.MAX_PARTS) in failures[0]
    assert "cannot be opened" in failures[0]


def test_exactly_max_parts_loads_normally():
    session = _session()

    failures = []
    session.load_failed.connect(failures.append)
    loaded = []
    session.score_loaded.connect(loaded.append)

    md = _music_data(MusicData.MAX_PARTS)
    session._on_loaded(md)

    assert session.music_data is md
    assert not failures
    assert loaded == [md]
