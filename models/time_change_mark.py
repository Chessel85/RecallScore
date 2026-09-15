# models/time_change_mark.py
from dataclasses import dataclass


@dataclass
class TimeChangeMark:
    """See KeyChangeMark's docstring - the same per-part tracking and
    stage 10 rule 2 resolution (is_score_level), for a part's own
    <attributes>/<time> changing partway through the piece."""

    part_id: str
    ts_num: int
    ts_den: int
    measure: int
    beat_position: float
    quarters_from_start: float
    is_score_level: bool = False
