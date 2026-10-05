import uuid
from datetime import timedelta

import httpx2
import pytest
from sqlalchemy import select, update

from app.core.db import utcnow
from app.modules.nutrition.models import FoodItem
from app.modules.nutrition.sources import (
    FoodData,
    FoodSourceError,
    OpenFoodFactsSource,
    parse_openfoodfacts_product,
)
from app.tests.conftest import auth_header, register

FOODS = "/api/v1/nutrition/foods"
SEARCH = "/api/v1/nutrition/search"
BARCODE = "/api/v1/nutrition/barcode"
CATALOG = "/api/v1/nutrition/catalog"

EAN = "7610000000017"
BAR = {
    "name": "Nussriegel",
    "brand": "Bergkraft",
    "barcode": EAN,
    "kcal_per_100g": 480,
    "protein_g": 12.5,
    "carbs_g": 45,
    "fat_g": 27,
    "sugar_g": 30,
    "salt_g": 0.3,
    "serving_size_g": 40,
}
HIDDEN_FIELDS = {"owner_id", "proposed_by", "deleted_at"}


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


def create_food(client, headers, **fields):
    response = client.post(
        FOODS, json={"name": "Brot", "kcal_per_100g": 250, **fields}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def propose(client, headers, food_id):
    return client.post(f"{FOODS}/{food_id}/propose-to-catalog", headers=headers)


def moderate(client, admin, catalog_id, **changes):
    return client.patch(f"{CATALOG}/{catalog_id}", json=changes, headers=admin)


def approved(client, admin, headers, **fields):
    """A catalog entry proposed by `headers` and approved by the admin."""
    entry = propose(client, headers, create_food(client, headers, **fields)["id"]).json()
    response = moderate(client, admin, entry["id"], visibility="catalog")
    assert response.status_code == 200, response.text
    return response.json()


# --- Access ---


@pytest.mark.parametrize(
    "path", [FOODS, SEARCH, f"{BARCODE}/{EAN}", f"{CATALOG}/mine", f"{CATALOG}/pending"]
)
def test_nutrition_requires_login(client, path, food_source):
    assert client.get(path).status_code == 401
    assert food_source.calls == []


# --- Own foods ---


def test_create_and_read_food(client, anna):
    created = create_food(client, anna, **BAR)

    response = client.get(f"{FOODS}/{created['id']}", headers=anna)

    assert response.json() == created
    assert {key: created[key] for key in BAR} == BAR
    assert (created["source"], created["visibility"]) == ("custom", "private")
    assert created["catalog_id"] is None and created["source_synced_at"] is None
    assert not HIDDEN_FIELDS & set(created)


def test_create_food_with_client_generated_id(client, anna):
    food_id = str(uuid.uuid4())

    assert create_food(client, anna, id=food_id)["id"] == food_id
    again = client.post(FOODS, json={"name": "X", "kcal_per_100g": 1, "id": food_id}, headers=anna)
    assert again.json()["error"]["code"] == "id_taken"


@pytest.mark.parametrize(
    "fields",
    [
        {"name": " "},
        {"kcal_per_100g": None},
        {"kcal_per_100g": -1},
        {"kcal_per_100g": 901},
        {"kcal_per_100g": "NaN"},
        {"fat_g": 101},
        {"protein_g": -0.1},
        {"carbs_g": 10, "sugar_g": 11},
        {"protein_g": 40, "carbs_g": 40, "fat_g": 30},
        {"serving_size_g": 0},
        {"barcode": "12345"},
        {"barcode": "76100000000ab"},
    ],
)
def test_food_validates_input(client, anna, fields):
    response = client.post(
        FOODS, json={"name": "Brot", "kcal_per_100g": 250, **fields}, headers=anna
    )

    assert response.status_code == 422


def test_update_and_soft_delete_food(client, db, anna):
    created = create_food(client, anna, **BAR)
    url = f"{FOODS}/{created['id']}"

    updated = client.put(url, json={"name": "Riegel neu", "kcal_per_100g": 455}, headers=anna)

    assert updated.status_code == 200
    assert updated.json()["name"] == "Riegel neu"
    assert updated.json()["brand"] is None and updated.json()["barcode"] is None
    assert client.delete(url, headers=anna).status_code == 204
    assert client.get(url, headers=anna).status_code == 404
    assert client.get(FOODS, headers=anna).json()["total"] == 0
    row = db.scalar(select(FoodItem).where(FoodItem.id == uuid.UUID(created["id"])))
    assert row.deleted_at is not None


def test_private_foods_are_invisible_to_others(client, admin, anna, bea):
    food = create_food(client, anna, **BAR)
    url = f"{FOODS}/{food['id']}"

    for other in (bea, admin):
        assert client.get(url, headers=other).status_code == 404
        assert (
            client.put(url, json={"name": "X", "kcal_per_100g": 1}, headers=other).status_code
            == 404
        )
        assert client.delete(url, headers=other).status_code == 404
        assert client.get(FOODS, headers=other).json()["total"] == 0
        assert client.get(SEARCH, params={"q": "nuss"}, headers=other).json()["total"] == 0
        assert propose(client, other, food["id"]).status_code == 404


def test_list_foods_searches_name_brand_and_barcode(client, anna):
    create_food(client, anna, **BAR)
    create_food(client, anna, name="Brot")

    def names(**params):
        return [f["name"] for f in client.get(FOODS, params=params, headers=anna).json()["items"]]

    assert names() == ["Brot", "Nussriegel"]
    assert names(q="bergkraft") == ["Nussriegel"]
    assert names(q=EAN) == ["Nussriegel"]
    assert names(limit=1, offset=1) == ["Nussriegel"]


# --- Barcode ---

OFF_BAR = FoodData(
    barcode=EAN,
    name="Nussriegel OFF",
    brand="Bergkraft",
    kcal_per_100g=470.0,
    protein_g=12.0,
    image_url="https://images.openfoodfacts.org/x.jpg",
)


def test_barcode_lookup_fetches_from_source_and_caches_in_catalog(client, anna, bea, food_source):
    food_source.products[EAN] = OFF_BAR

    first = client.get(f"{BARCODE}/{EAN}", headers=anna)
    second = client.get(f"{BARCODE}/{EAN}", headers=bea)

    assert first.status_code == 200
    food = first.json()
    assert (food["name"], food["kcal_per_100g"], food["barcode"]) == ("Nussriegel OFF", 470.0, EAN)
    assert (food["source"], food["visibility"]) == ("openfoodfacts", "catalog")
    assert food["source_synced_at"] is not None
    assert food["image_url"] == "https://images.openfoodfacts.org/x.jpg"
    assert second.json()["id"] == food["id"]
    assert food_source.calls == [EAN]
    assert client.get(SEARCH, params={"q": "off"}, headers=bea).json()["total"] == 1


def test_barcode_lookup_prefers_own_food(client, anna, bea, food_source):
    food_source.products[EAN] = OFF_BAR
    client.get(f"{BARCODE}/{EAN}", headers=bea)
    own = create_food(client, anna, **BAR)

    assert client.get(f"{BARCODE}/{EAN}", headers=anna).json()["id"] == own["id"]
    assert client.get(f"{BARCODE}/{EAN}", headers=bea).json()["source"] == "openfoodfacts"
    assert food_source.calls == [EAN]


def test_unknown_barcode_returns_404(client, anna, food_source):
    response = client.get(f"{BARCODE}/{EAN}", headers=anna)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "product_not_found"


def test_unreachable_source_returns_502(client, anna, food_source):
    food_source.fail = True

    response = client.get(f"{BARCODE}/{EAN}", headers=anna)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "source_unavailable"


@pytest.mark.parametrize("ean", ["123", "abcdefgh", "761000000001x", "123456789012345"])
def test_invalid_barcode_is_rejected_without_asking_the_source(client, anna, food_source, ean):
    assert client.get(f"{BARCODE}/{ean}", headers=anna).status_code == 422
    assert food_source.calls == []


def test_stale_cache_is_refreshed_and_survives_source_failure(client, db, anna, food_source):
    food_source.products[EAN] = OFF_BAR
    cached = client.get(f"{BARCODE}/{EAN}", headers=anna).json()
    db.execute(update(FoodItem).values(source_synced_at=utcnow() - timedelta(days=31)))
    db.commit()

    food_source.fail = True
    during_outage = client.get(f"{BARCODE}/{EAN}", headers=anna)
    food_source.fail = False
    food_source.products[EAN] = FoodData(barcode=EAN, name="Neue Rezeptur", kcal_per_100g=455.0)
    refreshed = client.get(f"{BARCODE}/{EAN}", headers=anna).json()

    assert during_outage.status_code == 200
    assert during_outage.json()["name"] == "Nussriegel OFF"
    assert refreshed["id"] == cached["id"]
    assert (refreshed["name"], refreshed["kcal_per_100g"]) == ("Neue Rezeptur", 455.0)
    assert len(food_source.calls) == 3
    assert client.get(f"{BARCODE}/{EAN}", headers=anna).json()["name"] == "Neue Rezeptur"
    assert len(food_source.calls) == 3


# --- Catalog ---


def test_proposal_is_a_separate_copy_hidden_until_approved(client, admin, anna, bea):
    own = create_food(client, anna, **BAR)

    response = propose(client, anna, own["id"])

    assert response.status_code == 201
    proposal = response.json()
    assert proposal["id"] != own["id"]
    assert proposal["visibility"] == "catalog_pending"
    assert {key: proposal[key] for key in BAR} == BAR
    assert not HIDDEN_FIELDS & set(proposal)
    assert client.get(f"{FOODS}/{own['id']}", headers=anna).json()["catalog_id"] == proposal["id"]
    assert client.get(FOODS, headers=anna).json()["total"] == 1
    assert client.get(SEARCH, headers=bea).json()["total"] == 0
    assert client.get(f"{FOODS}/{proposal['id']}", headers=bea).status_code == 404
    assert client.get(f"{BARCODE}/{EAN}", headers=bea).status_code == 404
    pending = client.get(f"{CATALOG}/pending", headers=admin).json()
    assert [row["id"] for row in pending["items"]] == [proposal["id"]]

    assert moderate(client, admin, proposal["id"], visibility="catalog").status_code == 200

    assert client.get(SEARCH, params={"q": "nuss"}, headers=bea).json()["total"] == 1
    assert client.get(f"{FOODS}/{proposal['id']}", headers=bea).json()["visibility"] == "catalog"
    assert client.get(f"{BARCODE}/{EAN}", headers=bea).json()["id"] == proposal["id"]
    assert client.get(f"{CATALOG}/pending", headers=admin).json()["total"] == 0


def test_only_admins_moderate(client, admin, anna):
    proposal = propose(client, anna, create_food(client, anna)["id"]).json()

    assert client.get(f"{CATALOG}/pending", headers=anna).status_code == 403
    assert moderate(client, anna, proposal["id"], visibility="catalog").status_code == 403
    assert moderate(client, admin, str(uuid.uuid4()), visibility="catalog").status_code == 404
    private = create_food(client, anna, name="Privat")
    assert moderate(client, admin, private["id"], visibility="catalog").status_code == 404


def test_admin_can_correct_data_while_moderating(client, admin, anna):
    own = create_food(client, anna, name="nussriegl", kcal_per_100g=48)
    proposal = propose(client, anna, own["id"]).json()

    response = moderate(
        client, admin, proposal["id"], visibility="catalog", name="Nussriegel", kcal_per_100g=480
    )
    invalid = moderate(client, admin, proposal["id"], kcal_per_100g=5000)
    implausible = moderate(client, admin, proposal["id"], carbs_g=5, sugar_g=20)

    assert (response.json()["name"], response.json()["kcal_per_100g"]) == ("Nussriegel", 480)
    assert invalid.status_code == 422 and implausible.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_food"
    # The proposer's own food is a separate record and keeps its data.
    assert client.get(f"{FOODS}/{own['id']}", headers=anna).json()["name"] == "nussriegl"


def test_users_see_the_status_of_their_own_proposals(client, admin, anna, bea):
    open_entry = propose(client, anna, create_food(client, anna, name="Offen")["id"]).json()
    accepted = approved(client, admin, anna, name="Frei")
    rejected = propose(client, anna, create_food(client, anna, name="Abgelehnt")["id"]).json()
    moderate(client, admin, rejected["id"], visibility="catalog_rejected")
    propose(client, bea, create_food(client, bea, name="Von Bea")["id"])

    page = client.get(f"{CATALOG}/mine", headers=anna).json()

    assert {row["id"]: row["visibility"] for row in page["items"]} == {
        open_entry["id"]: "catalog_pending",
        accepted["id"]: "catalog",
        rejected["id"]: "catalog_rejected",
    }
    assert client.get(f"{CATALOG}/mine", headers=bea).json()["total"] == 1
    assert client.get(SEARCH, params={"q": "abgelehnt"}, headers=bea).json()["total"] == 0


def test_food_cannot_be_proposed_twice_unless_rejected(client, admin, anna):
    own = create_food(client, anna)
    proposal = propose(client, anna, own["id"]).json()

    again = propose(client, anna, own["id"])
    moderate(client, admin, proposal["id"], visibility="catalog_rejected")
    after_rejection = propose(client, anna, own["id"])

    assert again.json()["error"]["code"] == "already_in_catalog"
    assert after_rejection.status_code == 201


def test_catalog_keeps_one_product_per_barcode(client, admin, anna, bea):
    approved(client, admin, anna, **BAR)
    duplicate = propose(client, bea, create_food(client, bea, **BAR)["id"]).json()

    response = moderate(client, admin, duplicate["id"], visibility="catalog")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "barcode_in_catalog"


def test_own_correction_of_a_catalog_product_is_a_private_copy(client, admin, anna, bea):
    entry = approved(client, admin, anna, **BAR)

    copy = create_food(client, bea, **{**BAR, "kcal_per_100g": 495}, catalog_id=entry["id"])

    assert copy["catalog_id"] == entry["id"]
    assert (copy["visibility"], copy["kcal_per_100g"]) == ("private", 495)
    assert client.get(f"{FOODS}/{entry['id']}", headers=bea).json()["kcal_per_100g"] == 480
    # Bea now finds her copy instead of the catalog entry, others still the catalog entry.
    found = client.get(SEARCH, params={"q": "nuss"}, headers=bea).json()["items"]
    assert [food["id"] for food in found] == [copy["id"]]
    assert client.get(f"{BARCODE}/{EAN}", headers=bea).json()["id"] == copy["id"]
    assert propose(client, bea, copy["id"]).json()["error"]["code"] == "already_in_catalog"
    # Catalog entries themselves cannot be changed by users.
    put = client.put(f"{FOODS}/{entry['id']}", json={"name": "X", "kcal_per_100g": 1}, headers=bea)
    assert put.status_code == 404
    assert client.delete(f"{FOODS}/{entry['id']}", headers=anna).status_code == 404


def test_copy_needs_an_existing_catalog_entry(client, anna, bea):
    pending = propose(client, anna, create_food(client, anna)["id"]).json()

    for catalog_id in (pending["id"], str(uuid.uuid4())):
        response = client.post(
            FOODS, json={"name": "Kopie", "kcal_per_100g": 1, "catalog_id": catalog_id}, headers=bea
        )
        assert response.json()["error"]["code"] == "unknown_catalog_item"


def test_search_lists_own_foods_before_the_catalog(client, admin, anna, bea):
    approved(client, admin, anna, name="Apfel Katalog")
    create_food(client, bea, name="Zwieback eigen")

    found = client.get(SEARCH, headers=bea).json()["items"]

    assert [food["name"] for food in found] == ["Zwieback eigen", "Apfel Katalog"]


# --- Open Food Facts adapter ---

OFF_PRODUCT = {
    "product_name": "Nut bar",
    "product_name_de": "Nussriegel",
    "brands": "Bergkraft, Other",
    "serving_quantity": "40",
    "image_front_small_url": "https://images.openfoodfacts.org/front.200.jpg",
    "nutriments": {
        "energy-kcal_100g": 480,
        "proteins_100g": 12.5,
        "carbohydrates_100g": "45",
        "fat_100g": 27,
        "sugars_100g": 30,
        "salt_100g": 0.3,
    },
}


def test_parse_openfoodfacts_product():
    assert parse_openfoodfacts_product(EAN, OFF_PRODUCT) == FoodData(
        barcode=EAN,
        name="Nussriegel",
        brand="Bergkraft",
        kcal_per_100g=480.0,
        protein_g=12.5,
        carbs_g=45.0,
        fat_g=27.0,
        sugar_g=30.0,
        salt_g=0.3,
        serving_size_g=40.0,
        image_url="https://images.openfoodfacts.org/front.200.jpg",
    )


def test_parser_tolerates_missing_and_broken_values():
    product = {
        "product_name": "  Mystery  ",
        "brands": None,
        "serving_quantity": "about 2",
        "image_front_small_url": "http://insecure.example/x.jpg",
        "nutriments": {"energy-kj_100g": 2008.32, "fat_100g": -3, "proteins_100g": "n/a"},
    }

    data = parse_openfoodfacts_product(EAN, product)

    assert data == FoodData(barcode=EAN, name="Mystery", kcal_per_100g=480.0)
    assert parse_openfoodfacts_product(EAN, {"product_name": "", "nutriments": "broken"}) is None
    assert parse_openfoodfacts_product(EAN, {"product_name": "X", "nutriments": []}).name == "X"


def _source(handler) -> OpenFoodFactsSource:
    return OpenFoodFactsSource(
        "https://off.test",
        "hiker/test (https://hiker.test)",
        transport=httpx2.MockTransport(handler),
    )


def test_adapter_requests_the_product_and_identifies_itself():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx2.Response(200, json={"status": 1, "product": OFF_PRODUCT})

    data = _source(handler).fetch_by_barcode(EAN)

    assert data.name == "Nussriegel"
    assert seen[0].url.path == f"/api/v2/product/{EAN}.json"
    assert seen[0].headers["user-agent"] == "hiker/test (https://hiker.test)"


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(404, json={"status": 0}),
        httpx2.Response(200, json={"status": 0, "status_verbose": "product not found"}),
        httpx2.Response(200, json=["unexpected"]),
    ],
)
def test_adapter_returns_none_for_unknown_products(response):
    assert _source(lambda request: response).fetch_by_barcode(EAN) is None


def test_adapter_raises_on_server_errors_timeouts_and_garbage():
    def timeout(request):
        raise httpx2.ConnectTimeout("too slow")

    for handler in (
        lambda request: httpx2.Response(503),
        lambda request: httpx2.Response(200, text="<html>maintenance</html>"),
        timeout,
    ):
        with pytest.raises(FoodSourceError):
            _source(handler).fetch_by_barcode(EAN)
