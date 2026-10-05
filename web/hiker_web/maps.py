"""Which map the pages show: the own vector map of the server, or cached raster tiles."""

import time

from flask import current_app, url_for

from hiker_web.api import ApiError, api
from hiker_web.texts_de import t

PLACE_KINDS = (
    "city",
    "town",
    "village",
    "hamlet",
    "peak",
    "saddle",
    "volcano",
    "hut",
    "lake",
    "viewpoint",
    "station",
    "halt",
    "parking",
    "camp_site",
    "shelter",
    "attraction",
    "castle",
    "ruins",
    "cave_entrance",
    "waterfall",
    "spring",
    "other",
)

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
        "layerTexts": {
            "title": t("map.layers"),
            "base": {
                "map": t("map.base.map"),
                "winter": t("map.base.winter"),
                "topo": t("map.base.topo"),
                "alpenverein": t("map.base.alpenverein"),
                "outdooractive": t("map.base.outdooractive"),
                "kompass": t("map.base.kompass"),
                "satellite": t("map.base.satellite"),
            },
            # Search for places of the own map; only a server with a vector map has it.
            "search": {
                "url": url_for("map_search"),
                "label": t("map.search"),
                "none": t("map.search.none"),
                "kinds": {kind: t(f"map.kind.{kind}") for kind in PLACE_KINDS},
            },
            "group": {
                "terrain": t("map.group.terrain"),
                "snow": t("map.group.snow"),
                "weather": t("map.group.weather"),
            },
            "opacity": t("map.opacity"),
            "overlay": {
                "satellite": t("map.base.satellite"),
                "slope": t("map.overlay.slope"),
                "avalanche": t("map.overlay.avalanche"),
                "snow": t("map.overlay.snow"),
                "precipitation": t("map.overlay.precipitation"),
                "weather0": t("map.overlay.weather0"),
                "weather1": t("map.overlay.weather1"),
                "weather2": t("map.overlay.weather2"),
                "snowdepth": t("map.overlay.snowdepth"),
            },
            "note": {
                "avalanche": t("map.note.avalanche"),
                "snow": t("map.note.snow"),
                "precipitation": t("map.note.precipitation"),
                "weather2": t("map.note.weather"),
                "snowdepth": t("map.note.snowdepth"),
            },
            "looks": t("map.looks"),
            "looksNote": t("map.base.note"),
            "slope": {
                "from": t("map.slope.from"),
                "to": t("map.slope.to"),
                "low": t("map.slope.low"),
                "high": t("map.slope.high"),
                "open": t("map.slope.open"),
            },
            "history": {
                "label": t("map.history.label"),
                "today": t("map.history.today"),
                "note": t("map.history.note"),
            },
            "radar": {
                "rain": t("map.radar.rain"),
                "clouds": t("map.radar.clouds"),
                "play": t("map.radar.play"),
                "note": t("map.radar.note"),
            },
            "terrain": t("map.terrain"),
            "paths": t("map.paths"),
            "pathsNote": t("map.paths_note"),
            "from": t("map.from"),
        },
    }
