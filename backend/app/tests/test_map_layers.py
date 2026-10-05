import gzip
import io
import math
from datetime import UTC, date, datetime, timedelta

import httpx2
import pytest
from PIL import Image

from app.core.config import get_settings
from app.modules.maps.avalanche import Avalanche, AvalancheSourceError, _thin, get_avalanche
from app.modules.maps.contours import _grid, contour_tile, interval_for, trace
from app.modules.maps.layers import (
    SATELLITE,
    SNOW,
    DatedTileSource,
    Layers,
    Provider,
    _Composite,
    get_layers,
    slope_tile,
    tile_center,
)
from app.modules.maps.radar import (
    HttpRadarSource,
    Radar,
    RadarUnavailableError,
    get_radar,
)
from app.modules.maps.style import build_style
from app.modules.maps.tiles import FetchedTile, TileSourceError
from app.modules.maps.weather import (
    ForecastSourceError,
    OpenMeteoForecast,
    day_label,
    get_forecast_source,
    places_of,
    weather_tile,
    word_for,
)
from app.tests.test_vector_maps import write_map

SIZE = 64


def terrain_png(elevation) -> bytes:
    """An elevation tile in Terrarium encoding; `elevation(column, row)` in metres."""
    image = Image.new("RGB", (SIZE, SIZE))
    for row in range(SIZE):
        for column in range(SIZE):
            value = elevation(column, row) + 32768
            image.putpixel(
                (column, row), (int(value) // 256, int(value) % 256, int(value % 1 * 256))
            )
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class FakeSource:
    def __init__(self, data: bytes | None = b"x" * 2000):
        self.data = data
        self.calls: list[tuple] = []
        self.fail = False

    def fetch(self, z, x, y, etag):
        self.calls.append((z, x, y))
        if self.fail:
            raise TileSourceError("unreachable")
        return None if self.data is None else FetchedTile(self.data, None)


# --- Slope ---


def metres_per_pixel(z: int, y: int) -> float:
    return 40075016.686 * math.cos(math.radians(tile_center(z, 0, y)[0])) / 2**z / SIZE


def test_flat_and_gentle_ground_stays_transparent():
    z, y = 12, 1436
    gentle = metres_per_pixel(z, y) * 0.4  # 22°
    for surface in (lambda c, r: 1500, lambda c, r: 1500 + c * gentle):
        image = Image.open(io.BytesIO(slope_tile(terrain_png(surface), z, y)))
        assert image.mode == "RGBA" and image.size == (SIZE, SIZE)
        assert image.getextrema()[3] == (0, 0)


@pytest.mark.parametrize(
    ("tangent", "colour"),
    [
        (0.62, (245, 215, 60)),  # 32°: yellow
        (0.77, (240, 130, 30)),  # 37.6°: orange
        (0.90, (200, 40, 40)),  # 42°: red
        (1.20, (124, 58, 173)),  # 50°: purple
    ],
)
def test_steep_slopes_are_coloured_by_class(tangent, colour):
    z, y = 12, 1436
    rise = metres_per_pixel(z, y) * tangent

    # The same steepness whichever way the slope faces.
    for surface in (lambda c, r: 1000 + c * rise, lambda c, r: 3000 - r * rise):
        image = Image.open(io.BytesIO(slope_tile(terrain_png(surface), z, y)))
        pixel = image.getpixel((SIZE // 2, SIZE // 2))
        assert pixel[:3] == colour and pixel[3] > 100
        # Also at the edge, where only one neighbour exists.
        assert image.getpixel((0, 0))[:3] == colour


# --- Providers ---


def test_aerial_images_come_from_the_first_provider_that_has_one():
    swiss, austria, world = FakeSource(), FakeSource(), FakeSource()
    composite = _Composite(list(zip(SATELLITE, (swiss, austria, world), strict=True)))

    # Säntis: Switzerland.
    assert composite.fetch(10, 538, 359, None).data == swiss.data
    assert (austria.calls, world.calls) == ([], [])
    # Vienna: only Austria and the world cover it.
    composite.fetch(10, 558, 355, None)
    assert len(austria.calls) == 1 and world.calls == []
    # Rome: the global source.
    composite.fetch(10, 547, 380, None)
    assert len(world.calls) == 1

    # Inside the Swiss rectangle but outside the country the image is blank: next one.
    swiss.data = b"blank"
    assert composite.fetch(10, 538, 359, "etag").data == world.data
    # Deeper than the global source goes: nothing; the map enlarges what it has.
    assert composite.fetch(17, 70050, 48700, None) is None

    swiss.fail = world.fail = True
    with pytest.raises(TileSourceError):
        composite.fetch(10, 538, 359, None)


def test_providers_name_their_licence():
    for provider in SATELLITE:
        assert isinstance(provider, Provider)
        assert provider.attribution and provider.licence
        assert provider.url.startswith("https://")


# --- Endpoints ---


@pytest.fixture
def layers(client, tmp_path):
    terrain = FakeSource(terrain_png(lambda c, r: 1000 + c * 150))
    satellite = FakeSource(b"\xff\xd8" + b"j" * 3000)
    fake = Layers(
        str(tmp_path / "tiles"), 14, 10_000_000, {"terrain": terrain, "satellite": satellite}
    )
    client.app.dependency_overrides[get_layers] = lambda: fake
    return {"terrain": terrain, "satellite": satellite}


def test_raster_layers_are_cached_and_served_without_login(client, layers):
    first = client.get("/api/v1/maps/raster/terrain/12/2153/1436")
    assert first.status_code == 200 and first.headers["content-type"] == "image/png"
    assert "max-age=604800" in first.headers["cache-control"]
    client.get("/api/v1/maps/raster/terrain/12/2153/1436")
    assert layers["terrain"].calls == [(12, 2153, 1436)]

    image = client.get("/api/v1/maps/raster/satellite/12/2153/1436")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"

    assert client.get("/api/v1/maps/raster/other/12/1/1").status_code == 422
    assert client.get("/api/v1/maps/raster/terrain/2/9/9").status_code == 404


def test_slope_tiles_are_computed_once_from_the_elevation(client, layers):
    first = client.get("/api/v1/maps/slope/12/2153/1436.png")

    assert first.status_code == 200 and first.headers["content-type"] == "image/png"
    image = Image.open(io.BytesIO(first.content))
    # 150 m per pixel of this small tile is steep.
    assert image.getpixel((30, 30))[3] > 100

    again = client.get("/api/v1/maps/slope/12/2153/1436.png")
    assert again.content == first.content
    assert layers["terrain"].calls == [(12, 2153, 1436)]

    # Stored elevation tiles survive an outage of the source; unknown ones do not.
    layers["terrain"].fail = True
    assert client.get("/api/v1/maps/slope/12/2153/1436.png").status_code == 200
    assert client.get("/api/v1/maps/slope/12/2153/1437.png").status_code == 502
    assert client.get("/api/v1/maps/slope/5/1/1.png").status_code == 422


def test_without_elevation_source_there_is_no_slope(client, tmp_path):
    client.app.dependency_overrides[get_layers] = lambda: Layers(str(tmp_path), 14, 1000, {})

    assert client.get("/api/v1/maps/slope/12/2153/1436.png").status_code == 404
    assert client.get("/api/v1/maps/raster/terrain/12/2153/1436").status_code == 404


# --- Style ---


def test_style_offers_the_layers_the_server_has(client, layers, tmp_path, monkeypatch):
    monkeypatch.setenv("MAP_DATA_PATH", str(tmp_path))
    get_settings.cache_clear()
    write_map(tmp_path / "alps.mbtiles")

    style = client.get("/api/v1/maps/style.json").json()

    base = "http://testserver/api/v1/maps"
    assert style["sources"]["terrain"]["tiles"] == [f"{base}/raster/terrain/{{z}}/{{x}}/{{y}}"]
    assert style["sources"]["terrain"]["encoding"] == "terrarium"
    assert style["sources"]["slope"]["tiles"] == [f"{base}/slope/{{z}}/{{x}}/{{y}}.png"]
    assert style["sources"]["satellite"]["tiles"] == [f"{base}/raster/satellite/{{z}}/{{x}}/{{y}}"]
    assert "swisstopo" in style["sources"]["satellite"]["attribution"]
    hiker = style["metadata"]["hiker"]
    assert [entry["id"] for entry in hiker["bases"]] == ["map", "winter"]
    assert style["sources"]["contours"]["tiles"] == [f"{base}/contours/{{z}}/{{x}}/{{y}}.pbf"]
    # In the order the clients offer them: the ground, then snow, then the weather.
    assert [(entry["id"], entry["group"]) for entry in hiker["overlays"]] == [
        ("slope", "terrain"),
        ("satellite", "terrain"),
        ("avalanche", "snow"),
        ("snowdepth", "snow"),
        ("weather0", "weather"),
        ("weather1", "weather"),
        ("weather2", "weather"),
    ]
    assert style["sources"]["avalanche"] == {
        "type": "geojson",
        "data": f"{base}/avalanche.geojson",
        "attribution": style["sources"]["avalanche"]["attribution"],
    }
    assert "avalanche.report" in style["sources"]["avalanche"]["attribution"]
    assert hiker["terrain"] == {"source": "terrain-3d", "exaggeration": 1.3}
    # Shading and 3D view take the elevation as fine as the tiles have it: sharper ridges.
    assert style["sources"]["terrain-3d"]["maxzoom"] == 15
    assert style["sources"]["terrain"]["maxzoom"] == 15


def test_switchable_layers_start_hidden_and_keep_their_place():
    style = build_style(
        "t",
        "g",
        "©",
        14,
        terrain_url="dem",
        slope_url="slope",
        satellite_url="sat",
        contour_url="contours",
    )
    order = [layer["id"] for layer in style["layers"]]
    layers = {layer["id"]: layer for layer in style["layers"]}
    hiker = style["metadata"]["hiker"]

    # Shading lies on the ground and under water, roads and names.
    assert order.index("wood") < order.index("hillshade") < order.index("waterway")
    assert order.index("hillshade") < order.index("slope") < order.index("path")
    # The aerial image is laid over the ground, under water lines, slope, paths and names.
    assert order.index("hillshade") < order.index("satellite") < order.index("waterway")
    assert order.index("satellite") < order.index("slope")
    assert layers["satellite"]["paint"]["raster-opacity"] == 0.7
    assert layers["slope"]["layout"]["visibility"] == "none"
    assert layers["satellite"]["layout"]["visibility"] == "none"
    assert "visibility" not in layers["hillshade"].get("layout", {})

    # Winter is a white veil under the shading; contour lines lie on the ground too.
    assert order.index("wood") < order.index("winter-snow") < order.index("hillshade")
    assert layers["winter-snow"]["layout"]["visibility"] == "none"
    assert hiker["bases"][1] == {"id": "winter", "show": ["winter-snow"], "hide": []}
    assert order.index("hillshade") < order.index("contour") < order.index("waterway")
    assert layers["contour"]["source-layer"] == "contour"
    assert layers["contour-label"]["filter"] == ["==", ["get", "index"], 1]
    # The user chooses how much of the map shines through the aerial image.
    assert [base["id"] for base in hiker["bases"]] == ["map", "winter"]
    assert hiker["overlays"][1] == {
        "id": "satellite",
        "layers": ["satellite"],
        "opacity": {"layer": "satellite", "default": 0.7, "min": 0.1},
        "group": "terrain",
    }
    legend = [entry["from"] for entry in hiker["overlays"][0]["legend"]]
    assert legend == [15, 20, 25, 30, 35, 40, 45]
    assert (
        hiker["overlays"][0]["range"]["low"] == 30 and hiker["overlays"][0]["range"]["high"] == 90
    )

    plain = build_style("t", "g", "©", 14)
    assert set(plain["sources"]) == {"hiker"}
    assert plain["metadata"]["hiker"]["bases"] == [{"id": "map", "show": [], "hide": []}]
    assert plain["metadata"]["hiker"]["overlays"] == []


# --- Contour lines ---


def read_varint(data: bytes, at: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = data[at]
        value |= (byte & 0x7F) << shift
        at += 1
        if not byte & 0x80:
            return value, at
        shift += 7


def read_message(data: bytes) -> list[tuple[int, object]]:
    """The fields of a protobuf message: (number, int or bytes)."""
    fields, at = [], 0
    while at < len(data):
        key, at = read_varint(data, at)
        if key & 7 == 0:
            value, at = read_varint(data, at)
        else:
            length, at = read_varint(data, at)
            value, at = data[at : at + length], at + length
        fields.append((key >> 3, value))
    return fields


def read_contours(tile: bytes) -> dict[int, dict]:
    """elevation → {"index": 0 or 1, "points": number of points} of a contour tile."""
    ((number, layer),) = read_message(gzip.decompress(tile))
    assert number == 3
    fields = read_message(layer)
    assert [value for key, value in fields if key == 1] == [b"contour"]
    assert [value for key, value in fields if key == 3] == [b"ele", b"index"]
    assert [value for key, value in fields if key == 5] == [4096]
    values = []
    for key, value in fields:
        if key == 4:
            ((kind, number),) = read_message(value)
            values.append((number >> 1) ^ -(number & 1) if kind == 6 else number)
    result = {}
    for key, value in fields:
        if key != 2:
            continue
        feature = dict(read_message(value))
        assert feature[3] == 2  # LINESTRING
        tags = feature[2]
        result[values[tags[1]]] = {"index": values[tags[3]], "bytes": len(feature[4])}
    return result


def test_contour_lines_follow_the_elevation():
    # A slope from 1000 m in the west to 1630 m in the east.
    tile = contour_tile(terrain_png(lambda c, r: 1000 + c * 10), 12)

    lines = read_contours(tile)

    # Every 50 m at zoom 12; every fifth line (250 m) is an index line.
    assert sorted(lines) == list(range(1050, 1650, 50))
    assert [level for level, line in lines.items() if line["index"]] == [1250, 1500]
    assert interval_for(13) == 20 and interval_for(9) == 200


def test_contour_lines_are_joined_and_reach_the_tile_edge():
    grid, count = _grid(terrain_png(lambda c, r: 1000 + c * 10))

    lines = trace(grid, count, 50)[1300]

    # One line from the top edge to the bottom edge, not hundreds of pieces.
    assert len(lines) == 1
    rows = [row for _column, row in lines[0]]
    assert min(rows) == 0 and max(rows) == count - 1
    assert {round(column, 3) for column, _row in lines[0]} == {15.0}


def test_flat_ground_has_no_contour_lines():
    assert read_contours(contour_tile(terrain_png(lambda c, r: 1234), 13)) == {}


def test_a_summit_gets_closed_rings():
    def cone(column, row):
        return 2000 - 12 * math.hypot(column - 32, row - 32)

    grid, count = _grid(terrain_png(cone))
    rings = trace(grid, count, 100)[1900]

    assert len(rings) == 1
    first, last = rings[0][0], rings[0][-1]
    assert math.isclose(first[0], last[0]) and math.isclose(first[1], last[1])


def test_contour_tiles_are_computed_once_and_served_compressed(client, layers):
    first = client.get("/api/v1/maps/contours/12/2153/1436.pbf")

    assert first.status_code == 200
    assert first.headers["content-type"] == "application/x-protobuf"
    assert first.headers["content-encoding"] == "gzip"
    client.get("/api/v1/maps/contours/12/2153/1436.pbf")
    assert layers["terrain"].calls == [(12, 2153, 1436)]
    assert client.get("/api/v1/maps/contours/15/1/1.pbf").status_code == 422


# --- Snow, precipitation, avalanche danger ---


def test_weather_layers_are_overlays_that_start_hidden():
    style = build_style(
        "t", "g", "©", 14, snow_url="snow", precipitation_url="rain", avalanche_url="danger"
    )
    layers = {layer["id"]: layer for layer in style["layers"]}
    overlays = {entry["id"]: entry for entry in style["metadata"]["hiker"]["overlays"]}

    assert set(overlays) == {"snow", "precipitation", "avalanche"}
    for name in ("snow", "precipitation", "avalanche", "avalanche-outline"):
        assert layers[name]["layout"]["visibility"] == "none"
    assert style["sources"]["snow"]["maxzoom"] == 8
    assert style["sources"]["precipitation"]["maxzoom"] == 6
    assert overlays["avalanche"]["layers"] == ["avalanche", "avalanche-outline"]
    # The colours of the European danger scale, one per level.
    assert [entry["level"] for entry in overlays["avalanche"]["legend"]] == [1, 2, 3, 4, 5]
    assert overlays["avalanche"]["legend"][2]["color"] == "#ff9900"


def test_snow_tiles_are_kept_only_for_hours(client, tmp_path):
    snow = FakeSource(b"\x89PNG" + b"s" * 2000)
    client.app.dependency_overrides[get_layers] = lambda: Layers(
        str(tmp_path), 14, 10_000_000, {"snow": snow}
    )

    response = client.get("/api/v1/maps/raster/snow/7/67/44")

    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert "max-age=1800" in response.headers["cache-control"]
    assert client.get("/api/v1/maps/raster/precipitation/5/16/11").status_code == 404


def test_snow_cover_is_asked_for_by_day():
    asked = []

    def handler(request):
        asked.append(str(request.url))
        return httpx2.Response(200, content=b"png", headers={"content-type": "image/png"})

    source = DatedTileSource(
        SNOW.url, "hiker-test", "http://testserver", transport=httpx2.MockTransport(handler)
    )

    assert source.fetch(7, 67, 44, "old-etag").data == b"png"

    yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    assert f"/default/{yesterday}/GoogleMapsCompatible_Level8/7/44/67.png" in asked[0]


SQUARE = [[9.0, 47.0], [9.1, 47.0], [9.1, 47.1], [9.0, 47.1], [9.0, 47.0]]


class FakeAvalancheSource:
    def __init__(self):
        self.rating_calls = 0
        self.region_calls: list[str] = []
        self.fail = False
        self.levels = {"CH-1111": 3, "CH-1111:high": 3, "CH-1111:low": 2, "AT-07-01": 4}

    def ratings(self, day):
        self.rating_calls += 1
        if self.fail:
            raise AvalancheSourceError("unreachable")
        return self.levels

    def regions(self, area):
        self.region_calls.append(area)
        names = {"CH": ["CH-1111", "CH-2222"], "AT-07": ["AT-07-01", "AT-07-99"]}.get(area, [])
        features = [
            {
                "type": "Feature",
                # AT-07-99 was replaced by a newer region.
                "properties": {
                    "id": name,
                    "end_date": "2023-01-01" if name == "AT-07-99" else None,
                },
                "geometry": {"type": "Polygon", "coordinates": [SQUARE]},
            }
            for name in names
        ]
        return {"type": "FeatureCollection", "features": features}


def test_avalanche_layer_shows_the_danger_level_of_today(tmp_path):
    source = FakeAvalancheSource()
    layer = Avalanche(source, str(tmp_path))

    data = layer.geojson(date(2026, 2, 1))

    assert data["date"] == "2026-02-01" and "avalanche.report" in data["attribution"]
    regions = {feature["properties"]["id"]: feature for feature in data["features"]}
    # Only regions with a bulletin today; regions that no longer exist are left out.
    assert set(regions) == {"CH-1111", "AT-07-01"}
    assert regions["CH-1111"]["properties"] == {
        "id": "CH-1111",
        "danger": 3,
        "danger_high": 3,
        "danger_low": 2,
        "date": "2026-02-01",
    }
    assert regions["AT-07-01"]["properties"]["danger_low"] == 4
    assert regions["CH-1111"]["geometry"]["type"] == "MultiPolygon"

    # Kept for a while: neither the levels nor the outlines are fetched again.
    calls = len(source.region_calls)
    layer.geojson(date(2026, 2, 1))
    assert source.rating_calls == 1 and len(source.region_calls) == calls
    # Another day asks again; the outlines come from the files kept here.
    layer.geojson(date(2026, 2, 2))
    assert source.rating_calls == 2 and len(source.region_calls) == calls


def test_avalanche_layer_survives_missing_data(tmp_path):
    source = FakeAvalancheSource()
    layer = Avalanche(source, str(tmp_path))
    source.fail = True
    # No answer and nothing kept: an empty layer, not an error.
    assert layer.geojson(date(2026, 2, 1))["features"] == []

    source.fail = False
    source.levels = {}
    # Out of season nobody publishes: no region is coloured and none is fetched.
    assert layer.geojson(date(2026, 8, 1))["features"] == []
    assert source.region_calls == []


def test_outlines_are_thinned_but_keep_their_shape():
    # A square with many points along its edges.
    edge = [[9 + i / 1000, 47.0] for i in range(101)]
    ring = edge + [[9.1, 47.1], [9.0, 47.1], [9.0, 47.0]]

    thinned = _thin(ring, 0.0015)

    assert thinned == [[9.0, 47.0], [9.1, 47.0], [9.1, 47.1], [9.0, 47.1], [9.0, 47.0]]
    assert _thin(SQUARE, 0.0015) == SQUARE


def test_avalanche_endpoint(client, tmp_path):
    client.app.dependency_overrides[get_avalanche] = lambda: Avalanche(
        FakeAvalancheSource(), str(tmp_path)
    )
    response = client.get("/api/v1/maps/avalanche.geojson")
    assert response.status_code == 200 and "max-age=1800" in response.headers["cache-control"]
    assert len(response.json()["features"]) == 2

    client.app.dependency_overrides[get_avalanche] = lambda: None
    assert client.get("/api/v1/maps/avalanche.geojson").status_code == 404


# --- Weather forecast and snow depth ---


class FakeForecast:
    def __init__(self):
        self.calls: list[int] = []
        self.days: list = []
        self.fail = False

    def forecast(self, places, day=None):
        self.calls.append(len(places))
        self.days.append(day)
        if self.fail:
            raise ForecastSourceError("unreachable")
        hours = [f"2026-02-01T{hour:02d}:00" for hour in range(24)]
        return [
            {
                "daily": {
                    "weather_code": [71, 3, 0],
                    "temperature_2m_max": [-2.4, 1.2, 4.0],
                    "temperature_2m_min": [-9.1, -6.0, -3.6],
                    "precipitation_sum": [14.0, 0.4, 0.0],
                    "snowfall_sum": [15.2, 0.0, 0.0],
                },
                # More snow in the north of the tile.
                "hourly": {"time": hours, "snow_depth": [0.87 if lat > 47.2 else 0.0] * 24},
            }
            for lat, _lon in places
        ]


def test_forecast_labels_are_short_and_readable():
    daily = FakeForecast().forecast([(47.0, 9.0)])[0]["daily"]

    assert day_label(daily, 0) == "Schnee\n-2°/-9° · 15 cm neu"
    # Less than a millimetre is not worth a number.
    assert day_label(daily, 1) == "bedeckt\n1°/-6°"
    assert day_label(daily, 2) == "sonnig\n4°/-4°"
    assert day_label({"temperature_2m_max": [None]}, 0) is None
    assert day_label({}, 0) is None
    rain = {**daily, "snowfall_sum": [0, 0, 0], "weather_code": [63, 3, 0]}
    assert day_label(rain, 0) == "Regen\n-2°/-9° · 14 mm"
    assert word_for(95) == "Gewitter" and word_for(1234) == ""


def test_weather_tile_holds_a_grid_of_places():
    source = FakeForecast()
    now = datetime(2026, 2, 1, 12, 30, tzinfo=UTC)

    tile = weather_tile(source, 9, 269, 179, now)

    assert source.calls == [9]
    places = places_of(9, 269, 179)
    assert len(places) == 9 and {px for _, _, px, _ in places} == {683, 2048, 3413}
    ((number, layer),) = read_message(gzip.decompress(tile))
    assert number == 3
    fields = read_message(layer)
    assert [value for key, value in fields if key == 1] == [b"weather"]
    keys = [value.decode() for key, value in fields if key == 3]
    values = [read_message(value)[0][1].decode() for key, value in fields if key == 4]
    features = [dict(read_message(value)) for key, value in fields if key == 2]
    assert len(features) == 9 and all(feature[3] == 1 for feature in features)  # POINT
    assert keys == ["day0", "day1", "day2", "snow"]
    assert "Schnee\n-2°/-9° · 15 cm neu" in values and "87 cm" in values
    # Snow depth only where snow lies: the northern places of the tile.
    with_snow = [feature for feature in features if len(feature[2]) == 8]
    assert 0 < len(with_snow) < 9


def test_weather_tiles_are_kept_and_survive_an_outage(client, layers):
    source = FakeForecast()
    client.app.dependency_overrides[get_forecast_source] = lambda: source

    first = client.get("/api/v1/maps/weather/9/269/179.pbf")
    assert first.status_code == 200 and first.headers["content-encoding"] == "gzip"
    assert "max-age=3600" in first.headers["cache-control"]
    client.get("/api/v1/maps/weather/9/269/179.pbf")
    assert source.calls == [9]

    source.fail = True
    assert client.get("/api/v1/maps/weather/9/269/180.pbf").status_code == 502
    assert client.get("/api/v1/maps/weather/9/269/179.pbf").status_code == 200
    assert client.get("/api/v1/maps/weather/12/1/1.pbf").status_code == 422

    client.app.dependency_overrides[get_forecast_source] = lambda: None
    assert client.get("/api/v1/maps/weather/9/269/179.pbf").status_code == 404


def test_forecast_days_and_snow_depth_are_overlays():
    style = build_style("t", "g", "©", 14, weather_url="weather")
    layers = {layer["id"]: layer for layer in style["layers"]}
    overlays = {entry["id"]: entry["layers"] for entry in style["metadata"]["hiker"]["overlays"]}

    assert overlays == {
        "weather0": ["weather-0"],
        "weather1": ["weather-1"],
        "weather2": ["weather-2"],
        "snowdepth": ["snow-depth"],
    }
    assert layers["weather-1"]["layout"]["text-field"] == ["get", "day1"]
    assert layers["snow-depth"]["filter"] == ["has", "snow"]
    assert all(
        layers[name]["layout"]["visibility"] == "none"
        for name in ("weather-0", "weather-1", "weather-2", "snow-depth")
    )
    assert style["sources"]["weather"]["maxzoom"] == 10


# --- Slope between two angles ---


def test_slope_is_coloured_only_between_the_chosen_angles():
    z, y = 12, 1436
    per_pixel = metres_per_pixel(z, y)

    def shade(tangent, low, high):
        surface = terrain_png(lambda c, r: 1000 + c * per_pixel * tangent)
        image = Image.open(io.BytesIO(slope_tile(surface, z, y, low, high)))
        return image.getpixel((SIZE // 2, SIZE // 2))

    # 22° is clear by default, green when gentle slopes are asked for.
    assert shade(0.4, 30, 90)[3] == 0
    assert shade(0.4, 20, 90)[:3] == (130, 200, 110)
    # 42° is red, but clear when only slopes up to 40° are wanted.
    assert shade(0.9, 30, 90)[:3] == (200, 40, 40)
    assert shade(0.9, 30, 40)[3] == 0
    # The lowest class starts exactly at the chosen angle: 31.8° is clear from 33°, not from 31°.
    assert shade(0.62, 33, 90)[3] == 0 and shade(0.62, 31, 90)[3] > 0


def test_slope_endpoint_takes_the_range(client, layers):
    usual = client.get("/api/v1/maps/slope/12/2153/1436.png")
    narrow = client.get("/api/v1/maps/slope/12/2153/1436.png", params={"low": 45, "high": 50})
    assert usual.status_code == narrow.status_code == 200
    assert usual.content != narrow.content
    wrong = client.get("/api/v1/maps/slope/12/2153/1436.png", params={"low": 40, "high": 35})
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "invalid_range"
    assert client.get("/api/v1/maps/slope/12/2153/1436.png", params={"low": 5}).status_code == 422


# --- A day in the past ---


def test_layers_with_history_take_a_date(client, layers, tmp_path):
    source = FakeAvalancheSource()
    client.app.dependency_overrides[get_avalanche] = lambda: Avalanche(source, str(tmp_path))
    forecast = FakeForecast()
    client.app.dependency_overrides[get_forecast_source] = lambda: forecast
    past = (datetime.now(UTC) - timedelta(days=200)).date().isoformat()

    danger = client.get("/api/v1/maps/avalanche.geojson", params={"date": past})
    assert danger.status_code == 200 and danger.json()["date"] == past
    assert "max-age=86400" in danger.headers["cache-control"]

    tile = client.get("/api/v1/maps/weather/9/269/179.pbf", params={"date": past})
    assert tile.status_code == 200 and forecast.days == [date.fromisoformat(past)]
    # Today is not history; the future and the distant past are refused.
    today = datetime.now(UTC).date()
    client.get("/api/v1/maps/weather/9/269/179.pbf", params={"date": today.isoformat()})
    assert forecast.days[-1] is None
    for wrong in (today + timedelta(days=1), today - timedelta(days=500)):
        response = client.get("/api/v1/maps/avalanche.geojson", params={"date": wrong.isoformat()})
        assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_date"


def test_snow_cover_of_a_past_day_is_asked_for_by_that_day(tmp_path):
    asked = []

    def handler(request):
        asked.append(str(request.url))
        return httpx2.Response(200, content=b"png" * 700, headers={"content-type": "image/png"})

    snow = DatedTileSource(
        SNOW.url, "hiker-test", "http://testserver", transport=httpx2.MockTransport(handler)
    )
    cached = Layers(str(tmp_path), 14, 10_000_000, {"snow": snow})

    cached.raster("snow", 7, 67, 44, date(2026, 2, 1))
    cached.raster("snow", 7, 67, 44, date(2026, 2, 1))

    assert len(asked) == 1 and "/default/2026-02-01/" in asked[0]
    assert (tmp_path / "_layers" / "snow-2026-02-01" / "7" / "67" / "44.png").is_file()


def test_past_weather_asks_for_one_day_and_old_days_in_the_archive():
    asked = []

    def handler(request):
        asked.append(request.url)
        return httpx2.Response(200, json={"daily": {}, "hourly": {}})

    source = OpenMeteoForecast(
        "https://forecast.example/v1/forecast",
        "hiker-test",
        archive_url="https://archive.example/v1/archive",
        transport=httpx2.MockTransport(handler),
    )
    recent = datetime.now(UTC).date() - timedelta(days=10)
    old = datetime.now(UTC).date() - timedelta(days=300)

    source.forecast([(47.0, 9.0)])
    source.forecast([(47.0, 9.0)], recent)
    source.forecast([(47.0, 9.0)], old)

    assert asked[0].params["forecast_days"] == "3" and "start_date" not in asked[0].params
    assert asked[1].host == "forecast.example"
    assert asked[1].params["start_date"] == asked[1].params["end_date"] == recent.isoformat()
    assert asked[2].host == "archive.example" and asked[2].params["start_date"] == old.isoformat()


def test_style_names_the_layers_with_history_and_the_radar():
    style = build_style(
        "t",
        "g",
        "©",
        14,
        snow_url="snow",
        avalanche_url="danger",
        weather_url="weather",
        history_days=400,
        radar={"frames": "frames", "rain": "rain/{time}", "clouds": "clouds/{time}"},
    )
    hiker = style["metadata"]["hiker"]

    assert hiker["history"] == {"sources": ["avalanche", "snow", "weather"], "days": 400}
    assert hiker["radar"]["rain"] == "rain/{time}" and hiker["radar"]["frames"] == "frames"
    assert "history" not in build_style("t", "g", "©", 14)["metadata"]["hiker"]


# --- Rain radar and clouds ---


class FakeRadarSource:
    def __init__(self):
        self.frame_calls = 0
        self.tiles: list[tuple] = []
        self.fail = False

    def rain_frames(self):
        self.frame_calls += 1
        if self.fail:
            raise RadarUnavailableError("unreachable")
        return {1000: "/v2/radar/a", 1600: "/v2/radar/b"}

    def rain_tile(self, path, z, x, y):
        self.tiles.append(("rain", path, z, x, y))
        return b"rain"

    def cloud_tile(self, moment, z, x, y):
        self.tiles.append(("clouds", moment, z, x, y))
        return b"clouds"


def test_radar_frames_and_tiles(client):
    source = FakeRadarSource()
    radar = Radar(source)
    client.app.dependency_overrides[get_radar] = lambda: radar

    frames = client.get("/api/v1/maps/radar/frames").json()
    assert frames["rain"] == [1000, 1600] and "RainViewer" in frames["attribution"]
    # Cloud images every 15 minutes for two hours, ending half an hour ago.
    clouds = frames["clouds"]
    assert len(clouds) == 9 and all(b - a == 900 for a, b in zip(clouds, clouds[1:], strict=False))
    assert 1800 <= datetime.now(UTC).timestamp() - clouds[-1] < 2700

    rain = client.get("/api/v1/maps/radar/rain/1600/6/33/22.png")
    assert rain.status_code == 200 and rain.content == b"rain"
    assert "max-age=86400" in rain.headers["cache-control"]
    assert source.tiles[-1] == ("rain", "/v2/radar/b", 6, 33, 22)
    # The list of times is asked for once, not with every tile.
    assert source.frame_calls == 1
    assert client.get("/api/v1/maps/radar/rain/1234/6/33/22.png").status_code == 404

    cloud = client.get(f"/api/v1/maps/radar/clouds/{clouds[-1]}/6/33/22.png")
    assert cloud.status_code == 200 and cloud.content == b"clouds"
    assert source.tiles[-1][1] == datetime.fromtimestamp(clouds[-1], UTC)
    # Only times of the grid and of the last day.
    assert client.get(f"/api/v1/maps/radar/clouds/{clouds[-1] + 60}/6/33/22.png").status_code == 404
    assert client.get("/api/v1/maps/radar/clouds/900/6/33/22.png").status_code == 404

    client.app.dependency_overrides[get_radar] = lambda: None
    assert client.get("/api/v1/maps/radar/frames").status_code == 404


def test_radar_survives_an_outage_of_the_frame_list():
    source = FakeRadarSource()
    source.fail = True
    radar = Radar(source)

    assert radar.frames()["rain"] == [] and len(radar.frames()["clouds"]) == 9


def test_cloud_tiles_are_asked_for_by_area_and_time():
    asked = []

    def handler(request):
        asked.append(request.url)
        return httpx2.Response(200, content=b"png", headers={"content-type": "image/png"})

    source = HttpRadarSource("hiker-test", transport=httpx2.MockTransport(handler))
    source.cloud_tile(datetime(2026, 10, 4, 12, 15, tzinfo=UTC), 1, 1, 0)

    params = asked[0].params
    assert params["layers"] == "mtg_fd:ir105_hrfi" and params["time"] == "2026-10-04T12:15:00Z"
    west, south, east, north = (float(part) for part in params["bbox"].split(","))
    assert west == 0 and south == 0 and round(east) == round(north) == 20037508


def test_sun_for_a_place_needs_no_login_and_knows_the_summit(client):
    place = {"lat": 47.2494, "lon": 9.3433, "date": "2026-06-21"}

    valley = client.get("/api/v1/maps/sun", params=place)

    assert valley.status_code == 200
    body = valley.json()
    assert body["date"] == "2026-06-21"
    assert body["sunrise"].startswith("2026-06-21T03:26") and body["sunset"][11:16] == "19:22"
    assert body["dawn"] < body["sunrise"] < body["noon"] < body["sunset"] < body["dusk"]

    # From a summit the horizon lies lower: the sun is seen some minutes longer at both ends.
    summit = client.get("/api/v1/maps/sun", params=place | {"elevation_m": 2500}).json()
    early = datetime.fromisoformat(body["sunrise"]) - datetime.fromisoformat(summit["sunrise"])
    assert timedelta(minutes=5) < early < timedelta(minutes=20)
    assert summit["sunset"] > body["sunset"] and summit["dawn"] == body["dawn"]

    # Without a date: today. In the polar summer there is no sunrise.
    assert client.get("/api/v1/maps/sun", params={"lat": 47, "lon": 9}).status_code == 200
    polar = client.get("/api/v1/maps/sun", params={"lat": 78.2, "lon": 15.6, "date": "2026-06-21"})
    assert polar.json()["sunrise"] is None
    assert client.get("/api/v1/maps/sun", params={"lat": 95, "lon": 9}).status_code == 422
