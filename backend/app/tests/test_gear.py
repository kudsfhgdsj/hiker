import uuid
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.files import FileObject
from app.modules.gear.models import GearItem
from app.tests.conftest import auth_header, make_image, register

ITEMS = "/api/v1/gear/items"
TYPES = "/api/v1/gear/types"
LISTS = "/api/v1/gear/lists"

FULL_ITEM = {
    "name": "Aeon 35",
    "brand": "Rab",
    "weight_g": 890,
    "purchase_date": "2025-05-17",
    "purchase_price": 149.9,
    "description": "Tagesrucksack",
    "notes": "Hüftgurt links repariert",
    "website_url": "https://example.org/aeon-35",
    "status": "active",
    "serial_number": "SN-123",
    "size": "M",
    "color": "blau",
}


@pytest.fixture
def admin(client):
    """The first registered user is the admin."""
    return auth_header(register(client, email="admin@example.org", display_name="Admin"))


@pytest.fixture
def anna(client, admin):
    return auth_header(register(client, email="anna@example.org", display_name="Anna"))


@pytest.fixture
def bea(client, admin):
    return auth_header(register(client, email="bea@example.org", display_name="Bea"))


def create_item(client, headers, **fields):
    response = client.post(ITEMS, json={"name": "Stirnlampe", **fields}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def create_type(client, headers, name="Fotoausrüstung", **fields):
    response = client.post(TYPES, json={"name": name, **fields}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Access ---


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", ITEMS),
        ("post", ITEMS),
        ("get", f"{ITEMS}/{uuid.uuid4()}"),
        ("get", TYPES),
        ("get", LISTS),
        ("get", "/api/v1/gear/catalog"),
        ("get", "/api/v1/gear/catalog/pending"),
    ],
)
def test_gear_requires_login(client, method, path):
    assert client.request(method, path).status_code == 401


def test_gear_routes_are_absent_when_the_module_is_disabled(monkeypatch):
    from app.core.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("ENABLED_MODULES", "auth")
    get_settings.cache_clear()

    paths = create_app().openapi()["paths"]

    assert "/api/v1/auth/login" in paths
    assert not any(path.startswith("/api/v1/gear") for path in paths)


# --- Items ---


def test_create_and_read_item_with_all_fields(client, anna):
    created = create_item(client, anna, **FULL_ITEM)

    response = client.get(f"{ITEMS}/{created['id']}", headers=anna)

    assert response.status_code == 200
    assert response.json() == created
    assert {key: created[key] for key in FULL_ITEM} == FULL_ITEM
    assert created["currency"] == "EUR" and created["favorite"] is False
    assert created["attributes"] == {}
    assert created["catalog_id"] is None and created["image_file_id"] is None


def test_create_item_with_client_generated_id(client, anna):
    item_id = str(uuid.uuid4())

    created = create_item(client, anna, id=item_id)
    again = client.post(ITEMS, json={"name": "Other", "id": item_id}, headers=anna)

    assert created["id"] == item_id
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "id_taken"


def test_blank_optional_fields_become_null(client, anna):
    created = create_item(client, anna, brand="   ", notes="", website_url="")

    assert created["brand"] is None
    assert created["notes"] is None
    assert created["website_url"] is None


@pytest.mark.parametrize(
    "fields",
    [
        {"name": "  "},
        {"weight_g": -1},
        {"purchase_price": -5},
        {"purchase_price": 1.999},
        {"purchase_price": 1_000_000.01},
        {"purchase_price": "abc"},
        {"purchase_price": "NaN"},
        {"status": "lost"},
        {"website_url": "javascript:alert(1)"},
        {"purchase_date": "17.05.2025"},
    ],
)
def test_item_validates_input(client, anna, fields):
    response = client.post(ITEMS, json={"name": "Stirnlampe", **fields}, headers=anna)

    assert response.status_code == 422


@pytest.mark.parametrize(("price", "stored"), [(0, 0.0), (19.99, 19.99), ("249.5", 249.5)])
def test_price_is_stored_as_number(client, anna, price, stored):
    created = create_item(client, anna, purchase_price=price)

    assert created["purchase_price"] == stored
    assert isinstance(created["purchase_price"], float)


def test_update_replaces_all_fields(client, anna):
    created = create_item(client, anna, **FULL_ITEM)

    response = client.put(
        f"{ITEMS}/{created['id']}",
        json={"name": "Aeon 35 (alt)", "status": "retired"},
        headers=anna,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Aeon 35 (alt)"
    assert updated["status"] == "retired"
    assert updated["brand"] is None and updated["purchase_price"] is None
    assert updated["updated_at"] >= created["updated_at"]


def test_items_of_other_users_are_invisible(client, anna, bea):
    item = create_item(client, anna)
    url = f"{ITEMS}/{item['id']}"

    assert client.get(url, headers=bea).status_code == 404
    assert client.put(url, json={"name": "Stolen"}, headers=bea).status_code == 404
    assert client.delete(url, headers=bea).status_code == 404
    assert client.get(ITEMS, headers=bea).json()["total"] == 0
    assert client.get(url, headers=anna).json()["name"] == "Stirnlampe"


def test_admin_cannot_read_items_of_other_users(client, admin, anna):
    item = create_item(client, anna)

    assert client.get(f"{ITEMS}/{item['id']}", headers=admin).status_code == 404


def test_delete_is_a_soft_delete(client, db, anna):
    item = create_item(client, anna)

    response = client.delete(f"{ITEMS}/{item['id']}", headers=anna)

    assert response.status_code == 204
    assert client.get(f"{ITEMS}/{item['id']}", headers=anna).status_code == 404
    assert client.get(ITEMS, headers=anna).json()["items"] == []
    row = db.scalar(select(GearItem).where(GearItem.id == uuid.UUID(item["id"])))
    assert row is not None and row.deleted_at is not None


def test_list_items_filters_searches_and_pages(client, anna):
    tent_type = create_type(client, anna, "Zelte")
    create_item(client, anna, name="Zelt Hubba", brand="MSR", type_id=tent_type["id"])
    create_item(client, anna, name="Kocher", brand="msr", status="retired")
    create_item(client, anna, name="Isomatte 100%", brand="Exped")

    def names(**params):
        response = client.get(ITEMS, params=params, headers=anna)
        assert response.status_code == 200
        return [item["name"] for item in response.json()["items"]]

    assert names() == ["Isomatte 100%", "Kocher", "Zelt Hubba"]
    assert names(q="MSR") == ["Kocher", "Zelt Hubba"]
    assert names(q="hubba") == ["Zelt Hubba"]
    assert names(q="100%") == ["Isomatte 100%"]
    assert names(q="%") == ["Isomatte 100%"]
    assert names(status="retired") == ["Kocher"]
    assert names(type_id=tent_type["id"]) == ["Zelt Hubba"]
    assert names(limit=1, offset=1) == ["Kocher"]
    page = client.get(ITEMS, params={"limit": 2}, headers=anna).json()
    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 0)
    assert client.get(ITEMS, params={"limit": 0}, headers=anna).status_code == 422


# --- Types ---


def test_users_see_standard_types_and_their_own(client, admin, anna, bea):
    standard = create_type(client, admin, "Rucksack", standard=True, sort_order=10)
    own = create_type(client, anna, "Fotoausrüstung", sort_order=20)

    annas = client.get(TYPES, headers=anna).json()
    beas = client.get(TYPES, headers=bea).json()

    assert annas == [standard, own]
    assert standard["standard"] is True and own["standard"] is False
    assert beas == [standard]


def test_only_admin_can_change_the_standard_list(client, admin, anna):
    standard = create_type(client, admin, "Rucksack", standard=True)
    url = f"{TYPES}/{standard['id']}"

    created = client.post(TYPES, json={"name": "Zelt", "standard": True}, headers=anna)
    updated = client.put(url, json={"name": "Tasche"}, headers=anna)
    deleted = client.delete(url, headers=anna)

    assert (created.status_code, updated.status_code, deleted.status_code) == (403, 403, 403)
    assert client.put(url, json={"name": "Rucksäcke"}, headers=admin).json()["name"] == "Rucksäcke"
    assert client.delete(url, headers=admin).status_code == 204


def test_own_types_are_private(client, admin, anna, bea):
    own = create_type(client, anna)
    url = f"{TYPES}/{own['id']}"

    assert client.put(url, json={"name": "Meins"}, headers=bea).status_code == 404
    assert client.delete(url, headers=bea).status_code == 404
    assert client.delete(url, headers=admin).status_code == 404
    response = client.post(ITEMS, json={"name": "Kamera", "type_id": own["id"]}, headers=bea)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_type"


def test_type_names_are_unique_per_user_view(client, admin, anna, bea):
    create_type(client, admin, "Rucksack", standard=True)
    create_type(client, anna, "Fotoausrüstung")

    standard_clash = client.post(TYPES, json={"name": "rucksack"}, headers=anna)
    own_clash = client.post(TYPES, json={"name": "Fotoausrüstung"}, headers=anna)
    other_user = client.post(TYPES, json={"name": "Fotoausrüstung"}, headers=bea)

    assert standard_clash.status_code == 409
    assert own_clash.json()["error"]["code"] == "type_name_taken"
    assert other_user.status_code == 201


def test_deleting_a_type_keeps_its_items_without_type(client, anna):
    own = create_type(client, anna)
    item = create_item(client, anna, type_id=own["id"])

    assert client.delete(f"{TYPES}/{own['id']}", headers=anna).status_code == 204

    assert client.get(f"{ITEMS}/{item['id']}", headers=anna).json()["type_id"] is None


# --- Packing lists ---


def test_packing_list_round_trip_with_total_weight(client, anna):
    tent = create_item(client, anna, name="Zelt", weight_g=1500)
    pegs = create_item(client, anna, name="Hering", weight_g=12)
    unknown_weight = create_item(client, anna, name="Karte")
    entries = [
        {"gear_item_id": tent["id"], "quantity": 1},
        {"gear_item_id": pegs["id"], "quantity": 8},
        {"gear_item_id": unknown_weight["id"], "quantity": 1},
    ]

    response = client.post(LISTS, json={"name": "Sommer 2 Tage", "entries": entries}, headers=anna)

    assert response.status_code == 201
    created = response.json()
    assert created["total_weight_g"] == 1500 + 8 * 12
    assert sorted(created["entries"], key=lambda e: e["gear_item_id"]) == sorted(
        entries, key=lambda e: e["gear_item_id"]
    )
    assert client.get(f"{LISTS}/{created['id']}", headers=anna).json() == created
    assert client.get(LISTS, headers=anna).json() == [created]


def test_update_replaces_the_entries_of_a_list(client, anna):
    tent = create_item(client, anna, name="Zelt", weight_g=1500)
    stove = create_item(client, anna, name="Kocher", weight_g=300)
    created = client.post(
        LISTS, json={"name": "Sommer", "entries": [{"gear_item_id": tent["id"]}]}, headers=anna
    ).json()

    response = client.put(
        f"{LISTS}/{created['id']}",
        json={"name": "Winter", "entries": [{"gear_item_id": stove["id"], "quantity": 2}]},
        headers=anna,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Winter"
    assert updated["entries"] == [{"gear_item_id": stove["id"], "quantity": 2}]
    assert updated["total_weight_g"] == 600


def test_list_rejects_foreign_unknown_and_duplicate_items(client, anna, bea):
    mine = create_item(client, anna)
    foreign = create_item(client, bea)

    def post(*ids):
        entries = [{"gear_item_id": item_id} for item_id in ids]
        return client.post(LISTS, json={"name": "Liste", "entries": entries}, headers=anna)

    assert post(foreign["id"]).json()["error"]["code"] == "unknown_gear_item"
    assert post(str(uuid.uuid4())).status_code == 422
    assert post(mine["id"], mine["id"]).json()["error"]["code"] == "duplicate_gear_item"
    assert (
        client.post(
            LISTS,
            json={"name": "Liste", "entries": [{"gear_item_id": mine["id"], "quantity": 0}]},
            headers=anna,
        ).status_code
        == 422
    )


def test_deleted_items_disappear_from_lists(client, anna):
    tent = create_item(client, anna, name="Zelt", weight_g=1500)
    stove = create_item(client, anna, name="Kocher", weight_g=300)
    entries = [{"gear_item_id": tent["id"]}, {"gear_item_id": stove["id"]}]
    created = client.post(LISTS, json={"name": "Sommer", "entries": entries}, headers=anna).json()

    client.delete(f"{ITEMS}/{tent['id']}", headers=anna)

    current = client.get(f"{LISTS}/{created['id']}", headers=anna).json()
    assert current["entries"] == [{"gear_item_id": stove["id"], "quantity": 1}]
    assert current["total_weight_g"] == 300


def test_lists_are_private_and_soft_deleted(client, anna, bea):
    created = client.post(LISTS, json={"name": "Sommer"}, headers=anna).json()
    url = f"{LISTS}/{created['id']}"

    assert client.get(url, headers=bea).status_code == 404
    assert client.put(url, json={"name": "Meins"}, headers=bea).status_code == 404
    assert client.delete(url, headers=bea).status_code == 404
    assert client.get(LISTS, headers=bea).json() == []
    assert client.delete(url, headers=anna).status_code == 204
    assert client.get(url, headers=anna).status_code == 404
    assert client.get(LISTS, headers=anna).json() == []


# --- Images ---


def upload_image(client, headers, item_id, data=None, filename="foto.jpg"):
    files = {"file": (filename, data if data is not None else make_image(), "image/jpeg")}
    return client.post(f"{ITEMS}/{item_id}/image", files=files, headers=headers)


def test_upload_reencodes_the_image_and_strips_gps(client, anna):
    item = create_item(client, anna)

    response = upload_image(
        client, anna, item["id"], make_image(size=(3000, 1500), image_format="PNG", exif_gps=True)
    )

    assert response.status_code == 200
    assert response.json()["image_file_id"] is not None
    served = client.get(f"{ITEMS}/{item['id']}/image", headers=anna)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    image = Image.open(BytesIO(served.content))
    assert image.format == "JPEG"
    assert image.size == (2000, 1000)
    assert len(image.getexif()) == 0


@pytest.mark.parametrize("data", [b"not an image", b"<svg xmlns='http://www.w3.org/2000/svg'/>"])
def test_upload_rejects_files_that_are_not_images(client, anna, data):
    item = create_item(client, anna)

    response = upload_image(client, anna, item["id"], data)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_image"
    assert client.get(f"{ITEMS}/{item['id']}", headers=anna).json()["image_file_id"] is None


def test_upload_rejects_files_above_the_size_limit(client, anna, monkeypatch):
    from app.core.config import get_settings

    item = create_item(client, anna)
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()

    response = upload_image(client, anna, item["id"], b"x" * (1024 * 1024 + 1))

    assert response.status_code == 413


def test_images_are_only_served_to_the_owner(client, anna, bea):
    item = create_item(client, anna)
    upload_image(client, anna, item["id"])
    url = f"{ITEMS}/{item['id']}/image"

    assert client.get(url).status_code == 401
    assert client.get(url, headers=bea).status_code == 404
    assert upload_image(client, bea, item["id"]).status_code == 404
    assert client.delete(url, headers=bea).status_code == 404


def test_replacing_and_removing_an_image_deletes_the_old_file(client, db, storage, anna):
    item = create_item(client, anna)
    first = upload_image(client, anna, item["id"]).json()["image_file_id"]
    first_key = db.get(FileObject, uuid.UUID(first)).storage_key

    second = upload_image(client, anna, item["id"]).json()["image_file_id"]
    db.expire_all()

    assert second != first
    assert db.get(FileObject, uuid.UUID(first)) is None
    assert not storage.exists(first_key)

    second_key = db.get(FileObject, uuid.UUID(second)).storage_key
    assert client.delete(f"{ITEMS}/{item['id']}/image", headers=anna).status_code == 204
    assert not storage.exists(second_key)
    assert client.get(f"{ITEMS}/{item['id']}/image", headers=anna).status_code == 404


def test_deleting_an_item_deletes_its_image(client, db, storage, anna):
    item = create_item(client, anna)
    file_id = upload_image(client, anna, item["id"]).json()["image_file_id"]
    key = db.get(FileObject, uuid.UUID(file_id)).storage_key

    client.delete(f"{ITEMS}/{item['id']}", headers=anna)
    db.expire_all()

    assert not storage.exists(key)
    assert db.get(FileObject, uuid.UUID(file_id)) is None


# --- Catalog ---

CATALOG = "/api/v1/gear/catalog"
PERSONAL_FIELDS = {
    "purchase_date",
    "purchase_price",
    "currency",
    "notes",
    "description",
    "serial_number",
    "size",
    "color",
    "owner_id",
    "created_by",
}


def propose(client, headers, item_id):
    return client.post(f"{ITEMS}/{item_id}/propose-to-catalog", headers=headers)


def approve(client, admin, catalog_id, **changes):
    response = client.patch(
        f"{CATALOG}/{catalog_id}", json={"status": "approved", **changes}, headers=admin
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_proposal_shares_product_data_only(client, admin, anna):
    standard = create_type(client, admin, "Rucksack", standard=True)
    item = create_item(client, anna, **FULL_ITEM, type_id=standard["id"])

    response = propose(client, anna, item["id"])

    assert response.status_code == 201
    entry = response.json()
    assert entry == {
        "id": entry["id"],
        "name": "Aeon 35",
        "brand": "Rab",
        "type_id": standard["id"],
        "nominal_weight_g": 890,
        "website_url": "https://example.org/aeon-35",
        "image_file_id": None,
        "status": "pending",
    }
    assert not PERSONAL_FIELDS & set(entry)
    for secret in ("149.9", "SN-123", "Hüftgurt", "Tagesrucksack"):
        assert secret not in response.text
    assert client.get(f"{ITEMS}/{item['id']}", headers=anna).json()["catalog_id"] == entry["id"]


def test_proposal_drops_personal_types(client, anna):
    own = create_type(client, anna)
    item = create_item(client, anna, type_id=own["id"])

    assert propose(client, anna, item["id"]).json()["type_id"] is None


def test_pending_entries_are_hidden_until_an_admin_approves(client, admin, anna, bea):
    item = create_item(client, anna, name="Aeon 35", brand="Rab")
    entry = propose(client, anna, item["id"]).json()

    assert client.get(CATALOG, headers=bea).json()["total"] == 0
    pending = client.get(f"{CATALOG}/pending", headers=admin).json()
    assert [row["id"] for row in pending["items"]] == [entry["id"]]

    approve(client, admin, entry["id"])

    found = client.get(CATALOG, params={"q": "rab"}, headers=bea).json()
    assert [row["name"] for row in found["items"]] == ["Aeon 35"]
    assert found["items"][0]["status"] == "approved"
    assert client.get(CATALOG, params={"q": "zelt"}, headers=bea).json()["total"] == 0
    assert client.get(f"{CATALOG}/pending", headers=admin).json()["total"] == 0


def test_only_admins_moderate(client, admin, anna):
    item = create_item(client, anna)
    entry = propose(client, anna, item["id"]).json()

    assert client.get(f"{CATALOG}/pending", headers=anna).status_code == 403
    patch = client.patch(f"{CATALOG}/{entry['id']}", json={"status": "approved"}, headers=anna)
    assert patch.status_code == 403
    assert client.get(CATALOG, headers=anna).json()["total"] == 0
    missing = client.patch(f"{CATALOG}/{uuid.uuid4()}", json={"status": "approved"}, headers=admin)
    assert missing.status_code == 404


def test_admin_can_correct_product_data_while_moderating(client, admin, anna):
    standard = create_type(client, admin, "Rucksack", standard=True)
    own = create_type(client, anna)
    item = create_item(client, anna, name="aeon", weight_g=900)
    entry = propose(client, anna, item["id"]).json()

    approved = approve(
        client, admin, entry["id"], name="Aeon 35", nominal_weight_g=890, type_id=standard["id"]
    )
    personal_type = client.patch(
        f"{CATALOG}/{entry['id']}", json={"type_id": own["id"]}, headers=admin
    )

    assert (approved["name"], approved["nominal_weight_g"]) == ("Aeon 35", 890)
    assert approved["type_id"] == standard["id"]
    assert personal_type.status_code == 422
    # The proposer's own item is a separate record and keeps its data.
    assert client.get(f"{ITEMS}/{item['id']}", headers=anna).json()["name"] == "aeon"


def test_item_cannot_be_proposed_twice_unless_rejected(client, admin, anna):
    item = create_item(client, anna)
    entry = propose(client, anna, item["id"]).json()

    again = propose(client, anna, item["id"])
    client.patch(f"{CATALOG}/{entry['id']}", json={"status": "rejected"}, headers=admin)
    after_rejection = propose(client, anna, item["id"])

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "already_in_catalog"
    assert after_rejection.status_code == 201
    assert after_rejection.json()["id"] != entry["id"]


def test_foreign_items_cannot_be_proposed(client, anna, bea):
    item = create_item(client, anna)

    assert propose(client, bea, item["id"]).status_code == 404


def test_catalog_entry_as_template_creates_an_independent_copy(client, db, admin, anna, bea):
    source = create_item(client, anna, name="Aeon 35", brand="Rab", weight_g=890)
    upload_image(client, anna, source["id"])
    entry = approve(client, admin, propose(client, anna, source["id"]).json()["id"])

    copy = create_item(
        client, bea, name=entry["name"], brand=entry["brand"], catalog_id=entry["id"]
    )

    assert copy["catalog_id"] == entry["id"]
    source_image = client.get(f"{ITEMS}/{source['id']}", headers=anna).json()["image_file_id"]
    image_ids = {source_image, entry["image_file_id"], copy["image_file_id"]}
    assert None not in image_ids and len(image_ids) == 3
    assert client.get(f"{ITEMS}/{copy['id']}/image", headers=bea).status_code == 200

    # Later changes to the catalog entry or the source do not touch the copy.
    approve(client, admin, entry["id"], name="Renamed")
    client.delete(f"{ITEMS}/{source['id']}", headers=anna)
    assert client.get(f"{ITEMS}/{copy['id']}", headers=bea).json()["name"] == "Aeon 35"
    assert client.get(f"{ITEMS}/{copy['id']}/image", headers=bea).status_code == 200
    assert client.get(f"{CATALOG}/{entry['id']}/image", headers=bea).status_code == 200


def test_template_must_be_an_approved_entry(client, admin, anna, bea):
    item = create_item(client, anna)
    pending = propose(client, anna, item["id"]).json()

    for catalog_id in (pending["id"], str(uuid.uuid4())):
        response = client.post(ITEMS, json={"name": "Kopie", "catalog_id": catalog_id}, headers=bea)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "unknown_catalog_item"


def test_catalog_image_visibility(client, admin, anna, bea):
    item = create_item(client, anna)
    upload_image(client, anna, item["id"])
    entry = propose(client, anna, item["id"]).json()
    url = f"{CATALOG}/{entry['id']}/image"

    assert client.get(url).status_code == 401
    assert client.get(url, headers=bea).status_code == 404
    assert client.get(url, headers=anna).status_code == 200
    assert client.get(url, headers=admin).status_code == 200

    approve(client, admin, entry["id"])

    assert client.get(url, headers=bea).status_code == 200


# --- Tags ---

TAGS = "/api/v1/gear/tags"
SUMMARY = "/api/v1/gear/summary"


def create_tag(client, headers, name, **fields):
    response = client.post(TAGS, json={"name": name, **fields}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_tags_are_defined_freely_per_user(client, anna, bea):
    winter = create_tag(client, anna, "Winter", color="#3366cc")
    ultralight = create_tag(client, anna, "Ultraleicht")

    favorite, *own = client.get(TAGS, headers=anna).json()
    assert own == [ultralight, winter]
    assert (favorite["name"], favorite["system"]) == ("Favorit", "favorite")
    assert winter["color"] == "#3366cc" and ultralight["color"] is None
    assert [tag["system"] for tag in client.get(TAGS, headers=bea).json()] == ["favorite"]
    assert client.post(TAGS, json={"name": "winter"}, headers=anna).status_code == 409
    assert client.post(TAGS, json={"name": "Winter"}, headers=bea).status_code == 201
    assert client.post(TAGS, json={"name": " "}, headers=anna).status_code == 422
    assert client.post(TAGS, json={"name": "Rot", "color": "red"}, headers=anna).status_code == 422


def test_tags_can_be_renamed_and_are_private(client, anna, bea):
    tag = create_tag(client, anna, "Winter")
    create_tag(client, anna, "Sommer")
    url = f"{TAGS}/{tag['id']}"

    renamed = client.put(url, json={"name": "Hochtour", "color": "#ff8800"}, headers=anna)

    assert renamed.json() == {
        "id": tag["id"],
        "name": "Hochtour",
        "color": "#ff8800",
        "system": None,
    }
    assert client.put(url, json={"name": "sommer"}, headers=anna).status_code == 409
    assert client.put(url, json={"name": "Meins"}, headers=bea).status_code == 404
    assert client.delete(url, headers=bea).status_code == 404


def test_items_carry_tags_and_can_be_filtered_by_them(client, anna):
    winter = create_tag(client, anna, "Winter")
    loan = create_tag(client, anna, "Verleihbar")
    axe = create_item(client, anna, name="Pickel", tag_ids=[winter["id"], loan["id"]])
    create_item(client, anna, name="Steigeisen", tag_ids=[winter["id"]])
    create_item(client, anna, name="Sonnenhut")

    def names(*tag_ids):
        response = client.get(ITEMS, params={"tag_id": list(tag_ids)}, headers=anna)
        assert response.status_code == 200
        return [item["name"] for item in response.json()["items"]]

    assert set(axe["tag_ids"]) == {winter["id"], loan["id"]}
    assert names(winter["id"]) == ["Pickel", "Steigeisen"]
    assert names(winter["id"], loan["id"]) == ["Pickel"]
    assert names(str(uuid.uuid4())) == []

    updated = client.put(
        f"{ITEMS}/{axe['id']}", json={"name": "Pickel", "tag_ids": [loan["id"]]}, headers=anna
    ).json()
    assert updated["tag_ids"] == [loan["id"]]
    assert names(winter["id"]) == ["Steigeisen"]


def test_items_reject_unknown_and_foreign_tags(client, anna, bea):
    foreign = create_tag(client, bea, "Winter")

    for tag_id in (foreign["id"], str(uuid.uuid4())):
        response = client.post(ITEMS, json={"name": "Pickel", "tag_ids": [tag_id]}, headers=anna)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "unknown_tag"


def test_deleting_a_tag_keeps_the_items(client, anna):
    winter = create_tag(client, anna, "Winter")
    item = create_item(client, anna, name="Pickel", tag_ids=[winter["id"]])

    assert client.delete(f"{TAGS}/{winter['id']}", headers=anna).status_code == 204

    assert client.get(f"{ITEMS}/{item['id']}", headers=anna).json()["tag_ids"] == []


# --- Summary ---


@pytest.fixture
def gear_set(client, admin, anna):
    """Four items of anna with types, tags, weights and prices in two currencies."""
    tents = create_type(client, admin, "Zelt", standard=True)
    winter = create_tag(client, anna, "Winter")
    loan = create_tag(client, anna, "Verleihbar")
    create_item(
        client,
        anna,
        name="Zelt",
        brand="MSR",
        weight_g=1500,
        purchase_price=399.9,
        type_id=tents["id"],
        tag_ids=[loan["id"]],
    )
    create_item(
        client,
        anna,
        name="Pickel",
        brand="Petzl",
        weight_g=450,
        purchase_price=120.1,
        tag_ids=[winter["id"], loan["id"]],
    )
    create_item(
        client,
        anna,
        name="Steigeisen",
        brand="Petzl",
        weight_g=800,
        purchase_price=95.5,
        status="retired",
        tag_ids=[winter["id"]],
    )
    create_item(client, anna, name="Karte")
    return {"tents": tents, "winter": winter, "loan": loan}


def summary(client, headers, **params):
    response = client.get(SUMMARY, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_summary_totals_weight_and_value(client, anna, gear_set):
    result = summary(client, anna)

    assert result == {
        "group_by": None,
        "total": {
            "item_count": 4,
            "weight_g": 2750,
            "items_without_weight": 1,
            "value": [{"currency": "EUR", "amount": 615.5}],
            "items_without_price": 1,
        },
        "groups": [],
    }


def test_summary_respects_filters(client, anna, gear_set):
    active = summary(client, anna, status="active")["total"]
    winter = summary(client, anna, tag_id=gear_set["winter"]["id"])["total"]
    petzl = summary(client, anna, q="petzl")["total"]

    assert (active["item_count"], active["weight_g"]) == (3, 1950)
    assert active["value"] == [{"currency": "EUR", "amount": 520.0}]
    assert (winter["item_count"], winter["weight_g"]) == (2, 1250)
    assert petzl["item_count"] == 2


def test_summary_groups_by_tag(client, anna, gear_set):
    groups = summary(client, anna, group_by="tag")["groups"]

    assert [(g["label"], g["item_count"], g["weight_g"]) for g in groups] == [
        ("Verleihbar", 2, 1950),
        ("Winter", 2, 1250),
        (None, 1, 0),
    ]
    assert groups[0]["key"] == gear_set["loan"]["id"]
    assert groups[0]["value"] == [{"currency": "EUR", "amount": 520.0}]
    assert groups[1]["value"] == [{"currency": "EUR", "amount": 215.6}]
    assert groups[2]["key"] is None


@pytest.mark.parametrize(
    ("group_by", "expected"),
    [
        ("type", [("Zelt", 1, 1500), (None, 3, 1250)]),
        ("status", [("active", 3, 1950), ("retired", 1, 800)]),
        ("brand", [("MSR", 1, 1500), ("Petzl", 2, 1250), (None, 1, 0)]),
    ],
)
def test_summary_groups_by_type_status_and_brand(client, anna, gear_set, group_by, expected):
    groups = summary(client, anna, group_by=group_by)["groups"]

    assert [(g["label"], g["item_count"], g["weight_g"]) for g in groups] == expected


def test_summary_is_private_and_ignores_deleted_items(client, anna, bea, gear_set):
    items = client.get(ITEMS, params={"q": "zelt"}, headers=anna).json()["items"]
    client.delete(f"{ITEMS}/{items[0]['id']}", headers=anna)

    assert summary(client, bea)["total"]["item_count"] == 0
    assert summary(client, anna)["total"]["item_count"] == 3
    assert client.get(SUMMARY).status_code == 401
    assert client.get(SUMMARY, params={"group_by": "color"}, headers=anna).status_code == 422


def test_users_see_the_status_of_their_own_proposals(client, admin, anna, bea):
    open_entry = propose(client, anna, create_item(client, anna, name="Offen")["id"]).json()
    approved = propose(client, anna, create_item(client, anna, name="Frei")["id"]).json()
    rejected = propose(client, anna, create_item(client, anna, name="Abgelehnt")["id"]).json()
    propose(client, bea, create_item(client, bea, name="Von Bea")["id"])
    approve(client, admin, approved["id"])
    client.patch(f"{CATALOG}/{rejected['id']}", json={"status": "rejected"}, headers=admin)

    response = client.get(f"{CATALOG}/mine", headers=anna)

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 3
    assert {row["id"]: row["status"] for row in page["items"]} == {
        open_entry["id"]: "pending",
        approved["id"]: "approved",
        rejected["id"]: "rejected",
    }
    assert client.get(f"{CATALOG}/mine", headers=bea).json()["total"] == 1
    assert client.get(f"{CATALOG}/mine", headers=admin).json()["total"] == 0
    assert client.get(f"{CATALOG}/mine").status_code == 401


# --- Favourites, currency and attributes by kind ---


def test_every_price_is_in_eur_whatever_the_client_sends(client, anna):
    priced = create_item(client, anna, purchase_price=20, currency="CHF")
    free = create_item(client, anna, name="Karte", currency="CHF")

    assert priced["currency"] == "EUR" and free["currency"] is None
    changed = client.put(
        f"{ITEMS}/{free['id']}", json={"name": "Karte", "purchase_price": 9.5}, headers=anna
    ).json()
    assert changed["currency"] == "EUR"


def test_favorite_is_the_tag_every_user_has(client, anna, bea):
    item = create_item(client, anna)
    other = create_item(client, anna, name="Kocher")
    url = f"{ITEMS}/{item['id']}/favorite"

    marked = client.put(url, headers=anna).json()
    favorite = next(t for t in client.get(TAGS, headers=anna).json() if t["system"])

    assert marked["favorite"] is True and marked["tag_ids"] == [favorite["id"]]
    assert client.put(url, headers=anna).json()["tag_ids"] == [favorite["id"]]

    def names(**params):
        listed = client.get(ITEMS, params=params, headers=anna).json()["items"]
        return [entry["name"] for entry in listed]

    assert names(favorite="true") == ["Stirnlampe"]
    assert names(favorite="false") == ["Kocher"]
    assert names(tag_id=favorite["id"]) == ["Stirnlampe"]
    # Setting the tag through the normal item form marks the favourite too.
    body = {"name": "Kocher", "tag_ids": [favorite["id"]]}
    assert client.put(f"{ITEMS}/{other['id']}", json=body, headers=anna).json()["favorite"] is True
    assert client.delete(url, headers=anna).json()["favorite"] is False
    assert client.put(url, headers=bea).status_code == 404


def test_favorite_tag_cannot_be_deleted_or_renamed(client, anna):
    favorite = client.get(TAGS, headers=anna).json()[0]
    url = f"{TAGS}/{favorite['id']}"

    assert client.delete(url, headers=anna).status_code == 409
    renamed = client.put(url, json={"name": "Lieblinge"}, headers=anna)
    assert renamed.status_code == 409 and renamed.json()["error"]["code"] == "system_tag"
    recolored = client.put(url, json={"name": "Favorit", "color": "#00aa00"}, headers=anna)
    assert recolored.status_code == 200 and recolored.json()["color"] == "#00aa00"
    assert len(client.get(TAGS, headers=anna).json()) == 1


def test_own_tag_named_like_the_favorite_becomes_it(client, anna):
    # Created before the favourite tag was needed for the first time.
    own = client.post(TAGS, json={"name": "favorit"}, headers=anna).json()

    tags = client.get(TAGS, headers=anna).json()

    assert [(tag["id"], tag["system"]) for tag in tags] == [(own["id"], "favorite")]


def test_meta_describes_the_extra_fields_per_kind(client, anna):
    meta = client.get("/api/v1/gear/meta", headers=anna).json()

    assert meta["currency"] == "EUR" and meta["image_formats"] == ["JPEG", "PNG", "WebP"]
    assert meta["max_upload_mb"] > 0
    kinds = {kind["kind"]: kind["attributes"] for kind in meta["kinds"]}
    assert kinds["backpack"][0] == {
        "key": "volume_l",
        "type": "number",
        "unit": "l",
        "minimum": 1,
        "maximum": 200,
        "options": [],
    }
    assert kinds["shoes"][0]["options"] == ["A", "B", "B/C", "C", "D"]


def test_attributes_follow_the_kind_of_the_type(client, anna, admin):
    packs = create_type(client, admin, "Rucksack", standard=True, kind="backpack")
    shoes = create_type(client, anna, "Bergschuhe", kind="shoes")
    plain = create_type(client, anna, "Sonstiges")
    assert packs["kind"] == "backpack" and plain["kind"] is None

    pack = create_item(client, anna, name="Aeon", type_id=packs["id"], attributes={"volume_l": 35})
    boot = create_item(
        client,
        anna,
        name="Nepal",
        type_id=shoes["id"],
        # A value that belongs to another kind is dropped.
        attributes={"shoe_category": "B/C", "volume_l": 35},
    )

    assert pack["attributes"] == {"volume_l": 35}
    assert boot["attributes"] == {"shoe_category": "B/C"}
    # Changing the type removes what no longer applies.
    moved = client.put(
        f"{ITEMS}/{pack['id']}",
        json={"name": "Aeon", "type_id": plain["id"], "attributes": {"volume_l": 35}},
        headers=anna,
    ).json()
    assert moved["attributes"] == {}


@pytest.mark.parametrize(
    ("kind", "attributes"),
    [
        ("backpack", {"volume_l": 0}),
        ("backpack", {"volume_l": 500}),
        ("backpack", {"volume_l": "viel"}),
        ("shoes", {"shoe_category": "E"}),
    ],
)
def test_invalid_attribute_values_are_rejected(client, anna, kind, attributes):
    gear_type = create_type(client, anna, "Typ", kind=kind)

    response = client.post(
        ITEMS,
        json={"name": "X", "type_id": gear_type["id"], "attributes": attributes},
        headers=anna,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_attribute"


def test_unknown_kind_is_rejected(client, anna):
    response = client.post(TYPES, json={"name": "Typ", "kind": "boat"}, headers=anna)

    assert response.status_code == 422
