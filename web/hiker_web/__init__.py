"""hiker web frontend: server-rendered pages on top of the hiker REST API."""

from urllib.parse import urlsplit

import httpx2
from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from hiker_web import formatting
from hiker_web.api import ApiError, api
from hiker_web.config import load_config
from hiker_web.security import check_csrf, csrf_token, install_log_redaction, pending_step
from hiker_web.sessions import SessionStore
from hiker_web.texts_de import TEXTS, label, t

__version__ = "0.1.0"

# Blueprint, and the API module that must be enabled for its pages.
NAVIGATION = (
    ("protocols", "protocols.tour_list", "nav.tours"),
    ("gear", "gear.item_list", "nav.gear"),
    ("nutrition", "nutrition.food_list", "nav.food"),
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

    from hiker_web.views import admin, auth, gear, nutrition, protocols, public

    app.register_blueprint(auth.blueprint)
    app.register_blueprint(admin.blueprint)
    app.register_blueprint(gear.blueprint)
    app.register_blueprint(nutrition.blueprint)
    app.register_blueprint(protocols.blueprint)
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
