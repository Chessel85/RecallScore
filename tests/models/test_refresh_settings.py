"""models/refresh_settings.py - the shape the Delay Refresh dialog edits and
persistence/app_settings.py stores globally."""
from models.refresh_settings import (
    MAX_REFRESH_DELAY_MS,
    MIN_REFRESH_DELAY_MS,
    RefreshSettings,
)


def test_shipped_defaults_are_refresh_on_no_delay():
    """A user who never opens the Delay Refresh dialog must notice nothing."""
    settings = RefreshSettings()

    assert settings.refresh_during_playback is True
    assert settings.delay_ms == 0


def test_delay_ms_clamps_to_the_max():
    settings = RefreshSettings(delay_ms=5000)
    assert settings.delay_ms == MAX_REFRESH_DELAY_MS


def test_delay_ms_clamps_to_the_min():
    settings = RefreshSettings(delay_ms=-5000)
    assert settings.delay_ms == MIN_REFRESH_DELAY_MS


def test_from_dict_none_returns_defaults():
    settings = RefreshSettings.from_dict(None)
    assert settings.refresh_during_playback is True
    assert settings.delay_ms == 0


def test_from_dict_with_junk_delay_falls_back_to_default():
    settings = RefreshSettings.from_dict({"delay_ms": "not-a-number"})
    assert settings.delay_ms == 0


def test_from_dict_missing_keys_fall_back_to_defaults():
    settings = RefreshSettings.from_dict({})
    assert settings.refresh_during_playback is True
    assert settings.delay_ms == 0


def test_from_dict_reads_both_fields():
    settings = RefreshSettings.from_dict(
        {"refresh_during_playback": False, "delay_ms": -400}
    )
    assert settings.refresh_during_playback is False
    assert settings.delay_ms == -400


def test_copy_is_independent():
    settings = RefreshSettings(refresh_during_playback=False, delay_ms=250)
    copy = settings.copy()
    copy.delay_ms = 0

    assert settings.delay_ms == 250
    assert copy.refresh_during_playback is False


def test_to_dict_round_trips_through_from_dict():
    settings = RefreshSettings(refresh_during_playback=False, delay_ms=-100)
    restored = RefreshSettings.from_dict(settings.to_dict())

    assert restored.refresh_during_playback is False
    assert restored.delay_ms == -100
