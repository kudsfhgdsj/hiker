"""Statistics: what all own tours add up to. Everything is computed by the API."""

from datetime import date, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from hiker_web import OSM_ATTRIBUTION, error_text, forms
from hiker_web.api import ApiError, api
from hiker_web.maps import map_config
from hiker_web.security import module_required
from hiker_web.texts_de import t

blueprint = Blueprint("reports", __name__, url_prefix="/stats")
report_page = module_required("reports")

# From how many metres of ascent a day gets the next darker colour.
LEVELS = (1, 400, 900, 1500)


def _weeks(year: int, days: list[dict]) -> list[list[dict | None]]:
    """The year as columns of weeks (Monday on top), like a wall calendar turned
    sideways. A cell is a day with its colour level (0 to 4) or None outside the year."""
    by_date = {day["date"]: day for day in days}
    first, last = date(year, 1, 1), date(year, 12, 31)
    current = first - timedelta(days=first.weekday())
    weeks = []
    while current <= last:
        week = []
        for _ in range(7):
            if current.year != year:
                week.append(None)
            else:
                day = by_date.get(current.isoformat())
                level = 0
                if day is not None:
                    # A day out always shows, also without a track.
                    level = 1 + sum(day["ascent_m"] >= step for step in LEVELS[1:])
                week.append({"date": current, "level": level, "day": day})
            current += timedelta(days=1)
        weeks.append(week)
    return weeks


@blueprint.get("/")
@report_page
def stats():
    client = api()
    year = (
        forms.to_number(request.args.get("year"), "year", int) if request.args.get("year") else None
    )
    calendar = client.get("/reports/calendar", year=year)
    stats_data = {
        **map_config(OSM_ATTRIBUTION),
        "tracksUrl": url_for("reports.tracks"),
        "tourUrl": url_for("protocols.tour_detail", tour_id="00000000-0000-0000-0000-000000000000"),
    }
    # A peak chosen on the map arrives as a filled-in wish.
    wish = {
        "name": request.args.get("wish_name", ""),
        "elevation_m": request.args.get("wish_ele", ""),
        "lat": request.args.get("wish_lat", ""),
        "lon": request.args.get("wish_lon", ""),
    }
    return render_template(
        "reports/stats.html",
        summary=client.get("/reports/summary"),
        peaks=client.get("/reports/peaks"),
        wishes=client.get("/reports/wishes"),
        calendar=calendar,
        weeks=_weeks(calendar["year"], calendar["days"]),
        stats_data=stats_data,
        wish=wish,
    )


@blueprint.get("/tracks.geojson")
@report_page
def tracks():
    """All own tracks as lines, for the map of the page."""
    return jsonify(api().get("/reports/tracks"))


@blueprint.post("/wishes")
@report_page
def wish_create():
    try:
        body = {
            "name": forms.text("name") or "",
            "elevation_m": forms.whole("elevation_m"),
            "lat": forms.number("lat"),
            "lon": forms.number("lon"),
            "note": forms.text("note"),
        }
        api().send("POST", "/reports/wishes", body)
        flash(t("common.saved"), "success")
    except forms.FormError:
        flash(t("error.validation"), "error")
    except ApiError as error:
        if error.status in (401, 404):
            raise
        flash(error_text(error), "error")
    return redirect(url_for("reports.stats", _anchor="wishes"))


@blueprint.post("/wishes/<uuid:wish_id>/delete")
@report_page
def wish_delete(wish_id):
    api().send("DELETE", f"/reports/wishes/{wish_id}")
    flash(t("common.deleted"), "success")
    return redirect(url_for("reports.stats", _anchor="wishes"))
