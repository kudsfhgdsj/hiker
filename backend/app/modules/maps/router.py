import re
from datetime import datetime
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import NotFoundError, error_responses
from app.core.ratelimit import rate_limit
from app.modules.auth.deps import CurrentUser
from app.modules.maps.contours import CONTOUR_MAX_ZOOM, CONTOUR_MIN_ZOOM
from app.modules.maps.layers import (
    SLOPE_MAX_ZOOM,
    SLOPE_MIN_ZOOM,
    MapLayers,
    attributions,
    media_type,
)
from app.modules.maps.style import build_style
from app.modules.maps.tiles import OSM_ATTRIBUTION, Cache, Tiles
from app.modules.maps.vector import REGION_NAME, VECTOR_ATTRIBUTION, Vectors

router = APIRouter()
PROTOBUF = "application/x-protobuf"

# Above this zoom the tile source has nothing.
MAX_ZOOM = 19


class MapInfo(BaseModel):
    tile_url: str = Field(description="URL template of the tiles on this server")
    max_zoom: int
    attribution: str = Field(description="Must be shown on the map (ODbL)")
    cache_days: int = Field(description="After this time the source is asked for an update")
    style_url: str | None = Field(
        description="MapLibre style of the own vector map; null if none is installed"
    )


@router.get("/info", response_model=MapInfo)
def read_info(vectors: Vectors):
    """Where the clients get their map from. No login."""
    settings = get_settings()
    return MapInfo(
        tile_url=f"{settings.public_base_url}/api/v1/maps/tiles/{{z}}/{{x}}/{{y}}.png",
        max_zoom=MAX_ZOOM,
        attribution=OSM_ATTRIBUTION,
        cache_days=settings.tile_cache_days,
        style_url=(
            f"{settings.public_base_url}/api/v1/maps/style.json" if vectors.regions() else None
        ),
    )


@router.get(
    "/tiles/{z}/{x}/{y}.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}, **error_responses(404, 429, 502)},
    dependencies=[Depends(rate_limit("tiles", limit=1500))],
)
def read_tile(
    z: Annotated[int, Path(ge=0, le=MAX_ZOOM)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    source: Tiles,
    cache: Cache,
):
    """A map tile, served from the cache of this server. No login (public link pages)."""
    if x >= 2**z or y >= 2**z:
        raise NotFoundError("No such tile")
    data = cache.get(source, z, x, y)
    # Browsers and the app may keep the tile for a day; the server decides about updates.
    return Response(
        data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
    )


# --- The own map: vector tiles built from OpenStreetMap data ---

FONTS = FilePath(__file__).parent / "fonts"
GLYPH_RANGE = r"^\d{1,5}-\d{1,5}$"


class RegionInfo(BaseModel):
    name: str
    size_bytes: int
    modified: datetime
    bounds: tuple[float, float, float, float] = Field(description="west, south, east, north")
    min_zoom: int
    max_zoom: int


@router.get("/style.json", responses=error_responses(404))
def read_style(vectors: Vectors, layers: MapLayers) -> dict:
    """The MapLibre style of the own map. No login (public link pages)."""
    if not vectors.regions():
        raise NotFoundError("No vector map is installed")
    base = f"{get_settings().public_base_url}/api/v1/maps"
    return build_style(
        tile_url=f"{base}/vector/{{z}}/{{x}}/{{y}}.pbf",
        glyph_url=f"{base}/fonts/{{fontstack}}/{{range}}.pbf",
        attribution=VECTOR_ATTRIBUTION,
        max_zoom=vectors.max_zoom(),
        terrain_url=(
            f"{base}/raster/terrain/{{z}}/{{x}}/{{y}}" if "terrain" in layers.available() else None
        ),
        slope_url=(
            f"{base}/slope/{{z}}/{{x}}/{{y}}.png" if "slope" in layers.available() else None
        ),
        satellite_url=(
            f"{base}/raster/satellite/{{z}}/{{x}}/{{y}}"
            if "satellite" in layers.available()
            else None
        ),
        contour_url=(
            f"{base}/contours/{{z}}/{{x}}/{{y}}.pbf" if "contours" in layers.available() else None
        ),
        attributions=attributions(layers.available()),
    )


@router.get(
    "/vector/{z}/{x}/{y}.pbf",
    response_class=Response,
    responses={200: {"content": {PROTOBUF: {}}}, 204: {"description": "No data here"}},
    dependencies=[Depends(rate_limit("tiles", limit=1500))],
)
def read_vector_tile(
    z: Annotated[int, Path(ge=0, le=22)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    vectors: Vectors,
):
    """A vector tile of the own map. No login. 204 where the map has no data."""
    data = vectors.tile(z, x, y) if x < 2**z and y < 2**z else None
    if data is None:
        # An empty answer instead of an error: the map simply shows nothing there.
        return Response(status_code=204, headers={"Cache-Control": "public, max-age=3600"})
    return Response(
        data,
        media_type=PROTOBUF,
        headers={"Content-Encoding": "gzip", "Cache-Control": "public, max-age=86400"},
    )


@router.get(
    "/raster/{layer}/{z}/{x}/{y}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}, "image/jpeg": {}}}, **error_responses(404, 502)},
    dependencies=[Depends(rate_limit("tiles", limit=1500))],
)
def read_layer_tile(
    layer: Annotated[str, Path(pattern="^(terrain|satellite)$")],
    z: Annotated[int, Path(ge=0, le=20)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    layers: MapLayers,
):
    """A tile of an open raster layer (elevation, aerial image), cached here. No login."""
    if x >= 2**z or y >= 2**z:
        raise NotFoundError("No such tile")
    return Response(
        layers.raster(layer, z, x, y),
        media_type=media_type(layer),
        headers={"Cache-Control": "public, max-age=604800"},
    )


@router.get(
    "/contours/{z}/{x}/{y}.pbf",
    response_class=Response,
    responses={200: {"content": {PROTOBUF: {}}}, **error_responses(404, 502)},
    dependencies=[Depends(rate_limit("tiles", limit=1500))],
)
def read_contour_tile(
    z: Annotated[int, Path(ge=CONTOUR_MIN_ZOOM, le=CONTOUR_MAX_ZOOM)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    layers: MapLayers,
):
    """Contour lines as a vector tile (layer `contour`), computed from the elevation tiles."""
    if x >= 2**z or y >= 2**z:
        raise NotFoundError("No such tile")
    return Response(
        layers.contours(z, x, y),
        media_type=PROTOBUF,
        headers={"Content-Encoding": "gzip", "Cache-Control": "public, max-age=604800"},
    )


@router.get(
    "/slope/{z}/{x}/{y}.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}, **error_responses(404, 502)},
    dependencies=[Depends(rate_limit("tiles", limit=1500))],
)
def read_slope_tile(
    z: Annotated[int, Path(ge=SLOPE_MIN_ZOOM, le=SLOPE_MAX_ZOOM)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    layers: MapLayers,
):
    """Slopes of 30° and more, coloured by steepness; computed from the elevation tiles."""
    if x >= 2**z or y >= 2**z:
        raise NotFoundError("No such tile")
    return Response(
        layers.slope(z, x, y),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=604800"},
    )


@router.get(
    "/fonts/{fontstack}/{glyphs}.pbf",
    response_class=Response,
    responses={200: {"content": {PROTOBUF: {}}}, **error_responses(404)},
)
def read_glyphs(fontstack: str, glyphs: Annotated[str, Path(pattern=GLYPH_RANGE)]):
    """Glyphs of a font for the labels of the map. No login."""
    fonts = {folder.name: folder for folder in FONTS.iterdir() if folder.is_dir()}
    # The map may ask for several fonts at once; the first one known answers.
    folder = next((fonts[name] for name in fontstack.split(",") if name in fonts), None)
    if folder is None:
        raise NotFoundError("No such font")
    file = folder / f"{glyphs}.pbf"
    # A range without glyphs is an empty answer, not an error.
    data = file.read_bytes() if file.is_file() else b""
    return Response(data, media_type=PROTOBUF, headers={"Cache-Control": "public, max-age=604800"})


@router.get("/regions", response_model=list[RegionInfo], responses=error_responses(401))
def list_regions(_user: CurrentUser, vectors: Vectors):
    """The maps this server offers for download, to be shown without network."""
    return [
        RegionInfo(
            name=region.name,
            size_bytes=region.size_bytes,
            modified=region.modified,
            bounds=region.bounds,
            min_zoom=region.min_zoom,
            max_zoom=region.max_zoom,
        )
        for region in vectors.regions()
    ]


@router.get(
    "/regions/{name}",
    response_class=FileResponse,
    responses={200: {"content": {"application/octet-stream": {}}}, **error_responses(401, 404)},
    dependencies=[Depends(rate_limit("map-download", limit=30))],
)
def download_region(name: str, _user: CurrentUser, vectors: Vectors):
    """The whole map of a region as an MBTiles file. Supports range requests."""
    region = vectors.region(name) if re.match(REGION_NAME, name) else None
    if region is None:
        raise NotFoundError("No such map")
    return FileResponse(
        region.path, media_type="application/octet-stream", filename=f"{name}.mbtiles"
    )
