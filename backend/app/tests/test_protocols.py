import uuid

import pytest
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.protocols import history
from app.modules.protocols.models import Tour, TourRevision, TourShare
from app.tests.conftest import auth_header, register

TOURS = "/api/v1/tours"
GEAR_ITEMS = "/api/v1/gear/items"
FOODS = "/api/v1/nutrition/foods"

OWNER_ONLY = {
    "start_time": "2026-08-01T06:00:00Z",
    "end_time": "2026-08-01T14:30:00Z",
    "duration_minutes": 480,
    "pack_weight_start_g": 9000,
    "calories_burned": 3200.0,
}


class Person:
    def __init__(self, client, name):
        data = register(client, email=f"{name}@example.org", display_name=name.title())
        self.id = data["user"]["id"]
        self.headers = auth_header(data)


@pytest.fixture
def people(client):
    """anna owns the tours; bea gets `edit`, cleo `read`, dora nothing."""
    return {name: Person(client, name) for name in ("anna", "bea", "cleo", "dora")}


@pytest.fixture
def anna(people):
    return people["anna"]


@pytest.fixture
def bea(people):
    return people["bea"]


@pytest.fixture
def cleo(people):
    return people["cleo"]


@pytest.fixture
def dora(people):
    return people["dora"]


def create_tour(client, person, **fields):
    response = client.post(TOURS, json={"title": "Säntis", **fields}, headers=person.headers)
    assert response.status_code == 201, response.text
    return response.json()


def share(db, tour, person, permission):
    db.add(
        TourShare(
            tour_id=uuid.UUID(tour["id"]), user_id=uuid.UUID(person.id), permission=permission
        )
    )
    db.commit()


@pytest.fixture
def shared_tour(client, db, anna, bea, cleo):
    tour = create_tour(client, anna, summary="Schöne Tour", **OWNER_ONLY)
    share(db, tour, bea, "edit")
    share(db, tour, cleo, "read")
    return tour


def document(tour, **changes):
    """The tour as a client would send it back in a PUT."""
    fields = ("title", "summary", *OWNER_ONLY, "gear", "food", "peaks", "partners", "version")
    return {field: tour[field] for field in fields} | changes


def put(client, person, tour, **changes):
    return client.put(
        f"{TOURS}/{tour['id']}", json=document(tour, **changes), headers=person.headers
    )


def gear_item(client, person, **fields):
    body = {"name": "Zelt", "weight_g": 1500, **fields}
    return client.post(GEAR_ITEMS, json=body, headers=person.headers).json()


def food_item(client, person, **fields):
    body = {"name": "Nussriegel", "kcal_per_100g": 480, **fields}
    return client.post(FOODS, json=body, headers=person.headers).json()


# --- CRUD ---


def test_tours_require_login(client):
    assert client.get(TOURS).status_code == 401
    assert client.post(TOURS, json={"title": "X"}).status_code == 401
    assert client.get(f"{TOURS}/{uuid.uuid4()}").status_code == 401


def test_create_and_read_tour(client, anna):
    created = create_tour(client, anna, summary="Schöne Tour", **OWNER_ONLY)

    response = client.get(f"{TOURS}/{created['id']}", headers=anna.headers)

    assert response.status_code == 200
    assert response.json() == created
    assert created["owner"] == {"id": anna.id, "display_name": "Anna"}
    assert created["permission"] == "owner"
    assert created["version"] == 1
    assert {key: created[key] for key in OWNER_ONLY} == OWNER_ONLY
    assert created["calories_burned_source"] == "manual"
    assert created["computed"] == {
        "duration_minutes": 510,
        "pack_weight_start_g": 0,
        "calories_eaten": 0.0,
        "calories_burned": None,
    }
    assert (created["gear"], created["food"], created["peaks"]) == ([], [], [])
    assert created["track_source"] == "none" and created["start_point"] is None
    assert "email" not in response.text


def test_minimal_tour_and_client_generated_id(client, anna):
    tour_id = str(uuid.uuid4())

    created = create_tour(client, anna, id=tour_id)
    again = client.post(TOURS, json={"title": "X", "id": tour_id}, headers=anna.headers)

    assert created["id"] == tour_id
    assert created["calories_burned"] is None and created["calories_burned_source"] is None
    assert created["computed"]["duration_minutes"] is None
    assert again.json()["error"]["code"] == "id_taken"


@pytest.mark.parametrize(
    "fields",
    [
        {"title": " "},
        {"start_time": "2026-08-01T06:00:00"},
        {"start_time": "2026-08-01T10:00:00Z", "end_time": "2026-08-01T09:00:00Z"},
        {"duration_minutes": -1},
        {"calories_burned": "NaN"},
        {"peaks": [{"name": "Säntis", "lat": 47.2}]},
        {"peaks": [{"name": "Säntis", "lat": 95, "lon": 9}]},
        {"food": [{"food_item_id": str(uuid.uuid4()), "amount_g": 0}]},
        {"gear": [{"gear_item_id": str(uuid.uuid4()), "quantity": 0}]},
    ],
)
def test_tour_validates_input(client, anna, fields):
    response = client.post(TOURS, json={"title": "Säntis", **fields}, headers=anna.headers)

    assert response.status_code == 422


def test_owner_updates_tour_and_version_rises(client, anna):
    tour = create_tour(client, anna, **OWNER_ONLY)

    response = put(client, anna, tour, title="Säntis Nordwand", calories_burned=None)

    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Säntis Nordwand"
    assert updated["version"] == 2
    assert updated["calories_burned"] is None and updated["calories_burned_source"] is None
    assert updated["duration_minutes"] == 480


def test_delete_is_a_soft_delete_for_everyone(client, db, anna, bea, shared_tour):
    url = f"{TOURS}/{shared_tour['id']}"

    assert client.delete(url, headers=anna.headers).status_code == 204

    assert client.get(url, headers=anna.headers).status_code == 404
    assert client.get(url, headers=bea.headers).status_code == 404
    assert client.get(TOURS, headers=bea.headers).json()["total"] == 0
    row = db.scalar(select(Tour).where(Tour.id == uuid.UUID(shared_tour["id"])))
    assert row.deleted_at is not None


# --- Permissions ---


def test_read_access_by_permission(client, people, shared_tour):
    url = f"{TOURS}/{shared_tour['id']}"
    expected = {"anna": "owner", "bea": "edit", "cleo": "read"}

    for name, permission in expected.items():
        response = client.get(url, headers=people[name].headers)
        assert response.status_code == 200
        assert response.json()["permission"] == permission
        assert response.json()["owner"]["display_name"] == "Anna"
    assert client.get(url, headers=people["dora"].headers).status_code == 404
    assert client.get(f"{url}/waypoints", headers=people["dora"].headers).status_code == 404


def test_edit_may_change_text_fields_and_lists(client, bea, shared_tour):
    tent = gear_item(client, bea)

    response = put(
        client,
        bea,
        shared_tour,
        title="Säntis mit Bea",
        summary="Ergänzt von Bea",
        gear=[{"gear_item_id": tent["id"]}],
        peaks=[{"name": "Säntis", "elevation_m": 2502}],
    )

    assert response.status_code == 200
    updated = response.json()
    assert (updated["title"], updated["summary"]) == ("Säntis mit Bea", "Ergänzt von Bea")
    assert [entry["name"] for entry in updated["gear"]] == ["Zelt"]
    assert [peak["name"] for peak in updated["peaks"]] == ["Säntis"]
    assert {key: updated[key] for key in OWNER_ONLY} == OWNER_ONLY
    assert updated["version"] == shared_tour["version"] + 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start_time", "2026-08-01T07:00:00Z"),
        ("end_time", None),
        ("duration_minutes", 100),
        ("pack_weight_start_g", None),
        ("calories_burned", 1.0),
    ],
)
def test_edit_must_not_change_owner_only_fields(client, anna, bea, shared_tour, field, value):
    response = put(client, bea, shared_tour, **{field: value})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "owner_only_field"
    assert field in response.json()["error"]["message"]
    current = client.get(f"{TOURS}/{shared_tour['id']}", headers=anna.headers).json()
    assert current == shared_tour


def test_edit_may_send_times_in_another_timezone_unchanged(client, bea, shared_tour):
    response = put(client, bea, shared_tour, start_time="2026-08-01T08:00:00+02:00")

    assert response.status_code == 200


def test_edit_must_not_delete(client, anna, bea, shared_tour):
    url = f"{TOURS}/{shared_tour['id']}"

    response = client.delete(url, headers=bea.headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_permission"
    assert client.get(url, headers=anna.headers).status_code == 200


def test_read_must_not_change_anything(client, anna, cleo, shared_tour):
    url = f"{TOURS}/{shared_tour['id']}"
    waypoint = {"name": "Hütte", "lat": 47.25, "lon": 9.34}
    existing = client.post(f"{url}/waypoints", json=waypoint, headers=anna.headers).json()
    before = client.get(url, headers=anna.headers).json()

    responses = [
        put(client, cleo, shared_tour, title="Geändert"),
        client.delete(url, headers=cleo.headers),
        client.post(f"{url}/waypoints", json=waypoint, headers=cleo.headers),
        client.patch(f"{url}/waypoints/{existing['id']}", json={"name": "X"}, headers=cleo.headers),
        client.delete(f"{url}/waypoints/{existing['id']}", headers=cleo.headers),
    ]

    assert [response.status_code for response in responses] == [403] * 5
    assert client.get(url, headers=anna.headers).json() == before
    assert client.get(f"{url}/waypoints", headers=cleo.headers).json() == [existing]


def test_users_without_access_get_404_everywhere(client, dora, shared_tour):
    url = f"{TOURS}/{shared_tour['id']}"
    waypoint = {"name": "Hütte", "lat": 47.25, "lon": 9.34}

    responses = [
        client.get(url, headers=dora.headers),
        put(client, dora, shared_tour, title="Geändert"),
        client.delete(url, headers=dora.headers),
        client.get(f"{url}/waypoints", headers=dora.headers),
        client.post(f"{url}/waypoints", json=waypoint, headers=dora.headers),
    ]

    assert [response.status_code for response in responses] == [404] * 5


def test_admin_has_no_special_access_to_tours(client, db, anna, bea):
    # anna is the first registered user and therefore admin; bea owns this tour.
    tour = create_tour(client, bea)

    assert client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).status_code == 404


# --- List ---


def test_list_shows_own_and_shared_tours_by_scope(client, db, anna, bea, dora):
    own = create_tour(client, bea, title="Eigene", start_time="2026-07-01T06:00:00Z")
    shared = create_tour(
        client,
        anna,
        title="Geteilte",
        start_time="2026-08-01T06:00:00Z",
        peaks=[{"name": "Säntis"}, {"name": "Lisengrat"}],
    )
    create_tour(client, anna, title="Fremde")
    share(db, shared, bea, "read")

    def listed(**params):
        response = client.get(TOURS, params=params, headers=bea.headers)
        assert response.status_code == 200
        return [(item["title"], item["permission"]) for item in response.json()["items"]]

    assert listed() == [("Geteilte", "read"), ("Eigene", "owner")]
    assert listed(scope="mine") == [("Eigene", "owner")]
    assert listed(scope="shared") == [("Geteilte", "read")]
    assert client.get(TOURS, headers=dora.headers).json()["total"] == 0
    item = client.get(TOURS, params={"scope": "shared"}, headers=bea.headers).json()["items"][0]
    assert item["peaks"] == ["Säntis", "Lisengrat"]
    assert item["owner"]["display_name"] == "Anna"
    assert item["id"] == shared["id"] and own["id"] != shared["id"]
    assert "gear" not in item and "summary" not in item


def test_list_searches_filters_by_date_and_pages(client, anna):
    create_tour(client, anna, title="Säntis", start_time="2026-08-01T06:00:00Z")
    create_tour(
        client, anna, title="Altmann", summary="über den Säntis", start_time="2026-06-10T06:00:00Z"
    )
    create_tour(client, anna, title="Ohne Datum")

    def titles(**params):
        response = client.get(TOURS, params=params, headers=anna.headers)
        assert response.status_code == 200, response.text
        return [item["title"] for item in response.json()["items"]]

    assert titles() == ["Säntis", "Altmann", "Ohne Datum"]
    assert titles(q="säntis") == ["Säntis", "Altmann"]
    assert titles(start_from="2026-07-01T00:00:00Z") == ["Säntis"]
    assert titles(start_to="2026-07-01T00:00:00Z") == ["Altmann"]
    assert titles(limit=1, offset=1) == ["Altmann"]
    assert client.get(TOURS, params={"scope": "other"}, headers=anna.headers).status_code == 422


# --- Gear and food in tours ---


def test_gear_is_stored_as_snapshot_and_sums_into_pack_weight(client, anna):
    tent = gear_item(client, anna, name="Zelt", brand="MSR", weight_g=1500)
    pegs = gear_item(client, anna, name="Hering", weight_g=12)
    boots = gear_item(client, anna, name="Schuhe", weight_g=1300)
    tour = create_tour(
        client,
        anna,
        gear=[
            {"gear_item_id": tent["id"]},
            {"gear_item_id": pegs["id"], "quantity": 8},
            {"gear_item_id": boots["id"], "carried": False},
        ],
    )

    assert [(e["name"], e["brand"], e["weight_g"], e["quantity"]) for e in tour["gear"]] == [
        ("Hering", None, 12, 8),
        ("Schuhe", None, 1300, 1),
        ("Zelt", "MSR", 1500, 1),
    ]
    assert tour["computed"]["pack_weight_start_g"] == 1500 + 8 * 12

    # The gear item changes or disappears later; the tour keeps its snapshot.
    client.put(
        f"{GEAR_ITEMS}/{tent['id']}",
        json={"name": "Zelt neu", "weight_g": 900},
        headers=anna.headers,
    )
    client.delete(f"{GEAR_ITEMS}/{pegs['id']}", headers=anna.headers)
    updated = put(client, anna, tour, title="Später").json()

    assert updated["gear"] == tour["gear"]
    assert updated["computed"]["pack_weight_start_g"] == 1500 + 8 * 12


def test_gear_entries_can_be_changed_and_removed(client, anna):
    tent = gear_item(client, anna, name="Zelt", weight_g=1500)
    stove = gear_item(client, anna, name="Kocher", weight_g=300)
    tour = create_tour(
        client, anna, gear=[{"gear_item_id": tent["id"]}, {"gear_item_id": stove["id"]}]
    )
    kept = next(entry for entry in tour["gear"] if entry["name"] == "Zelt")

    updated = put(client, anna, tour, gear=[{**kept, "quantity": 2}]).json()

    assert updated["gear"] == [{**kept, "quantity": 2}]
    assert updated["computed"]["pack_weight_start_g"] == 3000


def test_gear_must_belong_to_the_caller_and_appear_once(client, anna, bea):
    mine = gear_item(client, anna)
    foreign = gear_item(client, bea)

    def post(*ids):
        gear = [{"gear_item_id": item_id} for item_id in ids]
        return client.post(TOURS, json={"title": "Tour", "gear": gear}, headers=anna.headers)

    assert post(foreign["id"]).json()["error"]["code"] == "unknown_gear_item"
    assert post(str(uuid.uuid4())).json()["error"]["code"] == "unknown_gear_item"
    assert post(mine["id"], mine["id"]).json()["error"]["code"] == "duplicate_gear_item"
    missing_reference = client.post(
        TOURS, json={"title": "Tour", "gear": [{"quantity": 1}]}, headers=anna.headers
    )
    assert missing_reference.json()["error"]["code"] == "unknown_gear_item"


def test_everyone_adds_their_own_gear_and_all_can_read_it(client, anna, bea, cleo, shared_tour):
    annas = gear_item(client, anna, name="Annas Zelt", weight_g=1500)
    beas = gear_item(client, bea, name="Beas Kocher", weight_g=300)
    with_anna = put(client, anna, shared_tour, gear=[{"gear_item_id": annas["id"]}]).json()

    foreign = put(client, bea, with_anna, gear=[*with_anna["gear"], {"gear_item_id": annas["id"]}])
    response = put(client, bea, with_anna, gear=[*with_anna["gear"], {"gear_item_id": beas["id"]}])

    assert foreign.status_code == 422
    assert response.status_code == 200
    seen_by_cleo = client.get(f"{TOURS}/{shared_tour['id']}", headers=cleo.headers).json()
    assert [entry["name"] for entry in seen_by_cleo["gear"]] == ["Annas Zelt", "Beas Kocher"]
    assert seen_by_cleo["computed"]["pack_weight_start_g"] == 1800
    # Reading the tour does not open the gear database of the others.
    assert client.get(f"{GEAR_ITEMS}/{annas['id']}", headers=cleo.headers).status_code == 404


def test_food_counts_into_pack_weight_when_carried_and_calories_when_eaten(client, anna):
    bar = food_item(client, anna, name="Nussriegel", kcal_per_100g=480)
    soup = food_item(client, anna, name="Suppe", kcal_per_100g=60)
    tour = create_tour(
        client,
        anna,
        food=[
            {"food_item_id": bar["id"], "amount_g": 80, "carried": True, "eaten": True},
            {"food_item_id": bar["id"], "amount_g": 40, "carried": True, "eaten": False},
            {
                "food_item_id": soup["id"],
                "amount_g": 400,
                "carried": False,
                "eaten": True,
                "eaten_at": "2026-08-01T12:00:00Z",
            },
        ],
    )

    assert [(e["name"], e["amount_g"], e["kcal"]) for e in tour["food"]] == [
        ("Nussriegel", 80.0, 384.0),
        ("Nussriegel", 40.0, 192.0),
        ("Suppe", 400.0, 240.0),
    ]
    assert tour["computed"]["pack_weight_start_g"] == 120
    assert tour["computed"]["calories_eaten"] == 624.0
    assert tour["food"][2]["eaten_at"] == "2026-08-01T12:00:00Z"


def test_food_calories_are_a_snapshot(client, anna):
    bar = food_item(client, anna, kcal_per_100g=480)
    tour = create_tour(
        client, anna, food=[{"food_item_id": bar["id"], "amount_g": 50, "eaten": True}]
    )
    client.put(
        f"{FOODS}/{bar['id']}", json={"name": "Neu", "kcal_per_100g": 100}, headers=anna.headers
    )

    entry = tour["food"][0]
    updated = put(client, anna, tour, food=[{**entry, "amount_g": 100}]).json()

    assert (updated["food"][0]["name"], updated["food"][0]["kcal_per_100g"]) == (
        "Nussriegel",
        480.0,
    )
    assert updated["food"][0]["kcal"] == 480.0
    assert updated["food"][0]["id"] == entry["id"]


def test_food_must_be_readable_by_the_caller(client, anna, bea):
    foreign = food_item(client, bea)

    for food_id in (foreign["id"], str(uuid.uuid4())):
        response = client.post(
            TOURS,
            json={"title": "Tour", "food": [{"food_item_id": food_id, "amount_g": 50}]},
            headers=anna.headers,
        )
        assert response.json()["error"]["code"] == "unknown_food_item"


def test_entry_ids_are_unique(client, anna):
    peak_id = str(uuid.uuid4())
    create_tour(client, anna, peaks=[{"id": peak_id, "name": "Säntis"}])

    reused = client.post(
        TOURS,
        json={"title": "Zweite", "peaks": [{"id": peak_id, "name": "X"}]},
        headers=anna.headers,
    )
    twice = client.post(
        TOURS,
        json={
            "title": "Dritte",
            "peaks": [{"id": peak_id, "name": "A"}, {"id": peak_id, "name": "B"}],
        },
        headers=anna.headers,
    )

    assert reused.json()["error"]["code"] == "id_taken"
    assert twice.json()["error"]["code"] == "duplicate_entry"


def test_peaks_keep_their_order_and_can_be_edited(client, anna):
    tour = create_tour(
        client,
        anna,
        peaks=[
            {"name": "Säntis", "elevation_m": 2502, "lat": 47.2494, "lon": 9.3432},
            {"name": "Altmann", "reached_at": "2026-08-01T11:00:00Z"},
        ],
    )
    saentis, altmann = tour["peaks"]

    updated = put(client, anna, tour, peaks=[altmann, {**saentis, "elevation_m": 2501}]).json()

    assert [peak["name"] for peak in updated["peaks"]] == ["Altmann", "Säntis"]
    assert updated["peaks"][1] == {**saentis, "elevation_m": 2501}
    assert put(client, anna, updated, peaks=[]).json()["peaks"] == []


# --- Waypoints ---


def test_waypoint_crud_raises_the_tour_version(client, anna, bea, shared_tour):
    url = f"{TOURS}/{shared_tour['id']}/waypoints"

    created = client.post(
        url,
        json={"name": "Hütte", "description": "Kaffee", "icon": "hut", "lat": 47.25, "lon": 9.34},
        headers=bea.headers,
    )
    assert created.status_code == 201
    waypoint = created.json()
    patched = client.patch(
        f"{url}/{waypoint['id']}",
        json={"name": "Berghütte", "description": None},
        headers=anna.headers,
    )

    assert patched.json() == {**waypoint, "name": "Berghütte", "description": None}
    assert client.get(url, headers=anna.headers).json() == [patched.json()]
    assert (
        client.patch(
            f"{url}/{waypoint['id']}", json={"lat": None}, headers=anna.headers
        ).status_code
        == 422
    )
    assert (
        client.patch(f"{url}/{uuid.uuid4()}", json={"name": "X"}, headers=anna.headers).status_code
        == 404
    )
    assert client.delete(f"{url}/{waypoint['id']}", headers=bea.headers).status_code == 204
    assert client.get(url, headers=anna.headers).json() == []
    tour = client.get(f"{TOURS}/{shared_tour['id']}", headers=anna.headers).json()
    assert tour["version"] == shared_tour["version"] + 3


def test_waypoint_validates_position(client, anna):
    tour = create_tour(client, anna)
    url = f"{TOURS}/{tour['id']}/waypoints"

    assert (
        client.post(url, json={"name": "X", "lat": 91, "lon": 9}, headers=anna.headers).status_code
        == 422
    )
    assert client.post(url, json={"name": "X", "lat": 47}, headers=anna.headers).status_code == 422


def test_tour_routes_are_absent_and_startup_fails_without_dependencies(monkeypatch):
    from app.core.config import get_settings
    from app.core.registry import ModuleRegistryError
    from app.main import create_app

    monkeypatch.setenv("ENABLED_MODULES", "auth,gear,protocols")
    get_settings.cache_clear()

    with pytest.raises(ModuleRegistryError, match="depends on 'nutrition'"):
        create_app()


# --- History ---


def revisions(client, person, tour, **params):
    response = client.get(f"{TOURS}/{tour['id']}/revisions", params=params, headers=person.headers)
    assert response.status_code == 200, response.text
    return response.json()


def revision(client, person, tour, version):
    response = client.get(f"{TOURS}/{tour['id']}/revisions/{version}", headers=person.headers)
    assert response.status_code == 200, response.text
    return response.json()


def restore(client, person, tour, version):
    return client.post(f"{TOURS}/{tour['id']}/revisions/{version}/restore", headers=person.headers)


def test_creating_a_tour_writes_the_first_revision(client, anna):
    tour = create_tour(client, anna, summary="Schöne Tour", peaks=[{"name": "Säntis"}])

    page = revisions(client, anna, tour)
    first = revision(client, anna, tour, 1)

    assert page["total"] == 1
    assert page["items"][0]["kind"] == "created"
    assert page["items"][0]["author"] == {"id": anna.id, "display_name": "Anna"}
    assert first["diff"] == {}
    assert first["snapshot"]["title"] == "Säntis"
    assert first["snapshot"]["peaks"] == tour["peaks"]
    assert "snapshot" not in page["items"][0]


def test_every_change_adds_a_revision_with_author_and_diff(client, anna, bea, shared_tour):
    tent = gear_item(client, bea)
    second = put(client, anna, shared_tour, title="Säntis Nord", duration_minutes=500).json()
    put(client, bea, second, summary="Mit Zelt", gear=[{"gear_item_id": tent["id"]}])

    page = revisions(client, anna, shared_tour)

    assert [(r["version"], r["kind"], r["change_summary"]) for r in page["items"]] == [
        (3, "updated", "summary, gear"),
        (2, "updated", "title, duration_minutes"),
        (1, "created", ""),
    ]
    assert [r["author"]["display_name"] for r in page["items"]] == ["Bea", "Anna", "Anna"]
    assert revision(client, anna, shared_tour, 2)["diff"] == {
        "title": {"old": "Säntis", "new": "Säntis Nord"},
        "duration_minutes": {"old": 480, "new": 500},
    }
    third = revision(client, anna, shared_tour, 3)
    assert third["diff"]["summary"] == {"old": "Schöne Tour", "new": "Mit Zelt"}
    assert [entry["name"] for entry in third["diff"]["gear"]["added"]] == ["Zelt"]
    assert third["diff"]["gear"]["removed"] == [] and third["diff"]["gear"]["changed"] == []
    assert third["snapshot"]["title"] == "Säntis Nord"


def test_diff_describes_changed_removed_and_reordered_entries(client, anna):
    tour = create_tour(client, anna, peaks=[{"name": "Säntis"}, {"name": "Altmann"}, {"name": "X"}])
    saentis, altmann, removed = tour["peaks"]

    put(client, anna, tour, peaks=[altmann, {**saentis, "elevation_m": 2502}])

    peaks = revision(client, anna, tour, 2)["diff"]["peaks"]
    assert peaks["removed"] == [removed]
    assert peaks["added"] == []
    assert peaks["changed"] == [
        {
            "id": saentis["id"],
            "name": "Säntis",
            "changes": {"elevation_m": {"old": None, "new": 2502}},
        }
    ]
    assert peaks["reordered"] is True


def test_unchanged_update_adds_no_revision(client, anna):
    tour = create_tour(client, anna, **OWNER_ONLY)

    response = put(client, anna, tour)

    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert revisions(client, anna, tour)["total"] == 1


def test_waypoint_changes_are_part_of_the_history(client, anna):
    tour = create_tour(client, anna)
    url = f"{TOURS}/{tour['id']}/waypoints"
    waypoint = client.post(
        url, json={"name": "Hütte", "lat": 47.25, "lon": 9.34}, headers=anna.headers
    ).json()
    client.delete(f"{url}/{waypoint['id']}", headers=anna.headers)

    page = revisions(client, anna, tour)

    assert [(r["version"], r["change_summary"]) for r in page["items"]] == [
        (3, "waypoints"),
        (2, "waypoints"),
        (1, ""),
    ]
    assert revision(client, anna, tour, 2)["snapshot"]["waypoints"] == [waypoint]
    assert revision(client, anna, tour, 3)["diff"]["waypoints"]["removed"] == [waypoint]


def test_history_is_never_rewritten(client, db, anna):
    tour = create_tour(client, anna)
    current = tour
    for number in range(2, 6):
        current = put(client, anna, current, title=f"Stand {number}").json()
    before = [revision(client, anna, tour, version) for version in range(1, 6)]

    restore(client, anna, tour, 2)
    client.delete(f"{TOURS}/{tour['id']}", headers=anna.headers)

    stored = db.scalars(
        select(TourRevision)
        .where(TourRevision.tour_id == uuid.UUID(tour["id"]))
        .order_by(TourRevision.version)
    ).all()
    assert [row.version for row in stored] == [1, 2, 3, 4, 5, 6, 7]
    assert [row.kind for row in stored[5:]] == ["restored", "deleted"]
    assert [row.snapshot for row in stored[:5]] == [r["snapshot"] for r in before]
    assert [row.snapshot["title"] for row in stored] == [
        "Säntis",
        "Stand 2",
        "Stand 3",
        "Stand 4",
        "Stand 5",
        "Stand 2",
        "Stand 2",
    ]


def test_history_access_follows_the_tour_permissions(client, people, shared_tour):
    url = f"{TOURS}/{shared_tour['id']}/revisions"

    for name in ("anna", "bea", "cleo"):
        assert client.get(url, headers=people[name].headers).status_code == 200
        assert client.get(f"{url}/1", headers=people[name].headers).status_code == 200
    dora = people["dora"].headers
    assert client.get(url, headers=dora).status_code == 404
    assert client.get(f"{url}/1", headers=dora).status_code == 404
    assert client.post(f"{url}/1/restore", headers=dora).status_code == 404
    assert client.post(f"{url}/1/restore", headers=people["cleo"].headers).status_code == 403
    assert client.get(url).status_code == 401
    assert client.get(f"{url}/99", headers=people["anna"].headers).status_code == 404


def test_history_pages_and_compares_versions(client, anna):
    tour = create_tour(client, anna, title="A")
    second = put(client, anna, tour, title="B").json()
    put(client, anna, second, title="C", summary="neu")

    page = revisions(client, anna, tour, limit=1, offset=1)
    comparison = client.get(
        f"{TOURS}/{tour['id']}/revisions/1/compare/3", headers=anna.headers
    ).json()

    assert (page["total"], [r["version"] for r in page["items"]]) == (3, [2])
    assert comparison == {
        "from_version": 1,
        "to_version": 3,
        "diff": {"title": {"old": "A", "new": "C"}, "summary": {"old": None, "new": "neu"}},
    }


def test_author_is_anonymised_when_the_user_is_removed(client, db, anna, bea, shared_tour):
    put(client, bea, shared_tour, title="Von Bea")

    db.delete(db.get(User, uuid.UUID(bea.id)))
    db.commit()

    page = revisions(client, anna, shared_tour)
    assert [(r["version"], r["author"]) for r in page["items"][:1]] == [(2, None)]
    assert page["items"][1]["author"]["display_name"] == "Anna"


# --- Restore ---


def test_restore_brings_back_an_old_state_as_a_new_revision(client, anna):
    tent = gear_item(client, anna, name="Zelt", weight_g=1500)
    bar = food_item(client, anna)
    tour = create_tour(
        client,
        anna,
        summary="Original",
        gear=[{"gear_item_id": tent["id"]}],
        food=[{"food_item_id": bar["id"], "amount_g": 80, "eaten": True}],
        peaks=[{"name": "Säntis", "elevation_m": 2502}],
        **OWNER_ONLY,
    )
    changed = put(
        client,
        anna,
        tour,
        title="Kaputt",
        summary=None,
        gear=[],
        food=[],
        peaks=[],
        calories_burned=None,
    ).json()
    assert changed["computed"]["pack_weight_start_g"] == 0

    response = restore(client, anna, tour, 1)

    assert response.status_code == 200
    restored = response.json()
    assert restored["version"] == 3
    ignored = {"version", "updated_at"}
    assert {k: v for k, v in restored.items() if k not in ignored} == {
        k: v for k, v in tour.items() if k not in ignored
    }
    latest = revisions(client, anna, tour)["items"][0]
    assert (latest["version"], latest["kind"], latest["change_summary"]) == (
        3,
        "restored",
        "version 1",
    )
    assert revision(client, anna, tour, 3)["diff"]["title"] == {"old": "Kaputt", "new": "Säntis"}


def test_restore_works_after_gear_was_removed_and_added_again(client, anna):
    tent = gear_item(client, anna, name="Zelt", weight_g=1500)
    tour = create_tour(client, anna, gear=[{"gear_item_id": tent["id"]}])
    original_entry = tour["gear"][0]

    # Remove the entry and add the same item again in one change: a new entry id.
    readded = put(client, anna, tour, gear=[{"gear_item_id": tent["id"], "quantity": 2}]).json()
    response = restore(client, anna, tour, 1)

    assert readded["gear"][0]["id"] != original_entry["id"]
    assert response.status_code == 200
    assert response.json()["gear"] == [original_entry]


def test_restore_keeps_snapshots_of_gear_that_no_longer_exists(client, db, anna, bea, shared_tour):
    kocher = gear_item(client, bea, name="Beas Kocher", weight_g=300)
    with_gear = put(client, bea, shared_tour, gear=[{"gear_item_id": kocher["id"]}]).json()
    put(client, anna, with_gear, gear=[])
    db.delete(db.get(User, uuid.UUID(bea.id)))
    db.commit()

    response = restore(client, anna, shared_tour, 2)

    assert response.status_code == 200
    entry = response.json()["gear"][0]
    assert (entry["name"], entry["weight_g"], entry["gear_item_id"]) == ("Beas Kocher", 300, None)


def test_edit_may_restore_only_without_touching_owner_only_fields(client, anna, bea, shared_tour):
    second = put(client, bea, shared_tour, title="Von Bea").json()
    put(client, anna, second, duration_minutes=100)

    forbidden = restore(client, bea, shared_tour, 1)
    current = client.get(f"{TOURS}/{shared_tour['id']}", headers=anna.headers).json()
    put(client, anna, current, duration_minutes=480)
    allowed = restore(client, bea, shared_tour, 1)

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "owner_only_field"
    assert current["title"] == "Von Bea" and current["version"] == 3
    assert allowed.status_code == 200
    assert allowed.json()["title"] == "Säntis"


# --- Conflicts ---


def test_outdated_version_is_rejected_with_the_current_tour(client, anna, bea, shared_tour):
    newer = put(client, anna, shared_tour, title="Von Anna").json()

    response = put(client, bea, shared_tour, summary="Von Bea")

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "version_conflict"
    assert body["current"]["version"] == 2
    assert body["current"]["title"] == "Von Anna"
    assert body["current"]["permission"] == "edit"
    assert revisions(client, anna, shared_tour)["total"] == 2

    # The client merges field by field on top of the current state and tries again.
    merged = put(client, bea, body["current"], summary="Von Bea")
    assert merged.status_code == 200
    assert (merged.json()["title"], merged.json()["summary"]) == ("Von Anna", "Von Bea")
    assert merged.json()["version"] == newer["version"] + 1


def test_conflict_is_reported_before_the_owner_only_check(client, anna, bea, shared_tour):
    put(client, anna, shared_tour, duration_minutes=100)

    response = put(client, bea, shared_tour, title="Von Bea")

    assert response.status_code == 409


def test_update_requires_the_base_version(client, anna):
    tour = create_tour(client, anna)
    body = document(tour)
    del body["version"]

    response = client.put(f"{TOURS}/{tour['id']}", json=body, headers=anna.headers)

    assert response.status_code == 422


def test_concurrent_writes_cannot_both_succeed(client, session_factory, anna):
    tour_id = uuid.UUID(create_tour(client, anna)["id"])
    with session_factory() as first, session_factory() as second:
        author = first.get(User, uuid.UUID(anna.id))
        second_author = second.get(User, author.id)
        tour_a = first.get(Tour, tour_id)
        tour_b = second.get(Tour, tour_id)
        tour_a.title = "A"
        tour_b.title = "B"
        history.record_change(first, tour_a, author, history.UPDATED)

        with pytest.raises(history.VersionConflictError):
            history.record_change(second, tour_b, second_author, history.UPDATED)

    with session_factory() as check:
        stored = check.get(Tour, tour_id)
        assert (stored.title, stored.version) == ("A", 2)
        versions = check.scalars(
            select(TourRevision.version).where(TourRevision.tour_id == tour_id)
        ).all()
        assert sorted(versions) == [1, 2]


# --- Shares ---


def shares_url(tour, person=None):
    return f"{TOURS}/{tour['id']}/shares" + (f"/{person.id}" if person else "")


def test_owner_shares_changes_and_removes_access(client, anna, bea):
    tour = create_tour(client, anna)
    tour_url = f"{TOURS}/{tour['id']}"

    created = client.post(
        shares_url(tour), json={"user_id": bea.id, "permission": "read"}, headers=anna.headers
    )

    assert created.status_code == 201
    assert created.json()["user"] == {"id": bea.id, "display_name": "Bea"}
    assert created.json()["permission"] == "read"
    assert client.get(tour_url, headers=bea.headers).json()["permission"] == "read"
    assert client.get(shares_url(tour), headers=anna.headers).json() == [created.json()]
    assert "email" not in created.text

    patched = client.patch(shares_url(tour, bea), json={"permission": "edit"}, headers=anna.headers)

    assert patched.json()["permission"] == "edit"
    assert client.get(tour_url, headers=bea.headers).json()["permission"] == "edit"
    assert client.get(TOURS, params={"scope": "shared"}, headers=bea.headers).json()["total"] == 1

    assert client.delete(shares_url(tour, bea), headers=anna.headers).status_code == 204

    assert client.get(tour_url, headers=bea.headers).status_code == 404
    assert client.get(TOURS, headers=bea.headers).json()["total"] == 0
    assert client.get(shares_url(tour), headers=anna.headers).json() == []
    # Managing shares is not part of the tour history.
    assert revisions(client, anna, tour)["total"] == 1


def test_share_rejects_invalid_targets(client, anna, bea):
    tour = create_tour(client, anna)

    def post(user_id, permission="read"):
        body = {"user_id": user_id, "permission": permission}
        return client.post(shares_url(tour), json=body, headers=anna.headers)

    assert post(str(uuid.uuid4())).json()["error"]["code"] == "unknown_user"
    assert post(anna.id).json()["error"]["code"] == "share_with_owner"
    assert post(bea.id, "owner").status_code == 422
    assert post(bea.id).status_code == 201
    assert post(bea.id, "edit").json()["error"]["code"] == "already_shared"
    missing = client.patch(
        shares_url(tour) + f"/{uuid.uuid4()}", json={"permission": "edit"}, headers=anna.headers
    )
    assert missing.status_code == 404


def test_only_the_owner_manages_shares(client, people, shared_tour):
    dora = people["dora"]
    body = {"user_id": dora.id, "permission": "read"}

    for name in ("bea", "cleo"):
        headers = people[name].headers
        assert client.get(shares_url(shared_tour), headers=headers).status_code == 403
        assert client.post(shares_url(shared_tour), json=body, headers=headers).status_code == 403
        patch = client.patch(
            shares_url(shared_tour, people["cleo"]), json={"permission": "edit"}, headers=headers
        )
        assert patch.status_code == 403
    assert client.get(shares_url(shared_tour), headers=dora.headers).status_code == 404
    assert client.post(shares_url(shared_tour), json=body, headers=dora.headers).status_code == 404
    bea_removes_cleo = client.delete(
        shares_url(shared_tour, people["cleo"]), headers=people["bea"].headers
    )
    assert bea_removes_cleo.status_code == 403
    owner_view = client.get(shares_url(shared_tour), headers=people["anna"].headers).json()
    assert {share["user"]["display_name"]: share["permission"] for share in owner_view} == {
        "Bea": "edit",
        "Cleo": "read",
    }


def test_users_may_give_up_their_own_share(client, anna, cleo, shared_tour):
    response = client.delete(shares_url(shared_tour, cleo), headers=cleo.headers)

    assert response.status_code == 204
    assert client.get(f"{TOURS}/{shared_tour['id']}", headers=cleo.headers).status_code == 404
    remaining = client.get(shares_url(shared_tour), headers=anna.headers).json()
    assert [share["user"]["display_name"] for share in remaining] == ["Bea"]


# --- Contacts and partners ---

CONTACTS = "/api/v1/contacts"


def create_contact(client, person, display_name="Dani", **fields):
    body = {"display_name": display_name, **fields}
    response = client.post(CONTACTS, json=body, headers=person.headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_contact_crud_and_privacy(client, anna, bea):
    contact = create_contact(client, anna, "  Dani  ")
    url = f"{CONTACTS}/{contact['id']}"

    assert contact == {"id": contact["id"], "display_name": "Dani", "linked_user": None}
    assert client.get(CONTACTS, headers=anna.headers).json() == [contact]
    assert client.get(CONTACTS, headers=bea.headers).json() == []
    assert client.get(CONTACTS).status_code == 401
    assert client.patch(url, json={"display_name": "X"}, headers=bea.headers).status_code == 404
    assert client.delete(url, headers=bea.headers).status_code == 404
    renamed = client.patch(url, json={"display_name": "Daniela"}, headers=anna.headers)
    assert renamed.json()["display_name"] == "Daniela"
    assert client.patch(url, json={"display_name": None}, headers=anna.headers).status_code == 422
    assert (
        client.post(CONTACTS, json={"display_name": " "}, headers=anna.headers).status_code == 422
    )
    assert client.delete(url, headers=anna.headers).status_code == 204
    assert client.get(CONTACTS, headers=anna.headers).json() == []


def test_placeholder_can_be_linked_to_a_user_later(client, anna, bea):
    contact = create_contact(client, anna, "Bea (Platzhalter)")
    tour = create_tour(client, anna, partners=[{"contact_id": contact["id"]}])
    url = f"{CONTACTS}/{contact['id']}"

    assert tour["partners"] == [
        {"contact_id": contact["id"], "display_name": "Bea (Platzhalter)", "linked_user_id": None}
    ]

    linked = client.patch(url, json={"linked_user_id": bea.id}, headers=anna.headers)

    assert linked.json()["linked_user"] == {"id": bea.id, "display_name": "Bea"}
    assert linked.json()["display_name"] == "Bea (Platzhalter)"
    # The link applies at once to every tour that lists the contact.
    current = client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).json()
    assert current["partners"][0]["linked_user_id"] == bea.id
    # Being a partner does not give access to the tour.
    assert client.get(f"{TOURS}/{tour['id']}", headers=bea.headers).status_code == 404
    unknown = client.patch(url, json={"linked_user_id": str(uuid.uuid4())}, headers=anna.headers)
    assert unknown.json()["error"]["code"] == "unknown_user"
    unlinked = client.patch(url, json={"linked_user_id": None}, headers=anna.headers)
    assert unlinked.json()["linked_user"] is None


def test_partners_are_part_of_the_tour_document_and_history(client, anna):
    dani = create_contact(client, anna, "Dani")
    eva = create_contact(client, anna, "Eva")
    tour = create_tour(client, anna, partners=[{"contact_id": dani["id"]}])

    updated = put(client, anna, tour, partners=[{"contact_id": eva["id"]}]).json()

    assert [partner["display_name"] for partner in updated["partners"]] == ["Eva"]
    diff = revision(client, anna, tour, 2)["diff"]["partners"]
    assert diff["added"] == [{"id": eva["id"], "name": "Eva"}]
    assert diff["removed"] == [{"id": dani["id"], "name": "Dani"}]
    restored = restore(client, anna, tour, 1).json()
    assert [partner["display_name"] for partner in restored["partners"]] == ["Dani"]


def test_partners_must_be_own_contacts_and_unique(client, anna, bea):
    mine = create_contact(client, anna)
    foreign = create_contact(client, bea)

    def post(*ids):
        partners = [{"contact_id": contact_id} for contact_id in ids]
        return client.post(TOURS, json={"title": "T", "partners": partners}, headers=anna.headers)

    assert post(foreign["id"]).json()["error"]["code"] == "unknown_contact"
    assert post(str(uuid.uuid4())).json()["error"]["code"] == "unknown_contact"
    assert post(mine["id"], mine["id"]).json()["error"]["code"] == "duplicate_partner"


def test_edit_users_add_their_own_contacts_and_all_read_the_names(
    client, anna, bea, cleo, shared_tour
):
    annas = create_contact(client, anna, "Annas Freund")
    beas = create_contact(client, bea, "Beas Freundin")
    with_anna = put(client, anna, shared_tour, partners=[{"contact_id": annas["id"]}]).json()

    response = put(
        client, bea, with_anna, partners=[*with_anna["partners"], {"contact_id": beas["id"]}]
    )

    assert response.status_code == 200
    seen = client.get(f"{TOURS}/{shared_tour['id']}", headers=cleo.headers).json()
    assert [p["display_name"] for p in seen["partners"]] == ["Annas Freund", "Beas Freundin"]
    assert client.get(CONTACTS, headers=cleo.headers).json() == []


def test_deleted_contact_stays_visible_in_old_tours(client, anna):
    contact = create_contact(client, anna, "Dani")
    tour = create_tour(client, anna, partners=[{"contact_id": contact["id"]}])

    client.delete(f"{CONTACTS}/{contact['id']}", headers=anna.headers)

    current = client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).json()
    assert [partner["display_name"] for partner in current["partners"]] == ["Dani"]
    again = client.post(
        TOURS,
        json={"title": "Neu", "partners": [{"contact_id": contact["id"]}]},
        headers=anna.headers,
    )
    assert again.json()["error"]["code"] == "unknown_contact"


# --- Tags and the map of all tours ---


def _gpx(points) -> bytes:
    body = "".join(f'<trkpt lat="{lat}" lon="{lon}"><ele>1000</ele></trkpt>' for lat, lon in points)
    return (
        '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><trkseg>{body}</trkseg></trk></gpx>"
    ).encode()


def _add_track(client, person, tour, points) -> None:
    files = {"file": ("t.gpx", _gpx(points), "application/gpx+xml")}
    response = client.put(f"{TOURS}/{tour['id']}/gpx", files=files, headers=person.headers)
    assert response.status_code == 200, response.text


def test_tours_carry_tags_and_keep_them_when_a_client_does_not_send_any(client, anna):
    tour = create_tour(client, anna, tags=[" Skitour ", "skitour", "mit Kindern"])
    # Trimmed; the same tag in another case counts once, the first spelling stays.
    assert tour["tags"] == ["Skitour", "mit Kindern"]
    listed = client.get(TOURS, headers=anna.headers).json()["items"][0]
    assert listed["tags"] == ["Skitour", "mit Kindern"]

    # An older app does not know tags and sends none: they stay.
    renamed = put(client, anna, tour, title="Säntis im Winter").json()
    assert renamed["tags"] == ["Skitour", "mit Kindern"] and renamed["version"] == 2
    # An empty list removes them.
    cleared = put(client, anna, renamed, tags=[]).json()
    assert cleared["tags"] == []
    assert create_tour(client, anna, title="Ohne")["tags"] == []

    for bad in ([""], ["x" * 41], ["tag"] * 0 + [str(i) for i in range(21)]):
        assert put(client, anna, cleared, tags=bad).status_code == 422


def test_tags_are_part_of_history_and_may_be_set_with_edit_rights(client, anna, bea, shared_tour):
    tagged = put(client, bea, shared_tour, tags=["Hochtour"])
    assert tagged.status_code == 200 and tagged.json()["tags"] == ["Hochtour"]
    again = put(client, anna, tagged.json(), tags=["Hochtour", "Gletscher"]).json()

    assert [r["change_summary"] for r in revisions(client, anna, shared_tour)["items"]][:2] == [
        "tags",
        "tags",
    ]
    assert revision(client, anna, shared_tour, 3)["diff"]["tags"] == {
        "old": ["Hochtour"],
        "new": ["Hochtour", "Gletscher"],
    }
    # Setting the first tags is a change from none, not from "unknown".
    assert revision(client, anna, shared_tour, 2)["diff"]["tags"] == {
        "old": [],
        "new": ["Hochtour"],
    }

    # Restoring the version before brings its tags back, as a new revision.
    restored = restore(client, anna, shared_tour, 2)
    assert restored.status_code == 200, restored.text
    assert restored.json()["tags"] == ["Hochtour"]
    assert restored.json()["version"] == again["version"] + 1


def test_list_filters_by_tag_and_names_the_tags_in_use(client, db, anna, bea, dora):
    ski = create_tour(client, anna, title="Piz Palü", tags=["Skitour", "Gletscher"])
    create_tour(client, anna, title="Alpstein", tags=["Wandern"])
    create_tour(client, anna, title="Tödi", tags=["skitour"])
    create_tour(client, anna, title="Ohne")
    theirs = create_tour(client, bea, title="Beas Tour", tags=["Skitour", "Privat"])
    share(db, theirs, anna, "read")

    def titles(person=anna, **params):
        page = client.get(TOURS, params=params, headers=person.headers).json()
        return sorted(item["title"] for item in page["items"]), page["total"]

    # Case does not matter; shared tours count too.
    assert titles(tag="SKITOUR") == (["Beas Tour", "Piz Palü", "Tödi"], 3)
    assert titles(tag="skitour", scope="mine") == (["Piz Palü", "Tödi"], 2)
    assert titles(tag="Gletscher", q="palü") == (["Piz Palü"], 1)
    assert titles(tag="Nichts") == ([], 0)
    # Paging counts the tours that carry the tag.
    page = client.get(TOURS, params={"tag": "skitour", "limit": 2}, headers=anna.headers).json()
    assert len(page["items"]) == 2 and page["total"] == 3

    tags = client.get(f"{TOURS}/tags", headers=anna.headers).json()
    # The most used first, then by name; one entry whatever the case.
    assert tags == [
        {"tag": "Skitour", "count": 3},
        {"tag": "Gletscher", "count": 1},
        {"tag": "Privat", "count": 1},
        {"tag": "Wandern", "count": 1},
    ]
    mine = client.get(f"{TOURS}/tags", params={"scope": "mine"}, headers=anna.headers).json()
    assert {"tag": "Privat", "count": 1} not in mine and mine[0] == {"tag": "Skitour", "count": 2}
    assert client.get(f"{TOURS}/tags", headers=dora.headers).json() == []
    assert client.get(f"{TOURS}/tags").status_code == 401
    assert ski["tags"] == ["Skitour", "Gletscher"]


def test_all_tours_come_as_lines_for_one_map(client, db, anna, bea, dora):
    long_walk = [(47.0 + i * 0.0001, 9.0) for i in range(900)]
    walked = create_tour(
        client, anna, title="Lang", tags=["Wandern"], start_time="2026-07-18T07:00:00Z"
    )
    _add_track(client, anna, walked, long_walk)
    create_tour(client, anna, title="Ohne alles")
    # No track, but a start point set by hand: a point on the map.
    pointed = create_tour(client, anna, title="Nur Start", tags=["Skitour"])
    points = {"start": {"lat": 46.5, "lon": 9.9, "name": "Diavolezza"}, "end": None}
    assert (
        client.put(f"{TOURS}/{pointed['id']}/points", json=points, headers=anna.headers).status_code
        == 200
    )
    theirs = create_tour(client, bea, title="Beas Tour")
    _add_track(client, bea, theirs, [(46.0, 8.0), (46.01, 8.0)])
    share(db, theirs, anna, "read")
    hidden = create_tour(client, dora, title="Doras Tour")
    _add_track(client, dora, hidden, [(45.0, 7.0), (45.01, 7.0)])

    body = client.get(f"{TOURS}/tracks", headers=anna.headers).json()
    assert body["type"] == "FeatureCollection"
    by_title = {f["properties"]["title"]: f for f in body["features"]}
    assert set(by_title) == {"Lang", "Nur Start", "Beas Tour"}

    line = by_title["Lang"]
    assert line["properties"] == {
        "tour_id": walked["id"],
        "title": "Lang",
        "date": "2026-07-18",
        "tags": ["Wandern"],
        "own": True,
        "distance_m": line["properties"]["distance_m"],
        "ascent_m": line["properties"]["ascent_m"],
    }
    assert line["properties"]["distance_m"] > 9000
    coordinates = line["geometry"]["coordinates"]
    # Thinned out, but from the first to the last point.
    assert line["geometry"]["type"] == "LineString" and len(coordinates) <= 201
    assert coordinates[0] == [9.0, 47.0] and coordinates[-1] == [9.0, 47.0899]
    assert by_title["Nur Start"]["geometry"] == {"type": "Point", "coordinates": [9.9, 46.5]}
    assert by_title["Beas Tour"]["properties"]["own"] is False

    def shown(**params):
        found = client.get(f"{TOURS}/tracks", params=params, headers=anna.headers).json()
        return sorted(f["properties"]["title"] for f in found["features"])

    assert shown(scope="mine") == ["Lang", "Nur Start"]
    assert shown(tag="skitour") == ["Nur Start"]
    assert shown(scope="shared") == ["Beas Tour"]
    assert (
        client.get(f"{TOURS}/tracks", headers=dora.headers).json()["features"][0]["properties"][
            "title"
        ]
        == "Doras Tour"
    )
    assert client.get(f"{TOURS}/tracks").status_code == 401
