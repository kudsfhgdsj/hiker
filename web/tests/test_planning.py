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
PACE = {
    "preset": "sac",
    "name": None,
    "ascent_m_per_h": 400,
    "descent_m_per_h": 800,
    "distance_km_per_h": 4,
}
SAVED_PACE = {
    "id": "66666666-6666-4666-8666-666666666666",
    "name": "Mit Kindern",
    "ascent_m_per_h": 250,
    "descent_m_per_h": 400,
    "distance_km_per_h": 3,
}
TOUR_ID = "77777777-7777-4777-8777-777777777777"
LINKED_TOUR = {"tour_id": TOUR_ID, "title": "Auf den Gipfel", "start_time": None, "has_track": True}
ROUTE = {
    "id": ROUTE_ID,
    "title": "Auf den Gipfel",
    "description": "Über die Hütte",
    "tags": ["Sommer", "Gipfel"],
    "start_time": "2026-07-18T05:30:00Z",
    "profile": "hiking",
    "max_difficulty": 4,
    "via_ferrata": True,
    "pace": PACE,
    "sun": None,
    "engine": "brouter+direct",
    "version": 3,
    "waypoints": WAYPOINTS,
    "series": SERIES,
    **STATS,
}
INFO = {
    "routing_available": True,
    "paces": [
        {"id": "dav", "ascent_m_per_h": 300, "descent_m_per_h": 500, "distance_km_per_h": 4},
        {"id": "sac", "ascent_m_per_h": 400, "descent_m_per_h": 800, "distance_km_per_h": 4},
        {"id": "pro", "ascent_m_per_h": 600, "descent_m_per_h": 1000, "distance_km_per_h": 6},
    ],
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
    fake_api.route("GET", "/planning/paces", [SAVED_PACE])
    fake_api.route("GET", "/planning/routes/*/tours", [LINKED_TOUR])


def plan_data(page: str) -> dict:
    return json.loads(re.search(r'id="plan-data">(.*?)</script>', page, re.S).group(1))


def form(**overrides) -> dict:
    return {
        "title": "Auf den Gipfel",
        "description": "",
        "tags": "Sommer, Gipfel, ",
        "start_time": "2026-07-18T05:30:00.000Z",
        "pace_preset": "sac",
        "pace_ascent": "400",
        "pace_descent": "800",
        "pace_distance": "4",
        "pace_name": "",
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
    assert 'href="/routes/?tag=Sommer"' in page
    assert "1,1 km" in page and "100 m" in page and "33 min" in page


def test_list_can_be_narrowed_to_a_tag(user, fake_api):
    planning_api(fake_api)

    page = text(user.get("/routes/?tag=Gipfel"))

    assert fake_api.last("GET", "/planning/routes").url.params["tag"] == "Gipfel"
    assert "Routen mit dem Tag „Gipfel“" in page


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
    assert 'id="plan-ferrata" value="1" form="plan-form">' in page
    assert "OpenStreetMap" in page
    # The paces for the walking time: built in, own values, and the saved ones of the user.
    assert re.search(r'<option value="dav"[^>]*selected>DAV', page)
    assert "SAC: 400 Hm auf" in page and "Profi: 600 Hm auf" in page and "Individuell" in page
    assert re.search(r'<option value="saved:6666[^>]*data-name="Mit Kindern"', page)
    # No planned date any more; tags and the start instead.
    assert "planned_date" not in page and 'name="tags"' in page and 'id="plan-start"' in page


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
    assert 'id="plan-ferrata" value="1" form="plan-form" checked>' in page
    assert f'href="/routes/{ROUTE_ID}/gpx"' in page and "geschätzt" in page
    assert 'value="Sommer, Gipfel"' in page
    assert 'id="plan-start-utc" value="2026-07-18T05:30:00Z"' in page
    assert re.search(r'<option value="sac"[^>]*selected>', page)
    assert data["route"]["start_time"] == "2026-07-18T05:30:00Z"


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
        "tags": ["Sommer", "Gipfel"],
        "start_time": "2026-07-18T05:30:00.000Z",
        "profile": "hiking",
        "max_difficulty": 4,
        "via_ferrata": True,
        "pace": {"preset": "sac"},
        "waypoints": WAYPOINTS,
    }


def test_own_and_saved_paces_are_sent_with_their_values(user, fake_api):
    planning_api(fake_api)
    fake_api.route("POST", "/planning/routes", lambda r: httpx2.Response(201, json=ROUTE))
    values = {"pace_ascent": "250", "pace_descent": "400", "pace_distance": "3,5"}

    user.post("/routes/new", form(pace_preset="custom", start_time="", tags="", **values))
    sent = fake_api.body()
    assert sent["pace"] == {
        "preset": "custom",
        "ascent_m_per_h": 250,
        "descent_m_per_h": 400,
        "distance_km_per_h": 3.5,
    }
    assert sent["start_time"] is None and sent["tags"] == []

    saved = form(pace_preset=f"saved:{SAVED_PACE['id']}", pace_name="Mit Kindern", **values)
    user.post("/routes/new", saved)
    assert fake_api.body()["pace"]["preset"] == "custom"
    assert fake_api.body()["pace"]["name"] == "Mit Kindern"


def test_paces_are_saved_and_deleted_through_the_api(user, fake_api):
    planning_api(fake_api)
    fake_api.route("POST", "/planning/paces", lambda r: httpx2.Response(201, json=SAVED_PACE))
    fake_api.route("DELETE", "/planning/paces/*", lambda r: httpx2.Response(204))
    body = {k: SAVED_PACE[k] for k in SAVED_PACE if k != "id"}
    token = {"X-CSRF-Token": user.csrf()}

    assert user.client.post("/routes/paces", json=body).status_code == 400
    response = user.client.post("/routes/paces", json=body, headers=token)
    assert response.status_code == 201 and response.get_json()["id"] == SAVED_PACE["id"]
    assert fake_api.body() == body

    gone = user.client.post(f"/routes/paces/{SAVED_PACE['id']}/delete", json={}, headers=token)
    assert gone.status_code == 204
    assert f"DELETE /planning/paces/{SAVED_PACE['id']}" in fake_api.requested()


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
    assert 'value="Sommer, Gipfel"' in page and re.search(
        r'<option value="sac"[^>]*selected>', page
    )

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


def test_a_tour_is_started_from_the_route_and_compared_with_it(user, fake_api):
    planning_api(fake_api)
    fake_api.route(
        "POST", "/planning/routes/*/tour", lambda r: httpx2.Response(201, json=LINKED_TOUR)
    )
    compared = {
        "route_id": ROUTE_ID,
        "tour_id": TOUR_ID,
        "tour_title": "Auf den Gipfel",
        "planned": {
            **{k: STATS[k] for k in ("distance_m", "ascent_m", "descent_m", "duration_s")},
            "total_time_s": None,
        },
        "actual": {
            "distance_m": 1300,
            "ascent_m": 120,
            "descent_m": 10,
            "duration_s": 2400,
            "total_time_s": 3000,
        },
        "deviation": {"mean_m": 35, "max_m": 150, "on_plan_share": 0.8},
        "track": {
            "distance_m": [0, 1300],
            "lat": [47.0, 47.011],
            "lon": [9.0, 9.001],
            "elevation_m": None,
        },
    }
    fake_api.route("GET", "/planning/routes/*/comparison/*", compared)

    # The planner lists the tours of the route.
    page = text(user.get(f"/routes/{ROUTE_ID}"))
    assert "Touren zu dieser Route" in page
    assert (
        f'href="/routes/{ROUTE_ID}/compare/{TOUR_ID}"' in page
        and f'href="/tours/{TOUR_ID}"' in page
    )

    made = user.post(f"/routes/{ROUTE_ID}/tour")
    assert made.status_code == 302 and made.headers["Location"] == f"/tours/{TOUR_ID}"
    assert f"POST /planning/routes/{ROUTE_ID}/tour" in fake_api.requested()

    page = text(user.get(f"/routes/{ROUTE_ID}/compare/{TOUR_ID}"))
    assert "Geplant" in page and "Gegangen" in page
    assert "1,1 km" in page and "1,3 km" in page and "33 min" in page and "40 min" in page
    assert "im Mittel 35 m" in page and "höchstens 150 m" in page and "80 %" in page
    data = json.loads(re.search(r'id="compare-data">(.*?)</script>', page, re.S).group(1))
    assert data["plan"] == {"lat": SERIES["lat"], "lon": SERIES["lon"]}
    assert data["track"] == {"lat": [47.0, 47.011], "lon": [9.0, 9.001]}

    # A tour without a track: only the plan, with a hint.
    fake_api.route(
        "GET",
        "/planning/routes/*/comparison/*",
        compared | {"actual": None, "deviation": None, "track": None},
    )
    page = text(user.get(f"/routes/{ROUTE_ID}/compare/{TOUR_ID}"))
    assert "noch keinen Track" in page


def test_a_gpx_file_is_imported_as_a_route(user, fake_api):
    import io

    planning_api(fake_api)
    fake_api.route("POST", "/planning/routes/import", lambda r: httpx2.Response(201, json=ROUTE))

    assert "GPX-Datei als Route importieren" in text(user.get("/routes/"))
    upload = {"file": (io.BytesIO(b"<gpx/>"), "runde.gpx")}
    response = user.post("/routes/import", upload, content_type="multipart/form-data")

    assert response.status_code == 302 and response.headers["Location"] == f"/routes/{ROUTE_ID}"
    sent = fake_api.last("POST", "/planning/routes/import")
    assert b"runde.gpx" in sent.content and b"<gpx/>" in sent.content

    # Not a GPX file: back to the list with the reason.
    fake_api.route("POST", "/planning/routes/import", lambda r: error(422, "invalid_gpx"))
    upload = {"file": (io.BytesIO(b"x"), "x.gpx")}
    response = user.post("/routes/import", upload, content_type="multipart/form-data")
    assert response.status_code == 302 and response.headers["Location"] == "/routes/"
    assert user.post("/routes/import", {}).headers["Location"] == "/routes/"
