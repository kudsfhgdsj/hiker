import pytest

from app.tests.conftest import auth_header, register

TOURS = "/api/v1/tours"
REPORTS = "/api/v1/reports"
SAENTIS = {"name": "Säntis", "elevation_m": 2502, "lat": 47.2494, "lon": 9.3433}


@pytest.fixture
def anna(client):
    return auth_header(register(client))


@pytest.fixture
def ben(client):
    return auth_header(register(client, email="ben@example.org", display_name="Ben"))


def gpx(points) -> bytes:
    body = "".join(
        f'<trkpt lat="{lat}" lon="{lon}"><ele>{ele}</ele><time>{time}</time></trkpt>'
        for lat, lon, ele, time in points
    )
    return (
        '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><trkseg>{body}</trkseg></trk></gpx>"
    ).encode()


def tour(client, headers, track=None, **fields) -> dict:
    created = client.post(TOURS, json={"title": "Tour"} | fields, headers=headers)
    assert created.status_code == 201, created.text
    if track is not None:
        files = {"file": ("t.gpx", gpx(track), "application/gpx+xml")}
        assert (
            client.put(
                f"{TOURS}/{created.json()['id']}/gpx", files=files, headers=headers
            ).status_code
            == 200
        )
    return created.json()


def climb(day: str):
    """A walk of about 1.1 km with 300 m up, on the given day."""
    return [
        (47.24, 9.34, 2200, f"{day}T07:00:00Z"),
        (47.245, 9.34, 2350, f"{day}T07:30:00Z"),
        (47.25, 9.34, 2500, f"{day}T08:00:00Z"),
    ]


def test_totals_add_up_the_own_tours_per_year(client, anna, ben):
    empty = client.get(f"{REPORTS}/summary", headers=anna).json()
    assert empty["total"]["tours"] == 0 and empty["years"] == []

    tour(
        client,
        anna,
        climb("2026-07-18"),
        title="Säntis",
        start_time="2026-07-18T07:00:00Z",
        peaks=[SAENTIS],
    )
    tour(
        client,
        anna,
        climb("2026-08-02"),
        title="Nochmal",
        start_time="2026-08-02T07:00:00Z",
        peaks=[SAENTIS],
    )
    tour(client, anna, climb("2025-06-01"), title="Vorjahr", start_time="2025-06-01T07:00:00Z")
    # Without a track: a tour and a day, no distance. Without a date: in the total only.
    tour(client, anna, title="Ohne Track", start_time="2026-09-01T08:00:00Z")
    tour(client, anna, title="Irgendwann")
    # Tours of others do not count.
    tour(client, ben, climb("2026-07-18"), title="Bens Tour", start_time="2026-07-18T07:00:00Z")

    body = client.get(f"{REPORTS}/summary", headers=anna).json()

    total = body["total"]
    assert total["tours"] == 5 and total["tours_with_track"] == 3 and total["days"] == 4
    assert (
        3200 < total["distance_m"] < 3500 and total["ascent_m"] == 900 and total["descent_m"] == 0
    )
    assert total["moving_time_s"] > 0 and total["peaks"] == 1
    assert [year["year"] for year in body["years"]] == [2026, 2025]
    this_year, last_year = body["years"]
    assert this_year["tours"] == 3 and this_year["days"] == 3 and this_year["ascent_m"] == 600
    assert this_year["peaks"] == 1 and last_year["peaks"] == 0 and last_year["ascent_m"] == 300
    assert client.get(f"{REPORTS}/summary").status_code == 401


def test_climbed_peaks_are_listed_once_with_every_visit(client, anna):
    first = tour(client, anna, title="Erste", start_time="2025-07-01T06:00:00Z", peaks=[SAENTIS])
    second = tour(
        client,
        anna,
        title="Zweite",
        start_time="2026-07-18T06:00:00Z",
        peaks=[
            # The same summit entered by hand, slightly beside and spelled differently.
            {"name": "Saentis", "lat": 47.2496, "lon": 9.3435},
            {"name": "Hochkopf", "elevation_m": 1900, "lat": 47.1, "lon": 9.2},
            {"name": "Namenlos ohne Ort"},
        ],
    )
    # The same name far away is another mountain.
    tour(
        client,
        anna,
        title="Dritte",
        start_time="2026-08-01T06:00:00Z",
        peaks=[{"name": "Hochkopf", "elevation_m": 2100, "lat": 46.5, "lon": 10.9}],
    )

    peaks = client.get(f"{REPORTS}/peaks", headers=anna).json()

    assert [(peak["name"], peak["elevation_m"], peak["count"]) for peak in peaks] == [
        ("Säntis", 2502, 2),
        ("Hochkopf", 2100, 1),
        ("Hochkopf", 1900, 1),
        ("Namenlos ohne Ort", None, 1),
    ]
    saentis = peaks[0]
    assert saentis["first"].startswith("2025-07-01") and saentis["last"].startswith("2026-07-18")
    assert [visit["tour_id"] for visit in saentis["visits"]] == [second["id"], first["id"]]


def test_calendar_shows_the_days_out_of_a_year(client, anna):
    one = tour(client, anna, climb("2026-07-18"), title="Tag", start_time="2026-07-18T07:00:00Z")
    tour(client, anna, title="Nachmittag", start_time="2026-07-18T14:00:00Z")
    # Three days in the hut: every day counts, the figures are spread over them.
    tour(
        client,
        anna,
        title="Hüttentour",
        start_time="2026-08-01T07:00:00Z",
        end_time="2026-08-03T15:00:00Z",
    )
    tour(client, anna, title="Früher", start_time="2024-05-05T07:00:00Z")

    body = client.get(f"{REPORTS}/calendar", headers=anna).json()

    assert body["year"] == 2026 and body["years"] == [2026, 2024]
    assert [day["date"] for day in body["days"]] == [
        "2026-07-18",
        "2026-08-01",
        "2026-08-02",
        "2026-08-03",
    ]
    first = body["days"][0]
    assert first["tours"] == 2 and first["ascent_m"] == 300 and one["id"] in first["tour_ids"]
    earlier = client.get(f"{REPORTS}/calendar", params={"year": 2024}, headers=anna).json()
    assert [day["date"] for day in earlier["days"]] == ["2024-05-05"]
    assert (
        client.get(f"{REPORTS}/calendar", params={"year": 2023}, headers=anna).json()["days"] == []
    )


def test_all_tracks_come_as_lines_for_one_map(client, anna, ben):
    long_walk = [
        (47.0 + i * 0.0001, 9.0, 1000, f"2026-07-18T07:{i // 60:02d}:{i % 60:02d}Z")
        for i in range(900)
    ]
    walked = tour(client, anna, long_walk, title="Lang", start_time="2026-07-18T07:00:00Z")
    tour(client, anna, title="Ohne Track")
    tour(client, ben, climb("2026-07-18"), title="Bens Tour")

    body = client.get(f"{REPORTS}/tracks", headers=anna).json()

    assert body["type"] == "FeatureCollection" and len(body["features"]) == 1
    line = body["features"][0]
    assert line["properties"] == {"tour_id": walked["id"], "title": "Lang", "date": "2026-07-18"}
    points = line["geometry"]["coordinates"]
    # Thinned out, but from the first to the last point.
    assert len(points) <= 160 and points[0] == [9.0, 47.0] and points[-1] == [9.0, 47.0899]


def test_wish_peaks_are_private_and_know_when_they_were_climbed(client, anna, ben):
    wishes = f"{REPORTS}/wishes"
    made = client.post(wishes, json=SAENTIS | {"note": "Über den Lisengrat"}, headers=anna)
    assert made.status_code == 201 and made.json()["climbed"] is False
    client.post(wishes, json={"name": "Piz Bernina", "elevation_m": 4049}, headers=anna)
    client.post(wishes, json={"name": "hochkopf"}, headers=anna)
    assert client.post(wishes, json={"name": ""}, headers=anna).status_code == 422

    # Not climbed yet: the highest first.
    listed = client.get(wishes, headers=anna).json()
    assert [wish["name"] for wish in listed] == ["Piz Bernina", "Säntis", "hochkopf"]
    assert client.get(wishes, headers=ben).json() == []

    # A tour reaches the Säntis (entered a little beside) and a Hochkopf.
    tour(
        client,
        anna,
        title="Gipfeltag",
        start_time="2026-07-18T06:00:00Z",
        peaks=[{"name": "Saentis Gipfel", "lat": 47.2495, "lon": 9.3434}, {"name": "Hochkopf"}],
    )
    listed = {wish["name"]: wish for wish in client.get(wishes, headers=anna).json()}
    assert listed["Säntis"]["climbed"] is True and listed["Säntis"]["climbed_on"].startswith(
        "2026-07-18"
    )
    assert listed["hochkopf"]["climbed"] is True and listed["Piz Bernina"]["climbed"] is False
    # Still to do comes first.
    assert client.get(wishes, headers=anna).json()[0]["name"] == "Piz Bernina"

    wish_id = made.json()["id"]
    changed = client.put(f"{wishes}/{wish_id}", json=SAENTIS | {"note": None}, headers=anna)
    assert changed.status_code == 200 and changed.json()["note"] is None
    assert client.put(f"{wishes}/{wish_id}", json=SAENTIS, headers=ben).status_code == 404
    assert client.delete(f"{wishes}/{wish_id}", headers=ben).status_code == 404
    assert client.delete(f"{wishes}/{wish_id}", headers=anna).status_code == 204
    assert "Säntis" not in [wish["name"] for wish in client.get(wishes, headers=anna).json()]
