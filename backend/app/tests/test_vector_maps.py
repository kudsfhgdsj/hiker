import gzip
import sqlite3

import pytest

from app.core.config import get_settings
from app.modules.maps.style import build_style
from app.tests.conftest import auth_header, register

TILE = gzip.compress(b"vector tile")
# Zoom 10, the tile around the Säntis.
Z, X, Y = 10, 538, 359


def write_map(path, tiles=((Z, X, Y),), bounds="9.0,47.0,10.0,47.5", max_zoom=14):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
        db.execute(
            "CREATE TABLE tiles"
            " (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)"
        )
        db.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [("format", "pbf"), ("bounds", bounds), ("minzoom", "0"), ("maxzoom", str(max_zoom))],
        )
        for z, x, y in tiles:
            # MBTiles count rows from the south.
            db.execute("INSERT INTO tiles VALUES (?, ?, ?, ?)", (z, x, 2**z - 1 - y, TILE))


@pytest.fixture
def maps(tmp_path, monkeypatch):
    monkeypatch.setenv("MAP_DATA_PATH", str(tmp_path))
    get_settings.cache_clear()
    return tmp_path


@pytest.fixture
def anna(client):
    return auth_header(register(client))


def test_without_a_map_the_raster_tiles_stay(client, maps):
    info = client.get("/api/v1/maps/info").json()
    assert info["style_url"] is None and info["tile_url"].endswith("/{z}/{x}/{y}.png")
    assert client.get("/api/v1/maps/style.json").status_code == 404
    assert client.get(f"/api/v1/maps/vector/{Z}/{X}/{Y}.pbf").status_code == 204


def test_vector_tiles_come_from_the_map_file_without_login(client, maps):
    write_map(maps / "alps.mbtiles")

    info = client.get("/api/v1/maps/info").json()
    assert info["style_url"] == "http://testserver/api/v1/maps/style.json"

    tile = client.get(f"/api/v1/maps/vector/{Z}/{X}/{Y}.pbf")
    assert tile.status_code == 200
    assert tile.headers["content-type"] == "application/x-protobuf"
    assert tile.headers["content-encoding"] == "gzip"
    assert "max-age=86400" in tile.headers["cache-control"]
    # The test client unpacks the answer like a browser does.
    assert tile.content == b"vector tile"

    # Inside the map but without data, outside the map, and no such tile at all.
    assert client.get(f"/api/v1/maps/vector/{Z}/{X + 1}/{Y}.pbf").status_code == 204
    assert client.get("/api/v1/maps/vector/10/0/0.pbf").status_code == 204
    assert client.get("/api/v1/maps/vector/2/9/9.pbf").status_code == 204


def test_a_replaced_map_file_is_read_again(client, maps):
    write_map(maps / "alps.mbtiles", tiles=())
    assert client.get(f"/api/v1/maps/vector/{Z}/{X}/{Y}.pbf").status_code == 204

    (maps / "alps.mbtiles").unlink()
    write_map(maps / "alps.mbtiles")
    assert client.get(f"/api/v1/maps/vector/{Z}/{X}/{Y}.pbf").status_code == 200


def test_several_regions_complete_each_other(client, maps, anna):
    write_map(maps / "switzerland.mbtiles")
    write_map(maps / "austria.mbtiles", tiles=((Z, X + 4, Y),), bounds="9.5,46.4,17.2,49.0")
    (maps / "notes.mbtiles").write_text("not a map")
    (maps / "Bad Name.mbtiles").write_bytes(b"")

    assert client.get(f"/api/v1/maps/vector/{Z}/{X}/{Y}.pbf").status_code == 200
    assert client.get(f"/api/v1/maps/vector/{Z}/{X + 4}/{Y}.pbf").status_code == 200

    regions = client.get("/api/v1/maps/regions", headers=anna).json()
    assert {region["name"] for region in regions} == {"switzerland", "austria"}
    swiss = next(region for region in regions if region["name"] == "switzerland")
    assert swiss["bounds"] == [9.0, 47.0, 10.0, 47.5] and swiss["max_zoom"] == 14
    assert swiss["size_bytes"] > 0


def test_region_files_are_downloaded_with_login_and_in_parts(client, maps, anna):
    write_map(maps / "alps.mbtiles")
    whole = (maps / "alps.mbtiles").read_bytes()

    assert client.get("/api/v1/maps/regions").status_code == 401
    assert client.get("/api/v1/maps/regions/alps").status_code == 401

    response = client.get("/api/v1/maps/regions/alps", headers=anna)
    assert response.status_code == 200 and response.content == whole
    assert 'filename="alps.mbtiles"' in response.headers["content-disposition"]
    rest = client.get("/api/v1/maps/regions/alps", headers=anna | {"Range": "bytes=100-"})
    assert rest.status_code == 206 and rest.content == whole[100:]

    assert client.get("/api/v1/maps/regions/other", headers=anna).status_code == 404
    assert client.get("/api/v1/maps/regions/..%2Falps", headers=anna).status_code == 404


def test_style_points_to_this_server(client, maps):
    write_map(maps / "alps.mbtiles", max_zoom=12)

    style = client.get("/api/v1/maps/style.json").json()

    assert style["version"] == 8
    assert style["glyphs"] == "http://testserver/api/v1/maps/fonts/{fontstack}/{range}.pbf"
    source = style["sources"]["hiker"]
    assert source["tiles"] == ["http://testserver/api/v1/maps/vector/{z}/{x}/{y}.pbf"]
    assert source["maxzoom"] == 12
    assert "OpenStreetMap" in source["attribution"] and "OpenMapTiles" in source["attribution"]


def test_style_is_a_hiking_map_from_own_layers():
    style = build_style("tiles/{z}/{x}/{y}", "fonts/{fontstack}/{range}", "©", 14)
    layers = {layer["id"]: layer for layer in style["layers"]}

    # Paths, peaks and huts are what the map is for.
    assert layers["path"]["filter"] == ["==", ["get", "class"], "path"]
    assert {"peak", "peak-name", "hut", "hut-name", "rock", "ice", "wood"} <= set(layers)
    # Paths are drawn above the roads, labels above all lines.
    order = [layer["id"] for layer in style["layers"]]
    assert order.index("path") > order.index("road-motorway")
    assert order.index("peak-name") > order.index("path")
    # Every layer reads the one source, and no icon sprite is needed.
    assert all(layer.get("source", "hiker") == "hiker" for layer in style["layers"])
    assert "sprite" not in style
    # Only fonts the server has, one per label.
    fonts = {
        tuple(layer["layout"]["text-font"])
        for layer in style["layers"]
        if layer["type"] == "symbol"
    }
    assert fonts <= {("Noto Sans Regular",), ("Noto Sans Bold",), ("Noto Sans Italic",)}


def test_glyphs_of_the_fonts_are_served(client):
    glyphs = client.get("/api/v1/maps/fonts/Noto Sans Regular/0-255.pbf")
    assert glyphs.status_code == 200 and len(glyphs.content) > 10_000
    assert glyphs.headers["content-type"] == "application/x-protobuf"

    # A range without glyphs is empty, an unknown font is missing.
    empty = client.get("/api/v1/maps/fonts/Noto Sans Bold/20480-20735.pbf")
    assert empty.status_code == 200 and empty.content == b""
    assert client.get("/api/v1/maps/fonts/Comic Sans/0-255.pbf").status_code == 404
    assert client.get("/api/v1/maps/fonts/Noto Sans Bold/abc.pbf").status_code == 422
    # Several fonts in one request: the first one known answers.
    stack = client.get("/api/v1/maps/fonts/Unknown,Noto Sans Bold/0-255.pbf")
    assert stack.status_code == 200 and len(stack.content) > 10_000
