"""Elevation lookup behind an adapter, for tracks that carry no elevation."""

from functools import lru_cache
from typing import Annotated, Protocol

import httpx2
from fastapi import Depends

from app import __version__
from app.core.config import get_settings

# Open-Meteo accepts up to 100 coordinates per request.
BATCH_SIZE = 100
# Longer tracks are looked up at this many evenly spread points and interpolated.
MAX_LOOKUP_POINTS = 300


class ElevationSourceError(Exception):
    """The elevation service could not be reached or answered with garbage."""


class ElevationSource(Protocol):
    def elevations(self, coordinates: list[tuple[float, float]]) -> list[float | None]:
        """Elevation in metres for every (lat, lon), in the same order."""


class DisabledElevationSource:
    def elevations(self, coordinates: list[tuple[float, float]]) -> list[float | None]:
        raise ElevationSourceError("elevation lookup is disabled")


class OpenMeteoElevationSource:
    def __init__(
        self,
        url: str,
        user_agent: str,
        *,
        timeout: float = 5.0,
        transport: httpx2.BaseTransport | None = None,
    ):
        self._url = url
        self._client = httpx2.Client(
            headers={"User-Agent": user_agent}, timeout=timeout, transport=transport
        )

    def elevations(self, coordinates: list[tuple[float, float]]) -> list[float | None]:
        result: list[float | None] = []
        for start in range(0, len(coordinates), BATCH_SIZE):
            batch = coordinates[start : start + BATCH_SIZE]
            params = {
                "latitude": ",".join(f"{lat:.5f}" for lat, _ in batch),
                "longitude": ",".join(f"{lon:.5f}" for _, lon in batch),
            }
            try:
                response = self._client.get(self._url, params=params)
                response.raise_for_status()
                values = response.json()["elevation"]
            except (httpx2.HTTPError, ValueError, KeyError, TypeError) as exc:
                raise ElevationSourceError(str(exc)) from exc
            if not isinstance(values, list) or len(values) != len(batch):
                raise ElevationSourceError("unexpected answer of the elevation service")
            result.extend(
                float(value) if isinstance(value, int | float) else None for value in values
            )
        return result


@lru_cache
def get_elevation_source() -> ElevationSource:
    settings = get_settings()
    if not settings.open_meteo_elevation_url:
        return DisabledElevationSource()
    user_agent = f"hiker/{__version__} ({settings.public_base_url})"
    return OpenMeteoElevationSource(settings.open_meteo_elevation_url, user_agent)


Elevations = Annotated[ElevationSource, Depends(get_elevation_source)]


def lookup_along(
    source: ElevationSource, coordinates: list[tuple[float, float]]
) -> list[float | None]:
    """Elevations for all coordinates; long lists are sampled and interpolated by index."""
    count = len(coordinates)
    if count <= MAX_LOOKUP_POINTS:
        return source.elevations(coordinates)
    step = (count - 1) / (MAX_LOOKUP_POINTS - 1)
    indexes = sorted({round(i * step) for i in range(MAX_LOOKUP_POINTS)})
    known = dict(zip(indexes, source.elevations([coordinates[i] for i in indexes]), strict=True))
    result: list[float | None] = []
    position = 0
    for index in range(count):
        while indexes[position + 1] < index:
            position += 1
        left, right = indexes[position], indexes[position + 1]
        low, high = known[left], known[right]
        if index in known:
            result.append(known[index])
        elif low is None or high is None:
            result.append(None)
        else:
            result.append(low + (high - low) * (index - left) / (right - left))
    return result
