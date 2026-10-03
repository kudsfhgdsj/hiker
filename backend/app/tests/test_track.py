import uuid
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from sqlalchemy import select

from app.core.errors import UnprocessableError
from app.core.files import FileObject
from app.modules.protocols import track
from app.modules.protocols.elevation import (
    ElevationSourceError,
    OpenMeteoElevationSource,
    lookup_along,
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
    revision,
    revisions,
    share,
)
from app.tests.test_public_links import PUBLIC, create_link, token_of

START = datetime(2026, 8, 1, 6, 0, tzinfo=UTC)
GPX_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<gpx version="1.1" creator="Garmin Connect" xmlns="http://www.topografix.com/GPX/1/1" '
    'xmlns:ns3="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">'
)


def garmin_gpx(count=11, step_s=60, with_time=True, with_ele=True, with_sensors=True) -> bytes:
    """A track heading north: 0.001° (about 111 m) and 10 m of ascent per point."""
    points = []
    for index in range(count):
        parts = [f'<trkpt lat="{47.0 + index * 0.001:.6f}" lon="9.000000">']
        if with_ele:
            parts.append(f"<ele>{1000 + index * 10}</ele>")
        if with_time:
            time = START + timedelta(seconds=index * step_s)
            parts.append(f"<time>{time.strftime('%Y-%m-%dT%H:%M:%SZ')}</time>")
        if with_sensors:
            parts.append(
                "<extensions><ns3:TrackPointExtension>"
                f"<ns3:atemp>{20 - index * 0.5}</ns3:atemp>"
                f"<ns3:hr>{100 + index * 8}</ns3:hr><ns3:cad>{50 + index}</ns3:cad>"
                "</ns3:TrackPointExtension></extensions>"
            )
        parts.append("</trkpt>")
        points.append("".join(parts))
    body = "".join(points)
    return f"{GPX_HEADER}<trk><name>Tour</name><trkseg>{body}</trkseg></trk></gpx>".encode()


def upload(client, person, tour, data, filename="track.gpx"):
    files = {"file": (filename, data, "application/gpx+xml")}
    return client.put(f"{TOURS}/{tour['id']}/gpx", files=files, headers=person.headers)


# --- Parser ---


def test_parser_reads_position_time_elevation_and_garmin_sensors():
    points = track.parse_gpx(garmin_gpx(count=3))

    assert points[0] == TrackPoint(
        lat=47.0, lon=9.0, ele=1000.0, time=START, hr=100, cad=50, temp=20.0
    )
    assert (points[2].hr, points[2].cad, points[2].temp) == (116, 52, 19.0)
    assert points[2].time == START + timedelta(minutes=2)


def test_parser_tolerates_missing_time_elevation_and_sensors():
    points = track.parse_gpx(
        garmin_gpx(count=3, with_time=False, with_ele=False, with_sensors=False)
    )

    assert points == [TrackPoint(lat=47.0 + i * 0.001, lon=9.0) for i in range(3)]
    stats = track.compute_stats(points)
    assert stats["distance_m"] == pytest.approx(222, abs=1)
    for key in ("ascent_m", "max_elevation_m", "start_time", "total_time_s", "moving_time_s"):
        assert stats[key] is None
    assert stats["heart_rate"] is None and stats["cadence"] is None
    assert stats["temperature"] is None


def test_parser_tolerates_broken_values_inside_points():
    gpx = (
        f"{GPX_HEADER}<trk><trkseg>"
        '<trkpt lat="47.0" lon="9.0"><ele>abc</ele><time>2026-08-01T06:00:00Z</time>'
        "<extensions><ns3:TrackPointExtension><ns3:hr>fast</ns3:hr><ns3:cad>-5</ns3:cad>"
        "</ns3:TrackPointExtension></extensions></trkpt>"
        '<trkpt lat="47.001" lon="9.0"><ele>99999</ele>'
        "<extensions><ns3:TrackPointExtension><ns3:hr>500</ns3:hr></ns3:TrackPointExtension>"
        "</extensions></trkpt>"
        '<trkpt lat="91" lon="9.0"></trkpt>'
        "</trkseg></trk></gpx>"
    ).encode()

    points = track.parse_gpx(gpx)

    assert len(points) == 2
    assert all(p.ele is None and p.hr is None and p.cad is None for p in points)
    assert points[0].time == START and points[1].time is None


def test_parser_falls_back_to_route_points_and_joins_segments():
    route = (
        f'{GPX_HEADER}<rte><rtept lat="47.0" lon="9.0"/><rtept lat="47.1" lon="9.1"/></rte></gpx>'
    )
    segments = (
        f'{GPX_HEADER}<trk><trkseg><trkpt lat="47.0" lon="9.0"/></trkseg>'
        '<trkseg><trkpt lat="47.1" lon="9.0"/></trkseg></trk>'
        '<trk><trkseg><trkpt lat="47.2" lon="9.0"/></trkseg></trk></gpx>'
    )

    assert [p.lat for p in track.parse_gpx(route.encode())] == [47.0, 47.1]
    assert [p.lat for p in track.parse_gpx(segments.encode())] == [47.0, 47.1, 47.2]


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not xml at all",
        b"\xff\xfe\x00binary",
        f"{GPX_HEADER}<trk><trkseg>".encode(),
        f"{GPX_HEADER}<trk><trkseg></trkseg></trk></gpx>".encode(),
        b'<?xml version="1.0"?><!DOCTYPE gpx [<!ENTITY a "aaaa">]><gpx version="1.1">&a;</gpx>',
        b"<html><body>hello</body></html>",
    ],
)
def test_parser_rejects_files_that_are_no_usable_gpx(data):
    with pytest.raises(UnprocessableError) as error:
        track.parse_gpx(data)
    assert error.value.code == "invalid_gpx"


# --- Statistics ---


def test_stats_of_a_garmin_track():
    points = track.parse_gpx(garmin_gpx())

    stats = track.compute_stats(points, max_heart_rate=180)

    assert stats["point_count"] == 11
    assert stats["distance_m"] == pytest.approx(1112, abs=2)
    assert (stats["ascent_m"], stats["descent_m"]) == (100, 0)
    assert (stats["min_elevation_m"], stats["max_elevation_m"]) == (1000, 1100)
    assert stats["start_time"] == "2026-08-01T06:00:00Z"
    assert stats["end_time"] == "2026-08-01T06:10:00Z"
    assert (stats["total_time_s"], stats["moving_time_s"]) == (600, 600)
    assert stats["cadence"] == {"avg": 54, "min": 50, "max": 60}
    assert stats["temperature"] == {"avg": 17.8, "min": 15.0, "max": 20.0}
    heart = stats["heart_rate"]
    assert (heart["avg"], heart["min"], heart["max"]) == (136, 100, 180)
    assert heart["max_heart_rate_used"] == 180
    # Limits at 60/70/80/90 % of 180 bpm; each point counts for the minute that follows it,
    # so the last point (180 bpm) adds no time.
    assert [(z["zone"], z["from_bpm"], z["to_bpm"], z["seconds"]) for z in heart["zones"]] == [
        (1, None, 108, 60),
        (2, 108, 126, 180),
        (3, 126, 144, 120),
        (4, 144, 162, 120),
        (5, 162, None, 120),
    ]


def test_heart_rate_zones_need_a_maximum_and_time_stamps():
    with_time = track.parse_gpx(garmin_gpx())
    without_time = track.parse_gpx(garmin_gpx(with_time=False))

    assert track.compute_stats(with_time)["heart_rate"]["zones"] is None
    no_time = track.compute_stats(without_time, max_heart_rate=180)["heart_rate"]
    assert no_time["zones"] is None
    assert no_time["avg"] == 140


def test_ascent_ignores_noise_below_the_threshold_and_counts_descent():
    def points(*elevations):
        return [TrackPoint(lat=47 + i * 0.001, lon=9, ele=e) for i, e in enumerate(elevations)]

    noisy = track.compute_stats(points(1000, 1002, 999, 1001, 1000, 1002))
    hill = track.compute_stats(points(1000, 1050, 1049, 1100, 1040, None, 1000))

    assert (noisy["ascent_m"], noisy["descent_m"]) == (0, 0)
    assert (hill["ascent_m"], hill["descent_m"]) == (100, 100)


def test_moving_time_leaves_out_breaks():
    def point(index, minute, lat):
        return TrackPoint(lat=lat, lon=9, time=START + timedelta(minutes=minute))

    points = [
        point(0, 0, 47.000),
        point(1, 1, 47.001),
        point(2, 31, 47.001),  # 30 minutes of rest
        point(3, 32, 47.002),
        point(4, 31, 47.003),  # time going backwards is ignored
    ]

    stats = track.compute_stats(points)

    assert stats["total_time_s"] == 32 * 60
    assert stats["moving_time_s"] == 120


def test_single_point_track_has_zero_distance():
    stats = track.compute_stats([TrackPoint(lat=47, lon=9, ele=500, time=START)])

    assert (stats["distance_m"], stats["ascent_m"], stats["total_time_s"]) == (0, 0, 0)


def test_series_has_equal_columns_and_is_thinned_out():
    points = track.parse_gpx(garmin_gpx(count=501))

    full = track.build_series(points[:5])
    thin = track.build_series(points, max_points=50)

    assert full["distance_m"][0] == 0 and full["distance_m"][4] == pytest.approx(444.8, abs=0.5)
    assert full["time"][1] == "2026-08-01T06:01:00Z"
    assert full["heart_rate"] == [100, 108, 116, 124, 132]
    assert {len(column) for column in thin.values()} == {50}
    assert (thin["lat"][0], thin["lat"][-1]) == (47.0, 47.5)
    bare = track.build_series([TrackPoint(lat=47, lon=9), TrackPoint(lat=47.001, lon=9)])
    assert bare["time"] is None and bare["elevation_m"] is None and bare["heart_rate"] is None
    assert bare["lat"] == [47, 47.001]


def test_drawn_points_round_trip_through_generated_gpx():
    points = [
        TrackPoint(lat=47.0, lon=9.0, ele=1000.0, time=START),
        TrackPoint(lat=47.001, lon=9.001, ele=None, time=None),
    ]

    data = track.points_to_gpx(points, "Säntis & <Grat>")

    assert track.parse_gpx(data) == points
    assert b"S\xc3\xa4ntis &amp; &lt;Grat&gt;" in data


# --- Upload ---


def test_upload_evaluates_the_track_and_updates_the_tour(client, db, storage, anna):  # noqa: F811
    tour = create_tour(client, anna)
    original = garmin_gpx()

    response = upload(client, anna, tour, original)

    assert response.status_code == 200
    updated = response.json()
    assert updated["track_source"] == "device"
    assert updated["track_stats"]["distance_m"] == pytest.approx(1112, abs=2)
    assert updated["track_stats"]["elevation_source"] == "track"
    assert updated["points_source"] == "gpx"
    assert updated["start_point"] == {"lat": 47.0, "lon": 9.0, "name": None}
    assert updated["end_point"] == {"lat": 47.01, "lon": 9.0, "name": None}
    assert updated["start_time"] == "2026-08-01T06:00:00Z"
    assert updated["end_time"] == "2026-08-01T06:10:00Z"
    assert updated["computed"]["duration_minutes"] == 10
    assert updated["version"] == 2
    # The original file is stored unchanged and can be downloaded by the owner.
    stored = db.scalar(select(FileObject).where(FileObject.mime == "application/gpx+xml"))
    assert storage.read(stored.storage_key) == original
    download = client.get(f"{TOURS}/{tour['id']}/gpx", headers=anna.headers)
    assert download.content == original
    assert download.headers["content-type"].startswith("application/gpx+xml")


def test_track_endpoint_returns_series_for_charts(client, anna):  # noqa: F811
    tour = create_tour(client, anna)
    upload(client, anna, tour, garmin_gpx())

    data = client.get(f"{TOURS}/{tour['id']}/track", headers=anna.headers).json()

    assert data["source"] == "device"
    series = data["series"]
    assert {len(series[column]) for column in series} == {11}
    assert series["elevation_m"][:2] == [1000.0, 1010.0]
    assert series["heart_rate"][:2] == [100, 108]
    assert series["time"][0] == "2026-08-01T06:00:00Z"
    assert data["stats"]["heart_rate"]["max"] == 180


def test_tour_without_track_has_an_empty_track(client, anna):  # noqa: F811
    tour = create_tour(client, anna)

    data = client.get(f"{TOURS}/{tour['id']}/track", headers=anna.headers).json()

    assert data == {"source": "none", "stats": None, "series": None}
    assert client.get(f"{TOURS}/{tour['id']}/gpx", headers=anna.headers).status_code == 404


def test_zones_use_the_profile_of_the_owner(client, anna):  # noqa: F811
    client.put("/api/v1/me/profile", json={"max_heart_rate": 180}, headers=anna.headers)
    with_max = create_tour(client, anna)
    stats = upload(client, anna, with_max, garmin_gpx()).json()["track_stats"]
    client.put("/api/v1/me/profile", json={"birth_year": 1986}, headers=anna.headers)
    by_age = create_tour(client, anna)
    age_stats = upload(client, anna, by_age, garmin_gpx()).json()["track_stats"]

    assert stats["heart_rate"]["max_heart_rate_used"] == 180
    assert [zone["seconds"] for zone in stats["heart_rate"]["zones"]] == [60, 180, 120, 120, 120]
    assert age_stats["heart_rate"]["max_heart_rate_used"] == 220 - (datetime.now(UTC).year - 1986)


def test_simple_gpx_without_time_and_pulse_keeps_manual_times(client, anna):  # noqa: F811
    tour = create_tour(
        client, anna, start_time="2026-07-01T08:00:00Z", end_time="2026-07-01T12:00:00Z"
    )

    updated = upload(client, anna, tour, garmin_gpx(with_time=False, with_sensors=False)).json()

    assert updated["start_time"] == "2026-07-01T08:00:00Z"
    assert updated["track_stats"]["total_time_s"] is None
    assert updated["track_stats"]["heart_rate"] is None
    assert updated["track_stats"]["ascent_m"] == 100


@pytest.mark.parametrize("data", [b"not a gpx", b"<gpx></gpx>", b""])
def test_upload_rejects_invalid_files_and_leaves_the_tour_alone(client, anna, data):  # noqa: F811
    tour = create_tour(client, anna)

    response = upload(client, anna, tour, data)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_gpx"
    current = client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).json()
    assert current == tour


def test_upload_rejects_files_above_the_size_limit(client, anna, monkeypatch):  # noqa: F811
    from app.core.config import get_settings

    tour = create_tour(client, anna)
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()

    assert upload(client, anna, tour, b"x" * (1024 * 1024 + 1)).status_code == 413


# --- Elevation lookup ---


def test_missing_elevation_is_looked_up(client, anna, elevation_source):  # noqa: F811
    tour = create_tour(client, anna)

    updated = upload(client, anna, tour, garmin_gpx(with_ele=False)).json()

    assert elevation_source.calls == [11]
    assert updated["track_stats"]["elevation_source"] == "open-meteo"
    assert updated["track_stats"]["ascent_m"] == 100
    series = client.get(f"{TOURS}/{tour['id']}/track", headers=anna.headers).json()["series"]
    assert series["elevation_m"][:2] == [1000.0, 1010.0]


def test_track_with_elevation_never_asks_the_service(client, anna, elevation_source):  # noqa: F811
    tour = create_tour(client, anna)

    upload(client, anna, tour, garmin_gpx())

    assert elevation_source.calls == []


def test_failing_elevation_service_is_tolerated(client, anna, elevation_source):  # noqa: F811
    elevation_source.fail = True
    tour = create_tour(client, anna)

    response = upload(client, anna, tour, garmin_gpx(with_ele=False))

    assert response.status_code == 200
    stats = response.json()["track_stats"]
    assert stats["elevation_source"] is None and stats["ascent_m"] is None
    assert stats["distance_m"] == pytest.approx(1112, abs=2)


def test_long_tracks_are_sampled_and_interpolated():
    class Source:
        def __init__(self):
            self.requested = 0

        def elevations(self, coordinates):
            self.requested += len(coordinates)
            return [lat * 100 for lat, _ in coordinates]

    source = Source()
    coordinates = [(index / 10, 9.0) for index in range(1000)]

    result = lookup_along(source, coordinates)

    assert source.requested == 300
    assert len(result) == 1000
    assert result == pytest.approx([lat * 100 for lat, _ in coordinates])


def test_open_meteo_adapter_batches_requests_and_reports_failures():
    requests = []

    def handler(request):
        requests.append(request)
        count = len(request.url.params["latitude"].split(","))
        return httpx2.Response(200, json={"elevation": [500.0] * count})

    source = OpenMeteoElevationSource(
        "https://elevation.test/v1/elevation", "hiker/test", transport=httpx2.MockTransport(handler)
    )

    result = source.elevations([(47.0 + i / 1000, 9.0) for i in range(150)])

    assert result == [500.0] * 150
    assert [len(r.url.params["latitude"].split(",")) for r in requests] == [100, 50]
    assert requests[0].url.params["longitude"].startswith("9.00000,")
    assert requests[0].headers["user-agent"] == "hiker/test"
    for response in (
        httpx2.Response(500),
        httpx2.Response(200, json={"elevation": [1.0]}),
        httpx2.Response(200, text="oops"),
    ):
        broken = OpenMeteoElevationSource(
            "https://elevation.test", "x", transport=httpx2.MockTransport(lambda r, x=response: x)
        )
        with pytest.raises(ElevationSourceError):
            broken.elevations([(47.0, 9.0), (47.1, 9.0)])


# --- Drawn track ---


def test_drawn_track_becomes_a_gpx_with_looked_up_elevations(client, anna, elevation_source):  # noqa: F811
    tour = create_tour(client, anna)
    points = [{"lat": 47.0 + i * 0.001, "lon": 9.0} for i in range(5)]

    response = client.post(
        f"{TOURS}/{tour['id']}/track/drawn", json={"points": points}, headers=anna.headers
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["track_source"] == "drawn"
    assert updated["track_stats"]["elevation_source"] == "open-meteo"
    assert updated["track_stats"]["ascent_m"] == 40
    assert updated["track_stats"]["total_time_s"] is None
    assert updated["start_point"]["lat"] == 47.0 and updated["end_point"]["lat"] == 47.004
    gpx = client.get(f"{TOURS}/{tour['id']}/gpx", headers=anna.headers).content
    parsed = track.parse_gpx(gpx)
    assert [p.ele for p in parsed] == [1000.0, 1010.0, 1020.0, 1030.0, 1040.0]
    assert b'creator="hiker"' in gpx


def test_drawn_track_validates_points(client, anna):  # noqa: F811
    tour = create_tour(client, anna)
    url = f"{TOURS}/{tour['id']}/track/drawn"

    one_point = client.post(url, json={"points": [{"lat": 47, "lon": 9}]}, headers=anna.headers)
    bad = client.post(
        url, json={"points": [{"lat": 47, "lon": 9}, {"lat": 95, "lon": 9}]}, headers=anna.headers
    )

    assert one_point.status_code == 422 and bad.status_code == 422


# --- Permissions and health data ---


@pytest.fixture
def tracked_tour(client, db, anna, bea, cleo):  # noqa: F811
    tour = create_tour(client, anna)
    share(db, tour, bea, "edit")
    share(db, tour, cleo, "read")
    return upload(client, anna, tour, garmin_gpx()).json()


def test_only_the_owner_changes_the_track(client, people, tracked_tour):  # noqa: F811
    url = f"{TOURS}/{tracked_tour['id']}"
    drawn = {"points": [{"lat": 46, "lon": 8}, {"lat": 46.1, "lon": 8}]}

    for name, expected in (("bea", 403), ("cleo", 403), ("dora", 404)):
        person = people[name]
        assert upload(client, person, tracked_tour, garmin_gpx(count=3)).status_code == expected
        post = client.post(f"{url}/track/drawn", json=drawn, headers=person.headers)
        assert post.status_code == expected
        assert client.delete(f"{url}/track", headers=person.headers).status_code == expected
        assert client.get(f"{url}/gpx", headers=person.headers).status_code == expected
    current = client.get(url, headers=people["anna"].headers).json()
    assert current["track_stats"] == tracked_tour["track_stats"]
    assert current["version"] == tracked_tour["version"]


def test_heart_rate_is_only_visible_to_the_owner(client, people, tracked_tour):  # noqa: F811
    url = f"{TOURS}/{tracked_tour['id']}"

    owner_track = client.get(f"{url}/track", headers=people["anna"].headers).json()
    assert owner_track["series"]["heart_rate"] is not None
    assert "heart_rate" in owner_track["stats"]
    for name in ("bea", "cleo"):
        headers = people[name].headers
        shared_track = client.get(f"{url}/track", headers=headers).json()
        assert shared_track["series"]["heart_rate"] is None
        assert "heart_rate" not in shared_track["stats"]
        assert shared_track["series"]["elevation_m"] == owner_track["series"]["elevation_m"]
        assert shared_track["series"]["cadence"] is not None
        assert "heart_rate" not in client.get(url, headers=headers).json()["track_stats"]
        exported = client.get(f"{url}/export", headers=headers).json()
        assert "heart_rate" not in exported["track"]["stats"]
        assert exported["track"]["stats"]["distance_m"] > 0
    assert client.get(f"{url}/track", headers=people["dora"].headers).status_code == 404
    owner_export = client.get(f"{url}/export", headers=people["anna"].headers).json()
    assert owner_export["track"]["stats"]["heart_rate"]["max"] == 180


def test_public_link_hides_heart_rate_unless_enabled(client, anna, tracked_tour):  # noqa: F811
    default = token_of(create_link(client, anna, tracked_tour))
    with_health = token_of(create_link(client, anna, tracked_tour, show_health_data=True))

    hidden = client.get(f"{PUBLIC}/{default}/track")
    shown = client.get(f"{PUBLIC}/{with_health}/track").json()

    assert hidden.status_code == 200
    assert hidden.headers["x-robots-tag"] == "noindex, nofollow"
    assert hidden.json()["series"]["heart_rate"] is None
    assert "heart_rate" not in hidden.json()["stats"]
    assert "heart_rate" not in client.get(f"{PUBLIC}/{default}").json()["track_stats"]
    assert shown["series"]["heart_rate"][0] == 100
    assert shown["stats"]["heart_rate"]["max"] == 180
    assert client.get(f"{PUBLIC}/{uuid.uuid4()}/track").status_code == 404


def test_public_link_with_hidden_start_cuts_both_ends_of_the_track(client, anna):  # noqa: F811
    tour = create_tour(client, anna)
    upload(client, anna, tour, garmin_gpx(count=21))
    exact = token_of(create_link(client, anna, tour))
    hidden = token_of(create_link(client, anna, tour, hide_exact_start=True))

    full = client.get(f"{PUBLIC}/{exact}/track").json()["series"]
    cut = client.get(f"{PUBLIC}/{hidden}/track").json()["series"]

    assert len(full["lat"]) == 21
    # 500 m at 111 m per point: the first and the last five points are gone.
    assert cut["lat"] == full["lat"][5:16]
    assert {len(column) for column in cut.values() if column is not None} == {11}
    assert cut["distance_m"][0] == full["distance_m"][5]
    page = client.get(f"{PUBLIC}/{hidden}").json()
    assert page["start_point"] == {"lat": 47.0, "lon": 9.0, "name": None, "approximate": True}


# --- History ---


def test_track_changes_are_part_of_the_history_and_can_be_restored(client, anna):  # noqa: F811
    tour = create_tour(client, anna)
    first = upload(client, anna, tour, garmin_gpx(count=11)).json()
    second = upload(client, anna, tour, garmin_gpx(count=21)).json()
    url = f"{TOURS}/{tour['id']}"

    assert second["track_stats"]["point_count"] == 21
    diff = revision(client, anna, tour, 3)["diff"]
    # The highest point moved with the longer track, so the waypoints changed too.
    assert set(diff) == {"gpx_file_id", "end_lat", "end_time", "waypoints"}

    restored = restore(client, anna, tour, 2).json()

    assert restored["track_stats"] == first["track_stats"]
    assert restored["end_point"] == first["end_point"]
    assert restored["end_time"] == first["end_time"]
    series = client.get(f"{url}/track", headers=anna.headers).json()["series"]
    assert len(series["lat"]) == 11
    assert [r["kind"] for r in revisions(client, anna, tour)["items"]] == [
        "restored",
        "updated",
        "updated",
        "created",
    ]

    without = restore(client, anna, tour, 1).json()

    assert (without["track_source"], without["track_stats"]) == ("none", None)
    assert without["start_point"] is None and without["start_time"] is None
    assert client.get(f"{url}/track", headers=anna.headers).json()["series"] is None


def test_removing_the_track_keeps_manual_data(client, anna):  # noqa: F811
    tour = create_tour(client, anna, title="Mit Track")
    upload(client, anna, tour, garmin_gpx())

    response = client.delete(f"{TOURS}/{tour['id']}/track", headers=anna.headers)

    assert response.status_code == 200
    removed = response.json()
    assert (removed["track_source"], removed["track_stats"]) == ("none", None)
    assert removed["start_point"] is None and removed["points_source"] is None
    assert removed["title"] == "Mit Track"
    assert removed["start_time"] == "2026-08-01T06:00:00Z"
    assert removed["version"] == 3


def test_edit_cannot_restore_a_state_with_another_track(client, db, people, tracked_tour):  # noqa: F811
    response = restore(client, people["bea"], tracked_tour, 1)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "owner_only_field"


def test_edit_keeps_working_on_a_tour_with_a_track(client, people, tracked_tour):  # noqa: F811
    current = client.get(f"{TOURS}/{tracked_tour['id']}", headers=people["bea"].headers).json()

    response = put(client, people["bea"], current, title="Von Bea")

    assert response.status_code == 200
    assert response.json()["track_stats"]["distance_m"] == current["track_stats"]["distance_m"]
