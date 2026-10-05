import json
import logging
import re

import httpx2

from hiker_web.security import TokenRedactionFilter
from tests.conftest import error

TOKEN = "0b0e6a52-1d0f-4f0e-9d6e-3f0a1f6a9a11"
PUBLIC = {
    "title": "Säntis über Lisengrat",
    "summary": "Schöner Tag.",
    "owner_name": "Anna",
    "start_time": "2026-07-01T06:00:00Z",
    "end_time": "2026-07-01T13:30:00Z",
    "duration_minutes": 450,
    "pack_weight_start_g": 1600,
    "calories_eaten": 400.0,
    "calories_burned": None,
    "calories_burned_source": None,
    "start_point": {"lat": 47.28, "lon": 9.31, "name": None, "approximate": True},
    "end_point": None,
    "track_source": "device",
    "track_stats": {
        "distance_m": 12340.0,
        "ascent_m": 1210.0,
        "descent_m": 1180.0,
        "min_elevation_m": 1352.0,
        "max_elevation_m": 2502.0,
    },
    "photos": [
        {
            "index": 0,
            "caption": "Am Grat",
            "taken_at": None,
            "lat": None,
            "lon": None,
            "track_distance_m": 5100.0,
            "elevation_m": 2100.0,
            "is_cover": True,
        }
    ],
    "weather": [],
    "partners": ["Ben"],
    "peaks": [
        {"name": "Säntis", "elevation_m": 2502, "lat": 47.249, "lon": 9.343, "reached_at": None}
    ],
    "waypoints": [
        {
            "name": "Rotsteinpass",
            "kind": "saddle",
            "source": "osm",
            "reached_at": None,
            "description": None,
            "icon": None,
            "lat": 47.24,
            "lon": 9.36,
            "elevation_m": 2120.0,
        }
    ],
    "gear": [{"name": "Zelt", "brand": "MSR", "weight_g": 1500, "quantity": 1, "carried": True}],
    "food": [{"name": "Riegel", "amount_g": 100.0, "kcal": 400.0, "carried": True, "eaten": True}],
}


def text(response) -> str:
    return response.get_data(as_text=True)


def test_public_page_needs_no_login_and_is_not_indexed(browser, fake_api):
    fake_api.route("GET", f"/public/tours/{TOKEN}", PUBLIC)

    response = browser.get(f"/p/{TOKEN}")
    page = text(response)

    assert response.status_code == 200
    assert "Säntis über Lisengrat" in page and "von Anna" in page and "12,3 km" in page
    assert "Rotsteinpass" in page and "Zelt" in page and "Riegel" in page and "Ben" in page
    assert "ungefähr" in page and "© OpenStreetMap-Mitwirkende (ODbL)" in page
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Cache-Control"] == "no-store"
    assert '<meta name="robots" content="noindex, nofollow">' in page
    # Nothing of the signed-in area and no health data.
    assert (
        "Abmelden" not in page and "Verbrauch" not in page and "<dt>Herzfrequenz</dt>" not in page
    )
    assert "authorization" not in fake_api.calls[-1].headers
    data = json.loads(re.search(r'id="tour-data">(.*?)</script>', page, re.S).group(1))
    assert data["trackUrl"] == f"/p/{TOKEN}/track.json"
    assert data["photos"][0]["thumb"] == f"/p/{TOKEN}/photos/0?size=thumb"


def test_health_data_appears_only_if_the_link_allows_it(browser, fake_api):
    stats = {**PUBLIC["track_stats"], "heart_rate": {"avg": 128, "max": 171}}
    fake_api.route(
        "GET",
        f"/public/tours/{TOKEN}",
        {
            **PUBLIC,
            "calories_burned": 3210.0,
            "calories_burned_source": "estimated",
            "track_stats": stats,
        },
    )

    page = text(browser.get(f"/p/{TOKEN}"))

    assert "3.210 kcal" in page and "geschätzt" in page and "Ø 128, max. 171" in page
    assert "Nur für dich sichtbar" not in page


def test_unknown_revoked_or_malformed_links_are_not_found(browser, fake_api):
    fake_api.route("GET", "/public/tours/*", lambda r: error(404, "not_found"))

    assert browser.get(f"/p/{TOKEN}").status_code == 404
    assert browser.get("/p/not-a-token").status_code == 404
    assert browser.get("/p/not-a-token/photos/0").status_code == 404
    # A malformed token never reaches the API.
    assert len(fake_api.calls) == 1


def test_public_track_and_photos_are_passed_through(browser, fake_api):
    fake_api.route(
        "GET",
        f"/public/tours/{TOKEN}/track",
        {
            "source": "device",
            "stats": {},
            "series": {
                "distance_m": [0, 5],
                "lat": [47.0, 47.1],
                "lon": [9.0, 9.1],
                "elevation_m": None,
            },
        },
    )
    fake_api.route(
        "GET",
        f"/public/tours/{TOKEN}/photos/*",
        lambda r: httpx2.Response(
            200,
            content=b"IMG-" + r.url.params["size"].encode(),
            headers={"content-type": "image/jpeg"},
        ),
    )

    track = browser.get(f"/p/{TOKEN}/track.json")
    photo = browser.get(f"/p/{TOKEN}/photos/0?size=thumb")

    assert track.get_json()["series"]["lon"] == [9.0, 9.1]
    assert track.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert photo.data == b"IMG-thumb" and photo.mimetype == "image/jpeg"
    assert all("authorization" not in call.headers for call in fake_api.calls)


def test_rate_limit_of_the_api_is_reported(browser, fake_api):
    fake_api.route("GET", "/public/tours/*", lambda r: error(429, "rate_limited"))

    response = browser.get(f"/p/{TOKEN}")

    assert response.status_code == 429 and "Zu viele Versuche" in text(response)


def test_link_tokens_stay_out_of_the_log():
    record = logging.LogRecord(
        "werkzeug",
        logging.INFO,
        "",
        0,
        '%s - "%s" %s',
        ("127.0.0.1", f"GET /p/{TOKEN}/photos/0?size=thumb HTTP/1.1", "200"),
        None,
    )

    TokenRedactionFilter().filter(record)

    assert TOKEN not in record.getMessage()
    assert "/p/[redacted]/photos/0" in record.getMessage()


def test_map_tiles_are_passed_through_without_login(browser, fake_api, app):
    fake_api.route(
        "GET",
        "/maps/tiles/12/2150/1440.png",
        lambda r: httpx2.Response(
            200,
            content=b"PNG",
            headers={"content-type": "image/png", "cache-control": "public, max-age=86400"},
        ),
    )

    tile = browser.get("/tiles/12/2150/1440.png")
    missing = browser.get("/tiles/12/1/1.png")

    assert tile.data == b"PNG" and tile.mimetype == "image/png"
    assert tile.headers["Cache-Control"] == "public, max-age=86400"
    assert "authorization" not in fake_api.calls[0].headers
    assert missing.status_code == 404
    assert browser.get("/tiles/12/x/1.png").status_code == 404


def test_foreign_tile_source_is_allowed_by_the_security_policy(fake_api, tmp_path):
    from hiker_web import create_app

    app = create_app(
        {
            "SECRET_KEY": "test-secret-key-not-for-production-0123456789",
            "SESSION_DIR": str(tmp_path / "sessions"),
            "API_TRANSPORT": fake_api.transport,
            "MAP_TILE_URL": "https://tiles.example.org/{z}/{x}/{y}.png",
        }
    )

    policy = app.test_client().get("/login").headers["Content-Security-Policy"]

    assert "img-src 'self' data: blob: https://tiles.example.org" in policy
