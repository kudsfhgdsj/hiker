"""The page behind a public link: no login, not to be indexed, no internal ids."""

import re

from flask import Blueprint, abort, jsonify, render_template, request, url_for

from hiker_web import forms
from hiker_web.api import ApiError, api
from hiker_web.views.protocols import map_data

blueprint = Blueprint("public", __name__, url_prefix="/p")

_TOKEN = re.compile(r"[0-9a-fA-F-]{32,36}")


def _get(token: str, suffix: str = ""):
    if not _TOKEN.fullmatch(token):
        abort(404)
    try:
        return api().request("GET", f"/public/tours/{token}{suffix}", auth=False).json()
    except ApiError as error:
        if error.status in (404, 422):
            abort(404)
        raise


@blueprint.after_request
def _private(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@blueprint.get("/<token>")
def tour(token):
    data = _get(token)

    def urls(kind, photo=None, size=None):
        if kind == "track":
            return url_for("public.track", token=token)
        return url_for("public.photo", token=token, index=photo["index"], size=size)

    waypoints = data["waypoints"]
    return render_template(
        "public/tour.html",
        tour=data,
        token=token,
        map_data=map_data(data, data["photos"], waypoints, urls),
    )


@blueprint.get("/<token>/track.json")
def track(token):
    return jsonify(_get(token, "/track"))


@blueprint.get("/<token>/photos/<int:index>")
def photo(token, index):
    if not _TOKEN.fullmatch(token):
        abort(404)
    size = "thumb" if request.args.get("size") == "thumb" else "full"
    upstream = api().request(
        "GET", f"/public/tours/{token}/photos/{index}", auth=False, params={"size": size}
    )
    return forms.image_response(upstream)
