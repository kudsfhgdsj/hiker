"""Planned routes: list and planner. Line and key figures always come from the API."""

import json

from flask import (
    Blueprint,
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

blueprint = Blueprint("planning", __name__, url_prefix="/routes")
route_page = module_required("planning")

OSM_ATTRIBUTION = "© OpenStreetMap-Mitwirkende"
DEFAULT_DIFFICULTY = 3


@blueprint.get("/")
@route_page
def route_list():
    query = request.args.get("q", "").strip()
    return render_template(
        "planning/list.html", routes=api().pages("/planning/routes", q=query), query=query
    )


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


def _route_from_form() -> dict:
    return {
        "title": forms.text("title") or "",
        "description": forms.text("description"),
        "planned_date": forms.text("planned_date"),
        "profile": "direct" if request.form.get("profile") == "direct" else "hiking",
        "max_difficulty": forms.whole("max_difficulty") or DEFAULT_DIFFICULTY,
        "via_ferrata": forms.checked("via_ferrata"),
        "waypoints": _waypoints_from_form(),
    }


def _planner(route: dict, is_new: bool, status: int = 200):
    info = api().get("/planning/info")
    plan_data = {
        "tileUrl": current_app.config["MAP_TILE_URL"],
        "workerUrl": url_for("static", filename="vendor/maplibre-gl/maplibre-gl-csp-worker.js"),
        "attribution": OSM_ATTRIBUTION,
        "previewUrl": url_for("planning.preview"),
        "routingAvailable": info["routing_available"],
        "maxWaypoints": info["max_waypoints"],
        "route": {
            key: route.get(key)
            for key in (
                "waypoints",
                "series",
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
            )
        },
    }
    page = render_template(
        "planning/plan.html", route=route, is_new=is_new, info=info, plan_data=plan_data
    )
    return page, status


def _save(method: str, path: str, route_id: str | None):
    submitted = {
        **request.form.to_dict(),
        "id": route_id,
        "via_ferrata": forms.checked("via_ferrata"),
    }
    try:
        body = _route_from_form()
        submitted["waypoints"] = body["waypoints"]
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
