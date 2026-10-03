from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for

from hiker_web import error_text
from hiker_web.api import ApiError, api
from hiker_web.security import login_required
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


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        payload = {
            "email": request.form.get("email", ""),
            "password": request.form.get("password", ""),
        }
        try:
            _sign_in("/auth/login", payload)
            return redirect(_safe_next(request.args.get("next")))
        except ApiError as error:
            flash(error_text(error), "error")
    return render_template("auth/login.html", register=False)


@blueprint.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        payload = {
            "email": request.form.get("email", ""),
            "display_name": request.form.get("display_name", ""),
            "password": request.form.get("password", ""),
        }
        try:
            _sign_in("/auth/register", payload)
            return redirect(url_for("home"))
        except ApiError as error:
            flash(error_text(error), "error")
    return render_template("auth/login.html", register=True)


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
