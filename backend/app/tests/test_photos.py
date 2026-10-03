import uuid
from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.core.files import FileObject
from app.modules.protocols.photos import ExifInfo, read_exif
from app.tests.test_protocols import (  # noqa: F401
    TOURS,
    anna,
    bea,
    cleo,
    create_tour,
    dora,
    people,
    put,
    restore,
    revision,
    share,
)
from app.tests.test_public_links import PUBLIC, UUID_RE, create_link, token_of
from app.tests.test_track import garmin_gpx, upload

# The test track runs north from 47.000/9.000, one point per minute from 06:00 UTC,
# 0.001° (111.2 m) and 10 m of ascent per point.


def photo(time=None, offset=None, gps=None, altitude=None, size=(1200, 800), fmt="JPEG") -> bytes:
    exif = Image.Exif()
    if time is not None:
        exif[0x8769] = {0x9003: time} | ({0x9011: offset} if offset else {})
    if gps is not None:
        lat, lon = gps
        block = {
            1: "N" if lat >= 0 else "S",
            2: (float(int(abs(lat))), 0.0, round((abs(lat) % 1) * 3600, 4)),
            3: "E" if lon >= 0 else "W",
            4: (float(int(abs(lon))), 0.0, round((abs(lon) % 1) * 3600, 4)),
        }
        if altitude is not None:
            block |= {5: b"\x00", 6: float(altitude)}
        exif[0x8825] = block
    output = BytesIO()
    Image.new("RGB", size, (90, 140, 60)).save(output, format=fmt, exif=exif)
    return output.getvalue()


def upload_photos(client, person, tour, *images):
    files = [("files", (f"foto{i}.jpg", data, "image/jpeg")) for i, data in enumerate(images)]
    return client.post(f"{TOURS}/{tour['id']}/photos", files=files, headers=person.headers)


def photos_url(tour, photo=None, suffix=""):
    return f"{TOURS}/{tour['id']}/photos" + (f"/{photo['id']}" if photo else "") + suffix


@pytest.fixture
def tour(client, db, anna, bea, cleo):  # noqa: F811
    """A tour of anna with a track, shared with bea (edit) and cleo (read)."""
    created = create_tour(client, anna)
    share(db, created, bea, "edit")
    share(db, created, cleo, "read")
    return upload(client, anna, created, garmin_gpx()).json()


# --- EXIF ---


def test_read_exif_time_and_gps():
    info = read_exif(photo(time="2026:08:01 06:03:30", gps=(47.25, 9.5), altitude=1234))

    assert info.taken_at == datetime(2026, 8, 1, 6, 3, 30, tzinfo=UTC)
    assert (info.lat, info.lon) == pytest.approx((47.25, 9.5), abs=1e-6)
    assert info.altitude == 1234.0


def test_read_exif_uses_the_time_zone_offset_and_hemispheres():
    info = read_exif(photo(time="2026:08:01 08:03:30", offset="+02:00", gps=(-33.5, -70.25)))

    assert info.taken_at == datetime(2026, 8, 1, 6, 3, 30, tzinfo=UTC)
    assert (info.lat, info.lon) == pytest.approx((-33.5, -70.25), abs=1e-6)


def test_read_exif_tolerates_missing_and_broken_data():
    assert read_exif(photo()) == ExifInfo()
    assert read_exif(b"not an image") == ExifInfo()
    assert read_exif(photo(time="yesterday at noon")) == ExifInfo()
    assert read_exif(photo(gps=(0.0, 0.0))) == ExifInfo()
    png = photo(fmt="PNG")
    assert read_exif(png) == ExifInfo()


# --- Upload and matching ---


def test_photo_with_gps_is_attached_to_the_nearest_track_point(client, anna, tour):  # noqa: F811
    response = upload_photos(
        client, anna, tour, photo(time="2026:08:01 09:00:00", gps=(47.003, 9.0002), altitude=1500)
    )

    assert response.status_code == 201
    [item] = response.json()
    assert item["position_source"] == "exif_gps"
    assert (item["lat"], item["lon"]) == pytest.approx((47.003, 9.0002), abs=1e-6)
    assert item["track_distance_m"] == pytest.approx(333.6, abs=0.5)
    assert item["elevation_m"] == 1030.0
    assert item["taken_at"] == "2026-08-01T09:00:00Z"
    assert item["caption"] is None and item["is_cover"] is False


def test_photo_without_gps_is_matched_by_time(client, anna, tour):  # noqa: F811
    [item] = upload_photos(client, anna, tour, photo(time="2026:08:01 06:03:30")).json()

    assert item["position_source"] == "exif_time"
    assert (item["lat"], item["lon"]) == pytest.approx((47.0035, 9.0), abs=1e-6)
    assert item["track_distance_m"] == pytest.approx(389.2, abs=0.5)
    assert item["elevation_m"] == 1035.0


def test_photo_without_usable_exif_has_no_position(client, anna, tour):  # noqa: F811
    items = upload_photos(
        client, anna, tour, photo(), photo(time="2026:08:01 12:00:00"), photo(fmt="PNG")
    ).json()

    assert [item["position_source"] for item in items] == ["none"] * 3
    assert all(item["lat"] is None and item["track_distance_m"] is None for item in items)


def test_photo_far_from_the_track_keeps_its_gps_but_no_track_position(client, anna, tour):  # noqa: F811
    [item] = upload_photos(client, anna, tour, photo(gps=(47.2, 9.5), altitude=600)).json()

    assert item["position_source"] == "exif_gps"
    assert item["lat"] == pytest.approx(47.2, abs=1e-6)
    assert item["track_distance_m"] is None
    assert item["elevation_m"] == 600.0


def test_photos_work_without_a_track(client, anna):  # noqa: F811
    created = create_tour(client, anna)

    items = upload_photos(
        client, anna, created, photo(gps=(47.003, 9.0)), photo(time="2026:08:01 06:03:30")
    ).json()

    assert [item["position_source"] for item in items] == ["exif_gps", "none"]
    assert items[0]["track_distance_m"] is None


def test_time_offset_corrects_the_camera_clock_for_all_photos(client, anna, tour):  # noqa: F811
    # The camera was set to local summer time (UTC+2) and stores no time zone.
    upload_photos(
        client, anna, tour, photo(time="2026:08:01 08:03:30"), photo(time="2026:08:01 08:07:00")
    )
    before = client.get(photos_url(tour), headers=anna.headers).json()

    response = client.put(
        photos_url(tour, suffix="/time-offset"), json={"seconds": -7200}, headers=anna.headers
    )

    assert [item["position_source"] for item in before] == ["none", "none"]
    assert response.status_code == 200
    after = response.json()
    assert [item["position_source"] for item in after] == ["exif_time", "exif_time"]
    assert [item["track_distance_m"] for item in after] == pytest.approx([389.2, 778.4], abs=0.5)
    current = client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).json()
    assert current["photo_time_offset_seconds"] == -7200
    assert current["photo_count"] == 2
    too_much = client.put(
        photos_url(tour, suffix="/time-offset"), json={"seconds": 999_999}, headers=anna.headers
    )
    assert too_much.status_code == 422


def test_time_tolerance_at_the_ends_of_the_track(client, anna, tour):  # noqa: F811
    items = upload_photos(
        client,
        anna,
        tour,
        photo(time="2026:08:01 05:55:00"),
        photo(time="2026:08:01 06:15:00"),
        photo(time="2026:08:01 06:25:00"),
    ).json()
    by_time = {item["taken_at"]: item for item in items}

    assert by_time["2026-08-01T05:55:00Z"]["track_distance_m"] == 0.0
    assert by_time["2026-08-01T06:15:00Z"]["track_distance_m"] == pytest.approx(1112, abs=1)
    assert by_time["2026-08-01T06:25:00Z"]["position_source"] == "none"


def test_images_are_reencoded_without_exif_and_get_a_thumbnail(client, anna, tour):  # noqa: F811
    original = photo(time="2026:08:01 06:03:30", gps=(47.003, 9.0), size=(3000, 2000))
    [item] = upload_photos(client, anna, tour, original).json()
    url = photos_url(tour, item, "/image")

    full = client.get(url, headers=anna.headers)
    thumb = client.get(url, params={"size": "thumb"}, headers=anna.headers)

    assert full.status_code == 200 and full.headers["content-type"] == "image/jpeg"
    full_image, thumb_image = Image.open(BytesIO(full.content)), Image.open(BytesIO(thumb.content))
    assert full_image.size == (2000, 1333)
    assert thumb_image.size == (400, 267)
    assert len(full_image.getexif()) == 0 and len(thumb_image.getexif()) == 0
    assert client.get(url, params={"size": "huge"}, headers=anna.headers).status_code == 422


def test_one_bad_file_rejects_the_whole_upload(client, db, anna, tour):  # noqa: F811
    files_before = db.scalar(select(func.count()).select_from(FileObject))

    response = upload_photos(client, anna, tour, photo(), b"not an image", photo())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_image"
    assert client.get(photos_url(tour), headers=anna.headers).json() == []
    assert db.scalar(select(func.count()).select_from(FileObject)) == files_before


def test_upload_limits(client, anna, tour, monkeypatch):  # noqa: F811
    from app.core.config import get_settings

    too_many = upload_photos(client, anna, tour, *[photo(size=(8, 8))] * 21)
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    too_large = upload_photos(client, anna, tour, b"x" * (1024 * 1024 + 1))

    assert too_many.json()["error"]["code"] == "too_many_photos"
    assert too_large.status_code == 413


def test_gallery_is_ordered_along_the_track(client, anna, tour):  # noqa: F811
    upload_photos(
        client,
        anna,
        tour,
        photo(),
        photo(time="2026:08:01 06:08:00"),
        photo(gps=(47.002, 9.0)),
        photo(time="2026:08:01 06:01:00"),
    )

    items = client.get(photos_url(tour), headers=anna.headers).json()

    assert [item["track_distance_m"] for item in items] == pytest.approx(
        [111.2, 222.4, 889.6, None], abs=0.5
    )


def test_new_track_moves_the_photos(client, anna):  # noqa: F811
    created = create_tour(client, anna)
    upload_photos(
        client, anna, created, photo(time="2026:08:01 06:03:30"), photo(gps=(47.002, 9.0))
    )

    upload(client, anna, created, garmin_gpx())
    with_track = client.get(photos_url(created), headers=anna.headers).json()
    client.delete(f"{TOURS}/{created['id']}/track", headers=anna.headers)
    without = client.get(photos_url(created), headers=anna.headers).json()

    assert [p["position_source"] for p in with_track] == ["exif_gps", "exif_time"]
    assert [p["track_distance_m"] for p in with_track] == pytest.approx([222.4, 389.2], abs=0.5)
    assert sorted(p["position_source"] for p in without) == ["exif_gps", "none"]
    assert all(p["track_distance_m"] is None for p in without)


# --- Editing ---


def test_position_can_be_corrected_on_map_and_profile_and_reset(client, anna, tour):  # noqa: F811
    [item] = upload_photos(client, anna, tour, photo(time="2026:08:01 06:03:30")).json()
    url = photos_url(tour, item)

    on_map = client.patch(url, json={"lat": 47.0071, "lon": 9.0003}, headers=anna.headers).json()
    on_profile = client.patch(url, json={"track_distance_m": 500}, headers=anna.headers).json()
    automatic = client.patch(url, json={"auto_position": True}, headers=anna.headers).json()

    assert on_map["position_source"] == "manual"
    assert (on_map["lat"], on_map["lon"]) == (47.0071, 9.0003)
    assert on_map["track_distance_m"] == pytest.approx(778.4, abs=0.5)
    assert on_profile["position_source"] == "manual"
    assert on_profile["track_distance_m"] == 500.0
    assert on_profile["lat"] == pytest.approx(47.004497, abs=1e-5)
    assert on_profile["elevation_m"] == pytest.approx(1045.0, abs=0.2)
    assert automatic["position_source"] == "exif_time"
    assert automatic["track_distance_m"] == item["track_distance_m"]


def test_manual_position_survives_offset_and_track_changes(client, anna, tour):  # noqa: F811
    [item] = upload_photos(client, anna, tour, photo(time="2026:08:01 06:03:30")).json()
    client.patch(photos_url(tour, item), json={"lat": 47.007, "lon": 9.0}, headers=anna.headers)

    client.put(photos_url(tour, suffix="/time-offset"), json={"seconds": 120}, headers=anna.headers)
    upload(client, anna, tour, garmin_gpx(count=21))

    [current] = client.get(photos_url(tour), headers=anna.headers).json()
    assert current["position_source"] == "manual"
    assert (current["lat"], current["lon"]) == (47.007, 9.0)
    assert current["track_distance_m"] == pytest.approx(778.4, abs=0.5)


@pytest.mark.parametrize(
    "body",
    [
        {"lat": 47.0},
        {"lat": 95, "lon": 9},
        {"lat": 47, "lon": 9, "track_distance_m": 100},
        {"track_distance_m": -1},
        {"caption": "x" * 501},
    ],
)
def test_patch_validates_input(client, anna, tour, body):  # noqa: F811
    [item] = upload_photos(client, anna, tour, photo()).json()

    assert client.patch(photos_url(tour, item), json=body, headers=anna.headers).status_code == 422


def test_caption_and_cover(client, anna, tour):  # noqa: F811
    first, second = upload_photos(client, anna, tour, photo(), photo()).json()

    patched = client.patch(
        photos_url(tour, first),
        json={"caption": " Gipfelkreuz ", "is_cover": True},
        headers=anna.headers,
    ).json()
    client.patch(photos_url(tour, second), json={"is_cover": True}, headers=anna.headers)

    assert (patched["caption"], patched["is_cover"]) == ("Gipfelkreuz", True)
    items = {
        p["id"]: p["is_cover"] for p in client.get(photos_url(tour), headers=anna.headers).json()
    }
    assert items == {first["id"]: False, second["id"]: True}
    listed = client.get(TOURS, headers=anna.headers).json()["items"][0]
    assert listed["cover_photo_id"] == second["id"]
    unset = client.patch(photos_url(tour, second), json={"is_cover": False}, headers=anna.headers)
    assert unset.json()["is_cover"] is False
    assert (
        client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).json()["cover_photo_id"] is None
    )


def test_deleting_a_photo_removes_its_files_and_the_cover(client, db, storage, anna, tour):  # noqa: F811
    [item] = upload_photos(client, anna, tour, photo()).json()
    client.patch(photos_url(tour, item), json={"is_cover": True}, headers=anna.headers)
    keys = db.scalars(select(FileObject.storage_key).where(FileObject.mime == "image/jpeg")).all()
    assert len(keys) == 2 and all(storage.exists(key) for key in keys)

    response = client.delete(photos_url(tour, item), headers=anna.headers)

    assert response.status_code == 204
    assert not any(storage.exists(key) for key in keys)
    assert client.get(photos_url(tour), headers=anna.headers).json() == []
    assert client.get(photos_url(tour, item, "/image"), headers=anna.headers).status_code == 404
    assert (
        client.get(f"{TOURS}/{tour['id']}", headers=anna.headers).json()["cover_photo_id"] is None
    )


def test_deleting_the_tour_removes_photos_and_gpx_files(client, db, storage, anna, tour):  # noqa: F811
    upload_photos(client, anna, tour, photo(), photo())
    upload(client, anna, tour, garmin_gpx(count=5))
    keys = db.scalars(select(FileObject.storage_key)).all()
    assert len(keys) == 6

    client.delete(f"{TOURS}/{tour['id']}", headers=anna.headers)

    assert not any(storage.exists(key) for key in keys)
    assert db.scalar(select(func.count()).select_from(FileObject)) == 0


# --- Permissions ---


def test_edit_manages_photos_read_only_views(client, people, tour):  # noqa: F811
    anna_, bea_, cleo_, dora_ = (people[name] for name in ("anna", "bea", "cleo", "dora"))

    uploaded = upload_photos(client, bea_, tour, photo(time="2026:08:01 06:03:30"))
    assert uploaded.status_code == 201
    [item] = uploaded.json()
    url = photos_url(tour, item)
    assert (
        client.patch(
            url, json={"caption": "Von Bea", "is_cover": True}, headers=bea_.headers
        ).status_code
        == 200
    )
    offset = client.put(
        photos_url(tour, suffix="/time-offset"), json={"seconds": 60}, headers=bea_.headers
    )
    assert offset.status_code == 200

    assert client.get(photos_url(tour), headers=cleo_.headers).json()[0]["caption"] == "Von Bea"
    assert client.get(f"{url}/image", headers=cleo_.headers).status_code == 200
    assert upload_photos(client, cleo_, tour, photo()).status_code == 403
    assert client.patch(url, json={"caption": "X"}, headers=cleo_.headers).status_code == 403
    assert client.delete(url, headers=cleo_.headers).status_code == 403
    from_photos = f"{TOURS}/{tour['id']}/waypoints/from-photos"
    assert client.post(from_photos, headers=cleo_.headers).status_code == 403

    assert client.get(photos_url(tour), headers=dora_.headers).status_code == 404
    assert client.get(f"{url}/image", headers=dora_.headers).status_code == 404
    assert upload_photos(client, dora_, tour, photo()).status_code == 404
    assert client.get(f"{url}/image").status_code == 401

    assert client.delete(url, headers=bea_.headers).status_code == 204
    assert client.get(photos_url(tour), headers=anna_.headers).json() == []


def test_photo_of_another_tour_is_not_found(client, anna, tour):  # noqa: F811
    other = create_tour(client, anna, title="Andere")
    [item] = upload_photos(client, anna, other, photo()).json()

    assert client.get(photos_url(tour, item, "/image"), headers=anna.headers).status_code == 404
    assert client.delete(photos_url(tour, item), headers=anna.headers).status_code == 404
    assert (
        client.patch(
            photos_url(tour, {"id": uuid.uuid4()}), json={}, headers=anna.headers
        ).status_code
        == 404
    )


# --- Waypoints from photos ---


def test_waypoints_from_photos_groups_nearby_gps_photos(client, anna, tour):  # noqa: F811
    upload_photos(
        client,
        anna,
        tour,
        photo(gps=(47.003, 9.0)),
        photo(gps=(47.0031, 9.0)),
        photo(gps=(47.008, 9.0)),
        photo(time="2026:08:01 06:05:00"),
    )
    hut = [
        p for p in client.get(photos_url(tour), headers=anna.headers).json() if p["lat"] == 47.008
    ]
    client.patch(photos_url(tour, hut[0]), json={"caption": "Hütte"}, headers=anna.headers)
    url = f"{TOURS}/{tour['id']}/waypoints/from-photos"

    response = client.post(url, headers=anna.headers)

    assert response.status_code == 201
    waypoints = response.json()
    assert [(w["name"], w["icon"]) for w in waypoints] == [("Foto 1", "photo"), ("Hütte", "photo")]
    assert waypoints[0]["track_distance_m"] == pytest.approx(333.6, abs=0.5)
    assert waypoints[0]["elevation_m"] == 1030.0
    photos = client.get(photos_url(tour), headers=anna.headers).json()
    linked = [p["waypoint_id"] for p in photos]
    assert linked == [waypoints[0]["id"], waypoints[0]["id"], None, waypoints[1]["id"]]
    assert client.get(f"{TOURS}/{tour['id']}/waypoints", headers=anna.headers).json() == waypoints
    # Photos that already belong to a waypoint are not used again.
    assert client.post(url, headers=anna.headers).json() == []


def test_photo_can_be_attached_to_a_waypoint_and_loses_it_when_deleted(client, anna, tour):  # noqa: F811
    [item] = upload_photos(client, anna, tour, photo()).json()
    waypoints_url = f"{TOURS}/{tour['id']}/waypoints"
    waypoint = client.post(
        waypoints_url, json={"name": "Hütte", "lat": 47.005, "lon": 9.0}, headers=anna.headers
    ).json()

    attached = client.patch(
        photos_url(tour, item), json={"waypoint_id": waypoint["id"]}, headers=anna.headers
    )
    unknown = client.patch(
        photos_url(tour, item), json={"waypoint_id": str(uuid.uuid4())}, headers=anna.headers
    )
    client.delete(f"{waypoints_url}/{waypoint['id']}", headers=anna.headers)

    assert waypoint["track_distance_m"] == pytest.approx(556, abs=0.5)
    assert attached.json()["waypoint_id"] == waypoint["id"]
    assert unknown.json()["error"]["code"] == "unknown_waypoint"
    assert client.get(photos_url(tour), headers=anna.headers).json()[0]["waypoint_id"] is None


# --- History ---


def test_photo_changes_are_in_the_history(client, anna, tour):  # noqa: F811
    [item] = upload_photos(client, anna, tour, photo(time="2026:08:01 06:03:30")).json()
    client.patch(photos_url(tour, item), json={"caption": "Gipfel"}, headers=anna.headers)
    client.patch(photos_url(tour, item), json={"caption": "Falsch"}, headers=anna.headers)

    added = revision(client, anna, tour, 3)["diff"]["photos"]["added"]
    changed = revision(client, anna, tour, 5)["diff"]["photos"]["changed"]

    assert [entry["id"] for entry in added] == [item["id"]]
    assert changed == [
        {
            "id": item["id"],
            "name": "Falsch",
            "changes": {"name": {"old": "Gipfel", "new": "Falsch"}},
        }
    ]

    restore(client, anna, tour, 4)

    assert client.get(photos_url(tour), headers=anna.headers).json()[0]["caption"] == "Gipfel"


def test_restore_never_deletes_or_revives_photos(client, anna, tour):  # noqa: F811
    (old,) = upload_photos(client, anna, tour, photo()).json()
    client.delete(photos_url(tour, old), headers=anna.headers)
    (new,) = upload_photos(client, anna, tour, photo()).json()

    # Version 3 contained only the photo that was deleted afterwards.
    response = restore(client, anna, tour, 3)

    assert response.status_code == 200
    assert [p["id"] for p in client.get(photos_url(tour), headers=anna.headers).json()] == [
        new["id"]
    ]


# --- Public links and export ---


def test_public_view_lists_photos_without_ids(client, anna, tour):  # noqa: F811
    upload_photos(client, anna, tour, photo(gps=(47.005, 9.0)), photo(time="2026:08:01 06:01:00"))
    first = client.get(photos_url(tour), headers=anna.headers).json()[0]
    client.patch(
        photos_url(tour, first), json={"caption": "Start", "is_cover": True}, headers=anna.headers
    )
    token = token_of(create_link(client, anna, tour))

    response = client.get(f"{PUBLIC}/{token}")

    photos = response.json()["photos"]
    assert [(p["index"], p["caption"], p["is_cover"]) for p in photos] == [
        (0, "Start", True),
        (1, None, False),
    ]
    assert photos[1]["lat"] == pytest.approx(47.005)
    assert UUID_RE.search(response.text) is None
    image = client.get(f"{PUBLIC}/{token}/photos/1", params={"size": "thumb"})
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert image.headers["x-robots-tag"] == "noindex, nofollow"
    assert len(Image.open(BytesIO(image.content)).getexif()) == 0
    assert client.get(f"{PUBLIC}/{token}/photos/2").status_code == 404
    assert client.get(f"{PUBLIC}/{token}/photos/-1").status_code == 404
    assert client.get(f"{PUBLIC}/{uuid.uuid4()}/photos/0").status_code == 404


def test_public_link_can_strip_photo_positions(client, anna, tour):  # noqa: F811
    upload_photos(client, anna, tour, photo(gps=(47.005, 9.0)))
    stripped = token_of(create_link(client, anna, tour, strip_photo_gps=True))
    hidden_start = token_of(create_link(client, anna, tour, hide_exact_start=True))
    upload_photos(client, anna, tour, photo(gps=(47.001, 9.0)))

    without = client.get(f"{PUBLIC}/{stripped}").json()["photos"]
    near_start, on_route = client.get(f"{PUBLIC}/{hidden_start}").json()["photos"]

    assert all(
        p["lat"] is None and p["lon"] is None and p["track_distance_m"] is None for p in without
    )
    # 111 m from the hidden start: no position. 556 m away: shown.
    assert near_start["lat"] is None and near_start["track_distance_m"] is None
    assert on_route["lat"] == pytest.approx(47.005)


def test_export_contains_photo_metadata(client, anna, tour):  # noqa: F811
    [item] = upload_photos(client, anna, tour, photo(time="2026:08:01 06:03:30")).json()

    data = client.get(f"{TOURS}/{tour['id']}/export", headers=anna.headers).json()

    assert data["photos"] == [item]
