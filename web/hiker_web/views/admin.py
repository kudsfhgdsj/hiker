"""Administration of users; the API decides who is an administrator."""

from flask import Blueprint, flash, redirect, render_template, url_for

from hiker_web.api import api
from hiker_web.security import login_required
from hiker_web.texts_de import t

blueprint = Blueprint("admin", __name__, url_prefix="/admin")


@blueprint.get("/users")
@login_required
def users():
    return render_template("admin/users.html", users=api().get("/admin/users"))


@blueprint.post("/users/<uuid:user_id>/delete")
@login_required
def user_delete(user_id):
    api().send("DELETE", f"/admin/users/{user_id}")
    flash(t("admin.user_deleted"), "success")
    return redirect(url_for("admin.users"))


@blueprint.post("/users/<uuid:user_id>/reset-password")
@login_required
def user_reset_password(user_id):
    client = api()
    result = client.send("POST", f"/admin/users/{user_id}/reset-password")
    # The temporary password is shown once, on this page, and stored nowhere.
    return render_template(
        "admin/users.html",
        users=client.get("/admin/users"),
        reset_user_id=str(user_id),
        temporary_password=result["temporary_password"],
    )


@blueprint.post("/users/<uuid:user_id>/reset-mfa")
@login_required
def user_reset_mfa(user_id):
    api().send("POST", f"/admin/users/{user_id}/reset-mfa")
    flash(t("admin.mfa_reset"), "success")
    return redirect(url_for("admin.users"))
