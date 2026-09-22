# models/performance_indicator_mode.py
"""The three-way Options > Performance Indicator setting (Ctrl+C cycles it) -
whether the performance-cue "ding" (audio/performance_cue.py) sounds when the
cursor arrives on a row Region 3's note list marks as a MarkingRow (a
key/time/tempo change, a repeat, a hairpin, ... - see RegionPresenter.
update_timeline_views for the actual fire condition).

Same plain constants + cycle() shape as models/play_settings.py's PLAY_MODES -
stdlib-only, since models/ stays Qt-free (guarded by
test_models_package_does_not_import_qt).

  off                    - never dings.
  on_except_when_playing - dings on manual navigation, not during Play.
  always_on              - dings on manual navigation AND during Play.
"""
from typing import Tuple

PERFORMANCE_INDICATOR_OFF = "off"
PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING = "on_except_when_playing"
PERFORMANCE_INDICATOR_ALWAYS_ON = "always_on"

PERFORMANCE_INDICATOR_MODES: Tuple[str, str, str] = (
    PERFORMANCE_INDICATOR_OFF,
    PERFORMANCE_INDICATOR_ON_EXCEPT_WHEN_PLAYING,
    PERFORMANCE_INDICATOR_ALWAYS_ON,
)
DEFAULT_PERFORMANCE_INDICATOR_MODE = PERFORMANCE_INDICATOR_OFF


def cycle(mode: str) -> str:
    """Ctrl+C: Off -> On except when playing -> Always on -> Off. An unknown
    mode (a hand-edited settings.json) is treated as Off, so cycling from it
    lands on the first real state rather than raising."""
    if mode not in PERFORMANCE_INDICATOR_MODES:
        mode = DEFAULT_PERFORMANCE_INDICATOR_MODE
    index = PERFORMANCE_INDICATOR_MODES.index(mode)
    return PERFORMANCE_INDICATOR_MODES[(index + 1) % len(PERFORMANCE_INDICATOR_MODES)]
