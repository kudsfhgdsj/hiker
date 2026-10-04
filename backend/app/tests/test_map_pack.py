# ruff: noqa: F811 (the fixtures of the vector map tests are used as arguments)
import sqlite3

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
