"""Peaks, passes and other notable places along a track.

After a track is stored, the places it passes are found automatically:
- named peaks, saddles and passes from OpenStreetMap that lie on the track,
  i.e. within `PLACE_MAX_DISTANCE_M` (default 10 m) of its line;
- the waypoints contained in the GPX file itself;
- the highest point of the track, if no peak was found there.

OpenStreetMap is asked through the Overpass API behind an adapter. Only the
bounding box of the track is sent, never the track itself. The data is under
the ODbL: wherever a place with `source = osm` is shown, the source is named.
If the service cannot be reached, the track is stored anyway and only the
places from the file and the highest point are found.
"""

import logging
import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Annotated, Protocol
from xml.etree import ElementTree

import httpx2
from fastapi import Depends
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.protocols.models import Tour, TourPeak, TourWaypoint
from app.modules.protocols.track import TrackPoint, haversine_m

logger = logging.getLogger(__name__)

PEAK, SADDLE, WAYPOINT, HIGH_POINT = "peak", "saddle", "waypoint", "high_point"
SOURCE_OSM, SOURCE_GPX, SOURCE_TRACK = "osm", "gpx", "track"
# Entries with these sources are replaced whenever the places are detected again.
AUTOMATIC_SOURCES = (SOURCE_OSM, SOURCE_GPX, SOURCE_TRACK)
OSM_ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"

# Waypoints of the GPX file get a position on the track up to this distance.
GPX_WAYPOINT_MAX_DISTANCE_M = 1000
# No separate "highest point" if a peak was found this close to it along the track.
HIGH_POINT_MERGE_M = 100
METERS_PER_DEGREE = 111_320


@dataclass(frozen=True)
class Place:
    """A named place of the map, before it is matched to a track."""

    kind: str
    name: str
    lat: float
    lon: float
    elevation_m: float | None = None
    osm_id: int | None = None


@dataclass(frozen=True)
class Station:
    """A place on the track, with the position along it."""

    kind: str
    source: str
    name: str
    lat: float
    lon: float
    elevation_m: float | None
    track_distance_m: float | None
    reached_at: datetime | None
    osm_id: int | None = None


# --- OpenStreetMap adapter ---


class PlaceSourceError(Exception):
    """The map service could not be reached or answered with garbage."""


class PlaceSource(Protocol):
    def places_in(self, south: float, west: float, north: float, east: float) -> list[Place]:
        """Named peaks, saddles and passes inside the bounding box."""


class DisabledPlaceSource:
    def places_in(self, south, west, north, east) -> list[Place]:
        return []


def _elevation(text) -> float | None:
    try:
        value = float(str(text).replace(",", ".").replace("m", "").strip())
    except (TypeError, ValueError):
        return None
    return value if -500 <= value <= 9000 else None


class OverpassPlaceSource:
    def __init__(
        self,
        url: str,
        user_agent: str,
        *,
        timeout: float = 15.0,
        transport: httpx2.BaseTransport | None = None,
    ):
        self._url = url
        self._client = httpx2.Client(
            headers={"User-Agent": user_agent}, timeout=timeout, transport=transport
        )

    def places_in(self, south: float, west: float, north: float, east: float) -> list[Place]:
        box = f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"
        query = (
            "[out:json][timeout:10];"
            f'(node["natural"="peak"]["name"]({box});'
            f'node["natural"="saddle"]["name"]({box});'
            f'node["mountain_pass"="yes"]["name"]({box}););'
            "out body;"
        )
        try:
            response = self._client.post(self._url, data={"data": query})
            response.raise_for_status()
            elements = response.json()["elements"]
            places = []
            for element in elements:
                tags = element.get("tags") or {}
                name = str(tags.get("name") or "").strip()
                if element.get("type") != "node" or not name:
                    continue
                places.append(
                    Place(
                        kind=PEAK if tags.get("natural") == "peak" else SADDLE,
                        name=name[:200],
                        lat=float(element["lat"]),
                        lon=float(element["lon"]),
                        elevation_m=_elevation(tags.get("ele")),
                        osm_id=int(element["id"]),
                    )
                )
            return places
        except (httpx2.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise PlaceSourceError(str(exc)) from exc


@lru_cache
def get_place_source() -> PlaceSource:
    settings = get_settings()
    if not settings.overpass_url:
        return DisabledPlaceSource()
    user_agent = f"hiker/{__version__} ({settings.public_base_url})"
    return OverpassPlaceSource(settings.overpass_url, user_agent)


Places = Annotated[PlaceSource, Depends(get_place_source)]


# --- Waypoints inside the GPX file ---


def parse_gpx_waypoints(data: bytes) -> list[Place]:
    """Named `<wpt>` elements of a GPX file; anything unreadable is skipped."""
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        return []
    try:
        root = ElementTree.fromstring(data)
    except (ElementTree.ParseError, ValueError):
        return []
    places = []
    for element in root.iter():
        if str(element.tag).rsplit("}", 1)[-1].lower() != "wpt":
            continue
        values = {str(c.tag).rsplit("}", 1)[-1].lower(): (c.text or "").strip() for c in element}
        try:
            lat, lon = float(element.get("lat")), float(element.get("lon"))
        except (TypeError, ValueError):
            continue
        if not values.get("name") or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        places.append(
            Place(WAYPOINT, values["name"][:200], lat, lon, _elevation(values.get("ele")))
        )
    return places


# --- Matching places to the track ---


@dataclass(frozen=True)
class _Approach:
    offset_m: float
    distance_m: float
    elevation_m: float | None
    time: datetime | None


def _closest_approaches(
    points: list[TrackPoint], places: list[Place], max_distance_m: float
) -> dict[int, _Approach]:
    """For every place within `max_distance_m` of the track line: where it is closest.

    Distances are measured to the segments between the points, not only to the
    points themselves, in a local flat projection that is exact enough for metres.
    """
    if not places or not points:
        return {}
    lat0 = points[0].lat
    scale_x = METERS_PER_DEGREE * math.cos(math.radians(lat0))
    scale_y = METERS_PER_DEGREE

    def project(lat: float, lon: float) -> tuple[float, float]:
        return lon * scale_x, lat * scale_y

    # Places sorted into a grid, so that each stretch of track only looks at its neighbours.
    cell = max(max_distance_m, 25.0)
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    projected = [project(place.lat, place.lon) for place in places]
    for index, (x, y) in enumerate(projected):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                grid[int(x // cell) + dx, int(y // cell) + dy].append(index)

    best: dict[int, _Approach] = {}
    along = 0.0
    following = points[1:] or points
    for a, b in zip(points, following, strict=False):
        ax, ay = project(a.lat, a.lon)
        bx, by = project(b.lat, b.lon)
        length = math.hypot(bx - ax, by - ay)
        steps = max(1, math.ceil(length / cell))
        candidates: set[int] = set()
        for step in range(steps + 1):
            share = step / steps
            key = int((ax + (bx - ax) * share) // cell), int((ay + (by - ay) * share) // cell)
            candidates.update(grid.get(key, ()))
        for index in candidates:
            px, py = projected[index]
            share = 0.0
            if length > 0:
                share = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / (length * length)
                share = min(1.0, max(0.0, share))
            offset = math.hypot(px - (ax + (bx - ax) * share), py - (ay + (by - ay) * share))
            if offset <= max_distance_m and (index not in best or offset < best[index].offset_m):
                elevation = None
                if a.ele is not None and b.ele is not None:
                    elevation = a.ele + (b.ele - a.ele) * share
                time = None
                if a.time is not None and b.time is not None:
                    time = a.time + timedelta(seconds=(b.time - a.time).total_seconds() * share)
                best[index] = _Approach(offset, along + length * share, elevation, time)
        along += haversine_m(a.lat, a.lon, b.lat, b.lon)
    return best


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def detect_stations(
    points: list[TrackPoint],
    map_places: list[Place],
    gpx_waypoints: list[Place],
    max_distance_m: float,
) -> list[Station]:
    """The places a track passes, in the order along the track."""
    stations: list[Station] = []
    for index, approach in _closest_approaches(points, map_places, max_distance_m).items():
        place = map_places[index]
        stations.append(
            Station(
                kind=place.kind,
                source=SOURCE_OSM,
                name=place.name,
                lat=place.lat,
                lon=place.lon,
                # The surveyed elevation of the map beats the one measured on the track.
                elevation_m=_round(place.elevation_m or approach.elevation_m),
                track_distance_m=_round(approach.distance_m),
                reached_at=approach.time,
                osm_id=place.osm_id,
            )
        )
    near = _closest_approaches(points, gpx_waypoints, GPX_WAYPOINT_MAX_DISTANCE_M)
    for index, place in enumerate(gpx_waypoints):
        approach = near.get(index)
        stations.append(
            Station(
                kind=WAYPOINT,
                source=SOURCE_GPX,
                name=place.name,
                lat=place.lat,
                lon=place.lon,
                elevation_m=_round(place.elevation_m or (approach and approach.elevation_m)),
                track_distance_m=_round(approach.distance_m) if approach else None,
                reached_at=approach.time if approach else None,
            )
        )

    with_elevation = [(i, p) for i, p in enumerate(points) if p.ele is not None]
    if with_elevation:
        top_index, top = max(with_elevation, key=lambda item: item[1].ele)
        distance = sum(
            haversine_m(a.lat, a.lon, b.lat, b.lon)
            for a, b in zip(points[:top_index], points[1 : top_index + 1], strict=False)
        )
        peak_there = any(
            station.kind == PEAK
            and station.track_distance_m is not None
            and abs(station.track_distance_m - distance) <= HIGH_POINT_MERGE_M
            for station in stations
        )
        if not peak_there:
            stations.append(
                Station(
                    kind=HIGH_POINT,
                    source=SOURCE_TRACK,
                    name="",
                    lat=top.lat,
                    lon=top.lon,
                    elevation_m=_round(top.ele),
                    track_distance_m=_round(distance),
                    reached_at=top.time,
                )
            )
    stations.sort(key=lambda s: (s.track_distance_m is None, s.track_distance_m or 0, s.name))
    return stations


# --- Writing the result into the tour ---


def apply_to_tour(
    db: Session,
    tour: Tour,
    author: User,
    points: list[TrackPoint],
    gpx_data: bytes,
    source: PlaceSource,
) -> None:
    """Replace the automatically found places of the tour. Does not commit.

    Entries the user added by hand stay; peaks also go to the peak list.
    """
    settings = get_settings()
    margin = settings.place_max_distance_m / METERS_PER_DEGREE * 2
    lats, lons = [p.lat for p in points], [p.lon for p in points]
    map_places: list[Place] = []
    try:
        map_places = source.places_in(
            min(lats) - margin, min(lons) - margin, max(lats) + margin, max(lons) + margin
        )
    except PlaceSourceError as exc:
        # Tolerant: the track is usable without the names from the map.
        logger.warning("Place lookup failed: %s", exc)
    stations = detect_stations(
        points, map_places, parse_gpx_waypoints(gpx_data), settings.place_max_distance_m
    )

    removed = {w.id for w in tour.waypoints if w.source in AUTOMATIC_SOURCES}
    for photo in tour.photos:
        if photo.waypoint_id in removed:
            photo.waypoint_id = None
    tour.waypoints = [w for w in tour.waypoints if w.id not in removed]
    tour.peaks = [peak for peak in tour.peaks if peak.source not in AUTOMATIC_SOURCES]
    db.flush()

    known_peaks = {peak.name.casefold() for peak in tour.peaks}
    next_order = max((peak.sort_order for peak in tour.peaks), default=-1) + 1
    for station in stations:
        tour.waypoints.append(
            TourWaypoint(
                id=uuid.uuid4(),
                name=station.name,
                icon=station.kind,
                kind=station.kind,
                source=station.source,
                osm_id=station.osm_id,
                lat=station.lat,
                lon=station.lon,
                elevation_m=station.elevation_m,
                track_distance_m=station.track_distance_m,
                reached_at=station.reached_at,
            )
        )
        if station.kind == PEAK and station.name.casefold() not in known_peaks:
            known_peaks.add(station.name.casefold())
            tour.peaks.append(
                TourPeak(
                    id=uuid.uuid4(),
                    name=station.name,
                    elevation_m=round(station.elevation_m) if station.elevation_m else None,
                    lat=station.lat,
                    lon=station.lon,
                    reached_at=station.reached_at,
                    source=station.source,
                    sort_order=next_order,
                )
            )
            next_order += 1
