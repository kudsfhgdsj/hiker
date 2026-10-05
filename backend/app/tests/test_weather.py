# ruff: noqa: F811 - fixtures are imported from the protocols tests
from datetime import UTC, datetime, timedelta

import httpx2
import pytest

from app.modules.protocols.weather import OpenMeteoWeatherSource, WeatherSourceError
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
    revisions,
    share,
)
from app.tests.test_public_links import PUBLIC, create_link, token_of
from app.tests.test_track import START, garmin_gpx, upload

TIMES = {"start_time": "2026-08-01T06:00:00Z", "end_time": "2026-08-01T14:00:00Z"}
HOME = {"lat": 47.2835, "lon": 9.4123, "name": "Parkplatz"}
HUT = {"lat": 47.2511, "lon": 9.3399, "name": "Berghütte"}


def set_points(client, person, tour, **points):
    return client.put(f"{TOURS}/{tour['id']}/points", json=points, headers=person.headers)


def fetch_weather(client, person, tour, body=None):
    return client.post(f"{TOURS}/{tour['id']}/weather/fetch", json=body, headers=person.headers)


# --- Points ---


def test_owner_sets_start_and_end_on_the_map(client, anna):
    tour = create_tour(client, anna)

    response = set_points(client, anna, tour, start=HOME, end=HUT)

    assert response.status_code == 200
    updated = response.json()
    assert updated["start_point"] == HOME and updated["end_point"] == HUT
    assert updated["points_source"] == "manual"
    assert updated["version"] == 2
    cleared = set_points(client, anna, tour).json()
    assert cleared["start_point"] is None and cleared["points_source"] is None


def test_points_validate_coordinates(client, anna):
    tour = create_tour(client, anna)

    assert set_points(client, anna, tour, start={"lat": 91, "lon": 9}).status_code == 422
    assert set_points(client, anna, tour, start={"lat": 47}).status_code == 422


def test_with_a_track_only_the_names_can_be_set(client, anna):
    tour = upload(client, anna, create_tour(client, anna), garmin_gpx()).json()
    start, end = tour["start_point"], tour["end_point"]

    moved = set_points(client, anna, tour, start={"lat": 46.0, "lon": 8.0}, end=end)
    missing = set_points(client, anna, tour, start=start)
    named = set_points(client, anna, tour, start={**start, "name": "Parkplatz"}, end=end)

    assert moved.status_code == 409
    assert moved.json()["error"]["code"] == "points_from_track"
    assert missing.status_code == 409
    assert named.status_code == 200
    assert named.json()["start_point"] == {**start, "name": "Parkplatz"}
    assert named.json()["points_source"] == "gpx"


def test_only_the_owner_sets_points_and_fetches_weather(client, db, people):
    tour = create_tour(client, people["anna"], **TIMES)
    share(db, tour, people["bea"], "edit")
    share(db, tour, people["cleo"], "read")

    for name, expected in (("bea", 403), ("cleo", 403), ("dora", 404)):
        person = people[name]
        assert set_points(client, person, tour, start=HOME).status_code == expected
        assert fetch_weather(client, person, tour).status_code == expected
    current = client.get(f"{TOURS}/{tour['id']}", headers=people["anna"].headers).json()
    assert current["start_point"] is None


def test_points_are_part_of_the_history(client, anna):
    tour = create_tour(client, anna)
    set_points(client, anna, tour, start=HOME)

    restored = restore(client, anna, tour, 1).json()

    assert restored["start_point"] is None and restored["points_source"] is None
    assert [r["kind"] for r in revisions(client, anna, tour)["items"]] == [
        "restored",
        "updated",
        "created",
    ]


# --- Weather ---


def test_weather_is_fetched_automatically_for_manual_points(client, anna, weather_source):
    tour = create_tour(client, anna, **TIMES)

    updated = set_points(client, anna, tour, start=HOME, end=HUT).json()

    assert [w["sample_point"] for w in updated["weather"]] == ["start", "end"]
    start, end = updated["weather"]
    assert (start["lat"], start["lon"], start["time"]) == (47.2835, 9.4123, TIMES["start_time"])
    assert (end["lat"], end["time"]) == (47.2511, TIMES["end_time"])
    assert (start["temperature_c"], start["weather_code"], start["source"]) == (25.0, 2, "fake")
    assert updated["weather_outdated"] is False
    assert len(weather_source.calls) == 2
    # Weather is derived data: only setting the points added a revision.
    assert updated["version"] == 2


def test_summit_comes_from_a_peak_when_there_is_no_track(client, anna, weather_source):
    tour = create_tour(
        client,
        anna,
        peaks=[
            {"name": "Ohne Position"},
            {"name": "Säntis", "elevation_m": 2502, "lat": 47.2494, "lon": 9.3432},
        ],
        **TIMES,
    )

    updated = set_points(client, anna, tour, start=HOME, end=HOME).json()

    summit = updated["weather"][1]
    assert summit["sample_point"] == "summit"
    assert (summit["lat"], summit["elevation_m"]) == (47.2494, 2502.0)
    assert summit["time"] == "2026-08-01T10:00:00Z"
    assert summit["temperature_c"] == pytest.approx(25 - 25.02, abs=0.1)


def test_track_gives_start_summit_and_end_with_elevation_and_time(client, anna, weather_source):
    tour = upload(client, anna, create_tour(client, anna), garmin_gpx()).json()

    by_point = {w["sample_point"]: w for w in tour["weather"]}

    assert list(by_point) == ["start", "summit", "end"]
    assert (by_point["start"]["elevation_m"], by_point["start"]["time"]) == (
        1000.0,
        "2026-08-01T06:00:00Z",
    )
    # The track climbs all the way, so its highest point is the last one.
    assert (by_point["summit"]["lat"], by_point["summit"]["elevation_m"]) == (47.01, 1100.0)
    assert by_point["summit"]["time"] == "2026-08-01T06:10:00Z"
    assert by_point["start"]["temperature_c"] == 15.0
    assert by_point["summit"]["temperature_c"] == 14.0
    assert tour["weather_outdated"] is False


def test_no_weather_without_point_or_time(client, anna, weather_source):
    without_time = create_tour(client, anna)
    set_points(client, anna, without_time, start=HOME)
    without_point = create_tour(client, anna, **TIMES)

    for tour in (without_time, without_point):
        current = client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).json()
        assert current["weather"] == [] and current["weather_outdated"] is False
        response = fetch_weather(client, anna, tour)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "no_sample_points"
    assert weather_source.calls == []


def test_weather_follows_when_the_time_is_added_later(client, anna, weather_source):
    tour = create_tour(client, anna)
    with_point = set_points(client, anna, tour, start=HOME).json()
    assert with_point["weather"] == []

    updated = put(client, anna, with_point, **TIMES).json()

    assert [w["sample_point"] for w in updated["weather"]] == ["start"]


def test_later_changes_mark_the_weather_as_outdated_until_refetched(client, anna, weather_source):
    tour = create_tour(client, anna, **TIMES)
    fetched = set_points(client, anna, tour, start=HOME, end=HUT).json()

    moved = set_points(client, anna, tour, start={**HOME, "lat": 47.3}, end=HUT).json()

    assert moved["weather_outdated"] is True
    assert moved["weather"] == fetched["weather"]
    assert len(weather_source.calls) == 2
    later = put(client, anna, moved, start_time="2026-08-01T07:00:00Z").json()
    assert later["weather_outdated"] is True

    refreshed = fetch_weather(client, anna, tour).json()

    assert refreshed["weather_outdated"] is False
    assert refreshed["weather"][0]["lat"] == 47.3
    assert refreshed["weather"][0]["time"] == "2026-08-01T07:00:00Z"
    assert refreshed["version"] == later["version"]


def test_manual_sample_point_is_kept_next_to_the_automatic_ones(client, anna, weather_source):
    tour = create_tour(client, anna, **TIMES)
    set_points(client, anna, tour, start=HOME)
    manual = {"lat": 47.26, "lon": 9.35, "time": "2026-08-01T11:30:00Z", "elevation_m": 2000}

    with_manual = fetch_weather(client, anna, tour, {"manual": manual}).json()
    again = fetch_weather(client, anna, tour).json()

    assert [w["sample_point"] for w in with_manual["weather"]] == ["start", "manual"]
    assert with_manual["weather"][1]["temperature_c"] == 5.0
    assert [w["sample_point"] for w in again["weather"]] == ["start", "manual"]
    assert again["weather_outdated"] is False


def test_failing_service_never_breaks_saving_but_fails_the_manual_fetch(
    client, anna, weather_source
):
    weather_source.fail = True
    tour = create_tour(client, anna, **TIMES)

    saved = set_points(client, anna, tour, start=HOME)
    manual = fetch_weather(client, anna, tour)

    assert saved.status_code == 200
    assert saved.json()["start_point"] == HOME
    assert saved.json()["weather"] == [] and saved.json()["weather_outdated"] is True
    assert manual.status_code == 502
    assert manual.json()["error"]["code"] == "source_unavailable"

    weather_source.fail = False
    assert len(fetch_weather(client, anna, tour).json()["weather"]) == 1


def test_points_without_data_are_left_out(client, anna, weather_source):
    weather_source.no_data = True
    tour = create_tour(client, anna, **TIMES)

    saved = set_points(client, anna, tour, start=HOME).json()

    assert saved["weather"] == []


def test_weather_in_export_and_public_view(client, anna):
    tour = create_tour(client, anna, **TIMES)
    current = set_points(client, anna, tour, start=HOME).json()
    exact = token_of(create_link(client, anna, tour))
    hidden = token_of(create_link(client, anna, tour, hide_exact_start=True))

    exported = client.get(f"{TOURS}/{tour['id']}/export", headers=anna.headers).json()

    assert exported["weather"] == current["weather"]
    assert client.get(f"{PUBLIC}/{exact}").json()["weather"] == current["weather"]
    # The weather carries the exact coordinates of the start, so it is left out here.
    assert client.get(f"{PUBLIC}/{hidden}").json()["weather"] == []


# --- Open-Meteo adapter ---


def _source(handler) -> OpenMeteoWeatherSource:
    return OpenMeteoWeatherSource(
        "https://forecast.test/v1/forecast",
        "https://archive.test/v1/archive",
        "hiker/test",
        transport=httpx2.MockTransport(handler),
    )


def _hourly(date: str, **columns) -> dict:
    times = [f"{date}T{hour:02d}:00" for hour in range(24)]
    return {"hourly": {"time": times, **{name: list(values) for name, values in columns.items()}}}


def test_adapter_uses_the_archive_for_the_past_and_picks_the_hour():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(
            200,
            json=_hourly(
                "2026-08-01",
                temperature_2m=[hour + 0.5 for hour in range(24)],
                apparent_temperature=[hour for hour in range(24)],
                wind_speed_10m=[10.0] * 24,
                wind_gusts_10m=[25.0] * 24,
                precipitation=[0.2] * 24,
                cloud_cover=[80] * 24,
                weather_code=[61.0] * 24,
            ),
        )

    values = _source(handler).values_at(47.25, 9.34, 2500, START + timedelta(minutes=140))

    assert requests[0].url.host == "archive.test"
    params = requests[0].url.params
    assert (params["latitude"], params["longitude"], params["elevation"]) == (
        "47.25000",
        "9.34000",
        "2500",
    )
    assert params["start_date"] == params["end_date"] == "2026-08-01"
    assert "freezing_level_height" not in params["hourly"]
    assert requests[0].headers["user-agent"] == "hiker/test"
    # 08:20 UTC belongs to the hour starting at 08:00.
    assert (values.temperature_c, values.apparent_temperature_c) == (8.5, 8)
    assert (values.wind_gusts_kmh, values.precipitation_mm, values.cloud_cover_pct) == (
        25.0,
        0.2,
        80,
    )
    assert values.weather_code == 61 and values.freezing_level_m is None
    assert values.source == "open-meteo-archive"


def test_adapter_uses_the_forecast_for_recent_and_future_dates():
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).replace(minute=30)
    date = tomorrow.date().isoformat()
    requests = []

    def handler(request):
        requests.append(request)
        columns = {name: [1.0] * 24 for name in request.url.params["hourly"].split(",")}
        return httpx2.Response(200, json=_hourly(date, **columns))

    values = _source(handler).values_at(47.25, 9.34, None, tomorrow)

    assert requests[0].url.host == "forecast.test"
    assert "freezing_level_height" in requests[0].url.params["hourly"]
    assert "elevation" not in requests[0].url.params
    assert values.freezing_level_m == 1.0
    assert values.source == "open-meteo-forecast"


def test_adapter_reports_no_data_and_failures():
    def empty(request):
        return httpx2.Response(200, json=_hourly("2026-08-01", temperature_2m=[None] * 24))

    def timeout(request):
        raise httpx2.ConnectTimeout("too slow")

    assert (
        _source(lambda request: httpx2.Response(400, json={"error": True})).values_at(
            47, 9, None, START
        )
        is None
    )
    for handler in (
        lambda request: httpx2.Response(500),
        lambda request: httpx2.Response(200, json={"unexpected": 1}),
        lambda request: httpx2.Response(200, json=_hourly("2026-07-31", temperature_2m=[1] * 24)),
        timeout,
    ):
        with pytest.raises(WeatherSourceError):
            _source(handler).values_at(47, 9, None, START)
    with pytest.raises(WeatherSourceError):
        # Columns the adapter asked for are missing.
        _source(empty).values_at(47, 9, None, START)
