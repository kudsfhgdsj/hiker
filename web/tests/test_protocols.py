import html
import io
import json
import re

import httpx2

from tests.conftest import USER, error

TOUR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PHOTO_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
OTHER_ID = "22222222-2222-4222-8222-222222222222"
GEAR_ROW = {
    "id": "g1",
    "gear_item_id": "item-1",
    "name": "Zelt",
    "brand": "MSR",
    "weight_g": 1500,
    "quantity": 1,
    "carried": True,
}
FOOD_ROW = {
    "id": "f1",
    "food_item_id": "food-1",
    "name": "Riegel",
    "kcal_per_100g": 400.0,
    "amount_g": 100.0,
    "kcal": 400.0,
    "carried": True,
    "eaten": True,
    "eaten_at": "2026-07-01T10:00:00Z",
}
PEAK = {
    "id": "p1",
    "name": "Säntis",
    "elevation_m": 2502,
    "lat": 47.249,
    "lon": 9.343,
    "reached_at": "2026-07-01T09:30:00Z",
    "source": "osm",
}
STATS = {
    "distance_m": 12340.0,
    "ascent_m": 1210.0,
    "descent_m": 1180.0,
    "min_elevation_m": 1352.0,
    "max_elevation_m": 2502.0,
    "moving_time_s": 15300,
    "heart_rate": {"avg": 128, "max": 171},
}
TOUR = {
    "id": TOUR_ID,
    "owner": {"id": USER["id"], "display_name": "Anna"},
    "permission": "owner",
    "title": "Säntis über Lisengrat",
    "summary": "Schöner Tag.\nViel Sonne.",
    "start_time": "2026-07-01T06:00:00Z",
    "end_time": "2026-07-01T13:30:00Z",
    "cover_photo_id": PHOTO_ID,
    "version": 4,
    "created_at": "2026-07-01T05:00:00Z",
    "updated_at": "2026-07-02T05:00:00Z",
    "duration_minutes": None,
    "pack_weight_start_g": None,
    "calories_burned": None,
    "calories_burned_source": "estimated",
    "calories_estimate": {"method": "heart_rate", "reason": None, "parameters": {"weight_kg": 70}},
    "computed": {
        "duration_minutes": 450,
        "pack_weight_start_g": 1600,
        "calories_eaten": 400.0,
        "calories_burned": 3210.4,
    },
    "start_point": {"lat": 47.28, "lon": 9.31, "name": "Wasserauen"},
    "end_point": {"lat": 47.25, "lon": 9.34, "name": None},
    "points_source": "gpx",
    "track_source": "device",
    "track_stats": STATS,
    "photo_time_offset_seconds": -7200,
    "photo_count": 1,
    "weather": [
        {
            "sample_point": "summit",
            "lat": 47.249,
            "lon": 9.343,
            "elevation_m": 2502.0,
            "time": "2026-07-01T09:00:00Z",
            "temperature_c": 6.5,
            "apparent_temperature_c": 2.0,
            "wind_speed_kmh": 22.0,
            "wind_gusts_kmh": 41.0,
            "precipitation_mm": 0.0,
            "cloud_cover_pct": 35.0,
            "freezing_level_m": 3400.0,
            "weather_code": 2,
            "source": "open-meteo-archive",
            "fetched_at": "2026-07-02T05:00:00Z",
        }
    ],
    "weather_outdated": False,
    "gear": [GEAR_ROW],
    "food": [FOOD_ROW],
    "peaks": [PEAK],
    "partners": [{"contact_id": "c1", "display_name": "Ben", "linked_user_id": None}],
}
PHOTO = {
    "id": PHOTO_ID,
    "caption": "Am Grat",
    "taken_at": "2026-07-01T08:00:00Z",
    "lat": 47.26,
    "lon": 9.33,
    "position_source": "exif_gps",
    "track_distance_m": 5100.0,
    "elevation_m": 2100.0,
    "waypoint_id": None,
    "is_cover": True,
}
WAYPOINT = {
    "id": "w1",
    "name": "Rotsteinpass",
    "description": None,
    "icon": None,
    "lat": 47.24,
    "lon": 9.36,
    "track_distance_m": 8000.0,
    "elevation_m": 2120.0,
    "kind": "saddle",
    "source": "osm",
    "reached_at": "2026-07-01T10:40:00Z",
}
OVERVIEW = {
    "title": TOUR["title"],
    "facts": {},
    "attribution": "© OpenStreetMap-Mitwirkende (ODbL)",
    "stations": [
        {
            "kind": "start",
            "name": None,
            "lat": 47.28,
            "lon": 9.31,
            "elevation_m": 1352.0,
            "track_distance_m": 0.0,
            "time": "2026-07-01T06:00:00Z",
            "source": None,
        },
        {
            "kind": "peak",
            "name": "Säntis",
            "lat": 47.249,
            "lon": 9.343,
            "elevation_m": 2502.0,
            "track_distance_m": 6100.0,
            "time": "2026-07-01T09:30:00Z",
            "source": "osm",
        },
    ],
}
CONTACTS = [
    {"id": "c1", "display_name": "Ben", "linked_user": None},
    {
        "id": "c2",
        "display_name": "Cleo",
        "linked_user": {"id": OTHER_ID, "display_name": "Cleo K."},
    },
]


def page(items):
    return {"items": items, "total": len(items), "limit": 200, "offset": 0}


def text(response) -> str:
    return response.get_data(as_text=True)


def tour_api(fake_api, **changes):
    tour = {**TOUR, **changes}
    fake_api.route("GET", "/tours/*", tour)
    fake_api.route("GET", "/tours/*/photos", [PHOTO])
    fake_api.route("GET", "/tours/*/waypoints", [WAYPOINT])
    fake_api.route("GET", "/tours/*/overview", OVERVIEW)
    fake_api.route("GET", "/contacts", CONTACTS)
    fake_api.route(
        "GET", "/gear/items", page([{"id": "item-2", "name": "Kocher", "weight_g": 300}])
    )
    fake_api.route(
        "GET", "/nutrition/search", page([{"id": "food-2", "name": "Nüsse", "brand": None}])
    )
    return tour


def edit_form(**changes) -> dict:
    """What the browser sends for the unchanged edit form of TOUR."""
    form = {
        "version": "4",
        "title": TOUR["title"],
        "summary": TOUR["summary"],
        "start_time": TOUR["start_time"],
        "end_time": TOUR["end_time"],
        "duration_minutes": "",
        "pack_weight_start_g": "",
        "calories_burned": "",
        "peak_id": "p1",
        "peak_name": "Säntis",
        "peak_elevation": "2502",
        "peak_lat": "47.249",
        "peak_lon": "9.343",
        "peak_reached_at": PEAK["reached_at"],
        "peak_new_name": "",
        "peak_new_elevation": "",
        "partners": "c1",
        "gear_id": "g1",
        "gear_quantity": "1",
        "gear_carried": "g1",
        "gear_new": "",
        "gear_new_quantity": "1",
        "gear_new_carried": "on",
        "food_id": "f1",
        "food_amount": "100.0",
        "food_eaten_at": FOOD_ROW["eaten_at"],
        "food_carried": "f1",
        "food_eaten": "f1",
        "food_new": "",
        "food_new_amount": "",
    }
    form.update(changes)
    return {key: value for key, value in form.items() if value is not None}


# --- List and creation ---


def test_tours_need_login_and_the_module(browser, fake_api):
    assert browser.get("/tours/").status_code == 302
    fake_api.modules = ["auth", "gear"]
    browser.login()

    assert browser.get("/tours/").status_code == 404
    assert browser.get("/").headers["location"] == "/gear/"


def test_list_shows_tours_and_passes_scope_and_search(user, fake_api):
    shared = {
        **TOUR,
        "id": OTHER_ID,
        "title": "Geteilte Tour",
        "permission": "read",
        "owner": {"id": OTHER_ID, "display_name": "Ben"},
        "cover_photo_id": None,
        "peaks": [],
    }
    fake_api.route("GET", "/tours", page([{**TOUR, "peaks": ["Säntis"]}, shared]))

    listing = text(user.get("/tours/?scope=shared&q=grat"))

    assert "Säntis über Lisengrat" in listing and "01.07.2026 · Säntis" in listing
    assert f"/tours/{TOUR_ID}/photos/{PHOTO_ID}/image?size=thumb" in listing
    assert "von Ben · Nur lesen" in listing
    params = fake_api.last("GET", "/tours").url.params
    assert (params["scope"], params["q"]) == ("shared", "grat")
    user.get("/tours/?scope=nonsense")
    assert fake_api.last("GET", "/tours").url.params["scope"] == "all"


def test_new_tour_is_created_and_opened_for_editing(user, fake_api):
    fake_api.route("POST", "/tours", lambda r: httpx2.Response(201, json={**TOUR, "version": 1}))

    response = user.post("/tours/new", {"title": " Säntis ", "summary": ""})

    assert response.headers["location"] == f"/tours/{TOUR_ID}/edit"
    assert json.loads(fake_api.last("POST", "/tours").content) == {
        "title": "Säntis",
        "summary": None,
    }


# --- Detail ---


def test_detail_shows_facts_course_lists_and_map_data(user, fake_api):
    tour_api(fake_api)

    response = user.get(f"/tours/{TOUR_ID}")
    detail = text(response)

    assert "Säntis über Lisengrat" in detail and "Schöner Tag." in detail
    assert "12,3 km" in detail and "1.210 m" in detail and "7 h 30 min" in detail
    assert "1,6 kg" in detail and "400 kcal" in detail
    # The estimate is marked as such and its method is named.
    assert "3.210 kcal" in detail and "geschätzt" in detail and "Keytel" in detail
    assert "Ø 128, max. 171" in detail and "Nur für dich sichtbar." in detail
    assert (
        "Gipfel" in detail
        and "Rotsteinpass" not in detail.split('id="course"')[1].split("</section>")[0]
    )
    assert "© OpenStreetMap-Mitwirkende (ODbL)" in detail
    assert "6,5 °C" in detail and "22 (41) km/h" in detail and "Wetterdaten: Open-Meteo" in detail
    assert "Zelt" in detail and "Riegel" in detail and "Ben" in detail
    data = json.loads(re.search(r'id="tour-data">(.*?)</script>', detail, re.S).group(1))
    assert data["trackUrl"] == f"/tours/{TOUR_ID}/track.json?v=4"
    assert data["photos"][0]["thumb"] == f"/tours/{TOUR_ID}/photos/{PHOTO_ID}/image?size=thumb"
    assert data["waypoints"][0]["kind"] == "saddle" and data["start"]["name"] == "Wasserauen"
    assert data["workerUrl"].startswith("/static/vendor/maplibre-gl/")
    # No script or style from a foreign server.
    assert re.findall(r'<(?:script|link)[^>]+(?:src|href)="(?:https?:)?//', detail) == []
    assert "/static/vendor/maplibre-gl/maplibre-gl-csp.js" in detail
    policy = response.headers["Content-Security-Policy"]
    # Tiles come from the own server too; no foreign origin is allowed.
    assert "default-src 'self'" in policy and "http" not in policy
    assert data["tileUrl"] == "/tiles/{z}/{x}/{y}.png"


def test_owner_tools_are_hidden_from_other_users(user, fake_api):
    tour_api(fake_api)
    as_owner = text(user.get(f"/tours/{TOUR_ID}"))
    tour_api(
        fake_api,
        permission="edit",
        calories_estimate=None,
        owner={"id": OTHER_ID, "display_name": "Ben"},
    )
    with_edit = text(user.get(f"/tours/{TOUR_ID}"))
    tour_api(fake_api, permission="read", owner={"id": OTHER_ID, "display_name": "Ben"})
    read_only = text(user.get(f"/tours/{TOUR_ID}"))

    for owner_only in (
        "GPX hochladen",
        "Track entfernen",
        f"/tours/{TOUR_ID}/sharing",
        f"/tours/{TOUR_ID}/delete",
        "Wetter neu abrufen",
    ):
        assert owner_only in as_owner
        assert owner_only not in with_edit and owner_only not in read_only
    assert "Fotos hochladen" in with_edit and f"/tours/{TOUR_ID}/edit" in with_edit
    assert "Fotos hochladen" not in read_only and f"/tours/{TOUR_ID}/edit" not in read_only
    assert "Aus meiner Liste entfernen" in read_only and "von Ben" in read_only


def test_track_json_and_photo_are_passed_through(user, fake_api):
    fake_api.route(
        "GET",
        "/tours/*/track",
        {
            "source": "device",
            "stats": STATS,
            "series": {
                "distance_m": [0, 10],
                "lat": [47.0, 47.1],
                "lon": [9.0, 9.1],
                "elevation_m": [1000, 1010],
            },
        },
    )
    fake_api.route(
        "GET",
        "/tours/*/photos/*/image",
        lambda r: httpx2.Response(
            200,
            content=b"JPEG-" + r.url.params["size"].encode(),
            headers={"content-type": "image/jpeg"},
        ),
    )

    track = user.get(f"/tours/{TOUR_ID}/track.json")
    thumb = user.get(f"/tours/{TOUR_ID}/photos/{PHOTO_ID}/image?size=thumb")
    full = user.get(f"/tours/{TOUR_ID}/photos/{PHOTO_ID}/image?size=anything")

    assert track.get_json()["series"]["lat"] == [47.0, 47.1]
    assert thumb.data == b"JPEG-thumb" and full.data == b"JPEG-full"
    assert "private" in thumb.headers["Cache-Control"]


# --- Editing ---


def test_edit_form_shows_the_document(user, fake_api):
    tour_api(fake_api)

    form = text(user.get(f"/tours/{TOUR_ID}/edit"))

    assert 'name="version" value="4"' in form
    assert 'name="start_time" id="start_time" value="2026-07-01T06:00:00Z"' in form
    assert 'name="peak_name" value="Säntis"' in form and 'name="gear_quantity" value="1"' in form
    assert 'name="partners" value="c1" checked' in form and 'name="partners" value="c2">' in form
    assert "Kocher (300 g)" in form and "Nüsse" in form
    assert 'placeholder="450"' in form and 'placeholder="3210"' in form


def test_saving_sends_the_whole_document_with_the_version(user, fake_api):
    tour_api(fake_api)
    fake_api.route("PUT", "/tours/*", lambda r: httpx2.Response(200, json=TOUR))

    response = user.post(
        f"/tours/{TOUR_ID}/edit",
        edit_form(
            title="Säntis",
            duration_minutes="460",
            calories_burned="2900,5",
            gear_new="item-2",
            gear_new_quantity="2",
            food_new="food-2",
            food_new_amount="80",
            food_new_carried=None,
            peak_new_name="Lisengrat",
            peak_new_elevation="2100",
            food_eaten=None,
        ),
    )

    assert response.headers["location"] == f"/tours/{TOUR_ID}"
    body = json.loads(fake_api.last("PUT", f"/tours/{TOUR_ID}").content)
    assert (body["version"], body["title"], body["duration_minutes"]) == (4, "Säntis", 460)
    assert body["calories_burned"] == 2900.5 and body["pack_weight_start_g"] is None
    assert body["start_time"] == TOUR["start_time"]
    assert body["gear"] == [
        {"id": "g1", "quantity": 1, "carried": True},
        {"gear_item_id": "item-2", "quantity": 2, "carried": True},
    ]
    assert body["food"] == [
        {
            "id": "f1",
            "amount_g": 100.0,
            "carried": True,
            "eaten": False,
            "eaten_at": FOOD_ROW["eaten_at"],
        },
        {"food_item_id": "food-2", "amount_g": 80.0, "carried": False, "eaten": False},
    ]
    assert body["peaks"] == [
        {
            "id": "p1",
            "name": "Säntis",
            "elevation_m": 2502,
            "lat": 47.249,
            "lon": 9.343,
            "reached_at": PEAK["reached_at"],
        },
        {"name": "Lisengrat", "elevation_m": 2100},
    ]
    assert body["partners"] == [{"contact_id": "c1"}]


def test_removing_rows_and_staying_on_the_form(user, fake_api):
    tour_api(fake_api)
    fake_api.route("PUT", "/tours/*", lambda r: httpx2.Response(200, json=TOUR))

    response = user.post(
        f"/tours/{TOUR_ID}/edit",
        edit_form(gear_remove="g1", food_remove="f1", peak_remove="p1", partners=None, stay="1"),
    )

    body = json.loads(fake_api.last("PUT", f"/tours/{TOUR_ID}").content)
    assert body["gear"] == body["food"] == body["peaks"] == body["partners"] == []
    assert response.headers["location"] == f"/tours/{TOUR_ID}/edit"


def test_conflict_is_merged_field_by_field(user, fake_api):
    tour_api(fake_api)
    current = {
        **TOUR,
        "version": 5,
        "title": "Säntis mit Ben",
        "summary": "Neu von Ben.",
        "gear": [{**GEAR_ROW, "quantity": 1}, {**GEAR_ROW, "id": "g2", "name": "Pickel"}],
    }
    fake_api.route(
        "PUT",
        "/tours/*",
        lambda r: httpx2.Response(
            409,
            json={"error": {"code": "version_conflict", "message": "changed"}, "current": current},
        ),
    )
    base = json.dumps({name: TOUR[name] for name in ("title", "summary", "start_time", "end_time")})

    response = user.post(
        f"/tours/{TOUR_ID}/edit",
        edit_form(
            base=base, title="Mein Titel", gear_quantity="3", start_time="2026-07-01T06:00:00.000Z"
        ),
    )
    form = text(response)

    assert response.status_code == 409
    assert "Die Tour wurde inzwischen geändert" in form and "Abweichungen" in form
    # Saving again is based on the new version and keeps the own changes.
    assert 'name="version" value="5"' in form and 'name="title" value="Mein Titel"' in form
    assert 'name="gear_quantity" value="3"' in form and "Pickel" in form
    # The summary was not touched: it takes the new state and is no conflict.
    assert ">Neu von Ben.</textarea>" in form
    conflict = form.split('class="card conflict"')[1].split("</section>")[0]
    assert "Titel" in conflict and "Säntis mit Ben" in conflict and "Mein Titel" in conflict
    # The same point in time written differently is no difference either.
    assert "Beschreibung" not in conflict and "Beginn" not in conflict
    assert "Eigene Eingaben verwerfen" in form
    # The next attempt compares against the new state.
    assert "ntis mit Ben" in form.split('name="base" value="')[1].split('"')[0]


def test_conflict_without_own_changes_to_changed_fields(user, fake_api):
    tour_api(fake_api)
    current = {**TOUR, "version": 5, "summary": "Neu von Ben."}
    fake_api.route(
        "PUT",
        "/tours/*",
        lambda r: httpx2.Response(
            409,
            json={"error": {"code": "version_conflict", "message": "changed"}, "current": current},
        ),
    )
    form = text(user.get(f"/tours/{TOUR_ID}/edit"))
    base = form.split('name="base" value="')[1].split('"')[0]
    response = user.post(
        f"/tours/{TOUR_ID}/edit", edit_form(base=html.unescape(base), peak_new_name="Lisengrat")
    )

    assert response.status_code == 409
    assert "berühren keine Felder" in text(response)
    assert ">Neu von Ben.</textarea>" in text(response)


def test_rejected_or_unreadable_input_keeps_the_form(user, fake_api):
    tour_api(fake_api)
    fake_api.route("PUT", "/tours/*", lambda r: httpx2.Response(422, json={"detail": []}))

    rejected = user.post(f"/tours/{TOUR_ID}/edit", edit_form(title="Zu spät", gear_quantity="5000"))
    unreadable = user.post(f"/tours/{TOUR_ID}/edit", edit_form(food_amount="viel"))

    assert rejected.status_code == 422 and 'name="title" value="Zu spät"' in text(rejected)
    assert 'name="gear_quantity" value="5000"' in text(rejected)
    assert unreadable.status_code == 422
    assert fake_api.requested().count(f"PUT /tours/{TOUR_ID}") == 1


def test_edit_permission_sends_owner_only_fields_unchanged(user, fake_api):
    tour_api(
        fake_api,
        permission="edit",
        duration_minutes=455,
        calories_estimate=None,
        owner={"id": OTHER_ID, "display_name": "Ben"},
    )
    fake_api.route("PUT", "/tours/*", lambda r: httpx2.Response(200, json=TOUR))

    form = text(user.get(f"/tours/{TOUR_ID}/edit"))

    assert "kann nur der Besitzer" in form and 'type="datetime-local"' not in form
    assert '<input type="hidden" name="duration_minutes" value="455">' in form
    user.post(f"/tours/{TOUR_ID}/edit", edit_form(summary="Ergänzt", duration_minutes="455"))
    body = json.loads(fake_api.last("PUT", f"/tours/{TOUR_ID}").content)
    assert (body["summary"], body["duration_minutes"]) == ("Ergänzt", 455)
    assert body["start_time"] == TOUR["start_time"]


def test_read_permission_gets_no_edit_form_and_api_refusals_are_explained(user, fake_api):
    tour_api(fake_api, permission="read")
    assert user.get(f"/tours/{TOUR_ID}/edit").status_code == 403

    tour_api(fake_api, permission="edit")
    fake_api.route("PUT", "/tours/*", lambda r: error(403, "owner_only_field"))
    refused = user.post(f"/tours/{TOUR_ID}/edit", edit_form(duration_minutes="1"))

    assert refused.status_code == 422
    assert "Zeiten und Zahlenwerte kann nur der Besitzer der Tour ändern." in text(refused)


# --- Track, photos, weather ---


def test_gpx_and_photo_uploads_reach_the_api(user, fake_api):
    fake_api.route("PUT", "/tours/*/gpx", TOUR)
    fake_api.route("POST", "/tours/*/photos", lambda r: httpx2.Response(201, json=[PHOTO, PHOTO]))

    gpx = user.post(
        f"/tours/{TOUR_ID}/gpx",
        {"file": (io.BytesIO(b"<gpx/>"), "tour.gpx")},
        content_type="multipart/form-data",
    )
    photos = user.post(
        f"/tours/{TOUR_ID}/photos",
        {"files": [(io.BytesIO(b"one"), "a.jpg"), (io.BytesIO(b"two"), "b.jpg")]},
        content_type="multipart/form-data",
    )

    assert gpx.headers["location"] == f"/tours/{TOUR_ID}#track"
    sent = fake_api.last("PUT", f"/tours/{TOUR_ID}/gpx").content
    assert b"<gpx/>" in sent and b'name="file"; filename="tour.gpx"' in sent
    assert photos.headers["location"] == f"/tours/{TOUR_ID}#photos"
    sent = fake_api.last("POST", f"/tours/{TOUR_ID}/photos").content
    assert sent.count(b'name="files"') == 2 and b"one" in sent and b"two" in sent


def test_bad_upload_is_explained(user, fake_api):
    fake_api.route("PUT", "/tours/*/gpx", lambda r: error(422, "invalid_gpx"))

    response = user.post(
        f"/tours/{TOUR_ID}/gpx",
        {"file": (io.BytesIO(b"nope"), "x.gpx")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    assert "Die Datei ist keine lesbare GPX-Datei." in text(response)


def test_track_photo_and_weather_actions(user, fake_api):
    for method, path in (
        ("DELETE", "/tours/*/track"),
        ("POST", "/tours/*/track/places"),
        ("POST", "/tours/*/weather/fetch"),
        ("POST", "/tours/*/calories/estimate"),
        ("PATCH", "/tours/*/photos/*"),
        ("PUT", "/tours/*/photos/time-offset"),
        ("POST", "/tours/*/waypoints/from-photos"),
    ):
        fake_api.route(method, path, TOUR)
    fake_api.route("DELETE", "/tours/*/photos/*", lambda r: httpx2.Response(204))
    fake_api.route(
        "GET",
        "/tours/*/gpx",
        lambda r: httpx2.Response(
            200,
            content=b"<gpx/>",
            headers={
                "content-type": "application/gpx+xml",
                "content-disposition": 'attachment; filename="saentis.gpx"',
            },
        ),
    )
    base = f"/tours/{TOUR_ID}"

    for path in (
        "/track/delete",
        "/track/places",
        "/weather",
        "/calories",
        "/waypoints/from-photos",
    ):
        assert user.post(base + path).status_code == 302
    user.post(f"{base}/photos/{PHOTO_ID}", {"caption": " Gipfelkreuz "})
    caption = json.loads(fake_api.last("PATCH", f"{base}/photos/{PHOTO_ID}").content)
    user.post(f"{base}/photos/{PHOTO_ID}", {"caption": "x", "cover": "1"})
    cover = json.loads(fake_api.last("PATCH", f"{base}/photos/{PHOTO_ID}").content)
    user.post(f"{base}/photos/time-offset", {"minutes": "-120"})
    user.post(f"{base}/photos/{PHOTO_ID}/delete")
    download = user.get(f"{base}/gpx")

    assert caption == {"caption": "Gipfelkreuz"} and cover == {"is_cover": True}
    assert json.loads(fake_api.last("PUT", f"{base}/photos/time-offset").content) == {
        "seconds": -7200
    }
    for call in (
        f"DELETE {base}/track",
        f"POST {base}/track/places",
        f"POST {base}/weather/fetch",
        f"POST {base}/calories/estimate",
        f"DELETE {base}/photos/{PHOTO_ID}",
    ):
        assert call in fake_api.requested()
    assert download.data == b"<gpx/>" and "saentis.gpx" in download.headers["Content-Disposition"]


def test_export_and_delete(user, fake_api):
    fake_api.route(
        "GET",
        "/tours/*/export",
        lambda r: httpx2.Response(
            200,
            json={"schema_version": 1},
            headers={"content-disposition": 'attachment; filename="t.json"'},
        ),
    )
    fake_api.route("DELETE", "/tours/*", lambda r: httpx2.Response(204))

    export = user.get(f"/tours/{TOUR_ID}/export")
    deleted = user.post(f"/tours/{TOUR_ID}/delete")

    assert export.get_json() == {"schema_version": 1}
    assert export.headers["Content-Disposition"] == 'attachment; filename="t.json"'
    assert deleted.headers["location"] == "/tours/"


# --- History ---

REVISION = {
    "version": 3,
    "kind": "updated",
    "change_summary": "title, gear",
    "author": {"id": OTHER_ID, "display_name": "Ben"},
    "created_at": "2026-07-02T04:00:00Z",
    "snapshot": {
        "title": "Säntis",
        "summary": "Alt",
        "gear": [GEAR_ROW],
        "food": [],
        "peaks": [PEAK],
        "waypoints": [],
    },
    "diff": {
        "title": {"old": "Säntis alt", "new": "Säntis"},
        "gear": {
            "added": [{"id": "g1", "name": "Zelt"}],
            "removed": [{"id": "g0", "name": "Biwaksack"}],
            "changed": [
                {
                    "id": "g3",
                    "name": "Seil",
                    "changes": {
                        "carried": {"old": True, "new": False},
                        "quantity": {"old": 1, "new": 2},
                    },
                }
            ],
            "reordered": False,
        },
    },
}


def test_history_lists_revisions_and_shows_a_diff(user, fake_api):
    tour_api(fake_api)
    listed = {
        key: REVISION[key] for key in ("version", "kind", "change_summary", "author", "created_at")
    }
    fake_api.route(
        "GET",
        "/tours/*/revisions",
        page(
            [
                {**listed, "version": 4, "kind": "restored", "change_summary": "2", "author": None},
                listed,
            ]
        ),
    )
    fake_api.route("GET", "/tours/*/revisions/*", REVISION)

    history = text(user.get(f"/tours/{TOUR_ID}/history"))
    revision = text(user.get(f"/tours/{TOUR_ID}/history/3"))

    assert (
        "Version 4" in history and "wiederhergestellt" in history and "gelöschter Nutzer" in history
    )
    assert "aktuell" in history and "Titel, Ausrüstung" in history and "Ben" in history
    assert "<del>Säntis alt</del> → <ins>Säntis</ins>" in revision
    assert "hinzugefügt</span> Zelt" in revision and "entfernt</span> Biwaksack" in revision
    assert "getragen <del>ja</del> → <ins>nein</ins>" in revision
    assert "Anzahl <del>1</del> → <ins>2</ins>" in revision
    assert "Diesen Stand wiederherstellen" in revision


def test_restore_creates_a_new_version_through_the_api(user, fake_api):
    tour_api(fake_api, permission="read")
    fake_api.route("GET", "/tours/*/revisions/*", REVISION)
    fake_api.route("POST", "/tours/*/revisions/*/restore", TOUR)

    assert "Diesen Stand wiederherstellen" not in text(user.get(f"/tours/{TOUR_ID}/history/3"))
    response = user.post(f"/tours/{TOUR_ID}/history/3/restore")

    assert response.headers["location"] == f"/tours/{TOUR_ID}"
    assert f"POST /tours/{TOUR_ID}/revisions/3/restore" in fake_api.requested()


# --- Sharing ---

LINK = {
    "id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "active": True,
    "url": "https://hiker.example/p/0b0e6a52-1d0f-4f0e-9d6e-3f0a1f6a9a11",
    "created_at": "2026-07-02T00:00:00Z",
    "expires_at": "2026-08-01T23:59:59Z",
    "revoked_at": None,
    "hide_exact_start": True,
    "strip_photo_gps": False,
    "show_health_data": False,
}


def test_sharing_page_lists_shares_and_links(user, fake_api):
    tour_api(fake_api)
    fake_api.route(
        "GET",
        "/tours/*/shares",
        [
            {
                "user": {"id": OTHER_ID, "display_name": "Ben"},
                "permission": "edit",
                "created_at": "2026-07-02T00:00:00Z",
            }
        ],
    )
    fake_api.route(
        "GET",
        "/tours/*/public-link",
        [LINK, {**LINK, "active": False, "revoked_at": "2026-07-03T00:00:00Z"}],
    )

    sharing = text(user.get(f"/tours/{TOUR_ID}/sharing"))

    assert "Ben" in sharing and '<option value="edit" selected>' in sharing
    assert sharing.count(LINK["url"]) == 1 and "gültig bis 01.08.2026" in sharing
    assert "widerrufen" in sharing and "nur ungefähr zeigen" in sharing
    assert "onfocus" not in sharing


def test_sharing_with_a_user_looks_the_address_up_first(user, fake_api):
    fake_api.route(
        "GET",
        "/users/lookup",
        lambda r: (
            httpx2.Response(200, json={"id": OTHER_ID, "display_name": "Ben"})
            if r.url.params["email"] == "ben@example.org"
            else error(404, "not_found")
        ),
    )
    fake_api.route("POST", "/tours/*/shares", lambda r: httpx2.Response(201, json={}))
    fake_api.route("PATCH", "/tours/*/shares/*", {})
    fake_api.route("DELETE", "/tours/*/shares/*", lambda r: httpx2.Response(204))
    base = f"/tours/{TOUR_ID}"

    unknown = user.post(f"{base}/shares", {"email": "nobody@example.org", "permission": "edit"})
    assert unknown.status_code == 302 and f"POST {base}/shares" not in fake_api.requested()
    user.post(f"{base}/shares", {"email": "ben@example.org", "permission": "edit"})
    user.post(f"{base}/shares/{OTHER_ID}", {"permission": "something"})
    user.post(f"{base}/shares/{OTHER_ID}/delete")
    left = user.post(f"{base}/leave")

    assert json.loads(fake_api.last("POST", f"{base}/shares").content) == {
        "user_id": OTHER_ID,
        "permission": "edit",
    }
    assert json.loads(fake_api.last("PATCH", f"{base}/shares/{OTHER_ID}").content) == {
        "permission": "read"
    }
    assert f"DELETE {base}/shares/{OTHER_ID}" in fake_api.requested()
    assert fake_api.requested()[-1] == f"DELETE {base}/shares/{USER['id']}"
    assert left.headers["location"] == "/tours/"


def test_public_links_are_created_and_revoked(user, fake_api):
    fake_api.route("POST", "/tours/*/public-link", lambda r: httpx2.Response(201, json=LINK))
    fake_api.route("DELETE", "/tours/*/public-link/*", lambda r: httpx2.Response(204))
    base = f"/tours/{TOUR_ID}"

    user.post(f"{base}/links", {"expires": "2026-08-01", "hide_exact_start": "on"})
    limited = json.loads(fake_api.last("POST", f"{base}/public-link").content)
    user.post(f"{base}/links", {"expires": "", "show_health_data": "on"})
    unlimited = json.loads(fake_api.last("POST", f"{base}/public-link").content)
    user.post(f"{base}/links/{LINK['id']}/revoke")

    assert limited == {
        "expires_at": "2026-08-01T23:59:59Z",
        "hide_exact_start": True,
        "strip_photo_gps": False,
        "show_health_data": False,
    }
    assert unlimited["expires_at"] is None and unlimited["show_health_data"] is True
    assert f"DELETE {base}/public-link/{LINK['id']}" in fake_api.requested()


def test_contacts(user, fake_api):
    fake_api.route("GET", "/contacts", CONTACTS)
    fake_api.route("POST", "/contacts", lambda r: httpx2.Response(201, json=CONTACTS[0]))
    fake_api.route("DELETE", "/contacts/*", lambda r: httpx2.Response(204))
    fake_api.route("GET", "/users/lookup", {"id": OTHER_ID, "display_name": "Cleo K."})

    listing = text(user.get("/tours/contacts"))
    user.post("/tours/contacts", {"display_name": "Dora", "email": ""})
    plain = json.loads(fake_api.last("POST", "/contacts").content)
    user.post("/tours/contacts", {"display_name": "Cleo", "email": "cleo@example.org"})
    linked = json.loads(fake_api.last("POST", "/contacts").content)
    user.post("/tours/contacts/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/delete")

    assert "Ben" in listing and "Nutzer: Cleo K." in listing
    assert plain == {"display_name": "Dora"}
    assert linked == {"display_name": "Cleo", "linked_user_id": OTHER_ID}
    assert "DELETE /contacts/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" in fake_api.requested()
