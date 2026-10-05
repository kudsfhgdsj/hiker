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
        "avalanche": {
            "type": "geojson",
            "data": "https://api.example/api/v1/maps/avalanche.geojson",
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
    assert style["sources"]["avalanche"]["data"] == "http://localhost/map/avalanche.geojson"
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

    fake_api.route("GET", "/maps/raster/snow/7/67/44", lambda r: image)
    fake_api.route("GET", "/maps/avalanche.geojson", {"type": "FeatureCollection", "features": []})
    assert browser.get("/map/raster/snow/7/67/44").data == b"png"
    danger = browser.get("/map/avalanche.geojson")
    assert danger.get_json()["features"] == [] and danger.mimetype == "application/geo+json"

    fake_api.route(
        "GET", "/maps/contours/12/2153/1436.pbf", lambda r: httpx2.Response(200, content=b"lines")
    )
    fake_api.route(
        "GET", "/maps/weather/9/269/179.pbf", lambda r: httpx2.Response(200, content=b"forecast")
    )
    assert browser.get("/map/weather/9/269/179.pbf").data == b"forecast"
    contours = browser.get("/map/contours/12/2153/1436.pbf")
    assert contours.data == b"lines" and contours.mimetype == "application/x-protobuf"


def test_pages_carry_the_texts_of_the_layer_control(user, fake_api):
    planning_api(fake_api, INFO)
    vector_api(fake_api)

    page = user.get("/routes/new").get_data(as_text=True)

    texts = plan_data(page)["layerTexts"]
    assert texts["base"] == {
        "map": "Karte",
        "winter": "Winter",
        "topo": "Topo",
        "alpenverein": "Alpenverein",
        "outdooractive": "Outdooractive",
        "kompass": "Kompass",
        "satellite": "Luftbild",
    }
    assert texts["overlay"]["slope"] == "Hangneigung" and "3D" in texts["terrain"]
    # The drop-down fields of the map: layers, looks, slope angles, a past day, the radar.
    assert texts["title"] == "Ebenen" and texts["looks"] == "Darstellung"
    assert set(texts["slope"]) == {"from", "to", "low", "high", "open"}
    assert set(texts["history"]) == {"label", "today", "note"}
    assert set(texts["radar"]) == {"rain", "clouds", "play", "note"}
    # The overlays are offered in groups; the aerial image is one of them, with its opacity.
    assert texts["group"] == {
        "terrain": "Gelände",
        "snow": "Schnee und Lawinen",
        "weather": "Wetter",
    }
    assert texts["overlay"]["satellite"] == "Luftbild" and texts["opacity"] == "Deckkraft"
    # The key of the map: its words for sections and entries.
    key = texts["key"]
    assert key["title"] == "Legende" and key["sections"]["paths"] == "Wege"
    assert key["items"]["via_ferrata"] == "Klettersteig" and key["items"]["ladder"] == "Leiter"
    assert key["items"]["grade_easy"].endswith("(T1–T4)") and key["items"]["ice"] == "Gletscher"
    assert texts["overlay"]["avalanche"] == "Lawinengefahr"
    assert "Bulletin" in texts["note"]["avalanche"]
    assert "map_layers.js" in page


def test_map_mode_shows_the_map_and_links_into_the_planner(user, fake_api):
    planning_api(fake_api, INFO)
    vector_api(fake_api)

    page = user.get("/map").get_data(as_text=True)

    assert 'href="/map"' in page and ">Karte</a>" in page
    data = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
    assert data["styleUrl"] == "/map/style.json" and data["sunUrl"] == "/map/sun"
    assert data["planUrl"] == "/routes/new"
    assert data["texts"]["sac"]["alpine_hiking"] == "T4 – Schwere Bergtour"
    assert data["layerTexts"]["title"] == "Ebenen" and "map_view.js" in page

    # The planner starts where the map was looked at.
    planner = user.get("/routes/new?lat=46.5&lon=8.1&zoom=13").get_data(as_text=True)
    assert plan_data(planner)["view"] == {"center": [8.1, 46.5], "zoom": 13.0}
    assert plan_data(user.get("/routes/new?lat=x").get_data(as_text=True))["view"] is None


def test_map_mode_needs_a_login_and_the_module(browser, fake_api):
    assert browser.get("/map").status_code == 302
    fake_api.modules.remove("maps")
    browser.login()
    assert browser.get("/map").status_code == 404


def test_sun_radar_and_layer_choices_are_passed_on(browser, fake_api):
    image = httpx2.Response(200, content=b"png", headers={"content-type": "image/png"})
    sun = {"date": "2026-06-21", "sunrise": "2026-06-21T03:26:00Z", "sunset": None}
    fake_api.route("GET", "/maps/sun", sun)
    fake_api.route("GET", "/maps/radar/frames", {"rain": [1790000000], "clouds": []})
    fake_api.route("GET", "/maps/radar/rain/1790000000/7/67/44.png", lambda r: image)
    fake_api.route("GET", "/maps/slope/12/2153/1436.png", lambda r: image)
    fake_api.route("GET", "/maps/raster/snow/7/67/44", lambda r: image)

    answer = browser.get("/map/sun?lat=47.2&lon=9.3&elevation_m=2500&other=1")
    assert answer.get_json() == sun
    assert dict(fake_api.calls[-1].url.params) == {
        "lat": "47.2",
        "lon": "9.3",
        "elevation_m": "2500",
    }

    assert browser.get("/map/radar/frames").get_json()["rain"] == [1790000000]
    assert browser.get("/map/radar/rain/1790000000/7/67/44.png").data == b"png"
    assert browser.get("/map/radar/other/1/7/67/44.png").status_code == 404

    # The chosen angles of the slope layer and the day of a layer with a history.
    browser.get("/map/slope/12/2153/1436.png?low=35&high=50")
    assert dict(fake_api.calls[-1].url.params) == {"low": "35", "high": "50"}
    browser.get("/map/raster/snow/7/67/44?date=2026-02-01")
    assert dict(fake_api.calls[-1].url.params) == {"date": "2026-02-01"}


def test_search_is_passed_on_and_offered_by_the_map(user, fake_api):
    planning_api(fake_api, INFO)
    vector_api(fake_api)
    found = [{"name": "Säntis", "kind": "peak", "lat": 47.249, "lon": 9.343, "elevation_m": 2502}]
    fake_api.route("GET", "/maps/search", found)

    texts = plan_data(user.get("/routes/new").get_data(as_text=True))["layerTexts"]
    assert texts["search"]["url"] == "/map/search"
    assert (
        texts["search"]["kinds"]["peak"] == "Gipfel" and texts["search"]["kinds"]["hut"] == "Hütte"
    )

    answer = user.get("/map/search?q=santis&lat=47.2&lon=9.3&limit=8&other=1")
    assert answer.get_json() == found
    assert dict(fake_api.calls[-1].url.params) == {
        "q": "santis",
        "lat": "47.2",
        "lon": "9.3",
        "limit": "8",
    }
    # Too short for the API: no results instead of an error.
    fake_api.route("GET", "/maps/search", lambda r: httpx2.Response(422, json={}))
    assert user.get("/map/search?q=s").get_json() == []


def test_symbols_of_the_map_come_from_this_server(browser, fake_api):
    fake_api.route("GET", "/maps/info", {"style_url": "https://api.example/x", "tile_url": "t"})
    fake_api.route(
        "GET", "/maps/style.json", STYLE | {"sprite": "https://api.example/api/v1/maps/sprite"}
    )
    image = httpx2.Response(200, content=b"png", headers={"content-type": "image/png"})
    fake_api.route("GET", "/maps/sprite@2x.png", lambda r: image)
    fake_api.route("GET", "/maps/sprite.json", {"peak": {"x": 0}})

    assert browser.get("/map/style.json").get_json()["sprite"] == "http://localhost/map/sprite"
    assert browser.get("/map/sprite.json").get_json() == {"peak": {"x": 0}}
    double = browser.get("/map/sprite@2x.png")
    assert double.data == b"png" and double.mimetype == "image/png"
    assert browser.get("/map/sprite@9x.png").status_code == 404
    assert browser.get("/map/sprite.exe").status_code == 404
