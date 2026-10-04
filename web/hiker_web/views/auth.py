from urllib.parse import urlsplit

import segno
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup

from hiker_web import error_text
from hiker_web.api import ApiError, api
from hiker_web.security import login_required, signed_in
from hiker_web.texts_de import t

blueprint = Blueprint("auth", __name__)

PROFILE_FIELDS = ("weight_kg", "birth_year", "max_heart_rate", "resting_heart_rate")
SEX_VALUES = ("female", "male", "trans", "undisclosed")


def _safe_next(target: str | None) -> str:
    """Only paths of this site are followed after the login."""
    if target and target.startswith("/") and not urlsplit(target).netloc and "//" not in target[:2]:
        return target
    return url_for("home")


def _sign_in(path: str, payload: dict):
    client = api()
    auth = client.request("POST", path, auth=False, json=payload).json()
    token = {"Authorization": f"Bearer {auth['access_token']}"}
    modules = client.request("GET", "/modules", auth=False, headers=token).json()
    client.sign_in(auth, [module["name"] for module in modules])


def _sso() -> dict:
    """Whether the server offers single sign-on; the login page works without the answer."""
    try:
        return api().request("GET", "/auth/oidc", auth=False).json()
    except ApiError:
        return {"enabled": False, "name": ""}


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        payload = {
            "email": request.form.get("email", ""),
            "password": request.form.get("password", ""),
            "code": (request.form.get("code") or "").strip() or None,
        }
        try:
            _sign_in("/auth/login", payload)
            return redirect(_safe_next(request.args.get("next")))
        except ApiError as error:
            flash(error_text(error), "error")
    return render_template("auth/login.html", register=False, sso=_sso())


@blueprint.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        payload = {
            "email": request.form.get("email", ""),
            "display_name": request.form.get("display_name", ""),
            "password": request.form.get("password", ""),
        }
        if payload["password"] != request.form.get("password_repeat", ""):
            flash(t("auth.passwords_differ"), "error")
        else:
            try:
                _sign_in("/auth/register", payload)
                return redirect(url_for("home"))
            except ApiError as error:
                flash(error_text(error), "error")
    return render_template("auth/login.html", register=True, sso=_sso())


# --- Single sign-on ---


@blueprint.get("/login/sso")
def sso_start():
    try:
        started = api().request("POST", "/auth/oidc/start", auth=False).json()
    except ApiError as error:
        flash(error_text(error), "error")
        return redirect(url_for("auth.login"))
    # The answer of the provider must come back to the browser that started.
    session["sso_state"] = started["state"]
    return redirect(started["authorization_url"])


@blueprint.get("/login/sso/callback")
def sso_callback():
    expected = session.pop("sso_state", None)
    state, code = request.args.get("state", ""), request.args.get("code", "")
    if request.args.get("error") or not code or not expected or state != expected:
        flash(t("error.oidc_failed"), "error")
        return redirect(url_for("auth.login"))
    try:
        _sign_in("/auth/oidc/callback", {"state": state, "code": code})
    except ApiError as error:
        flash(error_text(error), "error")
        return redirect(url_for("auth.login"))
    return redirect(url_for("home"))


# --- Password and second factor ---


@blueprint.route("/password", methods=["GET", "POST"])
@signed_in
def password():
    client = api()
    if request.method == "POST":
        new = request.form.get("new_password", "")
        if new != request.form.get("password_repeat", ""):
            flash(t("auth.passwords_differ"), "error")
        else:
            try:
                body = {
                    "current_password": request.form.get("current_password", ""),
                    "new_password": new,
                }
                changed = client.send("POST", "/auth/password", body)
                client.sign_in(changed, client.data["modules"])
                flash(t("auth.password_changed"), "success")
                return redirect(url_for("home"))
            except ApiError as error:
                if error.status == 401:
                    raise
                flash(error_text(error), "error")
    return render_template("auth/password.html", forced=client.data["password_change_required"])


@blueprint.route("/mfa/setup", methods=["GET", "POST"])
@signed_in
def mfa_setup():
    client = api()
    if client.data.get("password_change_required"):
        return redirect(url_for("auth.password"))
    if request.method == "POST":
        try:
            enabled = client.send("POST", "/auth/mfa/enable", {"code": request.form.get("code")})
        except ApiError as error:
            if error.status == 401:
                raise
            flash(error_text(error), "error")
            return redirect(url_for("auth.mfa_setup"))
        client.sign_in(enabled, client.data["modules"])
        # Shown exactly once; they are not stored anywhere in the web frontend.
        return render_template("auth/recovery_codes.html", codes=enabled["recovery_codes"])
    pending = client.data.get("mfa_pending")
    if pending is None or "new" in request.args:
        pending = client.send("POST", "/auth/mfa/setup")
        client.remember(mfa_pending=pending)
    qr = segno.make(pending["otpauth_uri"], error="m").svg_inline(scale=5, border=2)
    return render_template(
        "auth/mfa_setup.html",
        secret=pending["secret"],
        qr=Markup(qr),
        forced=client.data["mfa_setup_required"],
    )


@blueprint.post("/mfa/recovery-codes")
@login_required
def mfa_recovery_codes():
    try:
        body = {"code": request.form.get("code")}
        codes = api().send("POST", "/auth/mfa/recovery-codes", body)["recovery_codes"]
    except ApiError as error:
        if error.status == 401:
            raise
        flash(error_text(error), "error")
        return redirect(url_for("auth.profile"))
    return render_template("auth/recovery_codes.html", codes=codes)


@blueprint.post("/logout")
def logout():
    client = api()
    data = client.data
    if data:
        try:
            client.request(
                "POST", "/auth/logout", auth=False, json={"refresh_token": data["refresh"]}
            )
        except ApiError:
            pass  # The local sign-out happens anyway.
    client.sign_out()
    return redirect(url_for("auth.login"))


def _number(text: str, convert):
    text = (text or "").strip().replace(",", ".")
    return convert(float(text)) if text else None


@blueprint.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    client = api()
    if request.method == "POST":
        try:
            payload = {
                "weight_kg": _number(request.form.get("weight_kg"), float),
                "birth_year": _number(request.form.get("birth_year"), int),
                "sex": request.form.get("sex") or None,
                "max_heart_rate": _number(request.form.get("max_heart_rate"), int),
                "resting_heart_rate": _number(request.form.get("resting_heart_rate"), int),
            }
            client.send("PUT", "/me/profile", payload)
            flash(t("common.saved"), "success")
            return redirect(url_for("auth.profile"))
        except ValueError:
            flash(t("error.validation"), "error")
        except ApiError as error:
            if error.status == 401:
                raise
            flash(error_text(error), "error")
    return render_template(
        "auth/profile.html", profile=client.get("/me/profile"), sex_values=SEX_VALUES
    )
