from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import NotFoundError, error_responses
from app.core.ratelimit import rate_limit
from app.modules.maps.tiles import OSM_ATTRIBUTION, Cache, Tiles

router = APIRouter()

# Above this zoom the tile source has nothing.
MAX_ZOOM = 19


class MapInfo(BaseModel):
    tile_url: str = Field(description="URL template of the tiles on this server")
    max_zoom: int
    attribution: str = Field(description="Must be shown on the map (ODbL)")
    cache_days: int = Field(description="After this time the source is asked for an update")


@router.get("/info", response_model=MapInfo)
def read_info():
    """Where the clients get their map tiles from. No login."""
    settings = get_settings()
    return MapInfo(
        tile_url=f"{settings.public_base_url}/api/v1/maps/tiles/{{z}}/{{x}}/{{y}}.png",
        max_zoom=MAX_ZOOM,
        attribution=OSM_ATTRIBUTION,
        cache_days=settings.tile_cache_days,
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
