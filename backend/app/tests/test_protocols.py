import uuid

import pytest
from sqlalchemy import select

from app.modules.protocols.models import Tour, TourShare
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
    fields = ("title", "summary", *OWNER_ONLY, "gear", "food", "peaks")
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
