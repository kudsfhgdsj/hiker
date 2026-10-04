"""Estimated walking time of a planned route.

A pace says how much a walker covers per hour: metres of ascent, metres of
descent and kilometres of distance. Of the time for the distance and the time
for the elevation the larger one counts in full and the smaller one by half
(the rule of DIN 33466). Breaks are not included.

Presets:
- `dav`: 300 m up, 500 m down, 4 km per hour (DIN 33466, German Alpine Club)
- `sac`: 400 m up, 800 m down, 4 km per hour (Swiss Alpine Club)
- `pro`: 600 m up, 1000 m down, 6 km per hour (well trained)
- `custom`: values of the user
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pace:
    ascent_m_per_h: float
    descent_m_per_h: float
    distance_km_per_h: float


PRESETS = {
    "dav": Pace(300, 500, 4),
    "sac": Pace(400, 800, 4),
    "pro": Pace(600, 1000, 6),
}
DEFAULT_PRESET = "dav"
CUSTOM = "custom"


def walking_time_s(
    distance_m: float,
    ascent_m: float | None,
    descent_m: float | None,
    pace: Pace = PRESETS[DEFAULT_PRESET],
) -> int:
    """Seconds for the route; without elevation only the distance counts."""
    horizontal_h = distance_m / (pace.distance_km_per_h * 1000)
    vertical_h = (ascent_m or 0) / pace.ascent_m_per_h + (descent_m or 0) / pace.descent_m_per_h
    hours = max(horizontal_h, vertical_h) + min(horizontal_h, vertical_h) / 2
    return round(hours * 3600)
