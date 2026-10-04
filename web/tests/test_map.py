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
        },
        "terrain": {
            "type": "raster-dem",
            "tiles": ["https://api.example/api/v1/maps/raster/terrain/{z}/{x}/{y}"],
        },
        "slope": {
            "type": "raster",
            "tiles": ["https://api.example/api/v1/maps/slope/{z}/{x}/{y}.png"],
        },
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
    assert style["sources"]["terrain"]["tiles"] == [
        "http://localhost/map/raster/terrain/{z}/{x}/{y}"
    ]
    assert style["sources"]["slope"]["tiles"] == ["http://localhost/map/slope/{z}/{x}/{y}.png"]
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


def test_raster_layers_and_slope_are_passed_on(browser, fake_api):
    image = httpx2.Response(200, content=b"png", headers={"content-type": "image/png"})
    fake_api.route("GET", "/maps/raster/terrain/12/2153/1436", lambda r: image)
    fake_api.route(
        "GET",
        "/maps/raster/satellite/12/2153/1436",
        lambda r: httpx2.Response(200, content=b"jpg", headers={"content-type": "image/jpeg"}),
    )
    fake_api.route("GET", "/maps/slope/12/2153/1436.png", lambda r: image)

    assert browser.get("/map/raster/terrain/12/2153/1436").data == b"png"
    aerial = browser.get("/map/raster/satellite/12/2153/1436")
    assert aerial.data == b"jpg" and aerial.mimetype == "image/jpeg"
    assert browser.get("/map/slope/12/2153/1436.png").mimetype == "image/png"
    assert browser.get("/map/raster/other/12/2153/1436").status_code == 404

    fake_api.route(
        "GET", "/maps/contours/12/2153/1436.pbf", lambda r: httpx2.Response(200, content=b"lines")
    )
    contours = browser.get("/map/contours/12/2153/1436.pbf")
    assert contours.data == b"lines" and contours.mimetype == "application/x-protobuf"


def test_pages_carry_the_texts_of_the_layer_control(user, fake_api):
    planning_api(fake_api, INFO)
    vector_api(fake_api)

    page = user.get("/routes/new").get_data(as_text=True)

    texts = plan_data(page)["layerTexts"]
    assert texts["base"] == {"map": "Karte", "winter": "Winter", "satellite": "Luftbild"}
    assert texts["overlay"]["slope"] == "Hangneigung" and texts["terrain"] == "3D-Gelände"
    assert "map_layers.js" in page
