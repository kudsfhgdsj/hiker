"""hiker web frontend: server-rendered pages on top of the hiker REST API."""

import re
from urllib.parse import urlsplit

import httpx2
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from hiker_web import formatting
from hiker_web.api import ApiError, api
from hiker_web.config import load_config
from hiker_web.maps import map_config
from hiker_web.security import (
    check_csrf,
    csrf_token,
    install_log_redaction,
    module_required,
    pending_step,
)
from hiker_web.sessions import SessionStore
from hiker_web.texts_de import TEXTS, label, t

__version__ = "0.1.0"

# Blueprint, and the API module that must be enabled for its pages.
NAVIGATION = (
    ("protocols", "protocols.tour_list", "nav.tours"),
    ("planning", "planning.route_list", "nav.planning"),
    ("maps", "map_page", "nav.map"),
    ("gear", "gear.item_list", "nav.gear"),
    ("nutrition", "nutrition.food_list", "nav.food"),
)


OSM_ATTRIBUTION = "© OpenStreetMap-Mitwirkende"
# The SAC hiking scale as OpenStreetMap names it, with its level T1 to T6.
SAC_SCALE = (
    (1, "hiking"),
    (2, "mountain_hiking"),
    (3, "demanding_mountain_hiking"),
    (4, "alpine_hiking"),
    (5, "demanding_alpine_hiking"),
    (6, "difficult_alpine_hiking"),
)


def error_text(error: ApiError) -> str:
    """German text for an error of the API; the API only sends codes."""
    reason = error.body.get("reason")
    for key in (f"error.{error.code}.{reason}", f"error.{error.code}"):
        if key in TEXTS:
            return t(key)
    by_status = {
        403: "error.forbidden",
        404: "error.not_found",
        409: "error.conflict",
        413: "error.too_large",
        422: "error.validation",
    }
    return t(by_status.get(error.status, "error.unknown"))


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(load_config())
    app.config.update(config or {})
    if len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("WEB_SECRET_KEY must be set and at least 32 characters long")

    # Behind the reverse proxy: take scheme and client address from its headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.extensions["session_store"] = SessionStore(
        app.config["SESSION_DIR"], max_age_seconds=app.config["SESSION_DAYS"] * 86400
    )
    app.extensions["api_client"] = httpx2.Client(
        base_url=app.config["API_BASE_URL"],
        timeout=30,
        transport=app.config.get("API_TRANSPORT"),
        headers={"User-Agent": f"hiker-web/{__version__}"},
    )
    install_log_redaction()
    app.jinja_env.filters.update(formatting.FILTERS)
    # As globals, so that imported macros can use them too.
    app.jinja_env.globals.update(t=t, label=label, csrf_token=csrf_token)
    app.before_request(check_csrf)

    # Scripts and styles only from this server; map tiles from the configured source.
    tiles = urlsplit(app.config["MAP_TILE_URL"])
    tile_origin = f"{tiles.scheme}://{tiles.netloc}" if tiles.netloc else "'self'"
    content_security_policy = "; ".join(
        (
            "default-src 'self'",
            f"img-src 'self' data: blob: {tile_origin}",
            f"connect-src 'self' {tile_origin}",
            "worker-src 'self' blob:",
            "style-src 'self' 'unsafe-inline'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'",
        )
    )

    @app.context_processor
    def _globals():
        data = api().data
        modules = (data or {}).get("modules", [])
        return {
            "t": t,
            "csrf_token": csrf_token,
            "current_user": (data or {}).get("user"),
            "session_ready": bool(data) and pending_step(data) is None,
            "navigation": [
                (endpoint, t(label))
                for module, endpoint, label in NAVIGATION
                if module in modules and endpoint in app.view_functions
            ],
        }

    @app.errorhandler(ApiError)
    def _api_error(error: ApiError):
        if error.status == 401:
            flash(t("error.session_expired"), "error")
            return redirect(url_for("auth.login"))
        if error.status == 404:
            return render_template("error.html", message=t("error.not_found")), 404
        # The API says the sign-in is not complete: go to the page that completes it.
        if error.code == "mfa_setup_required":
            api().remember(mfa_setup_required=True)
            return redirect(url_for("auth.mfa_setup"))
        if error.code == "password_change_required":
            api().remember(password_change_required=True)
            return redirect(url_for("auth.password"))
        # Back to where the user came from, with the reason.
        flash(error_text(error), "error")
        target = request.referrer if request.method != "GET" and request.referrer else None
        if target:
            return redirect(target)
        status = error.status if error.status < 500 else 502
        return render_template("error.html", message=error_text(error)), status

    @app.errorhandler(400)
    def _bad_request(error):
        message = (
            t("error.csrf")
            if getattr(error, "description", "") == "csrf"
            else t("error.validation")
        )
        return render_template("error.html", message=message), 400

    @app.errorhandler(404)
    def _not_found(_error):
        return render_template("error.html", message=t("error.page_404")), 404

    @app.errorhandler(413)
    def _too_large(_error):
        return render_template("error.html", message=t("error.too_large")), 413

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        # Other servers only learn the origin, never the path: the tile server of the map
        # requires a referrer, and the path of a public link contains its token.
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", content_security_policy)
        return response

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/tiles/<int:z>/<int:x>/<int:y>.png")
    def tile(z, x, y):
        """A map tile from the cache of the API. No login: public link pages show a map."""
        upstream = api().request("GET", f"/maps/tiles/{z}/{x}/{y}.png", auth=False)
        response = app.response_class(upstream.content, mimetype="image/png")
        response.headers["Cache-Control"] = upstream.headers.get(
            "cache-control", "public, max-age=86400"
        )
        return response

    # --- The own vector map of the API, passed on like the raster tiles. No login. ---

    def _passed_on(upstream, mimetype: str):
        if upstream.status_code == 204:
            response = app.response_class(status=204)
        else:
            response = app.response_class(upstream.content, mimetype=mimetype)
        response.headers["Cache-Control"] = upstream.headers.get(
            "cache-control", "public, max-age=3600"
        )
        return response

    @app.get("/map/style.json")
    def map_style():
        """The style of the map, with the addresses of this server instead of the API's."""
        style = api().request("GET", "/maps/style.json", auth=False).json()
        root = request.url_root.rstrip("/")
        style["glyphs"] = f"{root}/map/fonts/{{fontstack}}/{{range}}.pbf"
        if "sprite" in style:
            style["sprite"] = f"{root}/map/sprite"

        # Everything the style loads from the API's maps module comes from here instead.
        def own(address: str) -> str:
            if "/api/v1/maps/" not in address:
                return address
            return f"{root}/map/{address.split('/api/v1/maps/', 1)[1]}"

        for source in style.get("sources", {}).values():
            if "tiles" in source:
                source["tiles"] = [own(tile) for tile in source["tiles"]]
            if isinstance(source.get("data"), str):
                source["data"] = own(source["data"])
        radar = style.get("metadata", {}).get("hiker", {}).get("radar")
        if radar:
            for key in ("frames", "rain", "clouds"):
                radar[key] = own(radar[key])
        response = app.json.response(style)
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    @app.get("/map/sprite<any('', '@2x', '@3x'):ratio>.<any(json, png):kind>")
    def map_sprite(ratio, kind):
        """The symbols of the map: one image and the list of their places in it."""
        upstream = api().request("GET", f"/maps/sprite{ratio}.{kind}", auth=False)
        return _passed_on(upstream, "image/png" if kind == "png" else "application/json")

    @app.get("/map/vector/<int:z>/<int:x>/<int:y>.pbf")
    def map_vector_tile(z, x, y):
        upstream = api().request("GET", f"/maps/vector/{z}/{x}/{y}.pbf", auth=False)
        return _passed_on(upstream, "application/x-protobuf")

    def _query(*names: str) -> dict:
        """The query parameters a map layer takes, passed on as they are."""
        return {name: request.args[name] for name in names if name in request.args}

    @app.get("/map/avalanche.geojson")
    def map_avalanche():
        upstream = api().request(
            "GET", "/maps/avalanche.geojson", auth=False, params=_query("date")
        )
        return _passed_on(upstream, "application/geo+json")

    @app.get("/map/search")
    def map_search():
        """Places of the own map by name; searched by the API."""
        try:
            found = (
                api()
                .request(
                    "GET", "/maps/search", auth=False, params=_query("q", "lat", "lon", "limit")
                )
                .json()
            )
        except ApiError as error:
            if error.status != 422:
                raise
            # Too short to search for: no results.
            found = []
        response = app.json.response(found)
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    @app.get("/map/sun")
    def map_sun():
        """Sunrise and sunset at a place; computed by the API."""
        upstream = api().request(
            "GET", "/maps/sun", auth=False, params=_query("lat", "lon", "date", "elevation_m")
        )
        response = app.json.response(upstream.json())
        response.headers["Cache-Control"] = "public, max-age=600"
        return response

    @app.get("/map")
    @module_required("maps")
    def map_page():
        """Map mode: look at the map and look things up, without planning."""
        modules = (api().data or {}).get("modules", [])
        map_data = {
            **map_config(OSM_ATTRIBUTION),
            "sunUrl": url_for("map_sun"),
            "planUrl": url_for("planning.route_new") if "planning" in modules else None,
            "texts": {
                "sunrise": t("plan.js.sunrise"),
                "sunset": t("plan.js.sunset"),
                "sun_loading": t("mapmode.sun_loading"),
                "sun_none": t("mapmode.sun_none"),
                "sun_summit": t("mapmode.sun_summit"),
                "sun_light": t("mapmode.sun_light"),
                "plan_here": t("mapmode.plan_here"),
                "via_ferrata": t("mapmode.via_ferrata"),
                "sac": {scale: t(f"plan.difficulty.{level}") for level, scale in SAC_SCALE},
            },
        }
        return render_template("map.html", map_data=map_data)

    @app.get("/map/radar/frames")
    def map_radar_frames():
        response = app.json.response(api().request("GET", "/maps/radar/frames", auth=False).json())
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    @app.get("/map/radar/<any(rain, clouds):kind>/<int:frame>/<int:z>/<int:x>/<int:y>.png")
    def map_radar_tile(kind, frame, z, x, y):
        upstream = api().request("GET", f"/maps/radar/{kind}/{frame}/{z}/{x}/{y}.png", auth=False)
        return _passed_on(upstream, "image/png")

    @app.get(
        "/map/raster/<any(terrain, satellite, snow, precipitation):layer>/<int:z>/<int:x>/<int:y>"
    )
    def map_layer_tile(layer, z, x, y):
        upstream = api().request(
            "GET", f"/maps/raster/{layer}/{z}/{x}/{y}", auth=False, params=_query("date")
        )
        return _passed_on(upstream, upstream.headers.get("content-type", "image/png"))

    @app.get("/map/contours/<int:z>/<int:x>/<int:y>.pbf")
    def map_contour_tile(z, x, y):
        upstream = api().request("GET", f"/maps/contours/{z}/{x}/{y}.pbf", auth=False)
        return _passed_on(upstream, "application/x-protobuf")

    @app.get("/map/weather/<int:z>/<int:x>/<int:y>.pbf")
    def map_weather_tile(z, x, y):
        upstream = api().request(
            "GET", f"/maps/weather/{z}/{x}/{y}.pbf", auth=False, params=_query("date")
        )
        return _passed_on(upstream, "application/x-protobuf")

    @app.get("/map/slope/<int:z>/<int:x>/<int:y>.png")
    def map_slope_tile(z, x, y):
        upstream = api().request(
            "GET", f"/maps/slope/{z}/{x}/{y}.png", auth=False, params=_query("low", "high")
        )
        return _passed_on(upstream, "image/png")

    @app.get("/map/fonts/<fontstack>/<glyphs>.pbf")
    def map_glyphs(fontstack, glyphs):
        if not re.fullmatch(r"[\w ,-]{1,200}", fontstack) or not re.fullmatch(
            r"\d{1,5}-\d{1,5}", glyphs
        ):
            abort(404)
        upstream = api().request("GET", f"/maps/fonts/{fontstack}/{glyphs}.pbf", auth=False)
        return _passed_on(upstream, "application/x-protobuf")

    from hiker_web.views import admin, auth, gear, nutrition, planning, protocols, public

    app.register_blueprint(auth.blueprint)
    app.register_blueprint(admin.blueprint)
    app.register_blueprint(gear.blueprint)
    app.register_blueprint(nutrition.blueprint)
    app.register_blueprint(protocols.blueprint)
    app.register_blueprint(planning.blueprint)
    app.register_blueprint(public.blueprint)

    @app.get("/")
    def home():
        data = api().data
        if data is None:
            return redirect(url_for("auth.login"))
        if pending_step(data):
            return redirect(url_for(pending_step(data)))
        for module, endpoint, _label in NAVIGATION:
            if module in data.get("modules", []) and endpoint in app.view_functions:
                return redirect(url_for(endpoint))
        return redirect(url_for("auth.profile"))

    return app
