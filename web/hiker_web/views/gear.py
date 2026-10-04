from flask import Blueprint, flash, redirect, render_template, request, url_for

from hiker_web import error_text, forms
from hiker_web.api import ApiError, api
from hiker_web.security import module_required
from hiker_web.texts_de import t

blueprint = Blueprint("gear", __name__, url_prefix="/gear")
gear_page = module_required("gear")

GROUPINGS = ("type", "tag", "status", "brand")


def _filters() -> dict:
    return {
        "q": request.args.get("q", "").strip(),
        "status": request.args.get("status", ""),
        "type_id": request.args.get("type_id", ""),
        "tag_id": request.args.getlist("tag_id"),
    }


def _item_from_form() -> dict:
    currency = forms.text("currency")
    return {
        "name": forms.text("name") or "",
        "brand": forms.text("brand"),
        "type_id": forms.text("type_id"),
        "weight_g": forms.whole("weight_g"),
        "purchase_date": forms.text("purchase_date"),
        "purchase_price": forms.number("purchase_price"),
        "currency": currency.upper() if currency else None,
        "description": forms.text("description"),
        "notes": forms.text("notes"),
        "website_url": forms.text("website_url"),
        "status": request.form.get("status", "active"),
        "serial_number": forms.text("serial_number"),
        "size": forms.text("size"),
        "color": forms.text("color"),
        "tag_ids": request.form.getlist("tag_ids"),
    }


@blueprint.get("/")
@gear_page
def item_list():
    client = api()
    filters = _filters()
    types = client.get("/gear/types")
    return render_template(
        "gear/list.html",
        items=client.pages("/gear/items", **filters),
        types=types,
        type_names={entry["id"]: entry["name"] for entry in types},
        tags=client.get("/gear/tags"),
        filters=filters,
    )


def _form_page(item: dict, is_new: bool, status: int = 200):
    client = api()
    page = render_template(
        "gear/form.html",
        item=item,
        is_new=is_new,
        types=client.get("/gear/types"),
        tags=client.get("/gear/tags"),
    )
    return page, status


def _save(method: str, path: str, item_id: str | None):
    """Send the form to the API; show it again with the message if it is rejected."""
    submitted = {
        **request.form.to_dict(),
        "tag_ids": request.form.getlist("tag_ids"),
        "id": item_id,
    }
    try:
        api().send(method, path, _item_from_form())
    except forms.FormError:
        flash(t("error.validation"), "error")
        return _form_page(submitted, item_id is None, 422)
    except ApiError as error:
        if error.status in (401, 404):
            raise
        flash(error_text(error), "error")
        return _form_page(submitted, item_id is None, 422)
    flash(t("common.saved"), "success")
    return redirect(url_for("gear.item_list"))


@blueprint.route("/new", methods=["GET", "POST"])
@gear_page
def item_new():
    if request.method == "POST":
        return _save("POST", "/gear/items", None)
    return _form_page({"status": "active", "tag_ids": []}, True)


@blueprint.route("/<uuid:item_id>", methods=["GET", "POST"])
@gear_page
def item_edit(item_id):
    if request.method == "POST":
        return _save("PUT", f"/gear/items/{item_id}", str(item_id))
    return _form_page(api().get(f"/gear/items/{item_id}"), False)


@blueprint.post("/<uuid:item_id>/delete")
@gear_page
def item_delete(item_id):
    api().send("DELETE", f"/gear/items/{item_id}")
    flash(t("common.deleted"), "success")
    return redirect(url_for("gear.item_list"))


@blueprint.get("/<uuid:item_id>/image")
@gear_page
def item_image(item_id):
    return forms.proxy_image(f"/gear/items/{item_id}/image")


@blueprint.post("/<uuid:item_id>/image")
@gear_page
def item_image_upload(item_id):
    files = forms.upload()
    if files:
        api().request("POST", f"/gear/items/{item_id}/image", files=files)
        flash(t("common.saved"), "success")
    return redirect(url_for("gear.item_edit", item_id=item_id))


@blueprint.post("/<uuid:item_id>/image/delete")
@gear_page
def item_image_delete(item_id):
    api().send("DELETE", f"/gear/items/{item_id}/image")
    return redirect(url_for("gear.item_edit", item_id=item_id))


@blueprint.post("/<uuid:item_id>/propose")
@gear_page
def item_propose(item_id):
    api().send("POST", f"/gear/items/{item_id}/propose-to-catalog")
    flash(t("gear.proposed"), "success")
    return redirect(url_for("gear.item_edit", item_id=item_id))


@blueprint.get("/summary")
@gear_page
def summary():
    group_by = request.args.get("group_by", "")
    filters = _filters()
    data = api().get(
        "/gear/summary", group_by=group_by if group_by in GROUPINGS else None, **filters
    )
    return render_template(
        "gear/summary.html", summary=data, group_by=group_by, groupings=GROUPINGS, filters=filters
    )


@blueprint.route("/manage", methods=["GET", "POST"])
@gear_page
def manage():
    client = api()
    if request.method == "POST":
        kind = request.form.get("kind")
        name = forms.text("name") or ""
        if kind == "tag":
            client.send("POST", "/gear/tags", {"name": name, "color": forms.text("color")})
        else:
            client.send("POST", "/gear/types", {"name": name})
        flash(t("common.saved"), "success")
        return redirect(url_for("gear.manage"))
    return render_template(
        "gear/manage.html", types=client.get("/gear/types"), tags=client.get("/gear/tags")
    )


@blueprint.post("/manage/<kind>/<uuid:record_id>/delete")
@gear_page
def manage_delete(kind, record_id):
    path = "/gear/tags" if kind == "tag" else "/gear/types"
    api().send("DELETE", f"{path}/{record_id}")
    flash(t("common.deleted"), "success")
    return redirect(url_for("gear.manage"))


@blueprint.get("/catalog")
@gear_page
def catalog():
    client = api()
    is_admin = client.data["user"]["role"] == "admin"
    return render_template(
        "gear/catalog.html",
        mine=client.pages("/gear/catalog/mine"),
        pending=client.pages("/gear/catalog/pending") if is_admin else [],
        is_admin=is_admin,
    )


@blueprint.post("/catalog/<uuid:catalog_id>/<any(approved, rejected):decision>")
@gear_page
def catalog_decide(catalog_id, decision):
    api().send("PATCH", f"/gear/catalog/{catalog_id}", {"status": decision})
    return redirect(url_for("gear.catalog"))


# --- Packing lists ---


def _list_from_form() -> dict:
    removed = set(request.form.getlist("entry_remove"))
    ids = request.form.getlist("entry_item")
    quantities = request.form.getlist("entry_quantity")
    if len(ids) != len(quantities):
        raise forms.FormError("entries")
    entries = [
        {"gear_item_id": item_id, "quantity": forms.to_number(quantity, "quantity", int) or 1}
        for item_id, quantity in zip(ids, quantities, strict=True)
        if item_id not in removed
    ]
    present = {entry["gear_item_id"] for entry in entries}
    for item_id in request.form.getlist("entry_new"):
        if item_id and item_id not in present:
            entries.append(
                {"gear_item_id": item_id, "quantity": forms.number("entry_new_quantity", int) or 1}
            )
            present.add(item_id)
    return {
        "name": forms.text("name") or "",
        "description": forms.text("description"),
        "entries": entries,
    }


@blueprint.get("/lists")
@gear_page
def packing_lists():
    return render_template("gear/lists.html", lists=api().get("/gear/lists"))


def _list_page(gear_list: dict, is_new: bool, status: int = 200):
    items = api().pages("/gear/items")
    page = render_template(
        "gear/list_form.html",
        gear_list=gear_list,
        is_new=is_new,
        items=items,
        by_id={item["id"]: item for item in items},
    )
    return page, status


def _save_list(method: str, path: str, list_id: str | None):
    try:
        body = _list_from_form()
        saved = api().send(method, path, body)
    except forms.FormError:
        flash(t("error.validation"), "error")
        return redirect(request.url)
    except ApiError as error:
        if error.status in (401, 404):
            raise
        flash(error_text(error), "error")
        return _list_page({**body, "id": list_id}, list_id is None, 422)
    flash(t("common.saved"), "success")
    if "stay" in request.form:
        return redirect(url_for("gear.packing_list_edit", list_id=saved["id"]))
    return redirect(url_for("gear.packing_lists"))


@blueprint.route("/lists/new", methods=["GET", "POST"])
@gear_page
def packing_list_new():
    if request.method == "POST":
        return _save_list("POST", "/gear/lists", None)
    return _list_page({"entries": []}, True)


@blueprint.route("/lists/<uuid:list_id>", methods=["GET", "POST"])
@gear_page
def packing_list_edit(list_id):
    if request.method == "POST":
        return _save_list("PUT", f"/gear/lists/{list_id}", str(list_id))
    return _list_page(api().get(f"/gear/lists/{list_id}"), False)


@blueprint.post("/lists/<uuid:list_id>/delete")
@gear_page
def packing_list_delete(list_id):
    api().send("DELETE", f"/gear/lists/{list_id}")
    flash(t("common.deleted"), "success")
    return redirect(url_for("gear.packing_lists"))
