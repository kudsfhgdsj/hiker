# ruff: noqa: F811 - fixtures are imported from the protocols tests
import uuid

import pytest

from app.tests.test_protocols import (  # noqa: F401
    TOURS,
    anna,
    bea,
    cleo,
    create_tour,
    document,
    dora,
    gear_item,
    people,
    put,
    revisions,
    share,
)

CHANGES = "/api/v1/sync/changes"
PUSH = "/api/v1/sync/push"
GEAR_ITEMS = "/api/v1/gear/items"
FOODS = "/api/v1/nutrition/foods"


def changes(client, person, since=None):
    params = {"since": since} if since else {}
    response = client.get(CHANGES, params=params, headers=person.headers)
    assert response.status_code == 200, response.text
    return response.json()


def push(client, person, *operations):
    response = client.post(PUSH, json={"operations": list(operations)}, headers=person.headers)
    assert response.status_code == 200, response.text
    return response.json()["results"]


def op(collection, record_id, data=None, **fields):
    return {
        "collection": collection,
        "op": "delete" if data is None and "op" not in fields else "upsert",
        "id": record_id,
        "data": data,
        **fields,
    }


def test_sync_requires_login(client):
    assert client.get(CHANGES).status_code == 401
    assert client.post(PUSH, json={"operations": []}).status_code == 401


# --- Changes ---


def test_first_sync_delivers_everything_of_the_user(client, anna, bea):
    tent = gear_item(client, anna, name="Zelt")
    gear_item(client, bea, name="Fremd")
    food = client.post(
        FOODS, json={"name": "Riegel", "kcal_per_100g": 480}, headers=anna.headers
    ).json()
    tour = create_tour(client, anna)

    data = changes(client, anna)

    collections = data["collections"]
    assert set(collections) == {
        "gear_items",
        "gear_types",
        "gear_tags",
        "gear_lists",
        "foods",
        "tours",
        "routes",
        "paces",
    }
    assert [item["id"] for item in collections["gear_items"]["changed"]] == [tent["id"]]
    assert [f["id"] for f in collections["foods"]["changed"]] == [food["id"]]
    assert collections["tours"]["changed"][0]["id"] == tour["id"]
    assert collections["tours"]["changed"][0]["permission"] == "owner"
    assert collections["tours"]["ids"] == [tour["id"]]
    assert collections["gear_types"]["full"] is True
    assert collections["gear_items"]["full"] is False
    assert data["server_time"] is not None


def test_later_sync_delivers_only_what_changed_and_what_was_deleted(client, anna):
    kept = gear_item(client, anna, name="Bleibt")
    changed = gear_item(client, anna, name="Alt")
    removed = gear_item(client, anna, name="Weg")
    tour = create_tour(client, anna)
    old_tour = create_tour(client, anna, title="Unverändert")
    since = changes(client, anna)["server_time"]

    client.put(f"{GEAR_ITEMS}/{changed['id']}", json={"name": "Neu"}, headers=anna.headers)
    client.delete(f"{GEAR_ITEMS}/{removed['id']}", headers=anna.headers)
    put(client, anna, tour, title="Neuer Titel")

    data = changes(client, anna, since)["collections"]

    assert [(i["id"], i["name"]) for i in data["gear_items"]["changed"]] == [(changed["id"], "Neu")]
    assert data["gear_items"]["deleted"] == [removed["id"]]
    assert kept["id"] not in str(data["gear_items"])
    assert [t["title"] for t in data["tours"]["changed"]] == ["Neuer Titel"]
    assert sorted(data["tours"]["ids"]) == sorted([tour["id"], old_tour["id"]])
    assert (
        changes(client, anna, changes(client, anna)["server_time"])["collections"]["tours"][
            "changed"
        ]
        == []
    )


def test_shared_tours_arrive_and_leave_with_the_share(client, db, anna, bea):
    tour = create_tour(client, anna)
    share(db, tour, bea, "edit")

    with_share = changes(client, bea)["collections"]["tours"]
    client.delete(f"{TOURS}/{tour['id']}/shares/{bea.id}", headers=anna.headers)
    without = changes(client, bea, changes(client, bea)["server_time"])["collections"]["tours"]

    assert [(t["id"], t["permission"]) for t in with_share["changed"]] == [(tour["id"], "edit")]
    # Nothing "changed", but the tour is no longer in the list of visible ids.
    assert without["changed"] == [] and without["ids"] == []


def test_deleted_tour_is_reported_as_deleted(client, anna):
    tour = create_tour(client, anna)
    since = changes(client, anna)["server_time"]

    client.delete(f"{TOURS}/{tour['id']}", headers=anna.headers)

    data = changes(client, anna, since)["collections"]["tours"]
    assert data["deleted"] == [tour["id"]] and data["ids"] == []


def test_health_data_of_shared_tours_stays_hidden_in_the_sync(client, db, anna, bea):
    from app.tests.test_track import garmin_gpx, upload

    tour = upload(client, anna, create_tour(client, anna), garmin_gpx()).json()
    share(db, tour, bea, "read")

    [shared] = changes(client, bea)["collections"]["tours"]["changed"]
    [own] = changes(client, anna)["collections"]["tours"]["changed"]

    assert "heart_rate" not in shared["track_stats"] and shared["calories_estimate"] is None
    assert "heart_rate" in own["track_stats"]


# --- Push ---


def test_push_creates_updates_and_deletes_gear_made_offline(client, anna):
    new_id = str(uuid.uuid4())
    existing = gear_item(client, anna, name="Alt", weight_g=100)
    doomed = gear_item(client, anna, name="Weg")

    results = push(
        client,
        anna,
        op("gear_items", new_id, {"name": "Offline angelegt", "weight_g": 450}),
        op("gear_items", existing["id"], {**existing, "name": "Offline geändert"}),
        op("gear_items", doomed["id"]),
    )

    assert [r["status"] for r in results] == ["ok", "ok", "ok"]
    assert results[0]["record"]["id"] == new_id
    assert results[1]["record"]["name"] == "Offline geändert"
    assert results[1]["record"]["weight_g"] == 100
    assert results[2]["record"] is None
    names = {i["name"] for i in client.get(GEAR_ITEMS, headers=anna.headers).json()["items"]}
    assert names == {"Offline angelegt", "Offline geändert"}


def test_push_reports_a_conflict_when_the_record_changed_on_the_server(client, anna):
    item = gear_item(client, anna, name="Basis")
    newer = client.put(
        f"{GEAR_ITEMS}/{item['id']}", json={"name": "Am Server geändert"}, headers=anna.headers
    ).json()

    [conflict] = push(
        client,
        anna,
        op("gear_items", item["id"], {"name": "Offline"}, base_updated_at=item["updated_at"]),
    )
    [resolved] = push(
        client,
        anna,
        op("gear_items", item["id"], {"name": "Offline"}, base_updated_at=newer["updated_at"]),
    )

    assert conflict["status"] == "conflict"
    assert conflict["current"]["name"] == "Am Server geändert"
    assert resolved["status"] == "ok" and resolved["record"]["name"] == "Offline"


def test_one_failing_operation_does_not_stop_the_others(client, anna, bea):
    foreign = gear_item(client, bea)
    good_id = str(uuid.uuid4())

    results = push(
        client,
        anna,
        op("gear_items", str(uuid.uuid4()), {"name": " "}),
        op("gear_items", foreign["id"], {"name": "Gekapert"}),
        op("unknown_things", str(uuid.uuid4()), {"name": "X"}),
        op("gear_types", str(uuid.uuid4()), {"name": "Nur lesbar"}),
        op("gear_items", good_id, {"name": "Gut"}),
    )

    assert [(r["status"], r["code"]) for r in results] == [
        ("error", "validation"),
        ("error", "not_found"),
        ("error", "unknown_collection"),
        ("error", "unknown_collection"),
        ("ok", None),
    ]
    assert (
        client.get(f"{GEAR_ITEMS}/{foreign['id']}", headers=bea.headers).json()["name"]
        != "Gekapert"
    )
    assert client.get(f"{GEAR_ITEMS}/{good_id}", headers=anna.headers).status_code == 200


def test_push_foods(client, anna):
    food_id = str(uuid.uuid4())

    [created] = push(client, anna, op("foods", food_id, {"name": "Riegel", "kcal_per_100g": 480}))
    [invalid] = push(client, anna, op("foods", food_id, {"name": "Riegel", "kcal_per_100g": 5000}))
    [deleted] = push(client, anna, op("foods", food_id))

    assert created["status"] == "ok" and created["record"]["visibility"] == "private"
    assert (invalid["status"], invalid["code"]) == ("error", "validation")
    assert deleted["status"] == "ok"
    assert client.get(f"{FOODS}/{food_id}", headers=anna.headers).status_code == 404


def test_push_creates_and_updates_tours_with_history(client, anna):
    tour_id = str(uuid.uuid4())

    [created] = push(client, anna, op("tours", tour_id, {"title": "Offline geplant"}))
    tour = created["record"]
    [updated] = push(
        client,
        anna,
        op(
            "tours",
            tour_id,
            document(tour, title="Offline umbenannt"),
            base_version=tour["version"],
        ),
    )

    assert created["status"] == "ok" and tour["version"] == 1 and tour["permission"] == "owner"
    assert updated["record"]["title"] == "Offline umbenannt"
    assert updated["record"]["version"] == 2
    assert [r["kind"] for r in revisions(client, anna, tour)["items"]] == ["updated", "created"]


def test_outdated_tour_change_is_a_conflict_with_the_current_tour(client, anna):
    tour = create_tour(client, anna)
    put(client, anna, tour, title="Am Server geändert")

    [result] = push(
        client,
        anna,
        op("tours", tour["id"], document(tour, summary="Offline"), base_version=tour["version"]),
    )

    assert result["status"] == "conflict"
    assert result["current"]["title"] == "Am Server geändert"
    assert result["current"]["version"] == 2
    assert revisions(client, anna, tour)["total"] == 2


def test_push_respects_the_tour_permissions(client, db, people):
    anna_, bea_, cleo_, dora_ = (people[n] for n in ("anna", "bea", "cleo", "dora"))
    tour = create_tour(client, anna_, duration_minutes=480)
    share(db, tour, bea_, "edit")
    share(db, tour, cleo_, "read")

    def update(person, **changes):
        operation = op("tours", tour["id"], document(tour, **changes), base_version=tour["version"])
        return push(client, person, operation)[0]

    by_reader = update(cleo_, title="Von Cleo")
    by_stranger = update(dora_, title="Von Dora")
    owner_field = update(bea_, duration_minutes=100)
    delete_by_editor = push(client, bea_, op("tours", tour["id"]))[0]
    by_editor = update(bea_, title="Von Bea")

    assert (by_reader["status"], by_reader["code"]) == ("error", "insufficient_permission")
    assert (by_stranger["status"], by_stranger["code"]) == ("error", "not_found")
    assert (owner_field["status"], owner_field["code"]) == ("error", "owner_only_field")
    assert (delete_by_editor["status"], delete_by_editor["code"]) == (
        "error",
        "insufficient_permission",
    )
    assert by_editor["status"] == "ok" and by_editor["record"]["title"] == "Von Bea"
    assert by_editor["record"]["permission"] == "edit"


def test_owner_deletes_a_tour_by_push(client, anna):
    tour = create_tour(client, anna)

    results = push(client, anna, op("tours", tour["id"]), op("tours", str(uuid.uuid4())))

    assert [r["status"] for r in results] == ["ok", "ok"]
    assert client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).status_code == 404


def test_push_limits_the_number_of_operations(client, anna):
    operations = [op("gear_items", str(uuid.uuid4()), {"name": "X"}) for _ in range(501)]

    response = client.post(PUSH, json={"operations": operations}, headers=anna.headers)

    assert response.status_code == 422


@pytest.mark.parametrize("since", ["yesterday", "2026-08-01T06:00:00"])
def test_since_must_be_a_time_with_zone(client, anna, since):
    assert client.get(CHANGES, params={"since": since}, headers=anna.headers).status_code == 422
