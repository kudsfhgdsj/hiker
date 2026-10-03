import re

from flask import Blueprint, flash, redirect, render_template, request, url_for

from hiker_web import error_text, forms
from hiker_web.api import ApiError, api
from hiker_web.security import module_required
from hiker_web.texts_de import t

blueprint = Blueprint("nutrition", __name__, url_prefix="/food")
food_page = module_required("nutrition")

NUTRIENTS = ("protein_g", "carbs_g", "fat_g", "sugar_g", "salt_g")
PRODUCT_FIELDS = ("name", "brand", "barcode", "kcal_per_100g", *NUTRIENTS, "serving_size_g")


def _food_from_form() -> dict:
    return {
        "name": forms.text("name") or "",
        "brand": forms.text("brand"),
        "barcode": forms.text("barcode"),
        "kcal_per_100g": forms.number("kcal_per_100g"),
        **{name: forms.number(name) for name in NUTRIENTS},
        "serving_size_g": forms.number("serving_size_g"),
    }


@blueprint.get("/")
@food_page
def food_list():
    query = request.args.get("q", "").strip()
    with_catalog = request.args.get("catalog") == "1"
    path = "/nutrition/search" if with_catalog else "/nutrition/foods"
    return render_template(
        "nutrition/list.html",
        foods=api().pages(path, q=query),
        query=query,
        with_catalog=with_catalog,
    )


def _form_page(food: dict, is_new: bool, status: int = 200):
    return render_template("nutrition/form.html", food=food, is_new=is_new), status


def _save(method: str, path: str, food_id: str | None):
    submitted = {**request.form.to_dict(), "id": food_id}
    try:
        api().send(method, path, _food_from_form())
    except forms.FormError:
        flash(t("error.validation"), "error")
        return _form_page(submitted, food_id is None, 422)
    except ApiError as error:
        if error.status in (401, 404):
            raise
        flash(error_text(error), "error")
        return _form_page(submitted, food_id is None, 422)
    flash(t("common.saved"), "success")
    return redirect(url_for("nutrition.food_list"))


@blueprint.route("/new", methods=["GET", "POST"])
@food_page
def food_new():
    if request.method == "POST":
        return _save("POST", "/nutrition/foods", None)
    return _form_page({"barcode": request.args.get("barcode", "")}, True)


@blueprint.route("/<uuid:food_id>", methods=["GET", "POST"])
@food_page
def food_edit(food_id):
    if request.method == "POST":
        return _save("PUT", f"/nutrition/foods/{food_id}", str(food_id))
    food = api().get(f"/nutrition/foods/{food_id}")
    if food["visibility"] != "private":
        # Catalog entries are shared: they can be copied, not changed.
        return render_template("nutrition/detail.html", food=food)
    return _form_page(food, False)


@blueprint.post("/<uuid:food_id>/delete")
@food_page
def food_delete(food_id):
    api().send("DELETE", f"/nutrition/foods/{food_id}")
    flash(t("common.deleted"), "success")
    return redirect(url_for("nutrition.food_list"))


@blueprint.post("/<uuid:food_id>/propose")
@food_page
def food_propose(food_id):
    api().send("POST", f"/nutrition/foods/{food_id}/propose-to-catalog")
    flash(t("food.proposed"), "success")
    return redirect(url_for("nutrition.food_edit", food_id=food_id))


@blueprint.post("/<uuid:food_id>/copy")
@food_page
def food_copy(food_id):
    """Take a catalog entry over as an own food: a copy, not a reference."""
    client = api()
    entry = client.get(f"/nutrition/foods/{food_id}")
    copy = {name: entry.get(name) for name in PRODUCT_FIELDS}
    created = client.send("POST", "/nutrition/foods", {**copy, "catalog_id": entry["id"]})
    flash(t("food.copied"), "success")
    return redirect(url_for("nutrition.food_edit", food_id=created["id"]))


@blueprint.get("/barcode")
@food_page
def barcode():
    code = re.sub(r"[\s-]", "", request.args.get("ean", ""))
    if not re.fullmatch(r"\d{8}|\d{12,14}", code):
        flash(t("food.barcode_invalid"), "error")
        return redirect(url_for("nutrition.food_list"))
    try:
        food = api().get(f"/nutrition/barcode/{code}")
    except ApiError as error:
        if error.status != 404:
            raise
        flash(t("error.product_not_found"), "error")
        return redirect(url_for("nutrition.food_new", barcode=code))
    return redirect(url_for("nutrition.food_edit", food_id=food["id"]))


@blueprint.get("/catalog")
@food_page
def catalog():
    client = api()
    is_admin = client.data["user"]["role"] == "admin"
    return render_template(
        "nutrition/catalog.html",
        mine=client.pages("/nutrition/catalog/mine"),
        pending=client.pages("/nutrition/catalog/pending") if is_admin else [],
        is_admin=is_admin,
    )


@blueprint.post("/catalog/<uuid:catalog_id>/<any(catalog, catalog_rejected):decision>")
@food_page
def catalog_decide(catalog_id, decision):
    api().send("PATCH", f"/nutrition/catalog/{catalog_id}", {"visibility": decision})
    return redirect(url_for("nutrition.catalog"))
