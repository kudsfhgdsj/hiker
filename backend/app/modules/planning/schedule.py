"""When the walker is where, and where the sun is then.

The time at every point of the line follows from the pace: each piece of the
line gets its share of the walking time, by the same rule as the whole (the
larger of distance time and elevation time counts in full, the smaller by
half).
"""

from datetime import datetime, timedelta

from app.modules.planning.estimate import Pace
from app.modules.planning.sun import sun_position, sun_times


def times_along(series: dict, duration_s: int, pace: Pace) -> list[int]:
    """Seconds from the start at every point of the line; the last one is the duration."""
    distances = series["distance_m"]
    elevations = series.get("elevation_m") or [None] * len(distances)
    shares = [0.0]
    for index in range(1, len(distances)):
        horizontal = (distances[index] - distances[index - 1]) / (pace.distance_km_per_h * 1000)
        before, after = elevations[index - 1], elevations[index]
        vertical = 0.0
        if before is not None and after is not None:
            change = after - before
            vertical = (
                change / pace.ascent_m_per_h if change > 0 else -change / pace.descent_m_per_h
            )
        shares.append(shares[-1] + max(horizontal, vertical) + min(horizontal, vertical) / 2)
    total = shares[-1] or 1.0
    return [round(share / total * duration_s) for share in shares]


def sun_report(series: dict | None, start_time: datetime | None, duration_s: int) -> dict | None:
    """Sunrise and sunset at the start of the tour and how the tour lies in the day."""
    if start_time is None or not series or not series.get("lat"):
        return None
    lat, lon = series["lat"][0], series["lon"][0]
    end_time = start_time + timedelta(seconds=duration_s)
    sun = sun_times(lat, lon, start_time.date())
    report = {
        "dawn": sun.dawn,
        "sunrise": sun.sunrise,
        "noon": sun.noon,
        "sunset": sun.sunset,
        "dusk": sun.dusk,
        "end_time": end_time,
        # Walking in the dark: before first light or after last light.
        "starts_in_dark": sun.dawn is not None and start_time < sun.dawn,
        "ends_in_dark": sun.dusk is not None and end_time > sun.dusk,
        # Time between the end of the tour and sunset; negative if the sun sets first.
        "daylight_left_s": (
            None if sun.sunset is None else round((sun.sunset - end_time).total_seconds())
        ),
        "summit": None,
    }
    elevations = series.get("elevation_m")
    times = series.get("time_s")
    if elevations and times and any(value is not None for value in elevations):
        top = max(
            (index for index, value in enumerate(elevations) if value is not None),
            key=lambda index: elevations[index],
        )
        moment = start_time + timedelta(seconds=times[top])
        height, direction = sun_position(series["lat"][top], series["lon"][top], moment)
        report["summit"] = {
            "time": moment,
            "elevation_m": elevations[top],
            "distance_m": series["distance_m"][top],
            "sun_height_deg": round(height, 1),
            "sun_direction_deg": round(direction),
        }
    return report
