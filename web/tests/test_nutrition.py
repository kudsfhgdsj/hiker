import json

import httpx2

from tests.conftest import USER, error

OATS = {
    "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "catalog_id": None,
    "name": "Haferflocken",
    "brand": "Bio",
    "barcode": None,
    "kcal_per_100g": 372.0,
    "protein_g": 13.5,
    "carbs_g": 58.7,
    "fat_g": 7.0,
    "sugar_g": 0.7,
    "salt_g": None,
    "serving_size_g": 50.0,
    "image_url": None,
    "source": "custom",
    "visibility": "private",
}
BAR = {
    **OATS,
    "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "name": "Riegel",
    "brand": "Farmer",
    "barcode": "7613035974685",
    "kcal_per_100g": 410.0,
    "source": "openfoodfacts",
    "visibility": "catalog",
}


def page(items):
    return {"items": items, "total": len(items), "limit": 200, "offset": 0}


def text(response) -> str:
    return response.get_data(as_text=True)


def created(request):
    return httpx2.Response(201, json={**OATS, **json.loads(request.content)})


def test_food_needs_login_and_an_enabled_module(browser, fake_api):
    assert browser.get("/food/").status_code == 302
    fake_api.modules = ["auth", "gear"]
    browser.login()

    assert browser.get("/food/").status_code == 404
    assert "Essen" not in text(browser.get("/profile"))


def test_list_shows_own_foods_and_searches_the_catalog_on_request(user, fake_api):
    fake_api.route("GET", "/nutrition/foods", page([OATS]))
    fake_api.route("GET", "/nutrition/search", page([OATS, BAR]))

    own = text(user.get("/food/?q=hafer"))
    both = text(user.get("/food/?q=r&catalog=1"))

    assert "Haferflocken" in own and "372 kcal/100 g" in own and "Riegel" not in own
    assert fake_api.last("GET", "/nutrition/foods").url.params["q"] == "hafer"
    assert "Riegel" in both and "Farmer · 7613035974685" in both
    # Open Food Facts data is under the ODbL: the source is named.
    assert "Open Food Facts" in both and "ODbL" in both
    assert "Open Food Facts</a>" not in own


def test_create_food_reads_numbers_with_a_comma(user, fake_api):
    fake_api.route("POST", "/nutrition/foods", created)

    response = user.post(
        "/food/new",
        {"name": "Nüsse", "kcal_per_100g": "612,5", "fat_g": "54", "protein_g": "", "barcode": ""},
    )

    assert response.status_code == 302 and response.headers["location"] == "/food/"
    body = json.loads(fake_api.last("POST", "/nutrition/foods").content)
    assert (body["name"], body["kcal_per_100g"], body["fat_g"]) == ("Nüsse", 612.5, 54.0)
    assert body["protein_g"] is None and body["barcode"] is None


def test_rejected_food_shows_the_form_again(user, fake_api):
    fake_api.route("POST", "/nutrition/foods", lambda r: httpx2.Response(422, json={"detail": []}))

    response = user.post("/food/new", {"name": "Nüsse", "kcal_per_100g": "2000"})
    unreadable = user.post("/food/new", {"name": "Nüsse", "kcal_per_100g": "viel"})

    assert response.status_code == 422 and 'value="Nüsse"' in text(response)
    assert "Die Eingaben wurden nicht angenommen" in text(response)
    assert unreadable.status_code == 422
    assert fake_api.requested().count("POST /nutrition/foods") == 1


def test_own_food_can_be_edited_proposed_and_deleted(user, fake_api):
    fake_api.route("GET", "/nutrition/foods/*", OATS)
    fake_api.route("PUT", "/nutrition/foods/*", created)
    fake_api.route("POST", "/nutrition/foods/*/propose-to-catalog", OATS)
    fake_api.route("DELETE", "/nutrition/foods/*", lambda r: httpx2.Response(204))

    form = text(user.get(f"/food/{OATS['id']}"))
    saved = user.post(f"/food/{OATS['id']}", {"name": "Hafer", "kcal_per_100g": "370"})
    user.post(f"/food/{OATS['id']}/propose")
    deleted = user.post(f"/food/{OATS['id']}/delete")

    assert (
        'value="Haferflocken"' in form and 'value="372.0"' in form and "Im Katalog teilen" in form
    )
    assert saved.status_code == 302
    assert (
        json.loads(fake_api.last("PUT", f"/nutrition/foods/{OATS['id']}").content)["name"]
        == "Hafer"
    )
    assert f"POST /nutrition/foods/{OATS['id']}/propose-to-catalog" in fake_api.requested()
    assert deleted.headers["location"] == "/food/"


def test_catalog_entry_is_read_only_and_can_be_copied(user, fake_api):
    fake_api.route("GET", "/nutrition/foods/*", BAR)
    fake_api.route(
        "POST",
        "/nutrition/foods",
        lambda r: httpx2.Response(201, json={**json.loads(r.content), "id": OATS["id"]}),
    )

    detail = text(user.get(f"/food/{BAR['id']}"))
    copied = user.post(f"/food/{BAR['id']}/copy")

    assert "Riegel" in detail and "Als eigenes Lebensmittel übernehmen" in detail
    assert 'name="name"' not in detail and "Open Food Facts" in detail
    assert "product/7613035974685" in detail
    body = json.loads(fake_api.last("POST", "/nutrition/foods").content)
    assert body["catalog_id"] == BAR["id"] and body["name"] == "Riegel"
    assert "id" not in body and "visibility" not in body
    assert copied.headers["location"] == f"/food/{OATS['id']}"


def test_barcode_lookup(user, fake_api):
    fake_api.route("GET", "/nutrition/barcode/7613035974685", BAR)
    fake_api.route("GET", "/nutrition/barcode/40084107", lambda r: error(404, "product_not_found"))

    found = user.get("/food/barcode?ean=7613 0359-74685")
    unknown = user.get("/food/barcode?ean=40084107")
    invalid = user.get("/food/barcode?ean=12ab")

    assert found.headers["location"] == f"/food/{BAR['id']}"
    assert unknown.headers["location"] == "/food/new?barcode=40084107"
    assert 'value="40084107"' in text(user.get(unknown.headers["location"]))
    assert invalid.headers["location"] == "/food/"
    assert len([c for c in fake_api.requested() if c.startswith("GET /nutrition/barcode")]) == 2


def test_external_source_failure_is_explained(user, fake_api):
    fake_api.route("GET", "/nutrition/barcode/*", lambda r: error(502, "source_unavailable"))

    response = user.get("/food/barcode?ean=40084107")

    assert response.status_code == 502
    assert "Der externe Dienst ist gerade nicht erreichbar." in text(response)


def test_catalog_proposals_and_moderation(browser, fake_api):
    proposal = {
        **OATS,
        "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "visibility": "catalog_rejected",
    }
    fake_api.route("GET", "/nutrition/catalog/mine", page([proposal]))
    fake_api.route(
        "GET", "/nutrition/catalog/pending", page([{**proposal, "visibility": "catalog_pending"}])
    )
    fake_api.route("PATCH", "/nutrition/catalog/*", lambda r: httpx2.Response(200, json=proposal))
    browser.login()

    as_user = text(browser.get("/food/catalog"))

    assert (
        "Haferflocken" in as_user and "Abgelehnt" in as_user and "Offene Vorschläge" not in as_user
    )
    assert "GET /nutrition/catalog/pending" not in fake_api.requested()

    fake_api.route(
        "POST",
        "/auth/login",
        lambda r: httpx2.Response(200, json={**fake_api.auth(), "user": {**USER, "role": "admin"}}),
    )
    browser.login()
    as_admin = text(browser.get("/food/catalog"))
    browser.post(f"/food/catalog/{proposal['id']}/catalog")

    assert "Offene Vorschläge" in as_admin
    sent = json.loads(fake_api.last("PATCH", f"/nutrition/catalog/{proposal['id']}").content)
    assert sent == {"visibility": "catalog"}
    assert browser.post(f"/food/catalog/{proposal['id']}/private").status_code == 404
