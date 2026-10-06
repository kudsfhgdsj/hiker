import gzip

# ruff: noqa: F811 (the fixtures of the vector map tests are used as arguments)
import sqlite3

from app.core.config import get_settings
from app.modules.maps.pack import build, tiles_in
from app.tests.test_map_layers import terrain_png
from app.tests.test_vector_maps import anna, maps, write_map  # noqa: F401 (fixtures)

# --- Layer pack: elevation, slope and contour lines to take along ---


def test_tiles_of_an_area_are_listed_per_zoom():
    # The Säntis lies in tile 10/538/359.
    assert list(tiles_in((9.3, 47.2, 9.4, 47.25), 10)) == [(538, 359)]
    assert len(list(tiles_in((9.0, 47.0, 10.0, 47.5), 12))) == 12 * 9
    assert list(tiles_in((-180, -85, 180, 85), 0)) == [(0, 0)]


def test_layer_pack_holds_elevation_slope_and_contours(client, maps, anna):
    write_map(maps / "alps.mbtiles", bounds="9.3,47.2,9.4,47.3")
    asked = []

    def fetch(z, x, y):
        asked.append(z)
        # No data at zoom 8: the pack simply has nothing there.
        return None if z == 8 else terrain_png(lambda c, r: 1000 + c * 30)

    messages = []
    out = build(maps / "alps.mbtiles", fetch, workers=2, report=messages.append)

    assert out == maps / "alps.layers.sqlite" and not (maps / "alps.layers.part").exists()
    with sqlite3.connect(out) as db:
        counts = dict(db.execute("SELECT layer || z, count(*) FROM layer_tiles GROUP BY 1"))
        slope = db.execute(
            "SELECT data FROM layer_tiles WHERE layer = 'slope' AND z = 12"
        ).fetchone()
    # Elevation up to zoom 11, slope from 10 to 12, contour lines for 11 and 12.
    assert set(counts) == {
        "terrain7",
        "terrain9",
        "terrain10",
        "terrain11",
        "slope10",
        "slope11",
        "slope12",
        "contours11",
        "contours12",
    }
    assert slope[0][:4] == b"\x89PNG"
    assert sorted(set(asked)) == [7, 8, 9, 10, 11, 12]
    assert messages[1].startswith("zoom 8: 0 of")

    regions = client.get("/api/v1/maps/regions", headers=anna).json()
    assert regions[0]["layers_size_bytes"] == out.stat().st_size
    download = client.get("/api/v1/maps/regions/alps/layers", headers=anna)
    assert download.status_code == 200 and download.content == out.read_bytes()
    assert 'filename="alps.layers.sqlite"' in download.headers["content-disposition"]
    assert client.get("/api/v1/maps/regions/alps/layers").status_code == 401


def test_a_region_without_pack_offers_none(client, maps, anna):
    write_map(maps / "alps.mbtiles")

    assert client.get("/api/v1/maps/regions", headers=anna).json()[0]["layers_size_bytes"] is None
    assert client.get("/api/v1/maps/regions/alps/layers", headers=anna).status_code == 404


def test_the_server_answers_from_packs_built_ahead(client, maps, monkeypatch):
    from app.modules.maps import layers as layers_module
    from app.modules.maps.pack import build_server_pack, server_pack_path, server_plan

    # Below the levels of the app's pack, as deep as asked for and as the server serves.
    assert server_plan(13) == {
        "terrain": range(12, 14),
        "slope": range(13, 14),
        "contours": range(13, 14),
    }
    assert server_plan(15)["slope"] == range(13, 15) and server_plan(15)["contours"] == range(
        13, 14
    )
    assert list(server_plan(11)["terrain"]) == []

    write_map(maps / "saentis.mbtiles", bounds="9.30,47.22,9.40,47.28")
    made: list[tuple] = []
    elevation = terrain_png(lambda column, row: 1000 + row)

    def make(job):
        z, x, y, with_slope, with_contours = job
        made.append(job)
        rows = [("terrain", z, x, y, elevation)]
        if with_slope:
            rows.append(("slope", z, x, y, b"slope built ahead"))
        if with_contours:
            # Contour tiles are stored compressed, as the server sends them.
            rows.append(("contours", z, x, y, gzip.compress(b"contours built ahead")))
        return rows

    class Inline:
        """Stands in for the process pool: runs the jobs right here."""

        def __init__(self, max_workers):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *error):
            return False

        def map(self, function, jobs, chunksize=1):
            return [function(job) for job in jobs]

    monkeypatch.setattr("app.modules.maps.pack.ProcessPoolExecutor", Inline)
    lines: list[str] = []
    out = build_server_pack(maps / "saentis.mbtiles", make, max_zoom=13, report=lines.append)

    assert out == server_pack_path(maps / "saentis.mbtiles") and out.is_file()
    assert {job[0] for job in made} == {12, 13}
    assert all(job[3] and job[4] for job in made if job[0] == 13)
    assert not any(job[3] or job[4] for job in made if job[0] == 12)
    assert lines[-1].startswith("zoom 13:")

    # Built again, nothing is made twice; a neighbouring region skips what this one has.
    count = len(made)
    build_server_pack(maps / "saentis.mbtiles", make, max_zoom=13, report=lines.append)
    write_map(maps / "alpstein.mbtiles", bounds="9.30,47.22,9.40,47.28")
    build_server_pack(maps / "alpstein.mbtiles", make, max_zoom=13, report=lines.append)
    assert len(made) == count

    # The server hands out what the pack holds, without source and without computing.
    def no_source(*args, **kwargs):
        raise AssertionError("the pack must answer")

    get_settings.cache_clear()
    layers_module._layers.cache_clear()
    monkeypatch.setattr(layers_module.TileCache, "get", no_source)
    z, x, y = made[-1][:3]
    assert client.get(f"/api/v1/maps/slope/{z}/{x}/{y}.png").content == b"slope built ahead"
    assert client.get(f"/api/v1/maps/contours/{z}/{x}/{y}.pbf").content == b"contours built ahead"
    assert client.get(f"/api/v1/maps/raster/terrain/{z}/{x}/{y}").content == elevation
    layers_module._layers.cache_clear()


def test_a_fine_elevation_model_comes_first_and_is_named(client, maps, monkeypatch):
    from app.modules.maps import layers as layers_module
    from app.modules.maps.pack import derive

    write_map(maps / "austria.mbtiles", bounds="9.5,46.4,17.2,49.0")
    fine = terrain_png(lambda column, row: 2000 + column * 4)
    coarse = terrain_png(lambda column, row: 1000)

    def pack(name: str, elevation: bytes, attribution: str | None = None) -> None:
        with sqlite3.connect(maps / name) as db:
            db.execute(
                "CREATE TABLE layer_tiles (layer TEXT, z INTEGER, x INTEGER, y INTEGER,"
                " data BLOB, PRIMARY KEY (layer, z, x, y)) WITHOUT ROWID"
            )
            db.execute("CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT)")
            if attribution:
                db.execute("INSERT INTO metadata VALUES ('attribution', ?)", (attribution,))
            for z, x, y in ((13, 4420, 2850), (14, 8840, 5700), (12, 2210, 1425)):
                db.execute(
                    "INSERT INTO layer_tiles VALUES ('terrain', ?, ?, ?, ?)", (z, x, y, elevation)
                )

    pack("austria.server.sqlite", coarse)
    pack("austria.hires.sqlite", fine, "Höhendaten Österreich: © BEV (DGM 5 m), CC BY 4.0")

    class Inline:
        def __init__(self, max_workers):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *error):
            return False

        def map(self, function, jobs, chunksize=1):
            return [function(job) for job in jobs]

    monkeypatch.setattr("app.modules.maps.pack.ProcessPoolExecutor", Inline)
    lines: list[str] = []
    # Slope for every level of the model, contours down to their deepest level (13).
    assert derive(maps / "austria.hires.sqlite", report=lines.append) == 3
    # They go into a file of their own: the server reads the pack meanwhile.
    with sqlite3.connect(maps / "austria.derived.hires.sqlite") as db:
        made = db.execute("SELECT layer, z FROM layer_tiles ORDER BY 1, 2").fetchall()
    with sqlite3.connect(maps / "austria.hires.sqlite") as db:
        untouched = db.execute("SELECT count(*) FROM layer_tiles WHERE layer != 'terrain'")
        assert untouched.fetchone() == (0,)
    assert made == [("contours", 12), ("contours", 13), ("slope", 12), ("slope", 13), ("slope", 14)]
    # Run again, nothing is left to do.
    assert derive(maps / "austria.hires.sqlite", report=lines.append) == 0

    def no_source(*args, **kwargs):
        raise AssertionError("the pack must answer")

    get_settings.cache_clear()
    layers_module._layers.cache_clear()
    monkeypatch.setattr(layers_module.TileCache, "get", no_source)
    # The fine model wins over the tiles built ahead from the world-wide source.
    assert client.get("/api/v1/maps/raster/terrain/13/4420/2850").content == fine
    assert client.get("/api/v1/maps/slope/14/8840/5700.png").status_code == 200
    assert client.get("/api/v1/maps/contours/13/4420/2850.pbf").status_code == 200
    # Its source is named with the elevation data.
    style = client.get("/api/v1/maps/style.json").json()
    named = style["sources"]["terrain"]["attribution"]
    assert "Mapzen" in named and "© BEV (DGM 5 m), CC BY 4.0" in named
    layers_module._layers.cache_clear()


def test_detail_packs_take_finer_levels_from_what_was_built_ahead(client, maps, anna, monkeypatch):
    import io

    from PIL import Image

    from app.modules.maps.pack import build_details, coarser_steps

    write_map(maps / "alps.mbtiles", bounds="9.30,47.20,9.31,47.21")
    fine = terrain_png(lambda column, row: 2000 + column * 4.3 + row * 0.11)

    class Inline:
        def __init__(self, max_workers):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *error):
            return False

        def map(self, function, jobs, chunksize=1):
            return [function(job) for job in jobs]

    monkeypatch.setattr("app.modules.maps.pack.ProcessPoolExecutor", Inline)

    def tile(z: int) -> tuple[int, int, int]:
        return z, int((9.305 + 180) / 360 * 2**z), next(iter(pack_tiles(z)))

    def pack_tiles(z: int):
        from app.modules.maps.pack import tiles_in

        return [y for _x, y in tiles_in((9.30, 47.20, 9.31, 47.21), z)]

    def store(name: str, rows: list[tuple]) -> None:
        with sqlite3.connect(maps / name) as db:
            db.execute(
                "CREATE TABLE layer_tiles (layer TEXT, z INTEGER, x INTEGER, y INTEGER,"
                " data BLOB, PRIMARY KEY (layer, z, x, y)) WITHOUT ROWID"
            )
            db.executemany("INSERT INTO layer_tiles VALUES (?, ?, ?, ?, ?)", rows)

    # A fine model with elevation for 12 to 14 and what was derived from it; the pack
    # of the server has zoom 12 too, but the fine model comes first.
    store("alps.hires.sqlite", [("terrain", *tile(z), fine) for z in (12, 13, 14)])
    store(
        "alps.derived.hires.sqlite",
        [("slope", *tile(13), b"slope 13"), ("slope", *tile(14), b"slope 14")]
        + [("contours", *tile(13), b"lines 13")],
    )
    store("alps.server.sqlite", [("terrain", *tile(12), terrain_png(lambda c, r: 500))])

    # Without the pack of the app there is nothing to add to: no levels are offered.
    lines: list[str] = []
    written = build_details(maps / "alps.mbtiles", report=lines.append)
    assert [path.name for path in written] == [
        "alps.detail1.layers.sqlite",
        "alps.detail2.layers.sqlite",
        "alps.detail3.layers.sqlite",
    ]
    assert client.get("/api/v1/maps/regions", headers=anna).json()[0]["details"] == []
    store("alps.layers.sqlite", [])

    def held(level: int) -> dict:
        with sqlite3.connect(maps / f"alps.detail{level}.layers.sqlite") as db:
            return {
                f"{layer}{z}": data
                for layer, z, data in db.execute("SELECT layer, z, data FROM layer_tiles")
            }

    small, medium, full = held(1), held(2), held(3)
    assert set(small) == {"terrain12", "slope13", "contours13"}
    assert set(medium) == {"terrain13", "slope14"} and set(full) == {"terrain14"}
    assert small["slope13"] == b"slope 13" and small["contours13"] == b"lines 13"

    # Heights in steps of 25 cm: smaller, and never more than 25 cm lower.
    def heights(png: bytes) -> list[float]:
        pixels = Image.open(io.BytesIO(png)).convert("RGB").tobytes()
        return [
            pixels[i] * 256 + pixels[i + 1] + pixels[i + 2] / 256 - 32768
            for i in range(0, len(pixels), 3)
        ]

    assert small["terrain12"] == coarser_steps(fine) and len(small["terrain12"]) < len(fine)
    for before, after in zip(heights(fine), heights(small["terrain12"]), strict=True):
        assert 0 <= before - after < 0.25 and after * 4 == int(after * 4)

    regions = client.get("/api/v1/maps/regions", headers=anna).json()
    assert regions[0]["details"] == [
        {"level": level, "size_bytes": (maps / f"alps.detail{level}.layers.sqlite").stat().st_size}
        for level in (1, 2, 3)
    ]
    download = client.get("/api/v1/maps/regions/alps/layers/2", headers=anna)
    assert download.status_code == 200
    assert download.content == (maps / "alps.detail2.layers.sqlite").read_bytes()
    assert 'filename="alps.detail2.layers.sqlite"' in download.headers["content-disposition"]
    assert client.get("/api/v1/maps/regions/alps/layers/2").status_code == 401
    assert client.get("/api/v1/maps/regions/alps/layers/4", headers=anna).status_code == 404
    assert client.get("/api/v1/maps/regions/none/layers/1", headers=anna).status_code == 404

    # A level counts only with those before it: the app loads them one on top of the other.
    (maps / "alps.detail2.layers.sqlite").unlink()
    (maps / "alps.mbtiles").touch()
    assert [
        d["level"] for d in client.get("/api/v1/maps/regions", headers=anna).json()[0]["details"]
    ] == [1]

    # A region for which nothing was built ahead gets no detail packs.
    write_map(maps / "elsewhere.mbtiles", bounds="20.0,40.0,20.01,40.01")
    assert build_details(maps / "elsewhere.mbtiles", report=lines.append) == []
    assert not list(maps.glob("elsewhere.detail*"))
