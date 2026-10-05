"""The content of a tour as plain data: for API responses and for revisions."""

from app.modules.protocols.models import Tour, TourFoodEntry, TourGear
from app.modules.protocols.schemas import (
    PartnerSnapshot,
    PhotoSnapshot,
    TourComputed,
    TourFoodOut,
    TourGearOut,
    TourPartnerOut,
    TourPeakOut,
    TourSnapshot,
    WaypointOut,
)

SCALAR_FIELDS = (
    "title",
    "summary",
    "start_time",
    "end_time",
    "duration_minutes",
    "pack_weight_start_g",
    "calories_burned",
    "calories_burned_source",
    "cover_photo_id",
    "photo_time_offset_seconds",
    "track_source",
    "gpx_file_id",
    "points_source",
    "start_lat",
    "start_lon",
    "start_name",
    "end_lat",
    "end_lon",
    "end_name",
)
# Scalars that belong to the track and the points; only the owner changes them.
TRACK_FIELDS = SCALAR_FIELDS[SCALAR_FIELDS.index("track_source") :]
LIST_FIELDS = ("gear", "food", "peaks", "waypoints", "partners", "photos")


def _gear_out(entry: TourGear) -> TourGearOut:
    return TourGearOut(
        id=entry.id,
        gear_item_id=entry.gear_item_id,
        name=entry.name_snapshot,
        brand=entry.brand_snapshot,
        weight_g=entry.weight_g_snapshot,
        quantity=entry.quantity,
        carried=entry.carried,
    )


def _food_out(entry: TourFoodEntry) -> TourFoodOut:
    return TourFoodOut(
        id=entry.id,
        food_item_id=entry.food_item_id,
        name=entry.name_snapshot,
        kcal_per_100g=entry.kcal_per_100g_snapshot,
        amount_g=entry.amount_g,
        kcal=entry.kcal_snapshot,
        carried=entry.carried,
        eaten=entry.eaten,
        eaten_at=entry.eaten_at,
    )


def gear_list(tour: Tour) -> list[TourGearOut]:
    entries = sorted(tour.gear, key=lambda entry: (entry.name_snapshot.lower(), str(entry.id)))
    return [_gear_out(entry) for entry in entries]


def food_list(tour: Tour) -> list[TourFoodOut]:
    return [_food_out(entry) for entry in tour.food]


def peak_list(tour: Tour) -> list[TourPeakOut]:
    return [TourPeakOut.model_validate(peak) for peak in tour.peaks]


def waypoint_list(tour: Tour) -> list[WaypointOut]:
    """Waypoints in the order along the track; those without a position on it last."""
    ordered = sorted(
        tour.waypoints,
        key=lambda w: (w.track_distance_m is None, w.track_distance_m or 0, w.name, str(w.id)),
    )
    return [WaypointOut.model_validate(waypoint) for waypoint in ordered]


def _partners(tour: Tour) -> list:
    return sorted(tour.partners, key=lambda p: (p.contact.display_name.lower(), str(p.contact_id)))


def partner_list(tour: Tour) -> list[TourPartnerOut]:
    return [
        TourPartnerOut(
            contact_id=partner.contact_id,
            display_name=partner.contact.display_name,
            linked_user_id=partner.contact.linked_user_id,
        )
        for partner in _partners(tour)
    ]


def build_snapshot(tour: Tour) -> dict:
    """The complete editable state of a tour as JSON-compatible data."""
    snapshot = TourSnapshot(
        **{field: getattr(tour, field) for field in SCALAR_FIELDS},
        gear=gear_list(tour),
        food=food_list(tour),
        peaks=peak_list(tour),
        waypoints=waypoint_list(tour),
        partners=[
            PartnerSnapshot(id=partner.contact_id, name=partner.contact.display_name)
            for partner in _partners(tour)
        ],
        photos=[
            PhotoSnapshot(
                id=photo.id,
                name=photo.caption,
                taken_at=photo.taken_at,
                lat=photo.lat,
                lon=photo.lon,
                position_source=photo.position_source,
                track_distance_m=photo.track_distance_m,
                elevation_m=photo.elevation_m,
                waypoint_id=photo.waypoint_id,
            )
            for photo in sorted(tour.photos, key=lambda photo: (photo.sort_order, str(photo.id)))
        ],
    )
    return snapshot.model_dump(mode="json")


def computed_values(tour: Tour) -> TourComputed:
    duration = None
    if tour.start_time and tour.end_time:
        duration = int((tour.end_time - tour.start_time).total_seconds() // 60)
    gear_weight = sum(
        (entry.weight_g_snapshot or 0) * entry.quantity for entry in tour.gear if entry.carried
    )
    food_weight = sum(entry.amount_g for entry in tour.food if entry.carried)
    calories = sum(entry.kcal_snapshot or 0 for entry in tour.food if entry.eaten)
    return TourComputed(
        duration_minutes=duration,
        pack_weight_start_g=round(gear_weight + food_weight),
        calories_eaten=round(calories, 1),
    )
