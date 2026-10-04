"""Which map the pages show: the own vector map of the server, or cached raster tiles."""

import time

from flask import current_app, url_for

from hiker_web.api import ApiError, api

# How long the answer of the API about its map is kept.
_CHECK_EVERY_S = 300


def style_url() -> str | None:
    """Address of the map style on this server, if the API has a vector map."""
    known = current_app.extensions.get("hiker_map")
    now = time.monotonic()
    if known is None or now - known[0] > _CHECK_EVERY_S:
        try:
            info = api().request("GET", "/maps/info", auth=False).json()
            available = bool(info.get("style_url"))
        except (ApiError, ValueError):
            # No map module or no answer: the raster tiles still work.
            available = False
        known = current_app.extensions["hiker_map"] = (now, available)
    return url_for("map_style") if known[1] else None


def map_config(attribution: str) -> dict:
    """What every map on a page needs."""
    return {
        "tileUrl": current_app.config["MAP_TILE_URL"],
        "styleUrl": style_url(),
        "workerUrl": url_for("static", filename="vendor/maplibre-gl/maplibre-gl-csp-worker.js"),
        "attribution": attribution,
    }
