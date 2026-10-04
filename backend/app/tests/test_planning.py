import uuid
from datetime import date
from xml.etree import ElementTree

import httpx2
import pytest

from app.core.config import get_settings
from app.core.errors import UnprocessableError
from app.core.sun import sun_position, sun_times
from app.modules.planning.estimate import PRESETS, Pace, walking_time_s
from app.modules.planning.routing import BRouterEngine, RouteOptions, RoutingUnavailableError
from app.modules.protocols.track import haversine_m
from app.tests.conftest import auth_header, register

ROUTES = "/api/v1/planning/routes"
PREVIEW = "/api/v1/planning/preview"
START = {"lat": 47.0, "lon": 9.0, "name": "Parkplatz"}
HUT = {"lat": 47.01, "lon": 9.0, "name": "Hütte"}
PEAK = {"lat": 47.02, "lon": 9.01, "name": "Gipfel"}


@pytest.fixture
def anna(client):
    return auth_header(register(client))


@pytest.fixture
def ben(client):
    return auth_header(register(client, email="ben@example.org", display_name="Ben"))


def create(client, headers, **overrides):
    body = {"title": "Auf den Gipfel", "waypoints": [START, HUT, PEAK]} | overrides
    response = client.post(ROUTES, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Walking time ---


def test_walking_time_follows_din_33466():
    # 8 km are 2 h, 600 m up are 2 h: the larger counts in full, the smaller by half.
    assert walking_time_s(8000, 600, 0) == 3 * 3600
    # 4 km (1 h) with 900 m up (3 h) and 500 m down (1 h): 4 h + 0.5 h.
    assert walking_time_s(4000, 900, 500) == 4.5 * 3600
    # Without elevation only the distance counts.
    assert walking_time_s(6000, None, None) == 1.5 * 3600


def test_walking_time_follows_the_pace():
    # 8 km, 1200 m up, 400 m down.
    assert walking_time_s(8000, 1200, 400, PRESETS["dav"]) == round((4.8 + 1.0) * 3600)
    assert walking_time_s(8000, 1200, 400, PRESETS["sac"]) == round((3.5 + 1.0) * 3600)
    # Trained walkers: 600 m up, 1000 m down, 6 km per hour.
    assert walking_time_s(8000, 1200, 400, PRESETS["pro"]) == round((2.4 + 8 / 6 / 2) * 3600)
    assert walking_time_s(8000, 1200, 400, Pace(1200, 800, 8)) == round((1.5 + 0.5) * 3600)


# --- Sun, start time, tags ---


def test_sunrise_and_sunset_match_the_almanac():
    # Säntis at midsummer and midwinter (UTC; local time is two and one hour later).
    summer = sun_times(47.2494, 9.3433, date(2026, 6, 21))
    assert summer.sunrise.strftime("%H:%M") == "03:26"
    assert summer.sunset.strftime("%H:%M") == "19:22"
    assert summer.dawn < summer.sunrise < summer.noon < summer.sunset < summer.dusk
    winter = sun_times(47.2494, 9.3433, date(2026, 12, 21))
    assert winter.sunrise.strftime("%H:%M") == "07:06"
    assert winter.sunset.strftime("%H:%M") == "15:34"
    # North of the polar circle the sun does not set in summer.
    assert sun_times(78.2, 15.6, date(2026, 6, 21)).sunrise is None
    # At noon the sun stands in the south, high in summer.
    height, direction = sun_position(47.2494, 9.3433, summer.noon)
    assert 65 < height < 67 and 179 <= direction <= 181


def test_line_carries_the_time_at_every_point(client, anna):
    body = client.post(PREVIEW, json={"waypoints": [START, HUT, PEAK]}, headers=anna).json()

    times = body["series"]["time_s"]
    assert len(times) == len(body["series"]["lat"])
    assert times[0] == 0 and times[-1] == body["duration_s"] and times == sorted(times)
    assert body["sun"] is None

    faster = client.post(
        PREVIEW, json={"waypoints": [START, HUT, PEAK], "pace": {"preset": "pro"}}, headers=anna
    ).json()
    assert faster["series"]["time_s"][2] < times[2]


def test_start_time_places_the_tour_in_the_day(client, anna):
    # Setting out at 04:00 UTC in June: after first light, before sunrise.
    early = {"waypoints": [START, HUT, PEAK], "start_time": "2026-06-21T03:00:00Z"}
    sun = client.post(PREVIEW, json=early, headers=anna).json()["sun"]

    assert sun["sunrise"].startswith("2026-06-21T03:2") and sun["sunset"].startswith(
        "2026-06-21T19:2"
    )
    assert sun["starts_in_dark"] is False and sun["ends_in_dark"] is False
    assert sun["daylight_left_s"] > 10 * 3600
    assert sun["summit"]["elevation_m"] == 1900 and sun["summit"]["time"] == sun["end_time"]
    assert 0 < sun["summit"]["sun_height_deg"] < 40

    # In December at 15:00 UTC the sun sets during the tour and it ends in the dark.
    late = create(client, anna, start_time="2026-12-21T15:00:00Z")
    assert late["start_time"] == "2026-12-21T15:00:00Z"
    assert late["sun"]["daylight_left_s"] < 0 and late["sun"]["ends_in_dark"] is True
    night = {"waypoints": [START, HUT], "start_time": "2026-12-21T04:00:00Z"}
    assert client.post(PREVIEW, json=night, headers=anna).json()["sun"]["starts_in_dark"] is True
    # A time without zone is not accepted: the sun needs to know which moment is meant.
    naive = {"waypoints": [START, HUT], "start_time": "2026-12-21T04:00:00"}
    assert client.post(PREVIEW, json=naive, headers=anna).status_code == 422


def test_routes_are_found_by_tag(client, anna):
    create(client, anna, title="Säntis", tags=["Sommer", "Gipfel"])
    create(client, anna, title="Piz Palü", tags=["Skitour"])
    create(client, anna, title="Ohne")

    summer = client.get(ROUTES, params={"tag": "sommer"}, headers=anna).json()
    assert [item["title"] for item in summer["items"]] == ["Säntis"] and summer["total"] == 1
    assert summer["items"][0]["tags"] == ["Sommer", "Gipfel"]
    assert client.get(ROUTES, params={"tag": "Winter"}, headers=anna).json()["total"] == 0
    assert client.get(ROUTES, headers=anna).json()["total"] == 3

    too_many = {"title": "x", "waypoints": [START, HUT], "tags": [str(n) for n in range(21)]}
    assert client.post(ROUTES, json=too_many, headers=anna).status_code == 422


# --- Pace ---

SLOW = {
    "preset": "custom",
    "name": "Mit Kindern",
    "ascent_m_per_h": 200,
    "descent_m_per_h": 300,
    "distance_km_per_h": 3,
}


def test_preview_and_route_use_the_chosen_pace(client, anna, routing_engine):
    body = {"waypoints": [START, HUT, PEAK]}
    dav = client.post(PREVIEW, json=body, headers=anna).json()
    sac = client.post(PREVIEW, json=body | {"pace": {"preset": "sac"}}, headers=anna).json()
    assert sac["duration_s"] == walking_time_s(sac["distance_m"], 400, 0, PRESETS["sac"])
    assert sac["duration_s"] < dav["duration_s"]

    route = create(client, anna, pace=SLOW)
    assert route["pace"] == SLOW
    assert route["duration_s"] == walking_time_s(route["distance_m"], 400, 0, Pace(200, 300, 3))

    # A preset brings its own values, whatever else is sent; a new pace needs no new line.
    calls = len(routing_engine.calls)
    update = {
        "title": route["title"],
        "waypoints": route["waypoints"],
        "version": 1,
        "pace": {"preset": "pro", "ascent_m_per_h": 50},
    }
    changed = client.put(f"{ROUTES}/{route['id']}", json=update, headers=anna).json()
    assert changed["pace"] == {
        "preset": "pro",
        "name": None,
        "ascent_m_per_h": 600,
        "descent_m_per_h": 1000,
        "distance_km_per_h": 6,
    }
    assert changed["duration_s"] < route["duration_s"] and len(routing_engine.calls) == calls

    # Without a word about the pace: the German standard.
    assert create(client, anna)["pace"]["preset"] == "dav"
    crawl = {"waypoints": [START, HUT], "pace": {"preset": "custom", "ascent_m_per_h": 10}}
    assert client.post(PREVIEW, json=crawl, headers=anna).status_code == 422


def test_info_lists_the_built_in_paces(client, anna):
    info = client.get("/api/v1/planning/info", headers=anna).json()
    paces = {pace["id"]: pace for pace in info["paces"]}
    assert paces["dav"] == {
        "id": "dav",
        "ascent_m_per_h": 300,
        "descent_m_per_h": 500,
        "distance_km_per_h": 4,
    }
    assert paces["sac"]["ascent_m_per_h"] == 400 and paces["sac"]["descent_m_per_h"] == 800
    assert paces["pro"]["ascent_m_per_h"] == 600 and paces["pro"]["distance_km_per_h"] == 6


def test_own_paces_are_saved_under_a_name_and_stay_private(client, anna, ben):
    paces = "/api/v1/planning/paces"
    values = {"ascent_m_per_h": 250, "descent_m_per_h": 400, "distance_km_per_h": 3.5}
    body = {"name": " Gemütlich ", **values}

    created = client.post(paces, json=body, headers=anna)
    assert created.status_code == 201 and created.json()["name"] == "Gemütlich"
    pace_id = created.json()["id"]
    client.post(paces, json=body | {"name": "Alpin"}, headers=anna)

    names = [pace["name"] for pace in client.get(paces, headers=anna).json()]
    assert names == ["Alpin", "Gemütlich"]
    # Only the one who made it sees, changes or deletes it.
    assert client.get(paces, headers=ben).json() == []
    assert client.put(f"{paces}/{pace_id}", json=body, headers=ben).status_code == 404
    assert client.delete(f"{paces}/{pace_id}", headers=ben).status_code == 404
    assert client.get(paces).status_code == 401

    changed = client.put(f"{paces}/{pace_id}", json=body | {"ascent_m_per_h": 280}, headers=anna)
    assert changed.status_code == 200 and changed.json()["ascent_m_per_h"] == 280
    assert client.post(paces, json=body | {"ascent_m_per_h": 5}, headers=anna).status_code == 422

    # A route keeps the values it was computed with when the saved pace goes.
    route = create(client, anna, pace={"preset": "custom", "name": "Gemütlich", **values})
    assert client.delete(f"{paces}/{pace_id}", headers=anna).status_code == 204
    assert [pace["name"] for pace in client.get(paces, headers=anna).json()] == ["Alpin"]
    kept = client.get(f"{ROUTES}/{route['id']}", headers=anna).json()["pace"]
    assert kept["name"] == "Gemütlich" and kept["ascent_m_per_h"] == 250


def test_paces_are_part_of_the_offline_sync(client, anna, ben):
    pace_id = str(uuid.uuid4())
    data = {
        "name": "Offline",
        "ascent_m_per_h": 350,
        "descent_m_per_h": 600,
        "distance_km_per_h": 4,
    }
    body = {"operations": [{"collection": "paces", "op": "upsert", "id": pace_id, "data": data}]}

    result = client.post("/api/v1/sync/push", json=body, headers=anna).json()["results"][0]
    assert result["status"] == "ok" and result["record"]["name"] == "Offline"

    changes = client.get("/api/v1/sync/changes", headers=anna).json()["collections"]["paces"]
    assert [pace["id"] for pace in changes["changed"]] == [pace_id]
    others = client.get("/api/v1/sync/changes", headers=ben).json()["collections"]["paces"]
    assert others["changed"] == []
    # Someone else cannot overwrite it through the sync.
    foreign = client.post("/api/v1/sync/push", json=body, headers=ben).json()["results"][0]
    assert foreign["status"] == "error"


# --- Preview ---


def test_preview_follows_the_paths_and_estimates_the_time(client, anna, routing_engine):
    response = client.post(PREVIEW, json={"waypoints": [START, HUT, PEAK]}, headers=anna)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine"] == "brouter"
    # All legs go to the engine in one request, in the order of the waypoints.
    assert routing_engine.calls == [([(47.0, 9.0), (47.01, 9.0), (47.02, 9.01)], "hiking")]
    series = body["series"]
    assert len(series["lat"]) == len(series["lon"]) == len(series["distance_m"]) == 5
    assert series["elevation_m"][0] == 1500 and series["elevation_m"][-1] == 1900
    # The path bends, so it is longer than the straight line.
    assert body["distance_m"] > haversine_m(47.0, 9.0, 47.01, 9.0) + haversine_m(
        47.01, 9.0, 47.02, 9.01
    )
    assert body["ascent_m"] == 400 and body["descent_m"] == 0
    assert body["min_elevation_m"] == 1500 and body["max_elevation_m"] == 1900
    assert body["duration_s"] == walking_time_s(body["distance_m"], 400, 0)
    assert body["duration_estimated"] is True


def test_direct_profile_draws_straight_lines_with_looked_up_elevations(
    client, anna, routing_engine, elevation_source
):
    response = client.post(
        PREVIEW, json={"profile": "direct", "waypoints": [START, HUT]}, headers=anna
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine"] == "direct" and routing_engine.calls == []
    assert body["distance_m"] == round(haversine_m(47.0, 9.0, 47.01, 9.0))
    # A point about every 50 m, so that the profile has a shape.
    assert len(body["series"]["lat"]) == 23
    assert elevation_source.calls == [23]
    assert body["series"]["elevation_m"][0] == 1000 and body["ascent_m"] == 100


def test_direct_route_works_without_elevations(client, anna, elevation_source):
    elevation_source.fail = True

    response = client.post(
        PREVIEW, json={"profile": "direct", "waypoints": [START, HUT]}, headers=anna
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["series"]["elevation_m"] is None and body["ascent_m"] is None
    assert body["duration_s"] == walking_time_s(body["distance_m"], None, None)


def test_single_legs_can_be_straight_lines(client, anna, routing_engine, elevation_source):
    saddle = {"lat": 47.03, "lon": 9.01}
    waypoints = [START, HUT, PEAK | {"direct": True}, saddle]

    response = client.post(PREVIEW, json={"waypoints": waypoints}, headers=anna)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine"] == "brouter+direct"
    # Paths before and after the straight leg are computed on their own.
    assert [call[0] for call in routing_engine.calls] == [
        [(47.0, 9.0), (47.01, 9.0)],
        [(47.02, 9.01), (47.03, 9.01)],
    ]
    # Only the points of the straight leg need an elevation from the lookup.
    assert len(elevation_source.calls) == 1
    lats = body["series"]["lat"]
    assert lats == sorted(lats) and lats[0] == 47.0 and lats[-1] == 47.03
    assert None not in body["series"]["elevation_m"]


def test_preview_reports_missing_route_and_missing_engine(client, anna, routing_engine):
    routing_engine.no_route = True
    response = client.post(PREVIEW, json={"waypoints": [START, HUT]}, headers=anna)
    assert response.status_code == 422 and response.json()["error"]["code"] == "no_route"

    routing_engine.no_route = False
    routing_engine.available = False
    response = client.post(PREVIEW, json={"waypoints": [START, HUT]}, headers=anna)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "routing_unavailable"

    # Straight lines never need the engine.
    response = client.post(
        PREVIEW, json={"profile": "direct", "waypoints": [START, HUT]}, headers=anna
    )
    assert response.status_code == 200


def test_preview_validates_the_waypoints(client, anna):
    assert client.post(PREVIEW, json={"waypoints": [START]}, headers=anna).status_code == 422
    far = {"lat": 91, "lon": 9}
    assert client.post(PREVIEW, json={"waypoints": [START, far]}, headers=anna).status_code == 422
    many = [START] * 101
    assert client.post(PREVIEW, json={"waypoints": many}, headers=anna).status_code == 422
    assert client.post(PREVIEW, json={"waypoints": [START, HUT]}).status_code == 401


def test_info_names_the_profiles(client, anna, routing_engine):
    body = client.get("/api/v1/planning/info", headers=anna).json()
    assert body["routing_available"] is True and "OpenStreetMap" in body["attribution"]
    assert [level["code"] for level in body["difficulties"]] == ["T1", "T2", "T3", "T4", "T5", "T6"]
    assert body["difficulties"][3]["sac_scale"] == "alpine_hiking"
    assert body["profiles"] == [
        {"id": "hiking", "available": True},
        {"id": "direct", "available": True},
    ]

    routing_engine.available = False
    body = client.get("/api/v1/planning/info", headers=anna).json()
    assert body["routing_available"] is False and body["attribution"] is None
    assert body["profiles"][0] == {"id": "hiking", "available": False}


# --- Stored routes ---


def test_route_is_stored_with_line_and_key_figures(client, anna):
    route = create(
        client, anna, description=" Über die Hütte ", tags=[" Sommer ", "sommer", "Gipfel"]
    )

    assert route["title"] == "Auf den Gipfel" and route["description"] == "Über die Hütte"
    # Tags are trimmed and the same tag twice counts once.
    assert route["tags"] == ["Sommer", "Gipfel"] and route["version"] == 1
    assert route["start_time"] is None and route["sun"] is None
    assert route["profile"] == "hiking" and route["engine"] == "brouter"
    assert [point["name"] for point in route["waypoints"]] == ["Parkplatz", "Hütte", "Gipfel"]
    assert route["ascent_m"] == 400 and route["duration_estimated"] is True
    assert len(route["series"]["lat"]) == 5

    read = client.get(f"{ROUTES}/{route['id']}", headers=anna)
    assert read.status_code == 200 and read.json() == route


def test_list_shows_own_routes_without_lines(client, anna, ben):
    first = create(client, anna, title="Säntis")
    create(client, anna, title="Altmann")
    create(client, ben, title="Speer")

    body = client.get(ROUTES, headers=anna).json()
    assert body["total"] == 2 and {item["title"] for item in body["items"]} == {
        "Säntis",
        "Altmann",
    }
    assert "series" not in body["items"][0] and "waypoints" not in body["items"][0]

    found = client.get(ROUTES, params={"q": "sänt"}, headers=anna).json()
    assert [item["id"] for item in found["items"]] == [first["id"]]


def test_foreign_routes_answer_like_missing_ones(client, anna, ben):
    route = create(client, anna)
    address = f"{ROUTES}/{route['id']}"
    update = {"title": "Meins", "waypoints": [START, HUT], "version": 1}

    assert client.get(address, headers=ben).status_code == 404
    assert client.put(address, json=update, headers=ben).status_code == 404
    assert client.delete(address, headers=ben).status_code == 404
    assert client.get(f"{address}/gpx", headers=ben).status_code == 404
    assert client.get(address).status_code == 401
    assert client.get(address, headers=anna).json()["title"] == "Auf den Gipfel"


def test_update_computes_the_line_only_when_the_course_changes(client, anna, routing_engine):
    route = create(client, anna)
    address = f"{ROUTES}/{route['id']}"
    assert len(routing_engine.calls) == 1

    renamed = client.put(
        address,
        json={"title": "Neuer Name", "waypoints": route["waypoints"], "version": 1},
        headers=anna,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Neuer Name" and renamed.json()["version"] == 2
    assert len(routing_engine.calls) == 1

    shorter = client.put(
        address,
        json={"title": "Neuer Name", "waypoints": [START, HUT], "version": 2},
        headers=anna,
    )
    assert shorter.status_code == 200, shorter.text
    assert len(routing_engine.calls) == 2
    assert shorter.json()["ascent_m"] == 200 and shorter.json()["version"] == 3


def test_difficulty_and_via_ferrata_reach_the_engine_and_are_stored(client, anna, routing_engine):
    # T3 without via ferratas unless something else is chosen.
    route = create(client, anna)
    assert routing_engine.options[-1] == RouteOptions(max_difficulty=3, via_ferrata=False)
    assert route["max_difficulty"] == 3 and route["via_ferrata"] is False

    hard = create(client, anna, max_difficulty=6, via_ferrata=True)
    assert routing_engine.options[-1] == RouteOptions(max_difficulty=6, via_ferrata=True)
    assert hard["max_difficulty"] == 6 and hard["via_ferrata"] is True

    # Another difficulty is another course: the line is computed again.
    calls = len(routing_engine.calls)
    easier = client.put(
        f"{ROUTES}/{hard['id']}",
        json={
            "title": hard["title"],
            "waypoints": hard["waypoints"],
            "max_difficulty": 2,
            "via_ferrata": True,
            "version": 1,
        },
        headers=anna,
    )
    assert easier.status_code == 200, easier.text
    assert len(routing_engine.calls) == calls + 1
    assert routing_engine.options[-1] == RouteOptions(max_difficulty=2, via_ferrata=True)

    for wrong in (0, 7):
        body = {"waypoints": [START, HUT], "max_difficulty": wrong}
        assert client.post(PREVIEW, json=body, headers=anna).status_code == 422


def test_outdated_version_is_a_conflict_with_the_current_route(client, anna):
    route = create(client, anna)
    address = f"{ROUTES}/{route['id']}"
    body = {"title": "Erste Änderung", "waypoints": route["waypoints"], "version": 1}
    assert client.put(address, json=body, headers=anna).status_code == 200

    response = client.put(address, json=body | {"title": "Zweite"}, headers=anna)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"
    assert response.json()["current"]["title"] == "Erste Änderung"
    assert response.json()["current"]["version"] == 2


def test_route_keeps_its_line_when_the_engine_fails_on_a_new_course(client, anna, routing_engine):
    route = create(client, anna)
    routing_engine.fail = True

    response = client.put(
        f"{ROUTES}/{route['id']}",
        json={"title": "Kürzer", "waypoints": [START, HUT], "version": 1},
        headers=anna,
    )

    assert response.status_code == 502
    assert client.get(f"{ROUTES}/{route['id']}", headers=anna).json() == route


def test_client_can_choose_the_id_once(client, anna):
    route_id = str(uuid.uuid4())
    assert create(client, anna, id=route_id)["id"] == route_id

    again = client.post(
        ROUTES, json={"id": route_id, "title": "Doppelt", "waypoints": [START, HUT]}, headers=anna
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "id_taken"


def test_deleted_route_is_gone(client, anna):
    route = create(client, anna)
    address = f"{ROUTES}/{route['id']}"

    assert client.delete(address, headers=anna).status_code == 204
    assert client.get(address, headers=anna).status_code == 404
    assert client.get(ROUTES, headers=anna).json()["total"] == 0


def test_gpx_download_contains_the_line(client, anna):
    route = create(client, anna)

    response = client.get(f"{ROUTES}/{route['id']}/gpx", headers=anna)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/gpx+xml")
    assert "attachment" in response.headers["content-disposition"]
    root = ElementTree.fromstring(response.content)
    namespace = {"gpx": "http://www.topografix.com/GPX/1/1"}
    points = root.findall(".//gpx:trkpt", namespace)
    assert len(points) == 5 and points[0].get("lat") == "47.0000000"
    assert root.find(".//gpx:trk/gpx:name", namespace).text == "Auf den Gipfel"
    assert points[-1].find("gpx:ele", namespace).text == "1900.0"


# --- Path data for the app ---


def test_path_data_is_listed_and_downloaded_in_parts(client, anna, tmp_path, monkeypatch):
    assert client.get("/api/v1/planning/segments", headers=anna).json() == []

    (tmp_path / "E5_N45.rd5").write_bytes(b"0123456789")
    (tmp_path / "notes.txt").write_text("not path data")
    (tmp_path / "bad name.rd5").write_bytes(b"x")
    monkeypatch.setenv("BROUTER_SEGMENTS_PATH", str(tmp_path))
    get_settings.cache_clear()

    listed = client.get("/api/v1/planning/segments", headers=anna).json()
    assert [(item["name"], item["size_bytes"]) for item in listed] == [("E5_N45", 10)]

    whole = client.get("/api/v1/planning/segments/E5_N45", headers=anna)
    assert whole.status_code == 200 and whole.content == b"0123456789"
    # An interrupted download continues where it stopped.
    rest = client.get("/api/v1/planning/segments/E5_N45", headers=anna | {"Range": "bytes=4-"})
    assert rest.status_code == 206 and rest.content == b"456789"

    assert client.get("/api/v1/planning/segments/E10_N45", headers=anna).status_code == 404
    assert client.get("/api/v1/planning/segments/..%2Fnotes", headers=anna).status_code in (
        404,
        422,
    )
    assert client.get("/api/v1/planning/segments/notes.txt", headers=anna).status_code == 422
    assert client.get("/api/v1/planning/segments/E5_N45").status_code == 401


# --- Offline sync ---


def push(client, headers, **operation):
    body = {"operations": [{"collection": "routes", **operation}]}
    response = client.post("/api/v1/sync/push", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["results"][0]


def test_route_drafted_offline_gets_its_line_with_the_sync(client, anna, ben):
    route_id = str(uuid.uuid4())
    draft = {"title": "Offline geplant", "waypoints": [START, HUT], "max_difficulty": 4}

    result = push(client, anna, op="upsert", id=route_id, data=draft)

    assert result["status"] == "ok"
    record = result["record"]
    assert record["id"] == route_id and record["version"] == 1 and record["max_difficulty"] == 4
    assert len(record["series"]["lat"]) == 3 and record["ascent_m"] == 200

    changes = client.get("/api/v1/sync/changes", headers=anna).json()
    assert [route["id"] for route in changes["collections"]["routes"]["changed"]] == [route_id]
    # Routes are not shared: nobody else gets them.
    others = client.get("/api/v1/sync/changes", headers=ben).json()
    assert others["collections"]["routes"]["changed"] == []
    assert push(client, ben, op="delete", id=route_id)["status"] == "ok"
    assert client.get(f"{ROUTES}/{route_id}", headers=anna).status_code == 200


def test_sync_reports_conflicts_missing_routes_and_deletes(client, anna, routing_engine):
    route = create(client, anna)
    since = client.get("/api/v1/sync/changes", headers=anna).json()["server_time"]
    change = {"title": "Am Handy geändert", "waypoints": route["waypoints"]}

    ok = push(client, anna, op="upsert", id=route["id"], base_version=1, data=change)
    assert ok["status"] == "ok" and ok["record"]["version"] == 2

    late = push(client, anna, op="upsert", id=route["id"], base_version=1, data=change)
    assert late["status"] == "conflict" and late["current"]["title"] == "Am Handy geändert"

    routing_engine.no_route = True
    draft = {"title": "Unmöglich", "waypoints": [START, PEAK]}
    failed = push(client, anna, op="upsert", id=str(uuid.uuid4()), data=draft)
    assert failed["status"] == "error" and failed["code"] == "no_route"

    assert push(client, anna, op="delete", id=route["id"])["status"] == "ok"
    changes = client.get("/api/v1/sync/changes", params={"since": since}, headers=anna).json()
    assert changes["collections"]["routes"]["deleted"] == [route["id"]]
    assert changes["collections"]["routes"]["changed"] == []


# --- BRouter adapter ---


def brouter(handler) -> BRouterEngine:
    return BRouterEngine(
        "http://brouter:17777/",
        {"hiking": "hiker-hiking"},
        transport=httpx2.MockTransport(handler),
    )


def test_brouter_adapter_asks_with_lon_lat_and_reads_the_line():
    seen = []

    def handler(request):
        seen.append(request.url)
        geometry = {"coordinates": [[9.0, 47.0, 1500.5], [9.001, 47.005], [9.0, 47.01, 1700]]}
        return httpx2.Response(200, json={"features": [{"geometry": geometry}]})

    options = RouteOptions(max_difficulty=4, via_ferrata=True)
    line = brouter(handler).route([(47.0, 9.0), (47.01, 9.0)], "hiking", options)

    assert seen[0].path == "/brouter"
    assert seen[0].params["lonlats"] == "9.000000,47.000000|9.000000,47.010000"
    assert seen[0].params["profile"] == "hiker-hiking"
    assert seen[0].params["format"] == "geojson"
    # Nothing harder than T4, demanding paths up to it preferred, via ferratas allowed.
    assert seen[0].params["profile:SAC_scale_limit"] == "4"
    assert seen[0].params["profile:SAC_scale_preferred"] == "4"
    assert seen[0].params["profile:allow_via_ferrata"] == "1"
    assert [(point.lat, point.lon, point.ele) for point in line] == [
        (47.0, 9.0, 1500.5),
        (47.005, 9.001, None),
        (47.01, 9.0, 1700.0),
    ]


def test_brouter_adapter_tells_no_route_from_an_unreachable_engine():
    def no_path(_request):
        # BRouter answers 400 with the reason as plain text.
        return httpx2.Response(400, text="target island detected for section 0\n")

    with pytest.raises(UnprocessableError) as error:
        brouter(no_path).route([(47.0, 9.0), (47.01, 9.0)], "hiking", RouteOptions())
    assert error.value.code == "no_route" and "target island" in error.value.message

    def broken(_request):
        return httpx2.Response(500, text="OutOfMemoryError")

    with pytest.raises(RoutingUnavailableError):
        brouter(broken).route([(47.0, 9.0), (47.01, 9.0)], "hiking", RouteOptions())

    def down(_request):
        raise httpx2.ConnectError("refused")

    with pytest.raises(RoutingUnavailableError):
        brouter(down).route([(47.0, 9.0), (47.01, 9.0)], "hiking", RouteOptions())

    def garbage(_request):
        return httpx2.Response(200, text="<html>proxy</html>")

    with pytest.raises(RoutingUnavailableError):
        brouter(garbage).route([(47.0, 9.0), (47.01, 9.0)], "hiking", RouteOptions())
