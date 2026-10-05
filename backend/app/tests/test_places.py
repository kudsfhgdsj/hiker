# ruff: noqa: F811 - fixtures are imported from the protocols tests
from datetime import timedelta

import httpx2
import pytest

from app.modules.protocols import places
from app.modules.protocols.places import (
    OverpassPlaceSource,
    Place,
    PlaceSourceError,
    detect_stations,
    parse_gpx_waypoints,
)
from app.modules.protocols.track import TrackPoint
from app.tests.test_protocols import (  # noqa: F401
    TOURS,
    anna,
    bea,
    cleo,
    create_tour,
    dora,
    people,
    put,
    restore,
    share,
)
from app.tests.test_public_links import PUBLIC, create_link, token_of
from app.tests.test_track import GPX_HEADER, START, garmin_gpx, upload

# The test track runs north from 47.000/9.000: one point per minute, 111.2 m and 10 m of
# ascent per point. At this latitude 0.0001° of longitude is about 7.6 m.
ON_TRACK = 0.00005  # 3.8 m beside the track
OFF_TRACK = 0.0003  # 22.8 m beside the track


def line(count=11, with_time=True, with_ele=True) -> list[TrackPoint]:
    return [
        TrackPoint(
            lat=47.0 + i * 0.001,
            lon=9.0,
            ele=1000.0 + i * 10 if with_ele else None,
            time=START + timedelta(minutes=i) if with_time else None,
        )
        for i in range(count)
    ]


def peak(name="Säntis", lat=47.005, lon=9.0 + ON_TRACK, ele=2502.0, osm_id=1, kind="peak"):
    return Place(kind=kind, name=name, lat=lat, lon=lon, elevation_m=ele, osm_id=osm_id)


def waypoints_of(client, person, tour):
    return client.get(f"{TOURS}/{tour['id']}/waypoints", headers=person.headers).json()


# --- Detection ---


def test_place_on_the_track_becomes_a_station_with_distance_time_and_elevation():
    [station, high_point] = detect_stations(line(), [peak()], [], max_distance_m=10)

    assert (station.kind, station.source, station.name) == ("peak", "osm", "Säntis")
    assert station.track_distance_m == pytest.approx(556.0, abs=0.5)
    assert station.reached_at == START + timedelta(minutes=5)
    # The surveyed elevation of the map beats the one of the track.
    assert station.elevation_m == 2502.0
    assert station.osm_id == 1
    # The highest point of the track is elsewhere, so it is listed as well.
    assert (high_point.kind, high_point.source, high_point.name) == ("high_point", "track", "")


def test_only_places_within_the_tolerance_count():
    near = peak("Nah", lon=9.0 + ON_TRACK, osm_id=1)
    far = peak("Fern", lon=9.0 + OFF_TRACK, osm_id=2)

    strict = detect_stations(line(), [near, far], [], max_distance_m=10)
    loose = detect_stations(line(), [near, far], [], max_distance_m=30)

    assert [s.name for s in strict if s.kind == "peak"] == ["Nah"]
    assert sorted(s.name for s in loose if s.kind == "peak") == ["Fern", "Nah"]


def test_distance_is_measured_to_the_line_between_far_apart_points():
    # A drawn track with only two points, 1.1 km apart; the pass lies in the middle.
    track = [TrackPoint(lat=47.0, lon=9.0, ele=1000), TrackPoint(lat=47.01, lon=9.0, ele=1400)]
    middle = peak("Joch", lat=47.005, lon=9.0 + ON_TRACK, ele=None, kind="saddle", osm_id=7)

    [station, _high_point] = detect_stations(track, [middle], [], max_distance_m=10)

    assert (station.kind, station.name) == ("saddle", "Joch")
    assert station.track_distance_m == pytest.approx(556.0, abs=1.0)
    # Without a surveyed elevation the one of the track is used, interpolated.
    assert station.elevation_m == pytest.approx(1200.0, abs=0.5)
    assert station.reached_at is None


def test_stations_are_ordered_along_the_track_and_each_place_appears_once():
    out_and_back = [*line(6), *reversed(line(5))]
    found = detect_stations(
        out_and_back,
        [peak("Zweiter", lat=47.004, osm_id=2), peak("Erster", lat=47.002, osm_id=1)],
        [],
        max_distance_m=10,
    )

    assert [s.name for s in found if s.kind == "peak"] == ["Erster", "Zweiter"]


def test_no_separate_high_point_when_a_peak_is_at_the_top():
    summit = peak("Gipfel", lat=47.010, ele=1100.0)

    found = detect_stations(line(), [summit], [], max_distance_m=10)

    assert [s.kind for s in found] == ["peak"]


def test_track_without_elevation_has_no_high_point():
    assert detect_stations(line(with_ele=False), [], [], max_distance_m=10) == []


def test_waypoints_of_the_gpx_file_are_read_tolerantly():
    gpx = (
        f"{GPX_HEADER}"
        '<wpt lat="47.003" lon="9.0001"><ele>1234</ele><name>Alp Sigel</name></wpt>'
        '<wpt lat="47.2" lon="9.5"><name>Weit weg</name></wpt>'
        '<wpt lat="47.004" lon="9.0"><ele>hoch</ele></wpt>'
        '<wpt lat="abc" lon="9.0"><name>Kaputt</name></wpt>'
        '<trk><trkseg><trkpt lat="47.0" lon="9.0"/></trkseg></trk></gpx>'
    ).encode()

    found = parse_gpx_waypoints(gpx)
    stations = detect_stations(line(), [], found, max_distance_m=10)

    assert [(p.name, p.elevation_m) for p in found] == [("Alp Sigel", 1234.0), ("Weit weg", None)]
    by_name = {s.name: s for s in stations}
    assert by_name["Alp Sigel"].source == "gpx"
    assert by_name["Alp Sigel"].track_distance_m == pytest.approx(333.6, abs=0.5)
    # Too far away for a position on the track, but still part of the tour.
    assert by_name["Weit weg"].track_distance_m is None
    assert parse_gpx_waypoints(b"not xml") == []


# --- In tours ---


def test_upload_finds_peaks_and_passes_and_adds_peaks_to_the_peak_list(client, anna, place_source):
    place_source.places = [
        peak("Säntis", lat=47.006, ele=2502.0, osm_id=11),
        peak("Rotsteinpass", lat=47.003, ele=2120.0, kind="saddle", osm_id=12),
        peak("Daneben", lat=47.005, lon=9.0 + OFF_TRACK, osm_id=13),
    ]
    tour = create_tour(client, anna, peaks=[{"name": "Von Hand"}])

    updated = upload(client, anna, tour, garmin_gpx()).json()

    found = waypoints_of(client, anna, tour)
    assert [(w["kind"], w["name"], w["source"]) for w in found] == [
        ("saddle", "Rotsteinpass", "osm"),
        ("peak", "Säntis", "osm"),
        ("high_point", "", "track"),
    ]
    saentis = found[1]
    assert saentis["track_distance_m"] == pytest.approx(667.1, abs=0.5)
    assert saentis["reached_at"] == "2026-08-01T06:06:00Z"
    assert saentis["elevation_m"] == 2502.0
    assert [(p["name"], p["source"], p["elevation_m"]) for p in updated["peaks"]] == [
        ("Von Hand", "manual", None),
        ("Säntis", "osm", 2502),
    ]
    # Only the bounding box of the track goes to the map service.
    [(south, west, north, east)] = place_source.calls
    assert south == pytest.approx(47.0, abs=0.001) and north == pytest.approx(47.01, abs=0.001)
    assert west == pytest.approx(9.0, abs=0.001) and east == pytest.approx(9.0, abs=0.001)


def test_a_new_track_replaces_what_was_found_but_keeps_manual_entries(client, anna, place_source):
    place_source.places = [peak("Säntis", lat=47.006, osm_id=11)]
    tour = upload(client, anna, create_tour(client, anna), garmin_gpx()).json()
    url = f"{TOURS}/{tour['id']}/waypoints"
    client.post(url, json={"name": "Brunnen", "lat": 47.002, "lon": 9.0}, headers=anna.headers)
    current = client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).json()
    with_manual_peak = put(client, anna, current, peaks=[*current["peaks"], {"name": "Eigener"}])
    assert with_manual_peak.status_code == 200

    place_source.places = [peak("Altmann", lat=47.004, ele=2435.0, osm_id=20)]
    updated = upload(client, anna, tour, garmin_gpx(count=8)).json()

    assert sorted((w["kind"], w["name"]) for w in waypoints_of(client, anna, tour)) == [
        ("custom", "Brunnen"),
        ("high_point", ""),
        ("peak", "Altmann"),
    ]
    assert [(p["name"], p["source"]) for p in updated["peaks"]] == [
        ("Eigener", "manual"),
        ("Altmann", "osm"),
    ]


def test_peak_that_is_already_listed_by_hand_is_not_added_twice(client, anna, place_source):
    place_source.places = [peak("Säntis", lat=47.006, osm_id=11)]
    tour = create_tour(client, anna, peaks=[{"name": "säntis"}])

    updated = upload(client, anna, tour, garmin_gpx()).json()

    assert [(p["name"], p["source"]) for p in updated["peaks"]] == [("säntis", "manual")]


def test_unreachable_map_service_never_breaks_the_upload(client, anna, place_source):
    place_source.fail = True
    tour = create_tour(client, anna)

    response = upload(client, anna, tour, garmin_gpx())

    assert response.status_code == 200
    assert response.json()["track_stats"]["distance_m"] > 1000
    assert [w["kind"] for w in waypoints_of(client, anna, tour)] == ["high_point"]

    place_source.fail = False
    place_source.places = [peak("Säntis", lat=47.006, osm_id=11)]
    again = client.post(f"{TOURS}/{tour['id']}/track/places", headers=anna.headers)

    assert again.status_code == 200
    assert [p["name"] for p in again.json()["peaks"]] == ["Säntis"]
    assert again.json()["version"] == response.json()["version"] + 1


def test_found_places_can_be_renamed_and_removed(client, anna, place_source):
    place_source.places = [peak("Säntis", lat=47.006, osm_id=11)]
    tour = upload(client, anna, create_tour(client, anna), garmin_gpx()).json()
    station = next(w for w in waypoints_of(client, anna, tour) if w["kind"] == "peak")
    url = f"{TOURS}/{tour['id']}/waypoints/{station['id']}"

    renamed = client.patch(url, json={"name": "Säntis (Gipfelkreuz)"}, headers=anna.headers)
    removed = client.delete(url, headers=anna.headers)

    assert renamed.json()["name"] == "Säntis (Gipfelkreuz)"
    assert renamed.json()["source"] == "osm"
    assert removed.status_code == 204
    assert [w["kind"] for w in waypoints_of(client, anna, tour)] == ["high_point"]


def test_removing_the_track_removes_what_was_found_along_it(client, anna, place_source):
    place_source.places = [peak("Säntis", lat=47.006, osm_id=11)]
    tour = upload(
        client, anna, create_tour(client, anna, peaks=[{"name": "Von Hand"}]), garmin_gpx()
    ).json()

    removed = client.delete(f"{TOURS}/{tour['id']}/track", headers=anna.headers).json()

    assert waypoints_of(client, anna, tour) == []
    assert [p["name"] for p in removed["peaks"]] == ["Von Hand"]


def test_only_the_owner_detects_places_again(client, db, people, place_source):
    tour = upload(client, people["anna"], create_tour(client, people["anna"]), garmin_gpx()).json()
    share(db, tour, people["bea"], "edit")
    share(db, tour, people["cleo"], "read")
    url = f"{TOURS}/{tour['id']}/track/places"

    for name, expected in (("bea", 403), ("cleo", 403), ("dora", 404)):
        assert client.post(url, headers=people[name].headers).status_code == expected


def test_drawn_track_finds_places_too(client, anna, place_source):
    place_source.places = [peak("Joch", lat=47.002, kind="saddle", osm_id=5)]
    tour = create_tour(client, anna)
    points = [{"lat": 47.0, "lon": 9.0}, {"lat": 47.004, "lon": 9.0}]

    client.post(f"{TOURS}/{tour['id']}/track/drawn", json={"points": points}, headers=anna.headers)

    assert ("saddle", "Joch") in [(w["kind"], w["name"]) for w in waypoints_of(client, anna, tour)]


# --- Overview ---


def test_overview_lists_the_course_of_the_tour_in_track_order(client, anna, place_source):
    place_source.places = [
        peak("Säntis", lat=47.006, ele=2502.0, osm_id=11),
        peak("Rotsteinpass", lat=47.003, ele=2120.0, kind="saddle", osm_id=12),
    ]
    tour = upload(client, anna, create_tour(client, anna, title="Alpstein"), garmin_gpx()).json()

    response = client.get(f"{TOURS}/{tour['id']}/overview", headers=anna.headers)

    assert response.status_code == 200
    overview = response.json()
    assert overview["title"] == "Alpstein"
    assert overview["attribution"] == "© OpenStreetMap contributors (ODbL)"
    assert [(s["kind"], s["name"], s["elevation_m"]) for s in overview["stations"]] == [
        ("start", None, 1000.0),
        ("saddle", "Rotsteinpass", 2120.0),
        ("peak", "Säntis", 2502.0),
        ("high_point", None, 1100.0),
        ("end", None, 1100.0),
    ]
    distances = [s["track_distance_m"] for s in overview["stations"]]
    assert distances == sorted(distances) and distances[0] == 0
    assert [s["time"] for s in overview["stations"]][:3] == [
        "2026-08-01T06:00:00Z",
        "2026-08-01T06:03:00Z",
        "2026-08-01T06:06:00Z",
    ]
    facts = overview["facts"]
    assert (facts["ascent_m"], facts["descent_m"], facts["duration_minutes"]) == (100, 0, 10)
    assert (facts["min_elevation_m"], facts["max_elevation_m"]) == (1000, 1100)
    assert facts["distance_m"] == pytest.approx(1112, abs=2)


def test_overview_without_track_and_its_permissions(client, db, people):
    anna_ = people["anna"]
    tour = create_tour(client, anna_, title="Ohne Track")
    share(db, tour, people["cleo"], "read")
    url = f"{TOURS}/{tour['id']}/overview"

    overview = client.get(url, headers=anna_.headers).json()

    assert overview["stations"] == [] and overview["attribution"] is None
    assert overview["facts"]["distance_m"] is None
    assert client.get(url, headers=people["cleo"].headers).status_code == 200
    assert client.get(url, headers=people["dora"].headers).status_code == 404
    assert client.get(url).status_code == 401


def test_places_are_part_of_history_and_public_view(client, anna, place_source):
    place_source.places = [peak("Säntis", lat=47.006, osm_id=11)]
    tour = upload(client, anna, create_tour(client, anna), garmin_gpx()).json()
    token = token_of(create_link(client, anna, tour))

    public = client.get(f"{PUBLIC}/{token}").json()
    restored = restore(client, anna, tour, 1).json()

    assert ("peak", "Säntis", "osm") in [
        (w["kind"], w["name"], w["source"]) for w in public["waypoints"]
    ]
    assert restored["peaks"] == [] and waypoints_of(client, anna, tour) == []


# --- Overpass adapter ---


def _source(handler) -> OverpassPlaceSource:
    return OverpassPlaceSource(
        "https://overpass.test/api/interpreter",
        "hiker/test",
        transport=httpx2.MockTransport(handler),
    )


def test_adapter_asks_for_named_peaks_saddles_and_passes_in_the_box():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 26863664,
                        "lat": 47.2494,
                        "lon": 9.3432,
                        "tags": {"natural": "peak", "name": "Säntis", "ele": "2501.9"},
                    },
                    {
                        "type": "node",
                        "id": 2,
                        "lat": 47.23,
                        "lon": 9.36,
                        "tags": {"mountain_pass": "yes", "name": "Rotsteinpass", "ele": "2120 m"},
                    },
                    {"type": "node", "id": 3, "lat": 47.2, "lon": 9.3, "tags": {"natural": "peak"}},
                    {"type": "way", "id": 4, "tags": {"name": "Kein Punkt"}},
                ]
            },
        )

    found = _source(handler).places_in(47.2, 9.3, 47.3, 9.4)

    body = requests[0].content.decode()
    assert "47.20000%2C9.30000%2C47.30000%2C9.40000" in body
    assert "natural" in body and "saddle" in body and "mountain_pass" in body
    assert requests[0].headers["user-agent"] == "hiker/test"
    assert found == [
        Place("peak", "Säntis", 47.2494, 9.3432, 2501.9, 26863664),
        Place("saddle", "Rotsteinpass", 47.23, 9.36, 2120.0, 2),
    ]


def test_adapter_reports_failures():
    def timeout(request):
        raise httpx2.ConnectTimeout("too slow")

    for handler in (
        lambda request: httpx2.Response(429),
        lambda request: httpx2.Response(200, text="<html>busy</html>"),
        lambda request: httpx2.Response(200, json={"remark": "runtime error"}),
        timeout,
    ):
        with pytest.raises(PlaceSourceError):
            _source(handler).places_in(47.2, 9.3, 47.3, 9.4)


def test_tolerance_is_configurable(client, anna, place_source, monkeypatch):
    from app.core.config import get_settings

    place_source.places = [peak("Daneben", lat=47.005, lon=9.0 + OFF_TRACK, osm_id=13)]
    strict = upload(client, anna, create_tour(client, anna), garmin_gpx()).json()
    monkeypatch.setenv("PLACE_MAX_DISTANCE_M", "30")
    get_settings.cache_clear()
    loose = upload(client, anna, create_tour(client, anna, title="Zweite"), garmin_gpx()).json()

    assert strict["peaks"] == []
    assert [p["name"] for p in loose["peaks"]] == ["Daneben"]
    assert places.AUTOMATIC_SOURCES == ("osm", "gpx", "track")
