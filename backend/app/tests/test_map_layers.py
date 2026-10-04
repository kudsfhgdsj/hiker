import gzip
import io
import math

import pytest
from PIL import Image

from app.core.config import get_settings
from app.modules.maps.contours import _grid, contour_tile, interval_for, trace
from app.modules.maps.layers import (
    SATELLITE,
    Layers,
    Provider,
    _Composite,
    get_layers,
    slope_tile,
    tile_center,
)
from app.modules.maps.style import build_style
from app.modules.maps.tiles import FetchedTile, TileSourceError
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
    assert [entry["id"] for entry in hiker["bases"]] == ["map", "winter", "satellite"]
    assert style["sources"]["contours"]["tiles"] == [f"{base}/contours/{{z}}/{{x}}/{{y}}.pbf"]
    assert [entry["id"] for entry in hiker["overlays"]] == ["slope"]
    assert hiker["terrain"] == {"source": "terrain-3d", "exaggeration": 1.3}


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
    assert order.index("satellite") == 1
    assert layers["slope"]["layout"]["visibility"] == "none"
    assert layers["satellite"]["layout"]["visibility"] == "none"
    assert "visibility" not in layers["hillshade"].get("layout", {})

    # The aerial image replaces the drawn ground and the shading, not paths and names.
    # Winter is a white veil under the shading; contour lines lie on the ground too.
    assert order.index("wood") < order.index("winter-snow") < order.index("hillshade")
    assert layers["winter-snow"]["layout"]["visibility"] == "none"
    assert hiker["bases"][1] == {"id": "winter", "show": ["winter-snow"], "hide": []}
    assert order.index("hillshade") < order.index("contour") < order.index("waterway")
    assert layers["contour"]["source-layer"] == "contour"
    assert layers["contour-label"]["filter"] == ["==", ["get", "index"], 1]
    satellite = hiker["bases"][2]
    assert satellite["show"] == ["satellite"]
    assert {"wood", "rock", "water", "hillshade"} <= set(satellite["hide"])
    assert not {"background", "path", "peak-name", "waterway"} & set(satellite["hide"])
    assert [entry["from"] for entry in hiker["overlays"][0]["legend"]] == [30, 35, 40, 45]

    plain = build_style("t", "g", "©", 14)
    assert set(plain["sources"]) == {"hiker"}
    assert plain["metadata"]["hiker"] == {
        "bases": [{"id": "map", "show": [], "hide": []}],
        "overlays": [],
    }


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
