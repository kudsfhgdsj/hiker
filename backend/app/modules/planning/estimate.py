"""Estimated walking time of a planned route, after DIN 33466.

Horizontal 4 km/h, uphill 300 m of elevation per hour, downhill 500 m per hour.
Of the time for the distance and the time for the elevation the larger one
counts in full and the smaller one by half. Breaks are not included.
"""

HORIZONTAL_M_PER_H = 4000
ASCENT_M_PER_H = 300
DESCENT_M_PER_H = 500


def walking_time_s(distance_m: float, ascent_m: float | None, descent_m: float | None) -> int:
    """Seconds for the route; without elevation only the distance counts."""
    horizontal_h = distance_m / HORIZONTAL_M_PER_H
    vertical_h = (ascent_m or 0) / ASCENT_M_PER_H + (descent_m or 0) / DESCENT_M_PER_H
    hours = max(horizontal_h, vertical_h) + min(horizontal_h, vertical_h) / 2
    return round(hours * 3600)
