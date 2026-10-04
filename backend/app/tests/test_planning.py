import uuid
from xml.etree import ElementTree

import httpx2
import pytest

from app.core.errors import UnprocessableError
from app.modules.planning.estimate import walking_time_s
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
    route = create(client, anna, description=" Über die Hütte ", planned_date="2026-07-18")

    assert route["title"] == "Auf den Gipfel" and route["description"] == "Über die Hütte"
    assert route["planned_date"] == "2026-07-18" and route["version"] == 1
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


# --- BRouter adapter ---


def brouter(handler) -> BRouterEngine:
    return BRouterEngine(
        "http://brouter:17777/",
        {"hiking": "hiking-mountain"},
        transport=httpx2.MockTransport(handler),
    )


def test_brouter_adapter_asks_with_lon_lat_and_reads_the_line():
    seen = []

    def handler(request):
        seen.append(request.url)
        geometry = {"coordinates": [[9.0, 47.0, 1500.5], [9.001, 47.005], [9.0, 47.01, 1700]]}
        return httpx2.Response(200, json={"features": [{"geometry": geometry}]})

    line = brouter(handler).route([(47.0, 9.0), (47.01, 9.0)], "hiking", RouteOptions())

    assert seen[0].path == "/brouter"
    assert seen[0].params["lonlats"] == "9.000000,47.000000|9.000000,47.010000"
    assert seen[0].params["profile"] == "hiking-mountain"
    assert seen[0].params["format"] == "geojson"
    assert [(point.lat, point.lon, point.ele) for point in line] == [
        (47.0, 9.0, 1500.5),
        (47.005, 9.001, None),
        (47.01, 9.0, 1700.0),
    ]


def test_brouter_adapter_tells_no_route_from_an_unreachable_engine():
    def no_path(_request):
        return httpx2.Response(
            400, text="from-position not mapped in existing datafile\n", headers={}
        )

    with pytest.raises(UnprocessableError) as error:
        brouter(no_path).route([(47.0, 9.0), (47.01, 9.0)], "hiking", RouteOptions())
    assert error.value.code == "no_route" and "not mapped" in error.value.message

    def down(_request):
        raise httpx2.ConnectError("refused")

    with pytest.raises(RoutingUnavailableError):
        brouter(down).route([(47.0, 9.0), (47.01, 9.0)], "hiking", RouteOptions())

    def garbage(_request):
        return httpx2.Response(200, text="<html>proxy</html>")

    with pytest.raises(RoutingUnavailableError):
        brouter(garbage).route([(47.0, 9.0), (47.01, 9.0)], "hiking", RouteOptions())
