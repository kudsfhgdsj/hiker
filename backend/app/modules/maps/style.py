"""The style of the own map: a hiking map drawn from the OpenMapTiles schema.

An own design: paths and tracks stand out, rock, ice and forest are told apart,
peaks and huts are named. It needs no icon sprite; labels use Noto Sans.
"""

REGULAR = ["Noto Sans Regular"]
BOLD = ["Noto Sans Bold"]
ITALIC = ["Noto Sans Italic"]

# German names where the data has them, then names in Latin script.
# Wrapped in "to-string": the map library of the app otherwise turns a missing name into
# an empty text before "coalesce" can skip it, and no label would be drawn.
NAME = ["to-string", ["coalesce", ["get", "name:de"], ["get", "name:latin"], ["get", "name"]]]

LAND = "#f3f0e8"
WATER = "#a8d0ea"
WATER_LINE = "#7db4d8"
PATH = "#b5342a"
# Not "#ffffffcc": the map library of the app does not read colours with eight digits.
HALO = "rgba(255, 255, 255, 0.8)"


def _width(*stops: tuple[int, float]) -> list:
    """Line width that grows with the zoom level."""
    return ["interpolate", ["exponential", 1.5], ["zoom"], *[v for stop in stops for v in stop]]


def _line(layer_id: str, source_layer: str, where: list, paint: dict, **extra) -> dict:
    return {
        "id": layer_id,
        "type": "line",
        "source": "hiker",
        "source-layer": source_layer,
        "filter": where,
        "layout": {"line-join": "round", "line-cap": extra.pop("cap", "round")},
        "paint": paint,
        **extra,
    }


def _fill(layer_id: str, source_layer: str, where: list | None, color: str, **paint) -> dict:
    layer = {
        "id": layer_id,
        "type": "fill",
        "source": "hiker",
        "source-layer": source_layer,
        "paint": {"fill-color": color, **paint},
    }
    if where is not None:
        layer["filter"] = where
    return layer


def _label(
    layer_id: str, source_layer: str, where: list | None, layout: dict, paint: dict, **extra
):
    layer = {
        "id": layer_id,
        "type": "symbol",
        "source": "hiker",
        "source-layer": source_layer,
        "layout": {"text-field": NAME, "text-font": REGULAR, **layout},
        "paint": {"text-halo-color": HALO, "text-halo-width": 1.5, **paint},
        **extra,
    }
    if where is not None:
        layer["filter"] = where
    return layer


def _roads() -> list[dict]:
    roads = [
        # class, colour, widths at zoom 8 / 14 / 18
        ("motorway", "#e9a35a", 1.2, 5, 22),
        ("trunk", "#eeb872", 1.0, 4.5, 20),
        ("primary", "#f3cf8c", 0.8, 4, 18),
        ("secondary", "#f7e3a4", 0.5, 3.2, 16),
        ("tertiary", "#ffffff", 0.3, 2.6, 14),
        ("minor", "#ffffff", 0.0, 1.8, 11),
        ("service", "#ffffff", 0.0, 1.0, 7),
    ]
    not_tunnel = ["!=", ["get", "brunnel"], "tunnel"]
    layers = []
    for name, _colour, low, mid, high in reversed(roads):
        layers.append(
            _line(
                f"road-{name}-casing",
                "transportation",
                ["all", ["==", ["get", "class"], name], not_tunnel],
                {
                    "line-color": "#b9b2a6",
                    "line-width": _width((8, low + 0.6), (14, mid + 1.6), (18, high + 3)),
                },
                minzoom=13 if name == "service" else 11 if name == "minor" else 6,
                cap="butt",
            )
        )
    for name, colour, low, mid, high in reversed(roads):
        layers.append(
            _line(
                f"road-{name}",
                "transportation",
                ["all", ["==", ["get", "class"], name], not_tunnel],
                {"line-color": colour, "line-width": _width((8, low), (14, mid), (18, high))},
                minzoom=13 if name == "service" else 11 if name == "minor" else 6,
            )
        )
    return layers


def build_style(tile_url: str, glyph_url: str, attribution: str, max_zoom: int) -> dict:
    """The MapLibre style; `tile_url` and `glyph_url` are URL templates."""
    cls = ["get", "class"]
    layers: list[dict] = [
        {"id": "background", "type": "background", "paint": {"background-color": LAND}},
        _fill("residential", "landuse", ["==", cls, "residential"], "#e9e4dc"),
        _fill("farmland", "landcover", ["==", cls, "farmland"], "#eef0dc"),
        _fill("grass", "landcover", ["==", cls, "grass"], "#dfecc8"),
        _fill("wood", "landcover", ["==", cls, "wood"], "#c5dfb6"),
        _fill("wetland", "landcover", ["==", cls, "wetland"], "#d3e6dc"),
        _fill("sand", "landcover", ["==", cls, "sand"], "#efe6c8"),
        _fill("rock", "landcover", ["==", cls, "rock"], "#dcd6cd"),
        _fill(
            "ice", "landcover", ["==", cls, "ice"], "#eaf4fb", **{"fill-outline-color": "#b9d8ee"}
        ),
        _fill("park", "park", None, "#b7d9a8", **{"fill-opacity": 0.25}),
        _line(
            "waterway",
            "waterway",
            ["!=", ["get", "brunnel"], "tunnel"],
            {"line-color": WATER_LINE, "line-width": _width((8, 0.5), (14, 1.6), (18, 6))},
        ),
        _fill("water", "water", None, WATER),
        _fill("building", "building", None, "#d6cec3", **{"fill-outline-color": "#bdb4a6"})
        | {"minzoom": 13},
        _line(
            "tunnel",
            "transportation",
            ["all", ["==", ["get", "brunnel"], "tunnel"], ["!=", cls, "path"]],
            {
                "line-color": "#cfc9bf",
                "line-width": _width((10, 0.6), (14, 2.5), (18, 10)),
                "line-dasharray": [2, 2],
            },
            cap="butt",
        ),
        *_roads(),
        _line(
            "rail",
            "transportation",
            ["==", cls, "rail"],
            {"line-color": "#7d7d7d", "line-width": _width((8, 0.6), (14, 1.4), (18, 3))},
            minzoom=8,
        ),
        _line(
            "rail-ties",
            "transportation",
            ["==", cls, "rail"],
            {
                "line-color": "#ffffff",
                "line-width": _width((8, 0.3), (14, 0.8), (18, 1.6)),
                "line-dasharray": [4, 4],
            },
            minzoom=11,
            cap="butt",
        ),
        _line(
            "aerialway",
            "transportation",
            ["==", cls, "aerialway"],
            {"line-color": "#4a4a4a", "line-width": _width((10, 0.6), (14, 1.2), (18, 2))},
            minzoom=10,
        ),
        _line(
            "track",
            "transportation",
            ["==", cls, "track"],
            {
                "line-color": "#8a6a45",
                "line-width": _width((11, 0.5), (14, 1.4), (18, 4)),
                "line-dasharray": [5, 2],
            },
            minzoom=11,
            cap="butt",
        ),
        # Paths are what a hiking map is for: red and visible early.
        _line(
            "path-halo",
            "transportation",
            ["==", cls, "path"],
            {
                "line-color": "#ffffff",
                "line-opacity": 0.6,
                "line-width": _width((11, 1.4), (14, 3), (18, 7)),
            },
            minzoom=11,
        ),
        _line(
            "path",
            "transportation",
            ["==", cls, "path"],
            {
                "line-color": PATH,
                "line-width": _width((11, 0.5), (14, 1.3), (18, 3.5)),
                "line-dasharray": [3, 1.5],
            },
            minzoom=11,
            cap="butt",
        ),
        _line(
            "boundary",
            "boundary",
            ["all", ["<=", ["get", "admin_level"], 4], ["!=", ["get", "maritime"], 1]],
            {
                "line-color": "#9a6fa8",
                "line-width": ["case", ["<=", ["get", "admin_level"], 2], 1.6, 0.8],
                "line-dasharray": [4, 2, 1, 2],
            },
            cap="butt",
        ),
        _label(
            "waterway-name",
            "waterway",
            None,
            {
                "symbol-placement": "line",
                "text-font": ITALIC,
                "text-size": 11,
                "symbol-spacing": 400,
            },
            {"text-color": "#3f7fae"},
            minzoom=13,
        ),
        _label(
            "water-name",
            "water_name",
            None,
            {"text-font": ITALIC, "text-size": 12, "text-max-width": 6},
            {"text-color": "#3f7fae"},
        ),
        _label(
            "road-name",
            "transportation_name",
            ["!=", cls, "path"],
            {"symbol-placement": "line", "text-size": 10.5, "symbol-spacing": 350},
            {"text-color": "#5a554c"},
            minzoom=14,
        ),
        _label(
            "path-name",
            "transportation_name",
            ["==", cls, "path"],
            {"symbol-placement": "line", "text-size": 10, "symbol-spacing": 300},
            {"text-color": PATH},
            minzoom=14,
        ),
        _label(
            "park-name",
            "park",
            ["has", "name"],
            {"text-font": ITALIC, "text-size": 11, "text-max-width": 8},
            {"text-color": "#4f7a45"},
            minzoom=9,
        ),
        {
            "id": "hut",
            "type": "circle",
            "source": "hiker",
            "source-layer": "poi",
            "minzoom": 12,
            "filter": ["in", ["get", "subclass"], ["literal", ["alpine_hut", "wilderness_hut"]]],
            "paint": {
                "circle-radius": 4,
                "circle-color": "#8e3b2f",
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 1.5,
            },
        },
        _label(
            "hut-name",
            "poi",
            ["in", ["get", "subclass"], ["literal", ["alpine_hut", "wilderness_hut"]]],
            {"text-font": BOLD, "text-size": 11, "text-offset": [0, 0.9], "text-anchor": "top"},
            {"text-color": "#8e3b2f"},
            minzoom=12,
        ),
        {
            "id": "peak",
            "type": "circle",
            "source": "hiker",
            "source-layer": "mountain_peak",
            "minzoom": 9,
            "paint": {
                "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 2, 14, 3.5],
                "circle-color": "#6b4a2b",
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 1,
            },
        },
        _label(
            "peak-name",
            "mountain_peak",
            ["has", "name"],
            {
                # "Säntis\n2502 m"
                "text-field": [
                    "case",
                    ["has", "ele"],
                    ["concat", NAME, "\n", ["to-string", ["get", "ele"]], " m"],
                    NAME,
                ],
                "text-size": 11,
                "text-offset": [0, 0.7],
                "text-anchor": "top",
                "text-max-width": 8,
            },
            {"text-color": "#5a3d22"},
            minzoom=9,
        ),
        _label(
            "place-small",
            "place",
            ["in", cls, ["literal", ["village", "hamlet", "suburb", "isolated_dwelling"]]],
            {
                "text-size": ["interpolate", ["linear"], ["zoom"], 10, 10.5, 15, 14],
                "text-max-width": 7,
            },
            {"text-color": "#3a3a3a"},
            minzoom=10,
        ),
        _label(
            "place-town",
            "place",
            ["==", cls, "town"],
            {
                "text-font": BOLD,
                "text-size": ["interpolate", ["linear"], ["zoom"], 7, 11, 14, 17],
                "text-max-width": 7,
            },
            {"text-color": "#2b2b2b"},
            minzoom=7,
        ),
        _label(
            "place-city",
            "place",
            ["==", cls, "city"],
            {
                "text-font": BOLD,
                "text-size": ["interpolate", ["linear"], ["zoom"], 4, 11, 12, 20],
                "text-max-width": 7,
            },
            {"text-color": "#222222"},
        ),
        _label(
            "place-country",
            "place",
            ["==", cls, "country"],
            {
                "text-font": BOLD,
                "text-size": 13,
                "text-transform": "uppercase",
                "text-letter-spacing": 0.1,
            },
            {"text-color": "#6a5a78"},
            maxzoom=8,
        ),
    ]
    return {
        "version": 8,
        "name": "hiker",
        "glyphs": glyph_url,
        "sources": {
            "hiker": {
                "type": "vector",
                "tiles": [tile_url],
                "minzoom": 0,
                "maxzoom": max_zoom,
                "attribution": attribution,
            }
        },
        "layers": layers,
    }
