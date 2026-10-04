"""Planned routes: list and planner. Line and key figures always come from the API."""

import json

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from hiker_web import error_text, forms
from hiker_web.api import ApiError, api
from hiker_web.maps import map_config
from hiker_web.security import module_required
from hiker_web.texts_de import t

blueprint = Blueprint("planning", __name__, url_prefix="/routes")
route_page = module_required("planning")

OSM_ATTRIBUTION = "© OpenStreetMap-Mitwirkende"
DEFAULT_DIFFICULTY = 3
PACE_PRESETS = ("dav", "sac", "pro")
DEFAULT_PACE = {
    "preset": "dav",
    "name": None,
    "ascent_m_per_h": 300,
    "descent_m_per_h": 500,
    "distance_km_per_h": 4,
}


@blueprint.get("/")
@route_page
def route_list():
    query = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    routes = api().pages("/planning/routes", q=query, tag=tag)
    return render_template("planning/list.html", routes=routes, query=query, tag=tag)


def _waypoints_from_form() -> list[dict]:
    """The waypoints the planner collected, as JSON in a hidden field."""
    try:
        waypoints = json.loads(request.form.get("waypoints") or "[]")
    except ValueError as error:
        raise forms.FormError("waypoints") from error
    if not isinstance(waypoints, list) or not all(isinstance(point, dict) for point in waypoints):
        raise forms.FormError("waypoints")
    return [
        {
            "lat": point.get("lat"),
            "lon": point.get("lon"),
            "name": point.get("name") or None,
            "direct": bool(point.get("direct")),
        }
        for point in waypoints
    ]


def _tags_from_form() -> list[str]:
    return [tag.strip() for tag in (request.form.get("tags") or "").split(",") if tag.strip()]


def _pace_from_form() -> dict:
    """The pace for the walking time: a built-in one, own values, or a saved one."""
    preset = request.form.get("pace_preset") or "dav"
    if preset in PACE_PRESETS:
        return {"preset": preset}
    values = {
        # A saved pace is sent with its values; the route keeps them and its name.
        "name": forms.text("pace_name"),
        "ascent_m_per_h": forms.number("pace_ascent"),
        "descent_m_per_h": forms.number("pace_descent"),
        "distance_km_per_h": forms.number("pace_distance"),
    }
    return {"preset": "custom"} | {key: value for key, value in values.items() if value is not None}


def _route_from_form() -> dict:
    return {
        "title": forms.text("title") or "",
        "description": forms.text("description"),
        "tags": _tags_from_form(),
        # The page sends the moment in UTC; the browser knows the walker's time zone.
        "start_time": forms.text("start_time"),
        "profile": "direct" if request.form.get("profile") == "direct" else "hiking",
        "max_difficulty": forms.whole("max_difficulty") or DEFAULT_DIFFICULTY,
        "via_ferrata": forms.checked("via_ferrata"),
        "pace": _pace_from_form(),
        "waypoints": _waypoints_from_form(),
    }


def _view_from_query() -> dict | None:
    try:
        lat, lon = float(request.args["lat"]), float(request.args["lon"])
        zoom = float(request.args.get("zoom", 12))
    except (KeyError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= zoom <= 20):
        return None
    return {"center": [lon, lat], "zoom": zoom}


def _planner(route: dict, is_new: bool, status: int = 200):
    info = api().get("/planning/info")
    route.setdefault("pace", DEFAULT_PACE)
    plan_data = {
        **map_config(OSM_ATTRIBUTION),
        "previewUrl": url_for("planning.preview"),
        "pacesUrl": url_for("planning.pace_create"),
        "routingAvailable": info["routing_available"],
        "maxWaypoints": info["max_waypoints"],
        # Coming from the map mode: start where the map was looked at.
        "view": _view_from_query(),
        "route": {
            key: route.get(key)
            for key in (
                "waypoints",
                "series",
                "sun",
                "start_time",
                "distance_m",
                "ascent_m",
                "descent_m",
                "duration_s",
            )
        },
        "texts": {
            key: t(f"plan.js.{key}")
            for key in (
                "remove",
                "name",
                "direct",
                "start",
                "computing",
                "no_route",
                "routing_unavailable",
                "failed",
                "too_many",
                "distance",
                "elevation",
                "slope",
                "time",
                "walked",
                "difficulty",
                "duration_note",
                "sunrise",
                "sunset",
                "end",
                "summit",
                "sun_at_summit",
                "daylight_left",
                "after_sunset",
                "starts_in_dark",
                "ends_in_dark",
                "pace_name_missing",
                "pace_failed",
            )
        },
    }
    page = render_template(
        "planning/plan.html",
        route=route,
        is_new=is_new,
        info=info,
        paces=api().get("/planning/paces"),
        plan_data=plan_data,
    )
    return page, status


def _save(method: str, path: str, route_id: str | None):
    submitted = {
        **request.form.to_dict(),
        "id": route_id,
        "via_ferrata": forms.checked("via_ferrata"),
        "tags": _tags_from_form(),
        "start_time": forms.text("start_time"),
    }
    try:
        body = _route_from_form()
        submitted["waypoints"] = body["waypoints"]
        submitted["pace"] = DEFAULT_PACE | body["pace"]
        if route_id is not None:
            body["version"] = forms.whole("version")
        route = api().send(method, path, body)
    except forms.FormError:
        flash(t("error.validation"), "error")
        return _planner(submitted | {"waypoints": []}, route_id is None, 422)
    except ApiError as error:
        if error.status in (401, 404):
            raise
        flash(error_text(error), "error")
        return _planner(submitted, route_id is None, error.status if error.status == 409 else 422)
    flash(t("common.saved"), "success")
    return redirect(url_for("planning.route_plan", route_id=route["id"]))


@blueprint.route("/new", methods=["GET", "POST"])
@route_page
def route_new():
    if request.method == "POST":
        return _save("POST", "/planning/routes", None)
    return _planner({"waypoints": [], "max_difficulty": DEFAULT_DIFFICULTY}, True)


@blueprint.route("/<uuid:route_id>", methods=["GET", "POST"])
@route_page
def route_plan(route_id):
    if request.method == "POST":
        return _save("PUT", f"/planning/routes/{route_id}", str(route_id))
    return _planner(api().get(f"/planning/routes/{route_id}"), False)


@blueprint.post("/preview")
@route_page
def preview():
    """Line and key figures for the waypoints on the map; the planner asks after every change."""
    try:
        return jsonify(api().send("POST", "/planning/preview", request.get_json(silent=True) or {}))
    except ApiError as error:
        if error.status == 401:
            raise
        return jsonify({"error": error.code, "message": error_text(error)}), error.status


@blueprint.post("/paces")
@route_page
def pace_create():
    """Save the walker's own pace under a name; the planner sends it as JSON."""
    try:
        pace = api().send("POST", "/planning/paces", request.get_json(silent=True) or {})
    except ApiError as error:
        if error.status == 401:
            raise
        return jsonify({"error": error.code, "message": error_text(error)}), error.status
    return jsonify(pace), 201


@blueprint.post("/paces/<uuid:pace_id>/delete")
@route_page
def pace_delete(pace_id):
    try:
        api().send("DELETE", f"/planning/paces/{pace_id}")
    except ApiError as error:
        if error.status == 401:
            raise
        return jsonify({"error": error.code, "message": error_text(error)}), error.status
    return "", 204


@blueprint.post("/<uuid:route_id>/delete")
@route_page
def route_delete(route_id):
    api().send("DELETE", f"/planning/routes/{route_id}")
    flash(t("common.deleted"), "success")
    return redirect(url_for("planning.route_list"))


@blueprint.get("/<uuid:route_id>/gpx")
@route_page
def route_gpx(route_id):
    return forms.download(f"/planning/routes/{route_id}/gpx", f"route-{route_id}.gpx")
