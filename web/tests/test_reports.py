import json
import re

import httpx2

from hiker_web.views.reports import _weeks

TOUR_ID = "77777777-7777-4777-8777-777777777777"
WISH_ID = "88888888-8888-4888-8888-888888888888"
TOTALS = {
    "tours": 5,
    "tours_with_track": 3,
    "days": 4,
    "distance_m": 33500,
    "ascent_m": 2900,
    "descent_m": 2800,
    "moving_time_s": 36000,
    "peaks": 2,
}
DAY = {
    "date": "2026-07-18",
    "tours": 1,
    "distance_m": 12300,
    "ascent_m": 1100,
    "tour_ids": [TOUR_ID],
}
PEAK = {
    "name": "Säntis",
    "elevation_m": 2502,
    "lat": 47.2494,
    "lon": 9.3433,
    "count": 2,
    "first": "2025-07-01T06:00:00Z",
    "last": "2026-07-18T06:00:00Z",
    "visits": [{"tour_id": TOUR_ID, "title": "Gipfeltag", "date": "2026-07-18T06:00:00Z"}],
}
WISH = {
    "id": WISH_ID,
    "name": "Piz Bernina",
    "elevation_m": 4049,
    "lat": 46.3824,
    "lon": 9.908,
    "note": "Biancograt",
    "created_at": "2026-10-05T10:00:00Z",
    "climbed": False,
    "climbed_on": None,
}


def reports_api(fake_api):
    fake_api.route("GET", "/reports/summary", {"total": TOTALS, "years": [TOTALS | {"year": 2026}]})
    fake_api.route("GET", "/reports/peaks", [PEAK])
    fake_api.route("GET", "/reports/calendar", {"year": 2026, "years": [2026, 2025], "days": [DAY]})
    fake_api.route(
        "GET", "/reports/wishes", [WISH, WISH | {"id": "x", "name": "Säntis", "climbed": True}]
    )


def text(response) -> str:
    return response.get_data(as_text=True)


def test_the_year_is_laid_out_in_weeks():
    weeks = _weeks(2026, [DAY])

    # 2026 starts on a Thursday: the first column is empty down to it.
    assert weeks[0][:3] == [None, None, None] and weeks[0][3]["date"].isoformat() == "2026-01-01"
    assert all(len(week) == 7 for week in weeks) and 52 <= len(weeks) <= 54
    cells = [cell for week in weeks for cell in week if cell]
    assert len(cells) == 365
    out = next(cell for cell in cells if cell["day"])
    # 1100 m up: the third of four colour levels.
    assert out["date"].isoformat() == "2026-07-18" and out["level"] == 3
    assert sum(cell["level"] for cell in cells) == 3


def test_statistics_show_totals_calendar_peaks_and_wishes(user, fake_api):
    reports_api(fake_api)

    page = text(user.get("/stats/"))

    assert 'href="/stats/"' in page and "Statistik" in page
    assert "33,5 km" in page and "2.900 m" in page and "2.800 m" in page and "10 h" in page
    assert "2 Touren haben keinen Track" in page
    # The calendar: the day out is a link to its tour, coloured by its ascent.
    assert "Tage unterwegs 2026" in page
    assert re.search(rf'<a class="l3" href="/tours/{TOUR_ID}" title="18.07.2026: 12,3 km', page)
    assert 'href="/stats/?year=2025#calendar"' in page
    # Climbed peaks and wishes.
    assert "Bestiegene Gipfel (1)" in page and "Säntis" in page and "2.502 m" in page
    assert "Piz Bernina" in page and "Biancograt" in page and "bestiegen" in page
    assert f'action="/stats/wishes/{WISH_ID}/delete"' in page
    data = json.loads(re.search(r'id="stats-data">(.*?)</script>', page, re.S).group(1))
    assert data["tracksUrl"] == "/stats/tracks.geojson" and "stats.js" in page

    user.get("/stats/?year=2025")
    assert fake_api.last("GET", "/reports/calendar").url.params["year"] == "2025"


def test_a_wish_from_the_map_is_filled_in_and_saved(user, fake_api):
    reports_api(fake_api)
    fake_api.route("POST", "/reports/wishes", lambda r: httpx2.Response(201, json=WISH))
    fake_api.route("DELETE", "/reports/wishes/*", lambda r: httpx2.Response(204))

    page = text(user.get("/stats/?wish_name=Eiger&wish_ele=3970&wish_lat=46.5776&wish_lon=8.0053"))
    assert 'value="Eiger"' in page and 'value="3970"' in page and 'value="46.5776"' in page

    saved = user.post(
        "/stats/wishes",
        {"name": "Eiger", "elevation_m": "3970", "lat": "46,5776", "lon": "8.0053", "note": ""},
    )
    assert saved.status_code == 302 and saved.headers["Location"] == "/stats/#wishes"
    assert fake_api.body() == {
        "name": "Eiger",
        "elevation_m": 3970,
        "lat": 46.5776,
        "lon": 8.0053,
        "note": None,
    }
    assert user.post("/stats/wishes", {"name": "X", "lat": "abc"}).status_code == 302

    assert user.post(f"/stats/wishes/{WISH_ID}/delete").status_code == 302
    assert f"DELETE /reports/wishes/{WISH_ID}" in fake_api.requested()


def test_tracks_are_passed_on_and_the_pages_need_the_module(user, fake_api, browser):
    lines = {"type": "FeatureCollection", "features": []}
    fake_api.route("GET", "/reports/tracks", lines)
    assert user.get("/stats/tracks.geojson").get_json() == lines

    fake_api.modules.remove("reports")
    browser.login()
    assert browser.get("/stats/").status_code == 404
