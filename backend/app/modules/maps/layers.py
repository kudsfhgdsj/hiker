"""Map layers from open sources, behind one interface.

Every layer that does not come from the own vector map is described here: where
its tiles come from, under which licence, and how it must be named. The tiles
are fetched through the own server and kept as files, like the raster tiles of
OpenStreetMap; clients never talk to a source themselves. Commercial map
providers are deliberately not part of this list.

- `terrain`: elevation tiles (Terrarium encoding) for hillshading, the 3D view
  and the slope layer.
- `satellite`: aerial images; national sources where they are open, a global
  one elsewhere.
- `slope`: computed here from the elevation tiles, not fetched.
"""

import io
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from PIL import Image

from app import __version__
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.modules.maps.contours import contour_tile
from app.modules.maps.tiles import (
    FetchedTile,
    HttpTileSource,
    TileCache,
    TileSource,
    TileSourceError,
)


@dataclass(frozen=True)
class Provider:
    """One source of raster tiles."""

    id: str
    url: str
    attribution: str
    licence: str
    max_zoom: int
    # west, south, east, north; None: the whole world
    bounds: tuple[float, float, float, float] | None = None
    # y before x in the address (WMTS order)
    media_type: str = "image/jpeg"


TERRAIN = Provider(
    id="terrain",
    url="https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
    attribution="Höhendaten: Mapzen Terrain Tiles (AWS Open Data; SRTM, EU-DEM u. a.)",
    licence="Open data; attribution of the underlying sources required "
    "(https://github.com/tilezen/joerd/blob/master/docs/attribution.md)",
    max_zoom=13,
    media_type="image/png",
)

# Aerial images: the first provider whose area contains the tile and that has an image.
SATELLITE = (
    Provider(
        id="swissimage",
        url="https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/3857/{z}/{x}/{y}.jpeg",
        attribution="Luftbild: © swisstopo",
        licence="Open Government Data of swisstopo: free use with attribution",
        max_zoom=19,
        bounds=(5.9, 45.8, 10.55, 47.85),
    ),
    Provider(
        id="basemap-at",
        url="https://mapsneu.wien.gv.at/basemap/bmaporthofoto30cm/normal/google3857/{z}/{y}/{x}.jpeg",
        attribution="Luftbild: basemap.at",
        licence="CC BY 4.0",
        max_zoom=19,
        bounds=(9.5, 46.35, 17.2, 49.05),
    ),
    Provider(
        id="s2cloudless-2016",
        url="https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg",
        attribution="Satellitenbild: Sentinel-2 cloudless 2016 by EOX (Copernicus Sentinel data)",
        licence="CC BY 4.0",
        max_zoom=14,
    ),
)

# From satellites, through NASA's open tile service GIBS. Snow cover is asked for by day
# ({date} = yesterday, the newest complete day): "default" delivers broken tiles there.
_GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
SNOW = Provider(
    id="snow",
    url=_GIBS
    + "/MODIS_Terra_NDSI_Snow_Cover/default/{date}/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png",
    attribution="Schneebedeckung: MODIS/Terra, NASA EOSDIS GIBS",
    licence="NASA Earth science data: free and open, acknowledgement requested",
    max_zoom=8,
    media_type="image/png",
)
PRECIPITATION = Provider(
    id="precipitation",
    url=_GIBS
    + "/IMERG_Precipitation_Rate/default/default/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png",
    attribution="Niederschlag: GPM IMERG, NASA EOSDIS GIBS",
    licence="NASA Earth science data: free and open, acknowledgement requested",
    max_zoom=6,
    media_type="image/png",
)
# How long a tile of a layer is kept before the source is asked again, in days.
_FRESH_DAYS = {"snow": 0.25, "precipitation": 0.02}

# An image smaller than this is a blank tile outside the area a provider covers.
_BLANK_BYTES = 1500
SLOPE_MIN_ZOOM = 9
SLOPE_MAX_ZOOM = 14
# From this angle on a slope is coloured, like on avalanche maps.
SLOPE_CLASSES = (
    (45, (124, 58, 173, 165)),
    (40, (200, 40, 40, 165)),
    (35, (240, 130, 30, 160)),
    (30, (245, 215, 60, 150)),
)
_EQUATOR_M = 40075016.686


def tile_center(z: int, x: int, y: int) -> tuple[float, float]:
    """Latitude and longitude of the middle of a tile."""
    lon = (x + 0.5) / 2**z * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / 2**z))))
    return lat, lon


def _covers(provider: Provider, z: int, x: int, y: int) -> bool:
    if provider.bounds is None:
        return True
    lat, lon = tile_center(z, x, y)
    west, south, east, north = provider.bounds
    return west <= lon <= east and south <= lat <= north


class DatedTileSource(HttpTileSource):
    """A source whose address names a day: `{date}` becomes yesterday (UTC)."""

    def __init__(self, url_template: str, *args, **kwargs):
        super().__init__(url_template, *args, **kwargs)
        self._dated = url_template

    def fetch(self, z: int, x: int, y: int, etag: str | None) -> FetchedTile | None:
        day = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
        self._template = self._dated.replace("{date}", day)
        # Without the stored ETag: it belongs to the image of another day.
        return super().fetch(z, x, y, None)


class _Composite:
    """Several providers as one source: the first one that has an image answers."""

    def __init__(self, sources: list[tuple[Provider, TileSource]]):
        self._sources = sources

    def fetch(self, z: int, x: int, y: int, etag: str | None) -> FetchedTile | None:
        error: TileSourceError | None = None
        for provider, source in self._sources:
            if not _covers(provider, z, x, y):
                continue
            # Deeper than a provider goes there is nothing; the map enlarges what it has.
            if z > provider.max_zoom:
                continue
            try:
                # Without the stored ETag: it may belong to another provider.
                tile = source.fetch(z, x, y, None)
            except TileSourceError as exc:
                error = exc
                continue
            if tile is not None and tile.data is not None and len(tile.data) >= _BLANK_BYTES:
                return FetchedTile(tile.data, None)
        if error is not None:
            raise error
        return None


def slope_tile(terrain_png: bytes, z: int, y: int) -> bytes:
    """A transparent tile that colours slopes of 30° and more, from an elevation tile."""
    image = Image.open(io.BytesIO(terrain_png)).convert("RGB")
    width, height = image.size
    pixels = image.tobytes()
    # Terrarium: metres = red * 256 + green + blue / 256 - 32768
    elevation = [
        pixels[i] * 256 + pixels[i + 1] + pixels[i + 2] / 256 - 32768
        for i in range(0, len(pixels), 3)
    ]
    lat = math.radians(tile_center(z, 0, y)[0])
    metres = _EQUATOR_M * math.cos(lat) / 2**z / width
    # tan² of the class borders, so that no angle has to be computed per pixel.
    classes = [(math.tan(math.radians(angle)) ** 2, colour) for angle, colour in SLOPE_CLASSES]
    lowest = classes[-1][0]
    step = 2 * metres
    out = bytearray(width * height * 4)
    for row in range(height):
        up = max(row - 1, 0) * width
        down = min(row + 1, height - 1) * width
        here = row * width
        for column in range(width):
            left = max(column - 1, 0)
            right = min(column + 1, width - 1)
            # At the edge of the tile the difference spans one pixel instead of two.
            dx = (elevation[here + right] - elevation[here + left]) / (
                step if right - left == 2 else metres
            )
            dy = (elevation[down + column] - elevation[up + column]) / (
                step if down - up == 2 * width else metres
            )
            steepness = dx * dx + dy * dy
            if steepness < lowest:
                continue
            for limit, colour in classes:
                if steepness >= limit:
                    offset = (here + column) * 4
                    out[offset : offset + 4] = bytes(colour)
                    break
    result = io.BytesIO()
    Image.frombytes("RGBA", (width, height), bytes(out)).save(result, format="PNG", optimize=True)
    return result.getvalue()


class Layers:
    """The raster layers of this server and their caches."""

    def __init__(self, cache_path: str, cache_days: float, max_bytes: int, sources: dict):
        self._sources: dict[str, TileSource] = sources
        self._caches = {
            name: TileCache(
                Path(cache_path) / "_layers" / name, _FRESH_DAYS.get(name, cache_days), max_bytes
            )
            for name in (*sources, "slope", "contours")
        }

    def available(self) -> set[str]:
        names = set(self._sources)
        if "terrain" in names:
            names.update(("slope", "contours"))
        return names

    def raster(self, layer: str, z: int, x: int, y: int) -> bytes:
        source = self._sources.get(layer)
        if source is None:
            raise NotFoundError("No such layer")
        return self._caches[layer].get(source, z, x, y)

    def slope(self, z: int, x: int, y: int) -> bytes:
        if "terrain" not in self._sources:
            raise NotFoundError("No such layer")
        layers = self

        class _Computed:
            def fetch(self, z: int, x: int, y: int, etag: str | None) -> FetchedTile | None:
                return FetchedTile(slope_tile(layers.raster("terrain", z, x, y), z, y))

        return self._caches["slope"].get(_Computed(), z, x, y)

    def contours(self, z: int, x: int, y: int) -> bytes:
        """Gzip-compressed vector tile with contour lines, computed once and kept."""
        if "terrain" not in self._sources:
            raise NotFoundError("No such layer")
        layers = self

        class _Computed:
            def fetch(self, z: int, x: int, y: int, etag: str | None) -> FetchedTile | None:
                return FetchedTile(contour_tile(layers.raster("terrain", z, x, y), z))

        return self._caches["contours"].get(_Computed(), z, x, y)


def media_type(layer: str) -> str:
    return "image/jpeg" if layer == "satellite" else "image/png"


def attributions(available: set[str]) -> dict[str, str]:
    """What must be named when a layer is shown."""
    result = {}
    if "terrain" in available:
        result["terrain"] = TERRAIN.attribution
    if "satellite" in available:
        result["satellite"] = " · ".join(provider.attribution for provider in SATELLITE)
    for provider in (SNOW, PRECIPITATION):
        if provider.id in available:
            result[provider.id] = provider.attribution
    return result


@lru_cache
def _layers(
    cache_path: str,
    cache_days: int,
    max_mb: int,
    terrain_url: str,
    satellite: bool,
    weather: bool,
    public_base_url: str,
) -> Layers:
    user_agent = f"hiker/{__version__} (self-hosted; {public_base_url})"
    sources: dict[str, TileSource] = {}
    if terrain_url:
        sources["terrain"] = HttpTileSource(terrain_url, user_agent, public_base_url)
    if satellite:
        sources["satellite"] = _Composite(
            [
                (provider, HttpTileSource(provider.url, user_agent, public_base_url))
                for provider in SATELLITE
            ]
        )
    if weather:
        for provider in (SNOW, PRECIPITATION):
            source = DatedTileSource if "{date}" in provider.url else HttpTileSource
            sources[provider.id] = source(provider.url, user_agent, public_base_url)
    return Layers(cache_path, cache_days, max_mb * 1024 * 1024, sources)


def get_layers() -> Layers:
    settings = get_settings()
    return _layers(
        settings.tile_cache_path,
        settings.tile_cache_days,
        settings.tile_cache_max_mb,
        settings.terrain_tiles_url if settings.terrain_enabled else "",
        settings.satellite_enabled,
        settings.weather_layers_enabled,
        settings.public_base_url,
    )


MapLayers = Annotated[Layers, Depends(get_layers)]
