import logging
import re
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.core.db import utcnow
from app.core.log_redaction import ACCESS_LOGGER, PathRedactionFilter
from app.modules.protocols.models import Tour, TourPublicLink
from app.tests.test_protocols import (  # noqa: F401
    OWNER_ONLY,
    TOURS,
    Person,
    anna,
    bea,
    cleo,
    create_contact,
    create_tour,
    dora,
    food_item,
    gear_item,
    people,
    shared_tour,
)

PUBLIC = "/api/v1/public/tours"
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def links_url(tour):
    return f"{TOURS}/{tour['id']}/public-link"


def create_link(client, person, tour, **options):
    response = client.post(links_url(tour), json=options, headers=person.headers)
    assert response.status_code == 201, response.text
    return response.json()


def token_of(link) -> str:
    return link["url"].rsplit("/", 1)[1]


@pytest.fixture
def full_tour(client, db, anna):  # noqa: F811
    """A tour with every kind of content and a start point."""
    tent = gear_item(client, anna, name="Zelt", brand="MSR", weight_g=1500)
    bar = food_item(client, anna, name="Nussriegel", kcal_per_100g=480)
    contact = create_contact(client, anna, "Dani")
    tour = create_tour(
        client,
        anna,
        summary="Schöne Tour",
        gear=[{"gear_item_id": tent["id"]}],
        food=[{"food_item_id": bar["id"], "amount_g": 50, "eaten": True}],
        peaks=[{"name": "Säntis", "elevation_m": 2502, "lat": 47.2494, "lon": 9.3432}],
        partners=[{"contact_id": contact["id"]}],
        **OWNER_ONLY,
    )
    client.post(
        f"{TOURS}/{tour['id']}/waypoints",
        json={"name": "Hütte", "lat": 47.25, "lon": 9.34},
        headers=anna.headers,
    )
    db.execute(
        update(Tour)
        .where(Tour.id == uuid.UUID(tour["id"]))
        .values(
            start_lat=47.283456, start_lon=9.412345, start_name="Zuhause", points_source="manual"
        )
    )
    db.commit()
    return tour


def test_public_link_shows_the_tour_without_login(client, anna, full_tour):  # noqa: F811
    link = create_link(client, anna, full_tour)

    response = client.get(f"{PUBLIC}/{token_of(link)}")

    assert response.status_code == 200
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["cache-control"] == "no-store"
    tour = response.json()
    assert (tour["title"], tour["summary"], tour["owner_name"]) == ("Säntis", "Schöne Tour", "Anna")
    assert tour["duration_minutes"] == 480
    assert tour["pack_weight_start_g"] == 9000
    assert tour["calories_eaten"] == 240.0
    assert tour["partners"] == ["Dani"]
    assert [peak["name"] for peak in tour["peaks"]] == ["Säntis"]
    assert [waypoint["name"] for waypoint in tour["waypoints"]] == ["Hütte"]
    assert tour["gear"] == [
        {"name": "Zelt", "brand": "MSR", "weight_g": 1500, "quantity": 1, "carried": True}
    ]
    assert tour["food"][0]["name"] == "Nussriegel"
    assert tour["start_point"] == {
        "lat": 47.283456,
        "lon": 9.412345,
        "name": "Zuhause",
        "approximate": False,
    }


def test_public_view_contains_no_ids_emails_or_health_data(client, anna, full_tour):  # noqa: F811
    link = create_link(client, anna, full_tour)

    response = client.get(f"{PUBLIC}/{token_of(link)}")

    assert UUID_RE.search(response.text) is None
    assert "@" not in response.text
    assert "id" not in {key for key in _all_keys(response.json()) if key.endswith("id")}
    assert response.json()["calories_burned"] is None
    assert response.json()["calories_burned_source"] is None


def _all_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _all_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_keys(item)


def test_link_options_health_data_and_hidden_start(client, anna, full_tour):  # noqa: F811
    link = create_link(client, anna, full_tour, show_health_data=True, hide_exact_start=True)

    tour = client.get(f"{PUBLIC}/{token_of(link)}").json()

    assert (tour["calories_burned"], tour["calories_burned_source"]) == (3200.0, "manual")
    assert tour["start_point"] == {"lat": 47.28, "lon": 9.41, "name": None, "approximate": True}
    assert link["show_health_data"] is True and link["strip_photo_gps"] is False


def test_tokens_are_random_uuid4_and_links_use_the_public_base_url(client, anna):  # noqa: F811
    tour = create_tour(client, anna)

    links = [create_link(client, anna, tour) for _ in range(3)]

    tokens = [uuid.UUID(token_of(link)) for link in links]
    assert all(token.version == 4 for token in tokens)
    assert len(set(tokens)) == 3
    assert all(link["url"].startswith("http://testserver/p/") for link in links)
    # The token is unrelated to the ids of the tour and the link.
    assert not {tour["id"], *(link["id"] for link in links)} & {str(token) for token in tokens}


def test_revoked_expired_and_unknown_links_answer_alike(client, db, anna):  # noqa: F811
    tour = create_tour(client, anna)
    revoked = create_link(client, anna, tour)
    expired = create_link(
        client, anna, tour, expires_at=(utcnow() + timedelta(hours=1)).isoformat()
    )
    valid = create_link(client, anna, tour)
    assert client.get(f"{PUBLIC}/{token_of(expired)}").status_code == 200

    client.delete(f"{links_url(tour)}/{revoked['id']}", headers=anna.headers)
    db.execute(
        update(TourPublicLink)
        .where(TourPublicLink.id == uuid.UUID(expired["id"]))
        .values(expires_at=utcnow() - timedelta(seconds=1))
    )
    db.commit()

    responses = [
        client.get(f"{PUBLIC}/{token_of(revoked)}"),
        client.get(f"{PUBLIC}/{token_of(expired)}"),
        client.get(f"{PUBLIC}/{uuid.uuid4()}"),
        client.get(f"{PUBLIC}/not-a-token"),
        client.get(f"{PUBLIC}/{tour['id']}"),
    ]

    assert [response.status_code for response in responses] == [404] * 5
    assert len({response.text for response in responses}) == 1
    assert client.get(f"{PUBLIC}/{token_of(valid)}").status_code == 200
    listed = client.get(links_url(tour), headers=anna.headers).json()
    assert {link["id"]: link["active"] for link in listed} == {
        revoked["id"]: False,
        expired["id"]: False,
        valid["id"]: True,
    }


def test_link_of_a_deleted_tour_stops_working(client, anna):  # noqa: F811
    tour = create_tour(client, anna)
    link = create_link(client, anna, tour)

    client.delete(f"{TOURS}/{tour['id']}", headers=anna.headers)

    assert client.get(f"{PUBLIC}/{token_of(link)}").status_code == 404


def test_only_the_owner_manages_public_links(client, people, shared_tour):  # noqa: F811
    link = create_link(client, people["anna"], shared_tour)

    for name, expected in (("bea", 403), ("cleo", 403), ("dora", 404)):
        headers = people[name].headers
        assert client.get(links_url(shared_tour), headers=headers).status_code == expected
        assert client.post(links_url(shared_tour), json={}, headers=headers).status_code == expected
        revoke = client.delete(f"{links_url(shared_tour)}/{link['id']}", headers=headers)
        assert revoke.status_code == expected
    assert client.get(f"{PUBLIC}/{token_of(link)}").status_code == 200


def test_link_validates_expiry_and_belongs_to_its_tour(client, anna):  # noqa: F811
    tour = create_tour(client, anna)
    other = create_tour(client, anna, title="Andere")
    link = create_link(client, anna, tour)
    past = (utcnow() - timedelta(minutes=1)).isoformat()

    assert (
        client.post(links_url(tour), json={"expires_at": past}, headers=anna.headers).status_code
        == 422
    )
    wrong_tour = client.delete(f"{links_url(other)}/{link['id']}", headers=anna.headers)
    assert wrong_tour.status_code == 404
    assert client.get(f"{PUBLIC}/{token_of(link)}").status_code == 200


def test_public_view_is_rate_limited(client):
    statuses = [client.get(f"{PUBLIC}/{uuid.uuid4()}").status_code for _ in range(61)]

    assert statuses == [404] * 60 + [429]


def test_token_is_stored_once_and_never_logged(client, db, anna, caplog):  # noqa: F811
    tour = create_tour(client, anna)
    with caplog.at_level(logging.DEBUG):
        link = create_link(client, anna, tour)
        client.get(f"{PUBLIC}/{token_of(link)}")
        client.get(links_url(tour), headers=anna.headers)

    # The test client logs its own requests; only the server side counts here.
    server_side = [r.getMessage() for r in caplog.records if not r.name.startswith("httpx")]
    assert not any(token_of(link) in message for message in server_side)
    stored = db.scalar(select(TourPublicLink.token))
    assert str(stored) == token_of(link)


def test_access_log_filter_redacts_tokens():
    token = str(uuid.uuid4())
    log_filter = PathRedactionFilter(("/public/tours/", "/p/"))
    record = logging.LogRecord(
        ACCESS_LOGGER,
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1234", "GET", f"/api/v1/public/tours/{token}?x=1", "1.1", 200),
        None,
    )

    assert log_filter.filter(record) is True

    message = record.getMessage()
    assert token not in message
    assert "/api/v1/public/tours/[redacted]?x=1" in message
    assert log_filter.redact(f"GET /p/{token}") == "GET /p/[redacted]"
    assert log_filter.redact("GET /api/v1/tours/123") == "GET /api/v1/tours/123"


def test_access_logger_has_the_redaction_filter_installed(client):
    filters = logging.getLogger(ACCESS_LOGGER).filters

    assert any(isinstance(log_filter, PathRedactionFilter) for log_filter in filters)
