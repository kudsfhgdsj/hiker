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
