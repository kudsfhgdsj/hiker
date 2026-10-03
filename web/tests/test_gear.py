import io
import json

import httpx2

from tests.conftest import USER, error

TENT = {
    "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "name": "Zelt Hubba",
    "brand": "MSR",
    "type_id": "type-tent",
    "weight_g": 1500,
    "purchase_price": 399.9,
    "currency": "CHF",
    "status": "active",
    "tag_ids": ["tag-winter"],
    "image_file_id": None,
    "catalog_id": None,
}
STOVE = {
    "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "name": "Kocher",
    "brand": None,
    "type_id": None,
    "weight_g": 300,
    "status": "retired",
    "tag_ids": [],
    "image_file_id": "file-1",
    "catalog_id": None,
}
TYPES = [
    {"id": "type-tent", "name": "Zelt & Biwak", "standard": True},
    {"id": "type-photo", "name": "Fotoausrüstung", "standard": False},
]
TAGS = [{"id": "tag-winter", "name": "Winter", "color": "#3366cc"}]


def page(items):
    return {"items": items, "total": len(items), "limit": 200, "offset": 0}


def text(response) -> str:
    return response.get_data(as_text=True)


def gear_api(fake_api):
    fake_api.route("GET", "/gear/items", page([TENT, STOVE]))
    fake_api.route("GET", "/gear/types", TYPES)
    fake_api.route("GET", "/gear/tags", TAGS)
    return fake_api


def test_gear_needs_login_and_an_enabled_module(browser, fake_api):
    assert browser.get("/gear/").status_code == 302
    fake_api.modules = ["auth"]
    browser.login()

    assert browser.get("/gear/").status_code == 404


def test_list_shows_items_with_brand_type_and_weight(user, fake_api):
    gear_api(fake_api)

    page_text = text(user.get("/gear/"))

    assert "Zelt Hubba" in page_text and "MSR · Zelt &amp; Biwak" in page_text
    assert "1,5 kg" in page_text and "300 g" in page_text
    assert f"/gear/{STOVE['id']}/image" in page_text
    assert "Neuer Gegenstand" in page_text


def test_filters_are_passed_to_the_api(user, fake_api):
    gear_api(fake_api)

    user.get("/gear/?q=zelt&status=active&type_id=type-tent&tag_id=tag-winter")

    params = fake_api.last("GET", "/gear/items").url.params
    assert (params["q"], params["status"], params["type_id"]) == ("zelt", "active", "type-tent")
    assert params.get_list("tag_id") == ["tag-winter"]


def test_create_item_sends_typed_values(user, fake_api):
    gear_api(fake_api)
    fake_api.route(
        "POST", "/gear/items", lambda r: httpx2.Response(201, json=json.loads(r.content))
    )

    response = user.post(
        "/gear/new",
        {
            "name": " Pickel ",
            "brand": "",
            "weight_g": "450",
            "purchase_price": "120,50",
            "currency": "chf",
            "status": "active",
            "tag_ids": "tag-winter",
            "website_url": "",
        },
    )

    assert response.status_code == 302 and response.headers["location"] == "/gear/"
    body = json.loads(fake_api.last("POST", "/gear/items").content)
    assert body["name"] == "Pickel" and body["brand"] is None
    assert (body["weight_g"], body["purchase_price"], body["currency"]) == (450, 120.5, "CHF")
    assert body["tag_ids"] == ["tag-winter"]


def test_rejected_item_shows_the_form_again_with_the_input(user, fake_api):
    gear_api(fake_api)
    fake_api.route("POST", "/gear/items", lambda r: httpx2.Response(422, json={"detail": []}))

    rejected = user.post(
        "/gear/new", {"name": "Pickel", "purchase_price": "20", "status": "active"}
    )
    unreadable = user.post(
        "/gear/new", {"name": "Pickel", "weight_g": "schwer", "status": "active"}
    )

    assert rejected.status_code == 422
    assert "Die Eingaben wurden nicht angenommen" in text(rejected)
    assert 'value="Pickel"' in text(rejected)
    assert unreadable.status_code == 422
    assert fake_api.requested().count("POST /gear/items") == 1


def test_edit_shows_the_item_and_saves_with_put(user, fake_api):
    gear_api(fake_api)
    fake_api.route("GET", "/gear/items/*", TENT)
    fake_api.route(
        "PUT", "/gear/items/*", lambda r: httpx2.Response(200, json=json.loads(r.content))
    )

    form = text(user.get(f"/gear/{TENT['id']}"))
    response = user.post(f"/gear/{TENT['id']}", {"name": "Zelt neu", "status": "retired"})

    assert 'value="Zelt Hubba"' in form and 'value="399.9"' in form
    assert '<option value="type-tent" selected>' in form
    assert 'value="tag-winter" checked' in form
    assert response.status_code == 302
    body = json.loads(fake_api.last("PUT", f"/gear/items/{TENT['id']}").content)
    assert (body["name"], body["status"], body["tag_ids"]) == ("Zelt neu", "retired", [])


def test_delete_propose_and_image(user, fake_api):
    gear_api(fake_api)
    fake_api.route("DELETE", "/gear/items/*", lambda r: httpx2.Response(204))
    fake_api.route(
        "POST", "/gear/items/*/propose-to-catalog", lambda r: httpx2.Response(201, json={})
    )
    fake_api.route("POST", "/gear/items/*/image", lambda r: httpx2.Response(200, json=TENT))
    fake_api.route(
        "GET",
        "/gear/items/*/image",
        lambda r: httpx2.Response(200, content=b"JPEG", headers={"content-type": "image/jpeg"}),
    )

    image = user.get(f"/gear/{STOVE['id']}/image")
    upload = user.post(
        f"/gear/{TENT['id']}/image",
        {"file": (io.BytesIO(b"picture"), "zelt.jpg")},
        content_type="multipart/form-data",
    )
    user.post(f"/gear/{TENT['id']}/propose")
    deleted = user.post(f"/gear/{TENT['id']}/delete")

    assert image.data == b"JPEG" and image.mimetype == "image/jpeg"
    assert "private" in image.headers["Cache-Control"]
    assert upload.status_code == 302
    sent = fake_api.last("POST", f"/gear/items/{TENT['id']}/image")
    assert b"picture" in sent.content and b'filename="zelt.jpg"' in sent.content
    assert f"POST /gear/items/{TENT['id']}/propose-to-catalog" in fake_api.requested()
    assert deleted.headers["location"] == "/gear/"


def test_images_are_not_served_without_login(browser, fake_api):
    assert browser.get(f"/gear/{STOVE['id']}/image").status_code == 302
    assert fake_api.calls == []


def test_summary_with_grouping(user, fake_api):
    totals = {
        "item_count": 4,
        "weight_g": 2750,
        "items_without_weight": 1,
        "items_without_price": 0,
        "value": [{"currency": "CHF", "amount": 520.0}, {"currency": "EUR", "amount": 95.5}],
    }
    fake_api.route(
        "GET",
        "/gear/summary",
        lambda r: httpx2.Response(
            200,
            json={
                "group_by": r.url.params.get("group_by"),
                "total": totals,
                "groups": [
                    {
                        **totals,
                        "item_count": 2,
                        "weight_g": 1950,
                        "key": "t",
                        "label": "Verleihbar",
                    },
                    {**totals, "item_count": 1, "weight_g": 0, "key": None, "label": None},
                ]
                if r.url.params.get("group_by")
                else [],
            },
        ),
    )

    plain = text(user.get("/gear/summary"))
    grouped = text(user.get("/gear/summary?group_by=tag&status=active"))

    assert "2,75 kg" in plain and "520,00 CHF + 95,50 EUR" in plain and "1 ohne Gewicht." in plain
    assert "Verleihbar" in grouped and "Nicht zugeordnet" in grouped
    assert "zählt in jedem seiner Tags" in grouped
    params = fake_api.last("GET", "/gear/summary").url.params
    assert (params["group_by"], params["status"]) == ("tag", "active")


def test_manage_tags_and_types(user, fake_api):
    gear_api(fake_api)
    fake_api.route("POST", "/gear/tags", lambda r: httpx2.Response(201, json={}))
    fake_api.route("POST", "/gear/types", lambda r: error(409, "type_name_taken"))
    fake_api.route("DELETE", "/gear/tags/*", lambda r: httpx2.Response(204))

    page_text = text(user.get("/gear/manage"))
    user.post("/gear/manage", {"kind": "tag", "name": "Hochtour", "color": "#FF8800"})
    clash = user.post(
        "/gear/manage",
        {"kind": "type", "name": "Zelt & Biwak"},
        headers={"Referer": "http://localhost/gear/manage"},
    )
    after_clash = text(user.get("/gear/manage"))
    user.post("/gear/manage/tag/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/delete")

    assert "Winter" in page_text and "Standard" in page_text
    # A normal user gets no delete button for the standard type.
    assert "/gear/manage/type/type-tent/delete" not in page_text
    assert "/gear/manage/type/type-photo/delete" in page_text
    assert json.loads(fake_api.last("POST", "/gear/tags").content) == {
        "name": "Hochtour",
        "color": "#FF8800",
    }
    assert clash.status_code == 302
    assert "Das gibt es schon." in after_clash
    assert "DELETE /gear/tags/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" in fake_api.requested()


def test_catalog_proposals_and_moderation(browser, fake_api):
    proposal = {
        "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "name": "Aeon 35",
        "brand": "Rab",
        "nominal_weight_g": 890,
        "status": "rejected",
    }
    fake_api.route("GET", "/gear/catalog/mine", page([proposal]))
    fake_api.route("GET", "/gear/catalog/pending", page([{**proposal, "status": "pending"}]))
    fake_api.route("PATCH", "/gear/catalog/*", lambda r: httpx2.Response(200, json=proposal))
    browser.login()

    as_user = text(browser.get("/gear/catalog"))

    assert "Aeon 35" in as_user and "Abgelehnt" in as_user and "Rab · 890 g" in as_user
    assert "Offene Vorschläge" not in as_user
    assert "GET /gear/catalog/pending" not in fake_api.requested()

    fake_api.route(
        "POST",
        "/auth/login",
        lambda r: httpx2.Response(200, json={**fake_api.auth(), "user": {**USER, "role": "admin"}}),
    )
    browser.login()
    as_admin = text(browser.get("/gear/catalog"))
    browser.post(f"/gear/catalog/{proposal['id']}/approved")

    assert "Offene Vorschläge" in as_admin and "Freigeben" in as_admin
    assert json.loads(fake_api.last("PATCH", f"/gear/catalog/{proposal['id']}").content) == {
        "status": "approved"
    }
    assert browser.post(f"/gear/catalog/{proposal['id']}/deleted").status_code == 404
