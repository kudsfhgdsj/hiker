"""Reading GPX tracks and deriving statistics and chart series from them.

The parser is tolerant: missing time, elevation or sensor values never cause an
error, the statistics that depend on them simply stay empty. Sensor values are
read from the Garmin TrackPointExtension (heart rate, cadence, temperature).

Formulas and parameters:
- Distance: sum of the great-circle distances (haversine) between the points.
- Ascent/descent: elevation changes are only counted once they exceed
  ELEVATION_THRESHOLD_M since the last counted point, which filters sensor noise.
- Moving time: sum of the intervals with a speed of at least MOVING_SPEED_MPS.
- Heart rate average: weighted by time where the points have time stamps.
- Heart rate zones: shares of the maximum heart rate (ZONE_LIMITS); the maximum
  comes from the user profile, otherwise 220 minus age, otherwise no zones.
"""

import bisect
import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from xml.etree import ElementTree

from app.core.errors import UnprocessableError

EARTH_RADIUS_M = 6_371_000
ELEVATION_THRESHOLD_M = 3.0
MOVING_SPEED_MPS = 0.3
# Upper limits of zones 1 to 4 as share of the maximum heart rate; zone 5 is above.
ZONE_LIMITS = (0.6, 0.7, 0.8, 0.9)
MAX_SERIES_POINTS = 2000
MAX_TRACK_POINTS = 200_000
GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"


@dataclass(frozen=True)
class TrackPoint:
    lat: float
    lon: float
    ele: float | None = None
    time: datetime | None = None
    hr: int | None = None
    cad: int | None = None
    temp: float | None = None


def invalid_gpx(message: str) -> UnprocessableError:
    return UnprocessableError(message, code="invalid_gpx")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    half_dphi = (phi2 - phi1) / 2
    half_dlambda = math.radians(lon2 - lon1) / 2
    a = math.sin(half_dphi) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(half_dlambda) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


# --- Parsing ---


def _number(text, minimum: float, maximum: float) -> float | None:
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or not minimum <= value <= maximum:
        return None
    return value


def _local_name(element) -> str:
    return str(element.tag).rsplit("}", 1)[-1].lower()


def _parse_time(text: str | None) -> datetime | None:
    try:
        time = datetime.fromisoformat((text or "").strip())
    except ValueError:
        return None
    return time if time.tzinfo is not None else time.replace(tzinfo=UTC)


def _to_point(element) -> TrackPoint | None:
    lat = _number(element.get("lat"), -90, 90)
    lon = _number(element.get("lon"), -180, 180)
    if lat is None or lon is None:
        return None
    values: dict = {}
    for child in element.iter():
        name = _local_name(child)
        if name == "ele":
            values["ele"] = _number(child.text, -500, 9000)
        elif name == "time":
            values["time"] = _parse_time(child.text)
        # Sensor values of the Garmin TrackPointExtension (and similar extensions).
        elif name in ("hr", "heartrate"):
            values["hr"] = _number(child.text, 20, 260)
        elif name in ("cad", "cadence", "runcadence"):
            values["cad"] = _number(child.text, 0, 300)
        elif name in ("atemp", "temp", "temperature"):
            values["temp"] = _number(child.text, -80, 70)
    for key in ("hr", "cad"):
        if values.get(key) is not None:
            values[key] = round(values[key])
    return TrackPoint(lat=lat, lon=lon, **values)


def parse_gpx(data: bytes) -> list[TrackPoint]:
    """Read the points of all tracks; without tracks, the points of the routes."""
    # Entity declarations have no place in GPX and are a known attack on XML parsers.
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise invalid_gpx("File is not a GPX file")
    try:
        root = ElementTree.fromstring(data)
    except (ElementTree.ParseError, ValueError) as exc:
        raise invalid_gpx("File is not a GPX file") from exc
    if _local_name(root) != "gpx":
        raise invalid_gpx("File is not a GPX file")
    elements = [element for element in root.iter() if _local_name(element) == "trkpt"]
    if not elements:
        elements = [element for element in root.iter() if _local_name(element) == "rtept"]
    if len(elements) > MAX_TRACK_POINTS:
        raise invalid_gpx("Track has too many points")
    points = [point for point in map(_to_point, elements) if point is not None]
    if not points:
        raise invalid_gpx("GPX file contains no track points")
    return points


def points_to_gpx(points: list[TrackPoint], name: str) -> bytes:
    """Write a GPX 1.1 file with one track, for tracks drawn in the app."""
    root = ElementTree.Element("gpx", version="1.1", creator="hiker", xmlns=GPX_NAMESPACE)
    track = ElementTree.SubElement(root, "trk")
    ElementTree.SubElement(track, "name").text = name
    segment = ElementTree.SubElement(track, "trkseg")
    for point in points:
        element = ElementTree.SubElement(
            segment, "trkpt", lat=f"{point.lat:.7f}", lon=f"{point.lon:.7f}"
        )
        if point.ele is not None:
            ElementTree.SubElement(element, "ele").text = f"{point.ele:.1f}"
        if point.time is not None:
            time = point.time.astimezone(UTC).isoformat().replace("+00:00", "Z")
            ElementTree.SubElement(element, "time").text = time
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def with_elevations(points: list[TrackPoint], elevations: list[float | None]) -> list[TrackPoint]:
    return [replace(point, ele=ele) for point, ele in zip(points, elevations, strict=True)]


# --- Statistics ---


def _distances(points: list[TrackPoint]) -> list[float]:
    """Cumulative distance in metres at every point."""
    total, result = 0.0, [0.0]
    for previous, point in zip(points, points[1:], strict=False):
        total += haversine_m(previous.lat, previous.lon, point.lat, point.lon)
        result.append(total)
    return result


def _elevation_stats(points: list[TrackPoint]) -> dict:
    elevations = [point.ele for point in points if point.ele is not None]
    if not elevations:
        return {
            "ascent_m": None,
            "descent_m": None,
            "min_elevation_m": None,
            "max_elevation_m": None,
        }
    ascent = descent = 0.0
    reference = elevations[0]
    for elevation in elevations[1:]:
        change = elevation - reference
        if change >= ELEVATION_THRESHOLD_M:
            ascent += change
            reference = elevation
        elif change <= -ELEVATION_THRESHOLD_M:
            descent -= change
            reference = elevation
    return {
        "ascent_m": round(ascent),
        "descent_m": round(descent),
        "min_elevation_m": round(min(elevations)),
        "max_elevation_m": round(max(elevations)),
    }


def _intervals(points: list[TrackPoint]) -> list[float]:
    """Seconds from each point to the next; 0 where times are missing or go backwards."""
    result = []
    for point, following in zip(points, points[1:], strict=False):
        seconds = 0.0
        if point.time is not None and following.time is not None:
            seconds = max(0.0, (following.time - point.time).total_seconds())
        result.append(seconds)
    return [*result, 0.0]


def _time_stats(points: list[TrackPoint], distances: list[float], intervals: list[float]) -> dict:
    times = [point.time for point in points if point.time is not None]
    if not times:
        return {"start_time": None, "end_time": None, "total_time_s": None, "moving_time_s": None}
    moving = 0.0
    for index, seconds in enumerate(intervals[:-1]):
        if seconds > 0 and (distances[index + 1] - distances[index]) / seconds >= MOVING_SPEED_MPS:
            moving += seconds
    start, end = min(times), max(times)
    return {
        "start_time": start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "end_time": end.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "total_time_s": round((end - start).total_seconds()),
        "moving_time_s": round(moving),
    }


def _weighted_average(values: list, intervals: list[float]) -> float:
    pairs = [(v, w) for v, w in zip(values, intervals, strict=True) if v is not None]
    weight = sum(w for _, w in pairs)
    if weight > 0:
        return sum(v * w for v, w in pairs) / weight
    return sum(v for v, _ in pairs) / len(pairs)


def _heart_rate_stats(
    points: list[TrackPoint], intervals: list[float], max_heart_rate: int | None
) -> dict | None:
    rates = [point.hr for point in points]
    present = [rate for rate in rates if rate is not None]
    if not present:
        return None
    zones = None
    if max_heart_rate and sum(intervals) > 0:
        limits = [round(share * max_heart_rate) for share in ZONE_LIMITS]
        seconds = [0.0] * (len(limits) + 1)
        for rate, interval in zip(rates, intervals, strict=True):
            if rate is not None:
                seconds[sum(rate >= limit for limit in limits)] += interval
        bounds = [None, *limits, None]
        zones = [
            {
                "zone": index + 1,
                "from_bpm": bounds[index],
                "to_bpm": bounds[index + 1],
                "seconds": round(seconds[index]),
            }
            for index in range(len(seconds))
        ]
    return {
        "avg": round(_weighted_average(rates, intervals)),
        "min": min(present),
        "max": max(present),
        "max_heart_rate_used": max_heart_rate,
        "zones": zones,
    }


def _simple_stats(values: list, intervals: list[float], digits: int) -> dict | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return {
        "avg": round(_weighted_average(values, intervals), digits)
        if digits
        else round(_weighted_average(values, intervals)),
        "min": min(present),
        "max": max(present),
    }


def compute_stats(points: list[TrackPoint], max_heart_rate: int | None = None) -> dict:
    distances = _distances(points)
    intervals = _intervals(points)
    return {
        "point_count": len(points),
        "distance_m": round(distances[-1]),
        **_elevation_stats(points),
        **_time_stats(points, distances, intervals),
        "heart_rate": _heart_rate_stats(points, intervals, max_heart_rate),
        "cadence": _simple_stats([p.cad for p in points], intervals, 0),
        "temperature": _simple_stats([p.temp for p in points], intervals, 1),
    }


# --- Series for charts and the map ---


def _column(values: list, digits: int | None = None) -> list | None:
    if all(value is None for value in values):
        return None
    if digits is None:
        return values
    return [None if value is None else round(value, digits) for value in values]


def build_series(points: list[TrackPoint], max_points: int = MAX_SERIES_POINTS) -> dict:
    """Columns of equal length, thinned out evenly to at most `max_points` points."""
    distances = _distances(points)
    count = len(points)
    if count > max_points:
        step = (count - 1) / (max_points - 1)
        indexes = sorted({round(i * step) for i in range(max_points)})
    else:
        indexes = list(range(count))
    chosen = [points[i] for i in indexes]
    return {
        "time": _column(
            [
                p.time.astimezone(UTC).isoformat().replace("+00:00", "Z") if p.time else None
                for p in chosen
            ]
        ),
        "distance_m": [round(distances[i], 1) for i in indexes],
        "lat": [round(p.lat, 6) for p in chosen],
        "lon": [round(p.lon, 6) for p in chosen],
        "elevation_m": _column([p.ele for p in chosen], 1),
        "heart_rate": _column([p.hr for p in chosen]),
        "cadence": _column([p.cad for p in chosen]),
        "temperature": _column([p.temp for p in chosen], 1),
    }


SERIES_COLUMNS = (
    "time",
    "distance_m",
    "lat",
    "lon",
    "elevation_m",
    "heart_rate",
    "cadence",
    "temperature",
)


def trim_series_ends(series: dict, radius_m: float) -> dict:
    """Cut off the parts within `radius_m` of the first and the last point."""
    lats, lons = series["lat"], series["lon"]
    if not lats:
        return series
    first, last = 0, len(lats) - 1
    while first <= last and haversine_m(lats[0], lons[0], lats[first], lons[first]) < radius_m:
        first += 1
    while last >= first and haversine_m(lats[-1], lons[-1], lats[last], lons[last]) < radius_m:
        last -= 1
    return {
        column: None if series.get(column) is None else series[column][first : last + 1]
        for column in SERIES_COLUMNS
    }


# --- Positions on the series ---


@dataclass(frozen=True)
class SeriesPosition:
    lat: float
    lon: float
    distance_m: float
    elevation_m: float | None
    # How far the requested position is away from the track.
    offset_m: float = 0.0


def _elevation_at(series: dict, index: int) -> float | None:
    return series["elevation_m"][index] if series.get("elevation_m") else None


def _between(series: dict, index: int, share: float) -> SeriesPosition:
    """The position `share` (0..1) of the way from point `index` to the next one."""
    following = min(index + 1, len(series["lat"]) - 1)

    def mix(column: str) -> float:
        return series[column][index] + (series[column][following] - series[column][index]) * share

    low, high = _elevation_at(series, index), _elevation_at(series, following)
    elevation = None if low is None or high is None else round(low + (high - low) * share, 1)
    return SeriesPosition(
        lat=round(mix("lat"), 6),
        lon=round(mix("lon"), 6),
        distance_m=round(mix("distance_m"), 1),
        elevation_m=elevation,
    )


def nearest_on_series(series: dict, lat: float, lon: float) -> SeriesPosition | None:
    """The point of the series that is closest to the given position."""
    if not series["lat"]:
        return None
    offsets = [
        haversine_m(lat, lon, point_lat, point_lon)
        for point_lat, point_lon in zip(series["lat"], series["lon"], strict=True)
    ]
    index = min(range(len(offsets)), key=offsets.__getitem__)
    return replace(_between(series, index, 0.0), offset_m=round(offsets[index], 1))


def position_at_distance(series: dict, distance_m: float) -> SeriesPosition | None:
    distances = series["distance_m"]
    if not distances:
        return None
    distance_m = min(max(distance_m, distances[0]), distances[-1])
    index = max(0, bisect.bisect_right(distances, distance_m) - 1)
    if index >= len(distances) - 1:
        return _between(series, len(distances) - 1, 0.0)
    span = distances[index + 1] - distances[index]
    return _between(series, index, (distance_m - distances[index]) / span if span else 0.0)


def position_at_time(series: dict, moment: datetime, tolerance_s: float) -> SeriesPosition | None:
    """Interpolated position at a point in time; None outside the track (plus tolerance)."""
    if not series.get("time"):
        return None
    known = [
        (datetime.fromisoformat(text.replace("Z", "+00:00")), index)
        for index, text in enumerate(series["time"])
        if text is not None
    ]
    if not known:
        return None
    known.sort()
    times = [time for time, _ in known]
    if moment < times[0]:
        early = (times[0] - moment).total_seconds() <= tolerance_s
        return _between(series, known[0][1], 0.0) if early else None
    if moment >= times[-1]:
        late = (moment - times[-1]).total_seconds() <= tolerance_s
        return _between(series, known[-1][1], 0.0) if late else None
    place = bisect.bisect_right(times, moment) - 1
    (before, index), (after, following) = known[place], known[place + 1]
    span = (after - before).total_seconds()
    share = (moment - before).total_seconds() / span if span else 0.0
    if following != index + 1:
        # Points without time in between: stay at the last point with a known time.
        return _between(series, index, 0.0)
    return _between(series, index, share)
