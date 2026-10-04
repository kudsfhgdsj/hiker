import json
import re

import httpx2

from tests.conftest import error

ROUTE_ID = "55555555-5555-4555-8555-555555555555"
WAYPOINTS = [
    {"lat": 47.0, "lon": 9.0, "name": "Parkplatz", "direct": False},
    {"lat": 47.01, "lon": 9.0, "name": None, "direct": True},
]
SERIES = {
    "distance_m": [0, 1112],
    "lat": [47.0, 47.01],
    "lon": [9.0, 9.0],
    "elevation_m": [1000, 1100],
}
STATS = {
    "distance_m": 1112,
    "ascent_m": 100,
    "descent_m": 0,
    "min_elevation_m": 1000,
    "max_elevation_m": 1100,
    "duration_s": 2000,
    "duration_estimated": True,
}
ROUTE = {
    "id": ROUTE_ID,
    "title": "Auf den Gipfel",
    "description": "Über die Hütte",
    "planned_date": "2026-07-18",
    "profile": "hiking",
    "max_difficulty": 4,
    "via_ferrata": True,
    "engine": "brouter+direct",
    "version": 3,
    "waypoints": WAYPOINTS,
    "series": SERIES,
    **STATS,
}
INFO = {
    "routing_available": True,
    "profiles": [{"id": "hiking", "available": True}, {"id": "direct", "available": True}],
    "difficulties": [
        {"level": level, "code": f"T{level}", "sac_scale": "x"} for level in range(1, 7)
    ],
    "attribution": "Wegführung: BRouter, Daten © OpenStreetMap-Mitwirkende (ODbL)",
    "max_waypoints": 100,
}


def text(response) -> str:
    return response.get_data(as_text=True)


def planning_api(fake_api, info=INFO):
    fake_api.route("GET", "/planning/info", info)
    fake_api.route(
        "GET", "/planning/routes", {"items": [ROUTE], "total": 1, "limit": 200, "offset": 0}
    )
    fake_api.route("GET", "/planning/routes/*", ROUTE)


def plan_data(page: str) -> dict:
    return json.loads(re.search(r'id="plan-data">(.*?)</script>', page, re.S).group(1))


def form(**overrides) -> dict:
    return {
        "title": "Auf den Gipfel",
        "description": "",
        "planned_date": "2026-07-18",
        "profile": "hiking",
        "max_difficulty": "4",
        "via_ferrata": "1",
        "waypoints": json.dumps(WAYPOINTS),
    } | overrides


def test_navigation_and_list_show_the_routes(user, fake_api):
    planning_api(fake_api)

    page = text(user.get("/routes/"))

    assert 'href="/routes/"' in page and "Planung" in page
    assert "Auf den Gipfel" in page and "18.07.2026" in page
    assert "1,1 km" in page and "100 m" in page and "33 min" in page


def test_pages_do_not_exist_without_the_module(browser, fake_api):
    fake_api.modules.remove("planning")
    browser.login()

    assert browser.get("/routes/").status_code == 404
    assert 'href="/routes/"' not in text(browser.get("/gear/"))


def test_new_route_opens_an_empty_planner(user, fake_api):
    planning_api(fake_api)

    page = text(user.get("/routes/new"))

    data = plan_data(page)
    assert data["route"]["waypoints"] == [] and data["route"]["series"] is None
    assert data["previewUrl"] == "/routes/preview" and data["routingAvailable"] is True
    # All levels of the SAC scale, T3 chosen, via ferratas off.
    assert "T1 – Wanderung" in page and "T6 – Äußerst schwierige Bergtour" in page
    assert re.search(r'<option value="3" selected>', page)
    assert 'name="via_ferrata" id="plan-ferrata" value="1">' in page
    assert "OpenStreetMap" in page


def test_planner_without_routing_offers_straight_lines_only(user, fake_api):
    planning_api(fake_api, INFO | {"routing_available": False, "attribution": None})

    page = text(user.get("/routes/new"))

    assert "keine Wegführung eingerichtet" in page
    assert re.search(r'<option value="hiking" disabled>', page)
    assert re.search(r'<option value="direct" selected>', page)


def test_stored_route_is_shown_with_its_line(user, fake_api):
    planning_api(fake_api)

    page = text(user.get(f"/routes/{ROUTE_ID}"))

    data = plan_data(page)
    assert data["route"]["waypoints"] == WAYPOINTS and data["route"]["series"] == SERIES
    assert data["route"]["duration_s"] == 2000
    assert 'name="version" value="3"' in page
    assert re.search(r'<option value="4" selected>', page)
    assert 'value="1" checked>' in page
    assert f'href="/routes/{ROUTE_ID}/gpx"' in page and "geschätzt" in page


def test_preview_passes_the_waypoints_on_and_needs_the_csrf_token(user, fake_api):
    planning_api(fake_api)
    fake_api.route("POST", "/planning/preview", {"engine": "brouter", "series": SERIES, **STATS})
    body = {"profile": "hiking", "max_difficulty": 2, "via_ferrata": False, "waypoints": WAYPOINTS}

    refused = user.client.post("/routes/preview", json=body)
    assert refused.status_code == 400

    response = user.client.post("/routes/preview", json=body, headers={"X-CSRF-Token": user.csrf()})

    assert response.status_code == 200 and response.get_json()["distance_m"] == 1112
    assert fake_api.body() == body


def test_preview_names_the_reason_when_there_is_no_route(user, fake_api):
    planning_api(fake_api)
    fake_api.route("POST", "/planning/preview", lambda r: error(422, "no_route"))

    response = user.client.post(
        "/routes/preview", json={"waypoints": WAYPOINTS}, headers={"X-CSRF-Token": user.csrf()}
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == "no_route"
    assert "keinen Weg" in response.get_json()["message"]


def test_saving_a_new_route_sends_everything_to_the_api(user, fake_api):
    planning_api(fake_api)
    fake_api.route("POST", "/planning/routes", lambda r: httpx2.Response(201, json=ROUTE))

    response = user.post("/routes/new", form())

    assert response.status_code == 302 and response.headers["Location"] == f"/routes/{ROUTE_ID}"
    assert fake_api.body() == {
        "title": "Auf den Gipfel",
        "description": None,
        "planned_date": "2026-07-18",
        "profile": "hiking",
        "max_difficulty": 4,
        "via_ferrata": True,
        "waypoints": WAYPOINTS,
    }


def test_saving_a_change_sends_the_version(user, fake_api):
    planning_api(fake_api)
    fake_api.route("PUT", "/planning/routes/*", ROUTE)

    response = user.post(
        f"/routes/{ROUTE_ID}", form(version="3", profile="direct", via_ferrata=None)
    )

    assert response.status_code == 302
    sent = fake_api.body()
    assert sent["version"] == 3 and sent["profile"] == "direct" and sent["via_ferrata"] is False


def test_rejected_route_keeps_what_was_entered(user, fake_api):
    planning_api(fake_api)
    fake_api.route("POST", "/planning/routes", lambda r: error(422, "no_route"))

    response = user.post("/routes/new", form(title="Mein Plan"))

    page = text(response)
    assert response.status_code == 422 and "keinen Weg" in page
    assert 'value="Mein Plan"' in page and plan_data(page)["route"]["waypoints"] == WAYPOINTS

    fake_api.route("PUT", "/planning/routes/*", lambda r: error(409, "version_conflict"))
    response = user.post(f"/routes/{ROUTE_ID}", form(version="2"))
    assert response.status_code == 409 and "inzwischen geändert" in text(response)

    response = user.post("/routes/new", form(waypoints="not json"))
    assert response.status_code == 422


def test_delete_and_gpx_download(user, fake_api):
    planning_api(fake_api)
    fake_api.route("DELETE", "/planning/routes/*", lambda r: httpx2.Response(204))
    fake_api.route(
        "GET",
        "/planning/routes/*/gpx",
        lambda r: httpx2.Response(
            200,
            content=b"<gpx/>",
            headers={
                "content-type": "application/gpx+xml",
                "content-disposition": 'attachment; filename="route.gpx"',
            },
        ),
    )

    download = user.get(f"/routes/{ROUTE_ID}/gpx")
    assert download.data == b"<gpx/>" and "route.gpx" in download.headers["Content-Disposition"]

    response = user.post(f"/routes/{ROUTE_ID}/delete")
    assert response.status_code == 302 and response.headers["Location"] == "/routes/"
    assert f"DELETE /planning/routes/{ROUTE_ID}" in fake_api.requested()
