"""The content of a tour as plain data: for API responses and for revisions."""

from app.modules.protocols.models import Tour, TourFoodEntry, TourGear
from app.modules.protocols.schemas import (
    TourFoodOut,
    TourGearOut,
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
)
LIST_FIELDS = ("gear", "food", "peaks", "waypoints")


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
    return [WaypointOut.model_validate(waypoint) for waypoint in tour.waypoints]


def build_snapshot(tour: Tour) -> dict:
    """The complete editable state of a tour as JSON-compatible data."""
    snapshot = TourSnapshot(
        **{field: getattr(tour, field) for field in SCALAR_FIELDS},
        gear=gear_list(tour),
        food=food_list(tour),
        peaks=peak_list(tour),
        waypoints=waypoint_list(tour),
    )
    return snapshot.model_dump(mode="json")
