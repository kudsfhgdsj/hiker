"""Rain radar and cloud images with their time, as map layers.

- Rain: radar composites of the last two hours from RainViewer (every ten
  minutes; coarse, up to zoom 7).
- Clouds: the infrared image of the Meteosat satellites from EUMETSAT's open
  map service (EUMETView), every 15 minutes for the last two hours.

Both are fetched through this server; clients get the list of times and one
tile address per layer with `{time}` in it.
"""

import math
import threading
import time
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Protocol

import httpx2
from fastapi import Depends

from app import __version__
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError

FRAMES_URL = "https://api.rainviewer.com/public/weather-maps.json"
CLOUDS_URL = "https://view.eumetsat.int/geoserver/ows"
CLOUDS_LAYER = "mtg_fd:ir105_hrfi"
RADAR_ATTRIBUTION = "Regenradar: RainViewer · Wolken: EUMETSAT (Meteosat, Infrarot)"
RAIN_MAX_ZOOM = 7
CLOUDS_MAX_ZOOM = 8
_FRAMES_FOR_S = 300
_CLOUD_STEP_S = 900
# The newest satellite image appears with some delay.
_CLOUD_DELAY_S = 1800
_HALF_WORLD_M = 20037508.342789244


class RadarUnavailableError(AppError):
    status_code = 502
    code = "source_unavailable"


class RadarSource(Protocol):
    def rain_frames(self) -> dict[int, str]:
        """Unix time → path of the radar image of that time at the source."""

    def rain_tile(self, path: str, z: int, x: int, y: int) -> bytes: ...

    def cloud_tile(self, moment: datetime, z: int, x: int, y: int) -> bytes: ...


def tile_bounds_m(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """West, south, east, north of a tile in Web Mercator metres."""
    size = 2 * _HALF_WORLD_M / 2**z
    west = -_HALF_WORLD_M + x * size
    north = _HALF_WORLD_M - y * size
    return west, north - size, west + size, north


class HttpRadarSource:
    def __init__(self, user_agent: str, *, transport: httpx2.BaseTransport | None = None):
        self._client = httpx2.Client(
            headers={"User-Agent": user_agent},
            timeout=15.0,
            transport=transport,
            follow_redirects=True,
        )
        self._host = "https://tilecache.rainviewer.com"

    def _image(self, url: str, params: dict | None = None) -> bytes:
        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
        except httpx2.HTTPError as exc:
            raise RadarUnavailableError("The weather image source cannot be reached") from exc
        if not response.headers.get("content-type", "").startswith("image/"):
            raise RadarUnavailableError("Unexpected answer of the weather image source")
        return response.content

    def rain_frames(self) -> dict[int, str]:
        try:
            response = self._client.get(FRAMES_URL)
            response.raise_for_status()
            data = response.json()
            self._host = data["host"]
            return {int(frame["time"]): frame["path"] for frame in data["radar"]["past"]}
        except (httpx2.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RadarUnavailableError("The rain radar cannot be reached") from exc

    def rain_tile(self, path: str, z: int, x: int, y: int) -> bytes:
        # Colour scheme 2, smoothed, snow shown in its own colours.
        return self._image(f"{self._host}{path}/256/{z}/{x}/{y}/2/1_1.png")

    def cloud_tile(self, moment: datetime, z: int, x: int, y: int) -> bytes:
        west, south, east, north = tile_bounds_m(z, x, y)
        return self._image(
            CLOUDS_URL,
            {
                "service": "WMS",
                "version": "1.1.1",
                "request": "GetMap",
                "layers": CLOUDS_LAYER,
                "styles": "",
                "srs": "EPSG:3857",
                "bbox": f"{west},{south},{east},{north}",
                "width": "256",
                "height": "256",
                "format": "image/png",
                "transparent": "true",
                "time": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )


class Radar:
    """The layer: which times exist, and the tiles of a time."""

    def __init__(self, source: RadarSource):
        self._source = source
        self._lock = threading.Lock()
        self._frames: tuple[float, dict[int, str]] | None = None

    def _rain(self) -> dict[int, str]:
        with self._lock:
            known = self._frames
            if known is None or time.monotonic() - known[0] > _FRAMES_FOR_S:
                try:
                    known = self._frames = (time.monotonic(), self._source.rain_frames())
                except RadarUnavailableError:
                    if known is None:
                        raise
            return known[1]

    def frames(self, now: datetime | None = None) -> dict:
        """The times (Unix seconds, ascending) for which rain and cloud images exist."""
        moment = now or datetime.now(UTC)
        try:
            rain = sorted(self._rain())
        except RadarUnavailableError:
            rain = []
        newest = math.floor((moment.timestamp() - _CLOUD_DELAY_S) / _CLOUD_STEP_S) * _CLOUD_STEP_S
        clouds = [newest - step * _CLOUD_STEP_S for step in range(8, -1, -1)]
        return {"rain": rain, "clouds": clouds, "attribution": RADAR_ATTRIBUTION}

    def rain_tile(self, frame: int, z: int, x: int, y: int) -> bytes:
        path = self._rain().get(frame)
        if path is None:
            raise NotFoundError("No radar image of this time")
        return self._source.rain_tile(path, z, x, y)

    def cloud_tile(self, frame: int, z: int, x: int, y: int) -> bytes:
        now = time.time()
        # Only times of the grid and of the last day: nobody can make the server ask at will.
        if frame % _CLOUD_STEP_S or not now - 86400 <= frame <= now:
            raise NotFoundError("No cloud image of this time")
        return self._source.cloud_tile(datetime.fromtimestamp(frame, UTC), z, x, y)


@lru_cache
def _radar(public_base_url: str) -> Radar:
    return Radar(HttpRadarSource(f"hiker/{__version__} (self-hosted; {public_base_url})"))


def get_radar() -> Radar | None:
    settings = get_settings()
    if not settings.weather_layers_enabled:
        return None
    return _radar(settings.public_base_url)


RadarLayer = Annotated[Radar | None, Depends(get_radar)]
