import gzip
import json
import re
import sqlite3

import pytest

from app.core.config import get_settings
from app.modules.maps.join import TileFormatError, _bytes_field, _fields, _varint, join_tiles
from app.modules.maps.merge import merge
from app.modules.maps.style import build_style
from app.tests.conftest import auth_header, register

TILE = gzip.compress(b"vector tile")
# Zoom 10, the tile around the Säntis.
Z, X, Y = 10, 538, 359


def write_map(path, tiles=((Z, X, Y),), bounds="9.0,47.0,10.0,47.5", max_zoom=14, data=TILE):
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
            db.execute("INSERT INTO tiles VALUES (?, ?, ?, ?)", (z, x, 2**z - 1 - y, data))


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
    # Ridges and cliffs live in the same layer as lines; they are not summits.
    assert layers["peak"]["filter"] == ["==", ["geometry-type"], "Point"]
    # Paths are drawn above the roads, labels above all lines.
    order = [layer["id"] for layer in style["layers"]]
    assert order.index("path") > order.index("road-motorway")
    assert order.index("peak-name") > order.index("path")
    # Every layer reads the one source, and no icon sprite is needed.
    assert all(layer.get("source", "hiker") == "hiker" for layer in style["layers"])
    assert "sprite" not in style
    # Colours in a form every MapLibre reads: the app's library knows no "#rrggbbaa".
    assert not re.search(r'"#[0-9a-fA-F]{8}"', json.dumps(style))
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


# --- Joining the base map and the paths with their difficulty ---


def test_layers_of_a_second_map_are_added_to_the_first(tmp_path):
    def build(path, tiles: dict, layer: str):
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
            db.execute(
                "CREATE TABLE tiles"
                " (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)"
            )
            meta = {"format": "pbf", "bounds": "9,47,10,47.5", "minzoom": "0", "maxzoom": "14"}
            meta["json"] = json.dumps({"vector_layers": [{"id": layer}]})
            db.executemany("INSERT INTO metadata VALUES (?, ?)", meta.items())
            for (z, x, y), data in tiles.items():
                db.execute("INSERT INTO tiles VALUES (?, ?, ?, ?)", (z, x, y, gzip.compress(data)))

    build(tmp_path / "base.mbtiles", {(12, 1, 1): b"BASE", (12, 2, 2): b"only base"}, "water")
    build(tmp_path / "paths.mbtiles", {(12, 1, 1): b"PATHS", (12, 3, 3): b"only paths"}, "hiking")

    count = merge(tmp_path / "base.mbtiles", tmp_path / "paths.mbtiles", tmp_path / "alps.mbtiles")

    assert count == 2
    with sqlite3.connect(tmp_path / "alps.mbtiles") as db:
        tiles = {
            (z, x, y): gzip.decompress(data) for z, x, y, data in db.execute("SELECT * FROM tiles")
        }
        meta = dict(db.execute("SELECT name, value FROM metadata"))
    # A vector tile is a list of layers: both contents, one after the other.
    assert tiles == {
        (12, 1, 1): b"BASEPATHS",
        (12, 2, 2): b"only base",
        (12, 3, 3): b"only paths",
    }
    assert [layer["id"] for layer in json.loads(meta["json"])["vector_layers"]] == [
        "water",
        "hiking",
    ]
    assert meta["bounds"] == "9,47,10,47.5" and meta["format"] == "pbf"


def test_paths_are_coloured_by_their_difficulty():
    style = build_style("tiles/{z}/{x}/{y}", "fonts/{fontstack}/{range}", "©", 14)
    layers = {layer["id"]: layer for layer in style["layers"]}
    order = [layer["id"] for layer in style["layers"]]

    difficulty = layers["path-difficulty"]
    assert difficulty["source-layer"] == "hiking"
    # Drawn over the plain paths, under the names.
    assert order.index("path") < order.index("path-difficulty") < order.index("peak-name")
    colours = difficulty["paint"]["line-color"]
    assert colours[:2] == ["match", ["get", "sac_scale"]]
    assert "difficult_alpine_hiking" in colours and "hiking" in colours
    assert layers["via-ferrata"]["filter"] == ["==", ["get", "highway"], "via_ferrata"]
    # What the colours mean travels with the style.
    legend = style["metadata"]["hiker"]["legend"]
    assert [entry["label"] for entry in legend] == ["T1", "T2", "T3", "T4", "T5", "T6", "KS"]
    # Light blue, dark blue, yellow, orange, red, black.
    assert [entry["color"] for entry in legend[:6]] == [
        "#38b6ff",
        "#1d3fa8",
        "#f2c200",
        "#f28c1e",
        "#d92323",
        "#111111",
    ]
    assert colours[colours.index("hiking") + 1] == "#38b6ff"
    assert colours[colours.index("difficult_alpine_hiking") + 1] == "#111111"

    # Zoomed in closely the grade stands next to the path.
    label = layers["path-difficulty-label"]
    assert label["source-layer"] == "hiking" and label["minzoom"] == 15
    assert label["layout"]["symbol-placement"] == "line"
    assert label["layout"]["text-offset"] == [0, 0.9]
    text = label["layout"]["text-field"]
    assert text[2] == "KS" and text[3][text[3].index("alpine_hiking") + 1] == "T4"
    assert order.index("path-difficulty") < order.index("path-difficulty-label")


def layer(name: str, features: list[tuple[dict, bytes]], extent: int = 4096) -> bytes:
    """A layer of a vector tile: features as (attributes, geometry bytes)."""
    keys: list[str] = []
    values: list[str] = []
    body = _varint(15 << 3) + _varint(2) + _bytes_field(1, name.encode())
    for attributes, geometry in features:
        tags = b""
        for key, value in attributes.items():
            if key not in keys:
                keys.append(key)
            if value not in values:
                values.append(value)
            tags += _varint(keys.index(key)) + _varint(values.index(value))
        feature = _bytes_field(2, tags) + _varint(3 << 3) + _varint(2) + _bytes_field(4, geometry)
        body += _bytes_field(2, feature)
    for key in keys:
        body += _bytes_field(3, key.encode())
    for value in values:
        # A value is a message with a string in field 1.
        body += _bytes_field(4, _bytes_field(1, value.encode()))
    return _bytes_field(3, body + _varint(5 << 3) + _varint(extent))


def read_tile(tile: bytes) -> dict[str, list[tuple[dict, bytes]]]:
    """Layers of a tile with their features as (attributes, geometry bytes)."""
    result = {}
    for number, _wire, value, _raw in _fields(tile):
        assert number == 3
        keys, values, features, name = [], [], [], ""
        for field, _w, content, _r in _fields(value):
            if field == 1:
                name = content.decode()
            elif field == 2:
                features.append(content)
            elif field == 3:
                keys.append(content.decode())
            elif field == 4:
                values.append(next(v for n, _w2, v, _r2 in _fields(content) if n == 1).decode())
        assert name not in result, "a layer name appears once"
        result[name] = []
        for feature in features:
            parts = {field: content for field, _w, content, _r in _fields(feature)}
            tags = list(parts[2])
            attributes = {keys[tags[i]]: values[tags[i + 1]] for i in range(0, len(tags), 2)}
            result[name].append((attributes, parts[4]))
    return result


def test_tiles_of_two_maps_are_joined_layer_by_layer():
    swiss = layer("transportation", [({"class": "path"}, b"\x01"), ({"class": "road"}, b"\x02")])
    swiss += layer("water", [({"class": "lake"}, b"\x09")])
    austrian = layer(
        "transportation",
        # Other order of keys and values, one feature both maps have, one new.
        [({"surface": "gravel", "class": "road"}, b"\x03"), ({"class": "road"}, b"\x02")],
    )
    austrian += layer("place", [({"name": "Feldkirch"}, b"\x05")])

    joined = read_tile(join_tiles([swiss, austrian]))

    assert list(joined) == ["transportation", "water", "place"]
    assert joined["transportation"] == [
        ({"class": "path"}, b"\x01"),
        ({"class": "road"}, b"\x02"),
        ({"surface": "gravel", "class": "road"}, b"\x03"),
    ]
    assert joined["water"] == [({"class": "lake"}, b"\x09")]
    assert joined["place"] == [({"name": "Feldkirch"}, b"\x05")]
    # A single tile stays as it is; a layer on another grid is left out.
    assert join_tiles([swiss]) == swiss
    other_grid = layer("water", [({"class": "river"}, b"\x07")], extent=512)
    assert read_tile(join_tiles([swiss, other_grid]))["water"] == [({"class": "lake"}, b"\x09")]
    with pytest.raises(TileFormatError):
        join_tiles([swiss, b"\xff\xff\xff"])


def test_a_tile_on_a_border_holds_both_regions(client, maps):
    swiss = layer("place", [({"name": "Buchs"}, b"\x01")])
    austrian = layer("place", [({"name": "Feldkirch"}, b"\x02")])
    write_map(maps / "switzerland.mbtiles", data=gzip.compress(swiss))
    write_map(maps / "austria.mbtiles", bounds="9.4,46.4,17.2,49.0", data=gzip.compress(austrian))

    response = client.get(f"/api/v1/maps/vector/{Z}/{X}/{Y}.pbf")

    assert response.status_code == 200
    # The test client unpacks the compressed answer.
    places = read_tile(response.content)["place"]
    assert {attributes["name"] for attributes, _geometry in places} == {"Buchs", "Feldkirch"}
    # Asked again, the joined tile is the same (kept in memory).
    assert client.get(f"/api/v1/maps/vector/{Z}/{X}/{Y}.pbf").content == response.content

    # A tile that cannot be read does not take the map away: the larger map answers.
    write_map(maps / "bayern.mbtiles", bounds="9.0,47.0,13.9,50.6", data=gzip.compress(b"\xff\xff"))
    assert client.get(f"/api/v1/maps/vector/{Z}/{X}/{Y}.pbf").status_code == 200


# --- Search ---


def value(item) -> bytes:
    """A value of a layer: text in field 1, whole numbers in field 4."""
    if isinstance(item, int):
        return _varint(4 << 3) + _varint(item)
    return _bytes_field(1, item.encode())


def point_layer(name: str, features: list[tuple[dict, int, int]]) -> bytes:
    """A layer of point features: (attributes, x, y) in tile coordinates of 0 to 4096."""
    keys: list[str] = []
    values: list = []
    body = _varint(15 << 3) + _varint(2) + _bytes_field(1, name.encode())
    for attributes, x, y in features:
        tags = b""
        for key, item in attributes.items():
            if key not in keys:
                keys.append(key)
            if item not in values:
                values.append(item)
            tags += _varint(keys.index(key)) + _varint(values.index(item))
        # "Move to" once, then both coordinates zigzag encoded.
        geometry = _varint(9) + _varint(x << 1) + _varint(y << 1)
        body += _bytes_field(
            2, _bytes_field(2, tags) + _varint(3 << 3) + _varint(1) + _bytes_field(4, geometry)
        )
    for key in keys:
        body += _bytes_field(3, key.encode())
    for item in values:
        body += _bytes_field(4, value(item))
    return _bytes_field(3, body + _varint(5 << 3) + _varint(4096))


def search_map(path, max_zoom=14):
    """A map whose deepest tile holds a summit, a hut, two places, two lakes and a shop."""
    tile = point_layer(
        "mountain_peak",
        [({"name": "Säntis", "ele": 2502, "class": "peak"}, 2048, 2048)],
    )
    tile += point_layer(
        "poi",
        [
            (
                {"name": "Berggasthaus Alter Säntis", "class": "lodging", "subclass": "alpine_hut"},
                2100,
                2000,
            ),
            ({"name": "Säntis Souvenirs", "class": "shop", "subclass": "gift"}, 2050, 2050),
        ],
    )
    tile += point_layer(
        "place",
        [
            ({"name": "Schwägalp", "class": "hamlet"}, 100, 3000),
            ({"name": "Säntisdorf", "class": "village"}, 4000, 100),
            # In the margin: the neighbouring tile has it.
            ({"name": "Nebenan", "class": "village"}, 4200, 100),
        ],
    )
    tile += point_layer(
        "water_name",
        [
            ({"name": "Seealpsee", "class": "lake"}, 3900, 3900),
            ({"name": "Fälensee", "class": "lake"}, 100, 100),
        ],
    )
    write_map(path, tiles=((14, 8617, 5746),), max_zoom=max_zoom, data=gzip.compress(tile))


def test_search_finds_the_places_of_the_map(client, maps, anna):
    from app.modules.maps.search import build_index, fold

    assert fold("Säntis") == "santis" and fold("Großglockner") == "grossglockner"
    search_map(maps / "switzerland.mbtiles")
    # Without an index the search answers with nothing.
    assert client.get("/api/v1/maps/search", params={"q": "santis"}).json() == []

    # Summit, hut, two places and two lakes; not the shop and not the point in the margin.
    assert build_index(maps / "switzerland.mbtiles") == 6

    found = client.get("/api/v1/maps/search", params={"q": "santis"}).json()
    # The name itself first, then what starts with it, then what contains it.
    assert [place["name"] for place in found] == [
        "Säntis",
        "Säntisdorf",
        "Berggasthaus Alter Säntis",
    ]
    peak = found[0]
    assert peak["kind"] == "peak" and peak["elevation_m"] == 2502
    assert abs(peak["lat"] - 47.249) < 0.02 and abs(peak["lon"] - 9.343) < 0.03
    assert found[2]["kind"] == "hut"
    assert client.get("/api/v1/maps/search", params={"q": "SEEALP"}).json()[0]["kind"] == "lake"
    assert client.get("/api/v1/maps/search", params={"q": "souvenir"}).json() == []
    assert client.get("/api/v1/maps/search", params={"q": "nebenan"}).json() == []
    assert client.get("/api/v1/maps/search", params={"q": "100%"}).json() == []
    assert client.get("/api/v1/maps/search", params={"q": "s"}).status_code == 422
    assert len(client.get("/api/v1/maps/search", params={"q": "an", "limit": 2}).json()) == 2

    # The app takes the index along with the map.
    region = client.get("/api/v1/maps/regions", headers=anna).json()[0]
    assert region["search_size_bytes"] > 0
    file = client.get("/api/v1/maps/regions/switzerland/search", headers=anna)
    assert file.status_code == 200 and file.content.startswith(b"SQLite format 3")
    assert client.get("/api/v1/maps/regions/switzerland/search").status_code == 401


def test_search_prefers_the_nearer_place_and_knows_border_places_once(tmp_path):
    from app.modules.maps.search import build_index, search, search_path

    search_map(tmp_path / "a.mbtiles")
    search_map(tmp_path / "b.mbtiles")
    indexes = []
    for name in ("a", "b"):
        build_index(tmp_path / f"{name}.mbtiles")
        indexes.append(search_path(tmp_path / f"{name}.mbtiles"))

    # Both regions carry the same places: each is found once.
    assert [place["name"] for place in search(indexes, "säntis")] == [
        "Säntis",
        "Säntisdorf",
        "Berggasthaus Alter Säntis",
    ]
    # Two lakes whose names only contain the query: the nearer one comes first.
    lakes = {place["name"]: place for place in search(indexes, "ee")}
    for name, other in (("Seealpsee", "Fälensee"), ("Fälensee", "Seealpsee")):
        here = (lakes[name]["lat"], lakes[name]["lon"])
        assert [place["name"] for place in search(indexes, "ee", near=here)] == [name, other]
    assert search(indexes + [tmp_path / "missing.sqlite"], "santis")


def test_path_data_tiles_follow_the_built_maps(tmp_path):
    from app.modules.maps.coverage import tiles_for, tiles_of_maps

    # Switzerland lies in two tiles of 5° x 5°; northern Bavaria reaches into the next row.
    assert tiles_for((5.95, 45.82, 10.5, 47.81)) == {"E5_N45", "E10_N45"}
    assert tiles_for((8.98, 47.23, 14.09, 50.57)) == {"E5_N45", "E10_N45", "E5_N50", "E10_N50"}
    assert tiles_for((-1.5, -0.5, 0.5, 0.5)) == {"W5_S5", "W5_N0", "E0_S5", "E0_N0"}

    write_map(tmp_path / "switzerland.mbtiles", bounds="5.95,45.82,10.5,47.81")
    write_map(tmp_path / "bayern.mbtiles", bounds="8.98,47.23,14.09,50.57")
    (tmp_path / "broken.mbtiles").write_text("not a map")
    assert tiles_of_maps(tmp_path) == ["E10_N45", "E10_N50", "E5_N45", "E5_N50"]


# --- Symbols ---


def test_symbols_are_served_and_used_by_the_topo_look(client, maps):
    import io

    from PIL import Image

    from app.modules.maps.sprites import SIZE, SYMBOLS, build

    write_map(maps / "switzerland.mbtiles")
    style = client.get("/api/v1/maps/style.json").json()
    assert style["sprite"] == "http://testserver/api/v1/maps/sprite"

    index = client.get("/api/v1/maps/sprite.json").json()
    assert (
        set(index)
        == set(SYMBOLS)
        == {
            "peak",
            "saddle",
            "hut",
            "shelter",
            "viewpoint",
            "parking",
            "cable-car",
        }
    )
    sheet = Image.open(io.BytesIO(client.get("/api/v1/maps/sprite.png").content))
    assert sheet.size == (SIZE * len(SYMBOLS), SIZE)
    assert index["hut"] == {"x": 2 * SIZE, "y": 0, "width": SIZE, "height": SIZE, "pixelRatio": 1}
    # Double resolution, also for screens that ask for the triple one.
    double = client.get("/api/v1/maps/sprite@2x.json").json()
    assert double["hut"]["width"] == 2 * SIZE and double["hut"]["pixelRatio"] == 2
    big = Image.open(io.BytesIO(client.get("/api/v1/maps/sprite@3x.png").content))
    assert big.size == (2 * SIZE * len(SYMBOLS), 2 * SIZE)
    assert client.get("/api/v1/maps/sprite@9x.png").status_code == 422
    # The files in the repository are what the drawing code produces.
    assert build(1)[1] == index and build(2)[1] == double
    assert build(1)[0].size == sheet.size

    layers = {layer["id"]: layer for layer in style["layers"]}
    topo = next(base for base in style["metadata"]["hiker"]["bases"] if base["id"] == "topo")
    # Triangle or saddle sign instead of the dot, signs for huts and other places.
    assert {"topo-peak", "topo-poi"} <= set(topo["show"]) and {"peak", "hut"} <= set(topo["hide"])
    assert layers["topo-peak"]["layout"]["icon-image"][2:] == ["saddle", "peak"]
    assert layers["topo-peak"]["layout"]["visibility"] == "none"
    used = {v for v in layers["topo-poi"]["layout"]["icon-image"] if isinstance(v, str)}
    assert used - {"case"} <= set(SYMBOLS)

    # Without symbols the look keeps the dots.
    plain = build_style("t", "g", "©", 14)
    assert "sprite" not in plain and "topo-peak" not in {layer["id"] for layer in plain["layers"]}
