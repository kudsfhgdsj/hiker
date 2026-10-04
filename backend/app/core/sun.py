"""Where the sun is: sunrise, sunset and twilight for a place and a day.

The formulas follow the NOAA solar calculator (Jean Meeus, Astronomical
Algorithms); they are good to about a minute in the Alps. The horizon is the
mathematical one: mountains around a place make the sun rise later and set
earlier there.
"""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

# Sun's centre this far below the horizon: sunrise/sunset (with refraction), civil twilight.
_SUNRISE_DEG = -0.833
_CIVIL_DEG = -6.0


@dataclass(frozen=True)
class SunTimes:
    """All times in UTC; None where the sun does not cross that height on the day."""

    dawn: datetime | None
    sunrise: datetime | None
    noon: datetime
    sunset: datetime | None
    dusk: datetime | None


def _declination_and_equation(day: date) -> tuple[float, float]:
    """Declination of the sun (radians) and equation of time (minutes) at noon UTC."""
    julian = day.toordinal() + 1721424.5 + 0.5
    century = (julian - 2451545.0) / 36525.0
    mean_longitude = math.radians((280.46646 + century * (36000.76983 + century * 0.0003032)) % 360)
    mean_anomaly = math.radians(357.52911 + century * (35999.05029 - 0.0001537 * century))
    eccentricity = 0.016708634 - century * (0.000042037 + 0.0000001267 * century)
    centre = math.radians(
        math.sin(mean_anomaly) * (1.914602 - century * (0.004817 + 0.000014 * century))
        + math.sin(2 * mean_anomaly) * (0.019993 - 0.000101 * century)
        + math.sin(3 * mean_anomaly) * 0.000289
    )
    true_longitude = mean_longitude + centre
    omega = math.radians(125.04 - 1934.136 * century)
    apparent = true_longitude - math.radians(0.00569 + 0.00478 * math.sin(omega))
    obliquity = math.radians(
        23
        + (26 + (21.448 - century * (46.815 + century * (0.00059 - century * 0.001813))) / 60) / 60
        + 0.00256 * math.cos(omega)
    )
    declination = math.asin(math.sin(obliquity) * math.sin(apparent))
    y = math.tan(obliquity / 2) ** 2
    equation = 4 * math.degrees(
        y * math.sin(2 * mean_longitude)
        - 2 * eccentricity * math.sin(mean_anomaly)
        + 4 * eccentricity * y * math.sin(mean_anomaly) * math.cos(2 * mean_longitude)
        - 0.5 * y * y * math.sin(4 * mean_longitude)
        - 1.25 * eccentricity * eccentricity * math.sin(2 * mean_anomaly)
    )
    return declination, equation


def sun_times(lat: float, lon: float, day: date, elevation_m: float = 0) -> SunTimes:
    """The day at a place. With an elevation the horizon lies lower, as seen from a summit
    that stands above its surroundings: the sun rises earlier and sets later there."""
    declination, equation = _declination_and_equation(day)
    midnight = datetime(day.year, day.month, day.day, tzinfo=UTC)
    noon_minutes = 720 - 4 * lon - equation
    noon = midnight + timedelta(minutes=noon_minutes)

    def crossing(height_deg: float) -> float | None:
        """Half of the time the sun spends above the height, in minutes."""
        cosine = (
            math.sin(math.radians(height_deg)) - math.sin(math.radians(lat)) * math.sin(declination)
        ) / (math.cos(math.radians(lat)) * math.cos(declination))
        if not -1 <= cosine <= 1:
            return None
        return 4 * math.degrees(math.acos(cosine))

    def around(half: float | None) -> tuple[datetime | None, datetime | None]:
        if half is None:
            return None, None
        return noon - timedelta(minutes=half), noon + timedelta(minutes=half)

    # Dip of the horizon: about 1.76 arc minutes times the root of the height in metres.
    dip = 1.76 / 60 * math.sqrt(max(0.0, elevation_m))
    sunrise, sunset = around(crossing(_SUNRISE_DEG - dip))
    dawn, dusk = around(crossing(_CIVIL_DEG))
    return SunTimes(dawn=dawn, sunrise=sunrise, noon=noon, sunset=sunset, dusk=dusk)


def sun_position(lat: float, lon: float, moment: datetime) -> tuple[float, float]:
    """Height above the horizon and compass direction of the sun, in degrees."""
    utc = moment.astimezone(UTC)
    declination, equation = _declination_and_equation(utc.date())
    minutes = utc.hour * 60 + utc.minute + utc.second / 60
    hour_angle = math.radians((minutes + equation + 4 * lon) / 4 - 180)
    latitude = math.radians(lat)
    sine = math.sin(latitude) * math.sin(declination) + math.cos(latitude) * math.cos(
        declination
    ) * math.cos(hour_angle)
    height = math.asin(max(-1.0, min(1.0, sine)))
    azimuth = math.atan2(
        math.sin(hour_angle),
        math.cos(hour_angle) * math.sin(latitude) - math.tan(declination) * math.cos(latitude),
    )
    return math.degrees(height), (math.degrees(azimuth) + 180) % 360
