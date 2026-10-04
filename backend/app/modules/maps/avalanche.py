"""Avalanche danger as a map layer.

The danger levels of the European avalanche warning services (EAWS) come as one
file per day from avalanche.report, which gathers them from the services; the
outlines of the warning regions come from regions.avalanches.org (CC0). Both are
fetched through this server and kept for a while. The layer shows the highest
danger level of the day per region. It is an overview: what counts is the
bulletin of the warning service itself.
"""

import json
import logging
import threading
import time
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Protocol

import httpx2
from fastapi import Depends

from app import __version__
from app.core.config import get_settings

logger = logging.getLogger(__name__)

RATINGS_URL = "https://static.avalanche.report/eaws_bulletins/{date}/{date}.ratings.json"
REGIONS_URL = "https://regions.avalanches.org/micro-regions/{area}_micro-regions.geojson.json"
ATTRIBUTION = (
    "Lawinengefahr: Lawinenwarndienste der EAWS, zusammengeführt von avalanche.report "
    "(CC BY 4.0); Regionen: EAWS (CC0)"
)
# The warning regions of the Alps and their surroundings.
AREAS = (
    "CH",
    "LI",
    "AT-02",
    "AT-03",
    "AT-04",
    "AT-05",
    "AT-06",
    "AT-07",
    "AT-08",
    "DE-BY",
    "IT-21",
    "IT-23",
    "IT-25",
    "IT-32-BZ",
    "IT-32-TN",
    "IT-34",
    "IT-36",
    "IT-57",
    "SI",
)
_RATINGS_FOR_S = 30 * 60
_REGIONS_FOR_S = 30 * 86400
# Outlines are thinned out to about 150 m: enough for an overview, a tenth of the size.
_TOLERANCE_DEG = 0.0015


class AvalancheSourceError(Exception):
    """A source could not be reached or answered with garbage."""


class AvalancheSource(Protocol):
    def ratings(self, day: date) -> dict[str, int]:
        """Highest danger level (1 to 5) per region id and its variants (`:high`, `:am` …)."""

    def regions(self, area: str) -> dict:
        """GeoJSON FeatureCollection of the micro-regions of an area; empty if unknown."""


class HttpAvalancheSource:
    def __init__(self, user_agent: str, *, transport: httpx2.BaseTransport | None = None):
        self._client = httpx2.Client(
            headers={"User-Agent": user_agent},
            timeout=15.0,
            transport=transport,
            follow_redirects=True,
        )

    def _json(self, url: str) -> dict | None:
        try:
            response = self._client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            raise AvalancheSourceError(str(exc)) from exc

    def ratings(self, day: date) -> dict[str, int]:
        data = self._json(RATINGS_URL.replace("{date}", day.isoformat())) or {}
        ratings = data.get("maxDangerRatings", {})
        return {
            key: value
            for key, value in ratings.items()
            if isinstance(value, int) and 1 <= value <= 5
        }

    def regions(self, area: str) -> dict:
        return self._json(REGIONS_URL.replace("{area}", area)) or {"features": []}


def _thin(ring: list, tolerance: float) -> list:
    """Douglas-Peucker on a closed ring of [lon, lat] points."""
    if len(ring) < 5:
        return ring
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        first, last = stack.pop()
        (x1, y1), (x2, y2) = ring[first][:2], ring[last][:2]
        dx, dy = x2 - x1, y2 - y1
        length = dx * dx + dy * dy
        worst, index = 0.0, -1
        for i in range(first + 1, last):
            px, py = ring[i][:2]
            if length == 0:
                distance = (px - x1) ** 2 + (py - y1) ** 2
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length))
                distance = (px - x1 - t * dx) ** 2 + (py - y1 - t * dy) ** 2
            if distance > worst:
                worst, index = distance, i
        if index >= 0 and worst > tolerance * tolerance:
            keep[index] = True
            stack += [(first, index), (index, last)]
    thinned = [[round(p[0], 5), round(p[1], 5)] for p, kept in zip(ring, keep, strict=True) if kept]
    # A ring needs four points; a region that small keeps its shape.
    return thinned if len(thinned) >= 4 else [[round(p[0], 5), round(p[1], 5)] for p in ring]


def _thin_geometry(geometry: dict) -> dict:
    polygons = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [polygons]
    thinned = [[_thin(ring, _TOLERANCE_DEG) for ring in polygon] for polygon in polygons]
    return {"type": "MultiPolygon", "coordinates": thinned}


class Avalanche:
    """The layer: regions with their danger level of today, kept for half an hour."""

    def __init__(self, source: AvalancheSource, cache_path: str):
        self._source = source
        self._folder = Path(cache_path) / "_avalanche"
        self._lock = threading.Lock()
        self._built: tuple[float, date, dict] | None = None

    def _regions(self, area: str) -> list[dict]:
        """Thinned-out outlines of an area, from the file kept here if it is fresh."""
        path = self._folder / f"{area}.json"
        try:
            if time.time() - path.stat().st_mtime < _REGIONS_FOR_S:
                return json.loads(path.read_text())
        except (OSError, ValueError):
            pass
        try:
            features = [
                {"id": feature["properties"]["id"], "geometry": _thin_geometry(feature["geometry"])}
                for feature in self._source.regions(area).get("features", [])
                # Regions that were replaced by newer ones carry an end date.
                if feature.get("geometry") and not feature["properties"].get("end_date")
            ]
        except AvalancheSourceError as exc:
            logger.warning("Avalanche regions of %s unavailable: %s", area, exc)
            try:
                return json.loads(path.read_text())
            except (OSError, ValueError):
                return []
        try:
            self._folder.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(features))
        except OSError as exc:
            logger.warning("Could not store avalanche regions: %s", exc)
        return features

    def geojson(self, today: date | None = None) -> dict:
        """All regions that have a danger level today, as GeoJSON."""
        day = today or datetime.now(UTC).date()
        with self._lock:
            built = self._built
            if built and built[1] == day and time.monotonic() - built[0] < _RATINGS_FOR_S:
                return built[2]
            try:
                ratings = self._source.ratings(day)
            except AvalancheSourceError as exc:
                logger.warning("Avalanche ratings unavailable: %s", exc)
                if built and built[1] == day:
                    return built[2]
                ratings = {}
            features = []
            for area in AREAS if ratings else ():
                for region in self._regions(area):
                    level = ratings.get(region["id"])
                    if level is None:
                        continue
                    features.append(
                        {
                            "type": "Feature",
                            "geometry": region["geometry"],
                            "properties": {
                                "id": region["id"],
                                "danger": level,
                                # Above and below the elevation the bulletin names, if it does.
                                "danger_high": ratings.get(f"{region['id']}:high", level),
                                "danger_low": ratings.get(f"{region['id']}:low", level),
                                "date": day.isoformat(),
                            },
                        }
                    )
            result = {
                "type": "FeatureCollection",
                "date": day.isoformat(),
                "attribution": ATTRIBUTION,
                "features": features,
            }
            self._built = (time.monotonic(), day, result)
            return result


@lru_cache
def _avalanche(cache_path: str, public_base_url: str) -> Avalanche:
    user_agent = f"hiker/{__version__} (self-hosted; {public_base_url})"
    return Avalanche(HttpAvalancheSource(user_agent), cache_path)


def get_avalanche() -> Avalanche | None:
    settings = get_settings()
    if not settings.avalanche_enabled:
        return None
    return _avalanche(settings.tile_cache_path, settings.public_base_url)


AvalancheLayer = Annotated[Avalanche | None, Depends(get_avalanche)]
