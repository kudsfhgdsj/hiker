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
# T1 … T6 on the SAC scale, and via ferratas.
# Light blue, dark blue, yellow, orange, red, black: the harder, the warmer and darker.
DIFFICULTY = ["#38b6ff", "#1d3fa8", "#f2c200", "#f28c1e", "#d92323", "#111111"]
VIA_FERRATA = "#6b21a8"
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


def _add_topo_look(
    layers: list[dict], hiker: dict, insert_before, *, symbols: bool = False
) -> None:
    """The look "Topo": a classic topographic hiking map. Strong green forest, grey rock,
    heavy relief and dense brown contour lines, paths in red, summits in bold black.

    A look is a set of layers that are shown instead of others (`bases` in the metadata),
    so the clients switch it like the winter look, without loading another style.
    """
    cls = ["get", "class"]
    present = {layer["id"] for layer in layers}
    hidden = {"layout": {"visibility": "none"}}
    show: list[str] = []
    hide: list[str] = []

    def add(before: str, layer: dict, replaces: tuple[str, ...] = ()) -> None:
        layer["layout"] = {**layer.get("layout", {}), **hidden["layout"]}
        insert_before(before, layer)
        show.append(layer["id"])
        hide.extend(name for name in replaces if name in present)

    # Ground: meadow as the basic tone, forest clearly darker, rock and scree grey.
    add(
        "residential",
        {"id": "topo-ground", "type": "background", "paint": {"background-color": "#e6edc4"}},
    )
    for name, colour in (("grass", "#d3e6a4"), ("wood", "#7fb069"), ("rock", "#cbc9c4")):
        add("park", _fill(f"topo-{name}", "landcover", ["==", cls, name], colour), (name,))
    if "hillshade" in present:
        add(
            "waterway",
            {
                "id": "topo-hillshade",
                "type": "hillshade",
                "source": "terrain",
                "paint": {
                    "hillshade-exaggeration": 0.85,
                    "hillshade-shadow-color": "#1c2a18",
                    "hillshade-highlight-color": "#ffffff",
                    "hillshade-accent-color": "#26331f",
                },
            },
            ("hillshade",),
        )
    if "contour" in present:
        add(
            "waterway",
            {
                "id": "topo-contour",
                "type": "line",
                "source": "contours",
                "source-layer": "contour",
                "minzoom": 11,
                "paint": {
                    "line-color": "#5f4320",
                    "line-opacity": ["case", ["==", ["get", "index"], 1], 0.85, 0.5],
                    "line-width": ["case", ["==", ["get", "index"], 1], 1.3, 0.6],
                },
            },
            ("contour",),
        )
    # Paths: red on a light casing, dashed; the grade still stands next to them close up.
    path = ["==", cls, "path"]
    add(
        "boundary",
        _line(
            "topo-path-casing",
            "transportation",
            path,
            {
                "line-color": "#ffffff",
                "line-opacity": 0.75,
                "line-width": _width((11, 1.8), (14, 3.6), (18, 8)),
            },
            minzoom=11,
        ),
        ("path-halo", "path", "path-difficulty"),
    )
    add(
        "boundary",
        _line(
            "topo-path",
            "transportation",
            path,
            {
                "line-color": "#d0182b",
                "line-width": _width((11, 0.9), (14, 1.9), (18, 4.2)),
                "line-dasharray": [3, 1.6],
            },
            minzoom=11,
            cap="butt",
        ),
    )
    if "peak-name" in present:
        summit = next(layer for layer in layers if layer["id"] == "peak-name")
        add(
            "peak-name",
            {
                **summit,
                "id": "topo-peak-name",
                "layout": {**summit["layout"], "text-font": BOLD, "text-size": 13},
                "paint": {
                    "text-color": "#111111",
                    "text-halo-color": "rgba(255, 255, 255, 0.92)",
                    "text-halo-width": 2,
                },
            },
            ("peak-name",),
        )
    if symbols:
        # Symbols instead of dots: a triangle for a summit, two arcs for a saddle, and
        # signs for huts, shelters, viewpoints, car parks and cable car stations.
        point = ["==", ["geometry-type"], "Point"]
        add(
            "peak-name",
            {
                "id": "topo-peak",
                "type": "symbol",
                "source": "hiker",
                "source-layer": "mountain_peak",
                "minzoom": 10,
                "filter": point,
                "layout": {
                    "icon-image": ["case", ["==", cls, "saddle"], "saddle", "peak"],
                    "icon-size": ["interpolate", ["linear"], ["zoom"], 10, 0.55, 14, 0.8],
                    "icon-allow-overlap": True,
                    # The sign must not push away the name that belongs to it.
                    "icon-ignore-placement": True,
                },
            },
            ("peak",),
        )
        detail = ["get", "subclass"]
        huts = ["in", detail, ["literal", ["alpine_hut", "wilderness_hut"]]]
        add(
            "peak-name",
            {
                "id": "topo-poi",
                "type": "symbol",
                "source": "hiker",
                "source-layer": "poi",
                "minzoom": 12,
                "filter": [
                    "any",
                    huts,
                    ["==", detail, "viewpoint"],
                    ["in", cls, ["literal", ["shelter", "parking", "aerialway"]]],
                ],
                "layout": {
                    "icon-image": [
                        "case",
                        huts,
                        "hut",
                        ["==", detail, "viewpoint"],
                        "viewpoint",
                        ["==", cls, "shelter"],
                        "shelter",
                        ["==", cls, "parking"],
                        "parking",
                        "cable-car",
                    ],
                    "icon-size": ["interpolate", ["linear"], ["zoom"], 12, 0.7, 15, 0.95],
                    # Where signs would cover each other, huts are placed first.
                    "symbol-sort-key": ["case", huts, 0, 1],
                },
            },
            ("hut",),
        )
    hiker["bases"].append({"id": "topo", "show": show, "hide": hide})


SATELLITE_OPACITY = 0.7
# Deepest zoom level of the elevation tiles (see layers.TERRAIN).
TERRAIN_MAX_ZOOM = 15
OVERLAY_GROUPS = {
    "terrain": ("slope", "satellite"),
    "snow": ("avalanche", "snow", "snowdepth"),
    "weather": ("weather0", "weather1", "weather2", "precipitation"),
}


def build_style(
    tile_url: str,
    glyph_url: str,
    attribution: str,
    max_zoom: int,
    *,
    sprite_url: str | None = None,
    terrain_url: str | None = None,
    slope_url: str | None = None,
    satellite_url: str | None = None,
    contour_url: str | None = None,
    snow_url: str | None = None,
    precipitation_url: str | None = None,
    avalanche_url: str | None = None,
    weather_url: str | None = None,
    radar: dict | None = None,
    history_days: int = 0,
    attributions: dict[str, str] | None = None,
) -> dict:
    """The MapLibre style; the `*_url` arguments are URL templates.

    Layers that can be switched carry `visibility: none`; `metadata.hiker` tells the
    clients which layers belong to which choice, so that web and app offer the same.
    """
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
        # The difficulty of a path on the SAC hiking scale, where the data names it:
        # blue for hiking and mountain paths, yellow to red for mountain tours and alpine
        # routes, black for the hardest.
        _line(
            "path-difficulty",
            "hiking",
            ["has", "sac_scale"],
            {
                "line-color": [
                    "match",
                    ["get", "sac_scale"],
                    "hiking",
                    DIFFICULTY[0],
                    "mountain_hiking",
                    DIFFICULTY[1],
                    "demanding_mountain_hiking",
                    DIFFICULTY[2],
                    "alpine_hiking",
                    DIFFICULTY[3],
                    "demanding_alpine_hiking",
                    DIFFICULTY[4],
                    "difficult_alpine_hiking",
                    DIFFICULTY[5],
                    PATH,
                ],
                "line-width": _width((11, 0.9), (14, 1.8), (18, 4)),
            },
            minzoom=11,
        ),
        _line(
            "via-ferrata",
            "hiking",
            ["==", ["get", "highway"], "via_ferrata"],
            {
                "line-color": VIA_FERRATA,
                "line-width": _width((11, 1.0), (14, 2.2), (18, 4.5)),
                "line-dasharray": [1, 1.5],
            },
            minzoom=11,
            cap="butt",
        ),
        # Zoomed in closely the grade is written next to the path.
        _label(
            "path-difficulty-label",
            "hiking",
            ["any", ["has", "sac_scale"], ["==", ["get", "highway"], "via_ferrata"]],
            {
                "symbol-placement": "line",
                "text-field": [
                    "case",
                    ["==", ["get", "highway"], "via_ferrata"],
                    "KS",
                    [
                        "match",
                        ["get", "sac_scale"],
                        "hiking",
                        "T1",
                        "mountain_hiking",
                        "T2",
                        "demanding_mountain_hiking",
                        "T3",
                        "alpine_hiking",
                        "T4",
                        "demanding_alpine_hiking",
                        "T5",
                        "difficult_alpine_hiking",
                        "T6",
                        "",
                    ],
                ],
                "text-font": BOLD,
                "text-size": 11,
                # Beside the line, not on it, and often enough to be seen on a short piece.
                "text-offset": [0, 0.9],
                "symbol-spacing": 220,
                "text-keep-upright": True,
            },
            {
                "text-color": [
                    "case",
                    ["==", ["get", "highway"], "via_ferrata"],
                    VIA_FERRATA,
                    [
                        "match",
                        ["get", "sac_scale"],
                        "hiking",
                        "#1479c4",
                        "mountain_hiking",
                        DIFFICULTY[1],
                        "demanding_mountain_hiking",
                        "#8a6d00",
                        "alpine_hiking",
                        "#b55f00",
                        "demanding_alpine_hiking",
                        DIFFICULTY[4],
                        DIFFICULTY[5],
                    ],
                ],
                "text-halo-width": 1.8,
            },
            minzoom=15,
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
            # The layer also holds ridges and cliffs as lines: only points are summits.
            "filter": ["==", ["geometry-type"], "Point"],
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
            ["all", ["has", "name"], ["==", ["geometry-type"], "Point"]],
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
    notes = attributions or {}
    sources: dict[str, dict] = {
        "hiker": {
            "type": "vector",
            "tiles": [tile_url],
            "minzoom": 0,
            "maxzoom": max_zoom,
            "attribution": attribution,
        }
    }
    hiker: dict = {
        "bases": [{"id": "map", "show": [], "hide": []}],
        "overlays": [],
        # What the colours of the paths mean.
        "legend": [
            *(
                {"label": f"T{level + 1}", "color": colour}
                for level, colour in enumerate(DIFFICULTY)
            ),
            {"label": "KS", "color": VIA_FERRATA},
        ],
    }

    def insert_before(layer_id: str, layer: dict) -> None:
        layers.insert(next(i for i, item in enumerate(layers) if item["id"] == layer_id), layer)

    if terrain_url:
        dem = {
            "type": "raster-dem",
            "tiles": [terrain_url],
            "tileSize": 256,
            "encoding": "terrarium",
            # As fine as the data has it: sharper ridges and faces in the shading and in
            # the 3D view, instead of the rounded shapes of coarser tiles.
            "maxzoom": TERRAIN_MAX_ZOOM,
            "attribution": notes.get("terrain", ""),
        }
        # Two sources of the same tiles: one shades the map, one lifts it in the 3D view.
        sources["terrain"] = dem
        sources["terrain-3d"] = dict(dem)
        insert_before(
            "waterway",
            {
                "id": "hillshade",
                "type": "hillshade",
                "source": "terrain",
                "paint": {
                    "hillshade-exaggeration": 0.45,
                    "hillshade-shadow-color": "#3d3a34",
                    "hillshade-highlight-color": "#ffffff",
                    "hillshade-accent-color": "#5a554c",
                },
            },
        )
        hiker["terrain"] = {"source": "terrain-3d", "exaggeration": 1.3}
        # Winter: snow on the ground. A white veil over the drawn land; the shading above
        # it keeps the relief, and water, paths and names stay as they are.
        insert_before(
            "hillshade",
            {
                "id": "winter-snow",
                "type": "background",
                "layout": {"visibility": "none"},
                "paint": {"background-color": "#ffffff", "background-opacity": 0.78},
            },
        )
        hiker["bases"].append({"id": "winter", "show": ["winter-snow"], "hide": []})
    if contour_url:
        sources["contours"] = {
            "type": "vector",
            "tiles": [contour_url],
            "minzoom": 9,
            "maxzoom": 13,
            "attribution": notes.get("terrain", ""),
        }
        insert_before(
            "waterway",
            {
                "id": "contour",
                "type": "line",
                "source": "contours",
                "source-layer": "contour",
                "minzoom": 11,
                "paint": {
                    "line-color": "#8a5a2b",
                    "line-opacity": ["case", ["==", ["get", "index"], 1], 0.65, 0.35],
                    "line-width": ["case", ["==", ["get", "index"], 1], 1.1, 0.6],
                },
            },
        )
        layers.append(
            {
                "id": "contour-label",
                "type": "symbol",
                "source": "contours",
                "source-layer": "contour",
                "minzoom": 12,
                "filter": ["==", ["get", "index"], 1],
                "layout": {
                    "symbol-placement": "line",
                    "text-field": ["to-string", ["get", "ele"]],
                    "text-font": REGULAR,
                    "text-size": 10,
                    "symbol-spacing": 350,
                },
                "paint": {
                    "text-color": "#7a4f26",
                    "text-halo-color": HALO,
                    "text-halo-width": 1.2,
                },
            }
        )
    if slope_url:
        sources["slope"] = {
            "type": "raster",
            "tiles": [slope_url],
            "tileSize": 256,
            "minzoom": 9,
            "maxzoom": 14,
            "attribution": notes.get("terrain", ""),
        }
        insert_before(
            "tunnel",
            {
                "id": "slope",
                "type": "raster",
                "source": "slope",
                "minzoom": 9,
                "layout": {"visibility": "none"},
                "paint": {"raster-opacity": 0.75, "raster-fade-duration": 0},
            },
        )
        hiker["overlays"].append(
            {
                "id": "slope",
                "layers": ["slope"],
                # Angle in degrees and colour of every class, for the legend.
                "legend": [
                    {"from": 15, "color": "#50af8c"},
                    {"from": 20, "color": "#82c86e"},
                    {"from": 25, "color": "#bedc5a"},
                    {"from": 30, "color": "#f5d73c"},
                    {"from": 35, "color": "#f0821e"},
                    {"from": 40, "color": "#c82828"},
                    {"from": 45, "color": "#7c3aad"},
                ],
                # The user chooses from and up to which angle slopes are coloured: the
                # clients add `?low=…&high=…` to the tiles of the source.
                "range": {
                    "source": "slope",
                    "min": 15,
                    "max": 60,
                    "step": 5,
                    "low": 30,
                    "high": 90,
                },
            }
        )
    # Snow cover and precipitation: coarse satellite products, drawn over the ground.
    for name, url, max_zoom in (("snow", snow_url, 8), ("precipitation", precipitation_url, 6)):
        if not url:
            continue
        sources[name] = {
            "type": "raster",
            "tiles": [url],
            "tileSize": 256,
            "maxzoom": max_zoom,
            "attribution": notes.get(name, ""),
        }
        insert_before(
            "tunnel",
            {
                "id": name,
                "type": "raster",
                "source": name,
                "layout": {"visibility": "none"},
                "paint": {"raster-opacity": 0.65, "raster-fade-duration": 0},
            },
        )
        hiker["overlays"].append({"id": name, "layers": [name]})
    if avalanche_url:
        # The colours of the European avalanche danger scale, levels 1 to 5.
        colours = ["#ccff66", "#ffff00", "#ff9900", "#ff0000", "#000000"]
        sources["avalanche"] = {
            "type": "geojson",
            "data": avalanche_url,
            "attribution": notes.get("avalanche", ""),
        }
        level = ["get", "danger"]
        insert_before(
            "tunnel",
            {
                "id": "avalanche",
                "type": "fill",
                "source": "avalanche",
                "layout": {"visibility": "none"},
                "paint": {
                    "fill-color": [
                        "match",
                        level,
                        1,
                        colours[0],
                        2,
                        colours[1],
                        3,
                        colours[2],
                        4,
                        colours[3],
                        colours[4],
                    ],
                    "fill-opacity": 0.4,
                },
            },
        )
        insert_before(
            "tunnel",
            {
                "id": "avalanche-outline",
                "type": "line",
                "source": "avalanche",
                "layout": {"visibility": "none"},
                "paint": {"line-color": "#5a5a5a", "line-width": 0.8, "line-opacity": 0.7},
            },
        )
        hiker["overlays"].append(
            {
                "id": "avalanche",
                "layers": ["avalanche", "avalanche-outline"],
                "legend": [
                    {"level": index + 1, "color": colour} for index, colour in enumerate(colours)
                ],
            }
        )
    if weather_url:
        sources["weather"] = {
            "type": "vector",
            "tiles": [weather_url],
            "minzoom": 8,
            "maxzoom": 10,
            "attribution": notes.get("weather", ""),
        }

        def forecast_layer(layer_id: str, field: str, colour: str) -> dict:
            return {
                "id": layer_id,
                "type": "symbol",
                "source": "weather",
                "source-layer": "weather",
                "minzoom": 8,
                "filter": ["has", field],
                "layout": {
                    "visibility": "none",
                    "text-field": ["get", field],
                    "text-font": BOLD,
                    "text-size": 12,
                    "text-max-width": 12,
                    # The forecast matters more than the names beneath it.
                    "text-allow-overlap": True,
                },
                "paint": {
                    "text-color": colour,
                    "text-halo-color": "rgba(255, 255, 255, 0.92)",
                    "text-halo-width": 2,
                },
            }

        for day in range(3):
            layers.append(forecast_layer(f"weather-{day}", f"day{day}", "#14315c"))
            hiker["overlays"].append({"id": f"weather{day}", "layers": [f"weather-{day}"]})
        layers.append(forecast_layer("snow-depth", "snow", "#0b6fa4"))
        hiker["overlays"].append({"id": "snowdepth", "layers": ["snow-depth"]})
    if satellite_url:
        sources["satellite"] = {
            "type": "raster",
            "tiles": [satellite_url],
            "tileSize": 256,
            "maxzoom": 19,
            "attribution": notes.get("satellite", ""),
        }
        # The aerial image lies over the drawn ground and under water lines, paths and
        # names. The user chooses how much of the map shines through.
        insert_before(
            "waterway",
            {
                "id": "satellite",
                "type": "raster",
                "source": "satellite",
                "layout": {"visibility": "none"},
                "paint": {"raster-opacity": SATELLITE_OPACITY, "raster-fade-duration": 0},
            },
        )
        hiker["overlays"].append(
            {
                "id": "satellite",
                "layers": ["satellite"],
                "opacity": {"layer": "satellite", "default": SATELLITE_OPACITY, "min": 0.1},
            }
        )
    _add_topo_look(layers, hiker, insert_before, symbols=sprite_url is not None)
    # The order and the groups in which the clients offer the overlays: what belongs to
    # the ground, then everything about snow, then the weather.
    for overlay in hiker["overlays"]:
        overlay["group"] = next(
            group for group, members in OVERLAY_GROUPS.items() if overlay["id"] in members
        )
    order = [name for members in OVERLAY_GROUPS.values() for name in members]
    hiker["overlays"].sort(key=lambda overlay: order.index(overlay["id"]))
    # Layers that also show a day in the past: the clients add `?date=YYYY-MM-DD` to the
    # addresses of these sources.
    dated = [name for name in ("avalanche", "snow", "weather") if name in sources]
    if dated and history_days:
        hiker["history"] = {"sources": dated, "days": history_days}
    if radar:
        # Rain radar and clouds change every few minutes: the clients ask `frames` for
        # the times and build the layers themselves from the addresses with {time}.
        hiker["radar"] = radar | {"attribution": notes.get("radar", "")}
    return {
        "version": 8,
        "name": "hiker",
        "glyphs": glyph_url,
        **({"sprite": sprite_url} if sprite_url else {}),
        "metadata": {"hiker": hiker},
        "sources": sources,
        "layers": layers,
    }
