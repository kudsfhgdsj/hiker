import json
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from hiker_web import error_text, forms
from hiker_web.api import ApiError, api
from hiker_web.security import module_required
from hiker_web.texts_de import t

blueprint = Blueprint("protocols", __name__, url_prefix="/tours")
tour_page = module_required("protocols")

SCALARS = (
    "title",
    "summary",
    "start_time",
    "end_time",
    "duration_minutes",
    "pack_weight_start_g",
    "calories_burned",
)
SCOPES = ("all", "mine", "shared")
OSM_ATTRIBUTION = "© OpenStreetMap-Mitwirkende"


def _back(tour_id, anchor: str | None = None):
    return redirect(url_for("protocols.tour_detail", tour_id=tour_id, _anchor=anchor))


# --- List and creation ---


@blueprint.get("/")
@tour_page
def tour_list():
    scope = request.args.get("scope", "all")
    scope = scope if scope in SCOPES else "all"
    query = request.args.get("q", "").strip()
    tours = api().pages("/tours", scope=scope, q=query)
    return render_template(
        "protocols/list.html", tours=tours, scope=scope, scopes=SCOPES, query=query
    )


@blueprint.route("/new", methods=["GET", "POST"])
@tour_page
def tour_new():
    if request.method == "POST":
        document = {"title": forms.text("title") or "", "summary": forms.text("summary")}
        try:
            tour = api().send("POST", "/tours", document)
        except ApiError as error:
            if error.status == 401:
                raise
            flash(error_text(error), "error")
            return render_template("protocols/new.html", tour=document), 422
        return redirect(url_for("protocols.tour_edit", tour_id=tour["id"]))
    return render_template("protocols/new.html", tour={})


# --- Detail ---


def map_data(tour: dict, photos: list[dict], waypoints: list[dict], urls) -> dict:
    """What the map and the elevation profile need; `urls` builds the addresses."""
    return {
        "trackUrl": urls("track") if tour["track_source"] != "none" else None,
        "tileUrl": current_app.config["MAP_TILE_URL"],
        "workerUrl": url_for("static", filename="vendor/maplibre-gl/maplibre-gl-csp-worker.js"),
        "attribution": OSM_ATTRIBUTION,
        "start": tour.get("start_point"),
        "end": tour.get("end_point"),
        "photos": [
            {
                "lat": photo["lat"],
                "lon": photo["lon"],
                "distance": photo.get("track_distance_m"),
                "caption": photo.get("caption"),
                "thumb": urls("photo", photo, "thumb"),
                "full": urls("photo", photo, "full"),
            }
            for photo in photos
        ],
        "waypoints": [
            {key: point.get(key) for key in ("name", "kind", "lat", "lon", "elevation_m")}
            for point in waypoints
        ],
        "texts": {
            "start": t("tour.start"),
            "end": t("tour.end"),
            "heartRate": t("tour.heart_rate"),
        },
    }


@blueprint.get("/<uuid:tour_id>")
@tour_page
def tour_detail(tour_id):
    client = api()
    tour = client.get(f"/tours/{tour_id}")
    photos = client.get(f"/tours/{tour_id}/photos")
    waypoints = client.get(f"/tours/{tour_id}/waypoints")

    def urls(kind, photo=None, size=None):
        if kind == "track":
            return url_for("protocols.tour_track", tour_id=tour_id, v=tour["version"])
        return url_for("protocols.photo_image", tour_id=tour_id, photo_id=photo["id"], size=size)

    return render_template(
        "protocols/detail.html",
        tour=tour,
        photos=photos,
        waypoints=waypoints,
        overview=client.get(f"/tours/{tour_id}/overview"),
        map_data=map_data(tour, photos, waypoints, urls),
        is_owner=tour["permission"] == "owner",
        can_edit=tour["permission"] in ("owner", "edit"),
    )


@blueprint.get("/<uuid:tour_id>/track.json")
@tour_page
def tour_track(tour_id):
    response = jsonify(api().get(f"/tours/{tour_id}/track"))
    response.headers["Cache-Control"] = "private, max-age=300"
    return response


@blueprint.post("/<uuid:tour_id>/delete")
@tour_page
def tour_delete(tour_id):
    api().send("DELETE", f"/tours/{tour_id}")
    flash(t("common.deleted"), "success")
    return redirect(url_for("protocols.tour_list"))


@blueprint.get("/<uuid:tour_id>/export")
@tour_page
def tour_export(tour_id):
    return forms.download(f"/tours/{tour_id}/export", "tour.json")


# --- Editing the tour document ---


def _rows(prefix: str, *names: str) -> list[dict]:
    columns = [request.form.getlist(f"{prefix}_{name}") for name in names]
    if len({len(column) for column in columns}) > 1:
        raise forms.FormError(prefix)
    return [dict(zip(names, values, strict=True)) for values in zip(*columns, strict=True)]


def _document() -> dict:
    """The tour document as the API expects it, read from the edit form."""
    form = request.form
    removed = {name: set(form.getlist(f"{name}_remove")) for name in ("gear", "food", "peak")}
    carried_gear, carried_food = (
        set(form.getlist("gear_carried")),
        set(form.getlist("food_carried")),
    )
    eaten = set(form.getlist("food_eaten"))

    gear = [
        {
            "id": row["id"],
            "quantity": forms.to_number(row["quantity"], "gear_quantity", int) or 1,
            "carried": row["id"] in carried_gear,
        }
        for row in _rows("gear", "id", "quantity")
        if row["id"] not in removed["gear"]
    ]
    if forms.text("gear_new"):
        gear.append(
            {
                "gear_item_id": forms.text("gear_new"),
                "quantity": forms.number("gear_new_quantity", int) or 1,
                "carried": forms.checked("gear_new_carried"),
            }
        )

    food = [
        {
            "id": row["id"],
            "amount_g": forms.to_number(row["amount"], "food_amount"),
            "carried": row["id"] in carried_food,
            "eaten": row["id"] in eaten,
            "eaten_at": row["eaten_at"] or None,
        }
        for row in _rows("food", "id", "amount", "eaten_at")
        if row["id"] not in removed["food"]
    ]
    if forms.text("food_new"):
        food.append(
            {
                "food_item_id": forms.text("food_new"),
                "amount_g": forms.number("food_new_amount"),
                "carried": forms.checked("food_new_carried"),
                "eaten": forms.checked("food_new_eaten"),
            }
        )
    if any(entry["amount_g"] is None for entry in food):
        raise forms.FormError("food_amount")

    peaks = [
        {
            "id": row["id"],
            "name": row["name"].strip(),
            "elevation_m": forms.to_number(row["elevation"], "peak_elevation", int),
            "lat": forms.to_number(row["lat"], "peak_lat"),
            "lon": forms.to_number(row["lon"], "peak_lon"),
            "reached_at": row["reached_at"] or None,
        }
        for row in _rows("peak", "id", "name", "elevation", "lat", "lon", "reached_at")
        if row["id"] not in removed["peak"]
    ]
    if forms.text("peak_new_name"):
        peaks.append(
            {
                "name": forms.text("peak_new_name"),
                "elevation_m": forms.number("peak_new_elevation", int),
            }
        )

    return {
        "version": forms.number("version", int),
        "title": forms.text("title") or "",
        "summary": forms.text("summary"),
        "start_time": forms.text("start_time"),
        "end_time": forms.text("end_time"),
        "duration_minutes": forms.number("duration_minutes", int),
        "pack_weight_start_g": forms.number("pack_weight_start_g", int),
        "calories_burned": forms.number("calories_burned"),
        "gear": gear,
        "food": food,
        "peaks": peaks,
        "partners": [{"contact_id": value} for value in form.getlist("partners")],
    }


def _overlay(tour: dict, document: dict) -> dict:
    """The tour as the API has it, with the user's own input laid over it."""
    merged = {**tour, **{name: document[name] for name in SCALARS}}
    for name in ("gear", "food", "peaks"):
        mine = {entry["id"]: entry for entry in document[name] if entry.get("id")}
        merged[name] = [{**row, **mine.get(row["id"], {})} for row in tour[name]]
    names = {partner["contact_id"]: partner["display_name"] for partner in tour["partners"]}
    merged["partners"] = [
        {"contact_id": entry["contact_id"], "display_name": names.get(entry["contact_id"])}
        for entry in document["partners"]
    ]
    return merged


def _same(name: str, left, right) -> bool:
    if name.endswith("_time") and left and right:
        try:
            return datetime.fromisoformat(left.replace("Z", "+00:00")) == datetime.fromisoformat(
                right.replace("Z", "+00:00")
            )
        except ValueError:
            return False
    return left == right


def _scalars(tour: dict) -> dict:
    return {name: tour.get(name) for name in SCALARS}


def _submitted_base() -> dict | None:
    """The values the form was loaded with, as the form sends them back."""
    try:
        base = json.loads(request.form.get("base") or "null")
    except ValueError:
        return None
    return base if isinstance(base, dict) else None


def _merge(current: dict, document: dict, base: dict | None) -> list[dict]:
    """Merge field by field after a conflict; returns the fields that really collide.

    A field the user left as it was loaded takes the new value of the server. A field
    the user changed keeps the input; it is listed if the server changed it too.
    """
    conflicts = []
    for name in SCALARS:
        if base is not None and _same(name, base.get(name), document[name]):
            document[name] = current.get(name)
        elif base is not None and _same(name, base.get(name), current.get(name)):
            continue  # only the user changed it
        elif not _same(name, current.get(name), document[name]):
            conflicts.append({"field": name, "current": current.get(name), "mine": document[name]})
    return conflicts


def _edit_page(
    tour: dict, base: dict | None = None, conflict: list[dict] | None = None, status: int = 200
):
    if tour["permission"] not in ("owner", "edit"):
        abort(403)
    client = api()
    modules = client.data["modules"]
    contacts = client.get("/contacts")
    chosen = {partner["contact_id"] for partner in tour["partners"]}
    # Partners added by someone else are not among the own contacts; keep them selectable.
    known = {contact["id"] for contact in contacts}
    others = [partner for partner in tour["partners"] if partner["contact_id"] not in known]
    page = render_template(
        "protocols/edit.html",
        tour=tour,
        base=base if base is not None else _scalars(tour),
        is_owner=tour["permission"] == "owner",
        gear_items=client.pages("/gear/items", status="active") if "gear" in modules else [],
        foods=client.pages("/nutrition/search") if "nutrition" in modules else [],
        contacts=contacts,
        other_partners=others,
        chosen_partners=chosen,
        conflict=conflict,
    )
    return page, status


@blueprint.route("/<uuid:tour_id>/edit", methods=["GET", "POST"])
@tour_page
def tour_edit(tour_id):
    client = api()
    path = f"/tours/{tour_id}"
    if request.method == "GET":
        return _edit_page(client.get(path))
    try:
        document = _document()
    except forms.FormError:
        flash(t("error.validation"), "error")
        return _edit_page(client.get(path), status=422)
    try:
        client.send("PUT", path, document)
    except ApiError as error:
        current = error.body.get("current")
        if error.code == "version_conflict" and current:
            # Show the new state next to the own input; saving again is based on it.
            flash(t("tour.conflict"), "error")
            conflict = _merge(current, document, _submitted_base())
            page = _overlay(current, document)
            return _edit_page(page, base=_scalars(current), conflict=conflict, status=409)
        if error.status in (401, 404):
            raise
        flash(error_text(error), "error")
        return _edit_page(_overlay(client.get(path), document), _submitted_base(), status=422)
    flash(t("common.saved"), "success")
    if "stay" in request.form:
        return redirect(url_for("protocols.tour_edit", tour_id=tour_id))
    return _back(tour_id)


# --- Track ---


@blueprint.post("/<uuid:tour_id>/gpx")
@tour_page
def gpx_upload(tour_id):
    files = forms.upload()
    if files:
        api().request("PUT", f"/tours/{tour_id}/gpx", files=files)
        flash(t("tour.gpx_uploaded"), "success")
    return _back(tour_id, "track")


@blueprint.get("/<uuid:tour_id>/gpx")
@tour_page
def gpx_download(tour_id):
    return forms.download(f"/tours/{tour_id}/gpx", "track.gpx")


@blueprint.post("/<uuid:tour_id>/track/delete")
@tour_page
def track_delete(tour_id):
    api().send("DELETE", f"/tours/{tour_id}/track")
    return _back(tour_id, "track")


@blueprint.post("/<uuid:tour_id>/track/places")
@tour_page
def track_places(tour_id):
    api().send("POST", f"/tours/{tour_id}/track/places")
    flash(t("tour.places_done"), "success")
    return _back(tour_id, "course")


@blueprint.post("/<uuid:tour_id>/weather")
@tour_page
def weather_fetch(tour_id):
    api().send("POST", f"/tours/{tour_id}/weather/fetch")
    return _back(tour_id, "weather")


@blueprint.post("/<uuid:tour_id>/calories")
@tour_page
def calories_estimate(tour_id):
    api().send("POST", f"/tours/{tour_id}/calories/estimate")
    return _back(tour_id)


# --- Photos and waypoints ---


@blueprint.post("/<uuid:tour_id>/photos")
@tour_page
def photo_upload(tour_id):
    files = forms.upload("files", multiple=True)
    if files:
        api().request("POST", f"/tours/{tour_id}/photos", files=files)
        flash(t("tour.photos_uploaded", count=len(files)), "success")
    return _back(tour_id, "photos")


@blueprint.get("/<uuid:tour_id>/photos/<uuid:photo_id>/image")
@tour_page
def photo_image(tour_id, photo_id):
    size = "thumb" if request.args.get("size") == "thumb" else "full"
    return forms.proxy_image(f"/tours/{tour_id}/photos/{photo_id}/image", size=size)


@blueprint.post("/<uuid:tour_id>/photos/<uuid:photo_id>")
@tour_page
def photo_update(tour_id, photo_id):
    change = {"is_cover": True} if "cover" in request.form else {"caption": forms.text("caption")}
    api().send("PATCH", f"/tours/{tour_id}/photos/{photo_id}", change)
    return _back(tour_id, "photos")


@blueprint.post("/<uuid:tour_id>/photos/<uuid:photo_id>/delete")
@tour_page
def photo_delete(tour_id, photo_id):
    api().send("DELETE", f"/tours/{tour_id}/photos/{photo_id}")
    return _back(tour_id, "photos")


@blueprint.post("/<uuid:tour_id>/photos/time-offset")
@tour_page
def photo_time_offset(tour_id):
    try:
        minutes = forms.number("minutes", int) or 0
    except forms.FormError:
        abort(400)
    api().send("PUT", f"/tours/{tour_id}/photos/time-offset", {"seconds": minutes * 60})
    return _back(tour_id, "photos")


@blueprint.post("/<uuid:tour_id>/waypoints/from-photos")
@tour_page
def waypoints_from_photos(tour_id):
    api().send("POST", f"/tours/{tour_id}/waypoints/from-photos")
    return _back(tour_id, "course")


@blueprint.post("/<uuid:tour_id>/waypoints/<uuid:waypoint_id>/delete")
@tour_page
def waypoint_delete(tour_id, waypoint_id):
    api().send("DELETE", f"/tours/{tour_id}/waypoints/{waypoint_id}")
    return _back(tour_id, "course")


# --- History ---


@blueprint.get("/<uuid:tour_id>/history")
@tour_page
def history(tour_id):
    client = api()
    return render_template(
        "protocols/history.html",
        tour=client.get(f"/tours/{tour_id}"),
        revisions=client.pages(f"/tours/{tour_id}/revisions"),
    )


@blueprint.get("/<uuid:tour_id>/history/<int:version>")
@tour_page
def revision(tour_id, version):
    client = api()
    return render_template(
        "protocols/revision.html",
        tour=client.get(f"/tours/{tour_id}"),
        revision=client.get(f"/tours/{tour_id}/revisions/{version}"),
    )


@blueprint.post("/<uuid:tour_id>/history/<int:version>/restore")
@tour_page
def restore(tour_id, version):
    api().send("POST", f"/tours/{tour_id}/revisions/{version}/restore")
    flash(t("history.restored", version=version), "success")
    return _back(tour_id)


# --- Sharing and public links ---


def _lookup_user(email: str | None) -> dict | None:
    if not email:
        return None
    try:
        return api().get("/users/lookup", email=email)
    except ApiError as error:
        if error.status not in (404, 422):
            raise
        return None


@blueprint.get("/<uuid:tour_id>/sharing")
@tour_page
def sharing(tour_id):
    client = api()
    return render_template(
        "protocols/sharing.html",
        tour=client.get(f"/tours/{tour_id}"),
        shares=client.get(f"/tours/{tour_id}/shares"),
        links=client.get(f"/tours/{tour_id}/public-link"),
    )


def _to_sharing(tour_id):
    return redirect(url_for("protocols.sharing", tour_id=tour_id))


def _permission() -> str:
    return "edit" if request.form.get("permission") == "edit" else "read"


@blueprint.post("/<uuid:tour_id>/shares")
@tour_page
def share_create(tour_id):
    found = _lookup_user(forms.text("email"))
    if found is None:
        flash(t("error.unknown_user"), "error")
        return _to_sharing(tour_id)
    body = {"user_id": found["id"], "permission": _permission()}
    api().send("POST", f"/tours/{tour_id}/shares", body)
    flash(t("share.added", name=found["display_name"]), "success")
    return _to_sharing(tour_id)


@blueprint.post("/<uuid:tour_id>/shares/<uuid:user_id>")
@tour_page
def share_update(tour_id, user_id):
    api().send("PATCH", f"/tours/{tour_id}/shares/{user_id}", {"permission": _permission()})
    return _to_sharing(tour_id)


@blueprint.post("/<uuid:tour_id>/shares/<uuid:user_id>/delete")
@tour_page
def share_delete(tour_id, user_id):
    api().send("DELETE", f"/tours/{tour_id}/shares/{user_id}")
    return _to_sharing(tour_id)


@blueprint.post("/<uuid:tour_id>/leave")
@tour_page
def share_leave(tour_id):
    """Someone a tour is shared with removes it from their own list."""
    client = api()
    client.send("DELETE", f"/tours/{tour_id}/shares/{client.data['user']['id']}")
    return redirect(url_for("protocols.tour_list"))


@blueprint.post("/<uuid:tour_id>/links")
@tour_page
def link_create(tour_id):
    expires = forms.text("expires")
    body = {
        # The link stays valid until the end of the chosen day.
        "expires_at": f"{expires}T23:59:59Z" if expires else None,
        "hide_exact_start": forms.checked("hide_exact_start"),
        "strip_photo_gps": forms.checked("strip_photo_gps"),
        "show_health_data": forms.checked("show_health_data"),
    }
    api().send("POST", f"/tours/{tour_id}/public-link", body)
    return _to_sharing(tour_id)


@blueprint.post("/<uuid:tour_id>/links/<uuid:link_id>/revoke")
@tour_page
def link_revoke(tour_id, link_id):
    api().send("DELETE", f"/tours/{tour_id}/public-link/{link_id}")
    return _to_sharing(tour_id)


# --- Contacts (tour partners) ---


@blueprint.route("/contacts", methods=["GET", "POST"])
@tour_page
def contacts():
    client = api()
    if request.method == "POST":
        body = {"display_name": forms.text("display_name") or ""}
        email = forms.text("email")
        if email:
            found = _lookup_user(email)
            if found is None:
                flash(t("error.unknown_user"), "error")
                return redirect(url_for("protocols.contacts"))
            body["linked_user_id"] = found["id"]
        client.send("POST", "/contacts", body)
        flash(t("common.saved"), "success")
        return redirect(url_for("protocols.contacts"))
    return render_template("protocols/contacts.html", contacts=client.get("/contacts"))


@blueprint.post("/contacts/<uuid:contact_id>/delete")
@tour_page
def contact_delete(contact_id):
    api().send("DELETE", f"/contacts/{contact_id}")
    return redirect(url_for("protocols.contacts"))
