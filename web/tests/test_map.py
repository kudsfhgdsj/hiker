import json
import re

import httpx2

from tests.test_planning import INFO, planning_api

STYLE = {
    "version": 8,
    "glyphs": "https://api.example/api/v1/maps/fonts/{fontstack}/{range}.pbf",
    "sources": {
        "hiker": {
            "type": "vector",
            "tiles": ["https://api.example/api/v1/maps/vector/{z}/{x}/{y}.pbf"],
            "maxzoom": 14,
        }
    },
    "layers": [{"id": "background", "type": "background"}],
}


def vector_api(fake_api):
    fake_api.route("GET", "/maps/info", {"style_url": "https://api.example/x", "tile_url": "t"})
    fake_api.route("GET", "/maps/style.json", STYLE)
    fake_api.route(
        "GET",
        "/maps/vector/10/538/359.pbf",
        lambda r: httpx2.Response(
            200,
            content=b"tile",
            headers={"content-type": "application/x-protobuf", "cache-control": "max-age=86400"},
        ),
    )
    fake_api.route("GET", "/maps/vector/10/0/0.pbf", lambda r: httpx2.Response(204))
    fake_api.route(
        "GET", "/maps/fonts/*/0-255.pbf", lambda r: httpx2.Response(200, content=b"glyphs")
    )


def plan_data(page: str) -> dict:
    return json.loads(re.search(r'id="plan-data">(.*?)</script>', page, re.S).group(1))


def test_pages_use_the_vector_map_if_the_server_has_one(user, fake_api):
    planning_api(fake_api, INFO)
    vector_api(fake_api)

    data = plan_data(user.get("/routes/new").get_data(as_text=True))

    assert data["styleUrl"] == "/map/style.json"
    # The raster tiles stay as a fallback.
    assert data["tileUrl"] == "/tiles/{z}/{x}/{y}.png"


def test_pages_fall_back_to_raster_tiles_without_a_vector_map(user, fake_api):
    planning_api(fake_api, INFO)

    data = plan_data(user.get("/routes/new").get_data(as_text=True))

    assert data["styleUrl"] is None


def test_style_points_to_the_web_frontend_without_login(browser, fake_api):
    vector_api(fake_api)

    response = browser.get("/map/style.json")

    assert response.status_code == 200
    style = response.get_json()
    assert style["glyphs"] == "http://localhost/map/fonts/{fontstack}/{range}.pbf"
    assert style["sources"]["hiker"]["tiles"] == ["http://localhost/map/vector/{z}/{x}/{y}.pbf"]
    assert style["layers"] == STYLE["layers"]


def test_tiles_and_glyphs_are_passed_on(browser, fake_api):
    vector_api(fake_api)

    tile = browser.get("/map/vector/10/538/359.pbf")
    assert tile.status_code == 200 and tile.data == b"tile"
    assert tile.mimetype == "application/x-protobuf"
    assert tile.headers["Cache-Control"] == "max-age=86400"
    assert browser.get("/map/vector/10/0/0.pbf").status_code == 204

    glyphs = browser.get("/map/fonts/Noto Sans Regular/0-255.pbf")
    assert glyphs.status_code == 200 and glyphs.data == b"glyphs"
    assert browser.get("/map/fonts/Noto Sans Regular/evil.pbf").status_code == 404
