import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import utcnow
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.storage import Storage
from app.modules.auth import service as auth_service
from app.modules.auth.models import User
from app.modules.gear import service as gear_service
from app.modules.nutrition import service as nutrition_service
from app.modules.protocols import (
    contacts,
    history,
    photos,
    snapshots,
    track_service,
    weather,
)
from app.modules.protocols.models import (
    CALORIES_MANUAL,
    TRACK_NONE,
    Tour,
    TourFoodEntry,
    TourGear,
    TourPartner,
    TourPeak,
    TourShare,
    TourWaypoint,
)
from app.modules.protocols.schemas import (
    GeoPoint,
    PointsIn,
    TourBase,
    TourCreate,
    TourFoodIn,
    TourGearIn,
    TourIn,
    TourListItem,
    TourOut,
    TourOwner,
    TourPartnerIn,
    TourPeakIn,
    TourUpdate,
    WaypointIn,
    WaypointPatch,
)
from app.modules.protocols.sharing import (
    OWNER,
    OWNER_ONLY_FIELDS,
    TourAccess,
    check_owner_only_fields,
)

TEXT_FIELDS = ("title", "summary")
POINTS_MANUAL = "manual"


# --- Lists inside the tour document ---


def _match_entries(existing: list, incoming: list) -> list[tuple]:
    """Pair the incoming entries with existing ones by id: (incoming, existing or None)."""
    ids = [entry.id for entry in incoming if entry.id is not None]
    if len(set(ids)) != len(ids):
        raise UnprocessableError("An entry id appears more than once", code="duplicate_entry")
    by_id = {entry.id: entry for entry in existing}
    return [(entry, by_id.get(entry.id)) for entry in incoming]


def _check_new_id(db: Session, model, entry_id: uuid.UUID | None) -> None:
    if entry_id is not None and db.get(model, entry_id) is not None:
        raise ConflictError("An entry with this id already exists", code="id_taken")


def _kcal(kcal_per_100g: float | None, amount_g: float) -> float | None:
    if kcal_per_100g is None:
        return None
    return round(kcal_per_100g * amount_g / 100, 1)


def _sync_gear(db: Session, tour: Tour, user: User, incoming: list[TourGearIn]) -> None:
    result = []
    for data, entry in _match_entries(tour.gear, incoming):
        if entry is None:
            _check_new_id(db, TourGear, data.id)
            item = None
            if data.gear_item_id is not None:
                item = gear_service.get_item_for_user(db, user, data.gear_item_id)
            if item is None:
                raise UnprocessableError("Unknown gear item", code="unknown_gear_item")
            # Snapshot: later changes of the gear item do not change the tour.
            entry = TourGear(
                gear_item_id=item.id,
                added_by=user.id,
                name_snapshot=item.name,
                brand_snapshot=item.brand,
                weight_g_snapshot=item.weight_g,
            )
            if data.id is not None:
                entry.id = data.id
        entry.quantity = data.quantity
        entry.carried = data.carried
        result.append(entry)
    item_ids = [entry.gear_item_id for entry in result if entry.gear_item_id is not None]
    if len(set(item_ids)) != len(item_ids):
        raise UnprocessableError("A gear item appears more than once", code="duplicate_gear_item")
    # Remove dropped entries first: an item may be removed and added again in one change.
    tour.gear = [entry for entry in tour.gear if entry in result]
    db.flush()
    tour.gear = result


def _sync_food(db: Session, tour: Tour, user: User, incoming: list[TourFoodIn]) -> None:
    result = []
    for position, (data, entry) in enumerate(_match_entries(tour.food, incoming)):
        if entry is None:
            _check_new_id(db, TourFoodEntry, data.id)
            food = None
            if data.food_item_id is not None:
                food = nutrition_service.get_food_for_user(db, user, data.food_item_id)
            if food is None:
                raise UnprocessableError("Unknown food", code="unknown_food_item")
            entry = TourFoodEntry(
                food_item_id=food.id,
                added_by=user.id,
                name_snapshot=food.name,
                kcal_per_100g_snapshot=food.kcal_per_100g,
            )
            if data.id is not None:
                entry.id = data.id
        entry.amount_g = data.amount_g
        entry.kcal_snapshot = _kcal(entry.kcal_per_100g_snapshot, data.amount_g)
        entry.carried = data.carried
        entry.eaten = data.eaten
        entry.eaten_at = data.eaten_at
        entry.sort_order = position
        result.append(entry)
    tour.food = result


def _sync_peaks(db: Session, tour: Tour, incoming: list[TourPeakIn]) -> None:
    result = []
    for position, (data, entry) in enumerate(_match_entries(tour.peaks, incoming)):
        if entry is None:
            _check_new_id(db, TourPeak, data.id)
            entry = TourPeak()
            if data.id is not None:
                entry.id = data.id
        for field, value in data.model_dump(exclude={"id"}).items():
            setattr(entry, field, value)
        entry.sort_order = position
        result.append(entry)
    tour.peaks = result


def _sync_partners(db: Session, tour: Tour, user: User, incoming: list[TourPartnerIn]) -> None:
    ids = [partner.contact_id for partner in incoming]
    if len(set(ids)) != len(ids):
        raise UnprocessableError("A partner appears more than once", code="duplicate_partner")
    existing = {partner.contact_id: partner for partner in tour.partners}
    result = []
    for contact_id in ids:
        partner = existing.get(contact_id)
        if partner is None:
            # New partners come from the caller's own contacts.
            contact = contacts.get_usable_contact(db, user, contact_id)
            if contact is None:
                raise UnprocessableError("Unknown contact", code="unknown_contact")
            partner = TourPartner(contact=contact, added_by=user.id)
        result.append(partner)
    tour.partners = result


def _apply_document(db: Session, tour: Tour, user: User, data: TourIn, *, owner: bool) -> None:
    for field in TEXT_FIELDS:
        setattr(tour, field, getattr(data, field))
    if owner:
        for field in OWNER_ONLY_FIELDS:
            setattr(tour, field, getattr(data, field))
        # A manual value always wins; an estimate (later) only fills the gap.
        if data.calories_burned is not None:
            tour.calories_burned_source = CALORIES_MANUAL
        elif tour.calories_burned_source == CALORIES_MANUAL:
            tour.calories_burned_source = None
    _sync_gear(db, tour, user, data.gear)
    _sync_food(db, tour, user, data.food)
    _sync_peaks(db, tour, data.peaks)
    _sync_partners(db, tour, user, data.partners)


# --- Tours ---


def create_tour(db: Session, user: User, data: TourCreate) -> Tour:
    if data.id is not None and db.get(Tour, data.id) is not None:
        raise ConflictError("A tour with this id already exists", code="id_taken")
    tour = Tour(owner_id=user.id, version=0)
    if data.id is not None:
        tour.id = data.id
    db.add(tour)
    _apply_document(db, tour, user, data, owner=True)
    history.record_change(db, tour, user, history.CREATED)
    return tour


def update_tour(db: Session, access: TourAccess, data: TourUpdate) -> Tour:
    if data.version != access.tour.version:
        current = tour_out(db, access).model_dump(mode="json")
        raise history.VersionConflictError(current)
    check_owner_only_fields(access, data.model_dump(include=set(OWNER_ONLY_FIELDS)))
    _apply_document(db, access.tour, access.user, data, owner=access.is_owner)
    history.record_change(db, access.tour, access.user, history.UPDATED)
    return access.tour


def delete_tour(db: Session, storage: Storage, access: TourAccess) -> None:
    """Soft delete; the tour disappears for everyone it was shared with.

    The row stays for the offline sync, but photos and GPX files are removed for good.
    """
    tour = access.tour
    tour.deleted_at = utcnow()
    history.record_change(db, tour, access.user, history.DELETED)
    photos.delete_all_files(db, storage, tour)
    track_service.delete_all_files(db, storage, tour)


def list_tours(
    db: Session,
    user: User,
    *,
    scope: str,
    q: str | None,
    start_from: datetime | None,
    start_to: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[TourListItem], int]:
    shared = select(TourShare.tour_id).where(TourShare.user_id == user.id)
    visible = {
        "mine": Tour.owner_id == user.id,
        "shared": Tour.id.in_(shared),
        "all": or_(Tour.owner_id == user.id, Tour.id.in_(shared)),
    }[scope]
    conditions = [visible, Tour.deleted_at.is_(None)]
    if q:
        pattern = q.lower()
        conditions.append(
            or_(
                func.lower(Tour.title).contains(pattern, autoescape=True),
                func.lower(Tour.summary).contains(pattern, autoescape=True),
            )
        )
    if start_from is not None:
        conditions.append(Tour.start_time >= start_from)
    if start_to is not None:
        conditions.append(Tour.start_time <= start_to)
    total = db.scalar(select(func.count()).select_from(Tour).where(*conditions))
    # Newest first; tours without a date at the end.
    order_by = (Tour.start_time.is_(None), Tour.start_time.desc(), Tour.created_at.desc(), Tour.id)
    query = select(Tour).where(*conditions).order_by(*order_by).options(selectinload(Tour.peaks))
    tours = list(db.scalars(query.limit(limit).offset(offset)))

    ids = [tour.id for tour in tours]
    permissions = dict(
        db.execute(
            select(TourShare.tour_id, TourShare.permission).where(
                TourShare.user_id == user.id, TourShare.tour_id.in_(ids)
            )
        ).all()
    )
    names = auth_service.get_display_names(db, {tour.owner_id for tour in tours})
    items = [
        TourListItem(
            **_base(tour, OWNER if tour.owner_id == user.id else permissions[tour.id], names),
            peaks=[peak.name for peak in tour.peaks],
        )
        for tour in tours
    ]
    return items, total


def set_points(db: Session, access: TourAccess, data: PointsIn) -> None:
    """Set start and end point by hand; with a track only their names can change."""
    tour = access.tour
    has_track = tour.track_source != TRACK_NONE
    for prefix, point in (("start", data.start), ("end", data.end)):
        current = (getattr(tour, f"{prefix}_lat"), getattr(tour, f"{prefix}_lon"))
        if has_track:
            moved = point is None or any(
                abs(new - old) > 1e-6
                for new, old in zip((point.lat, point.lon), current, strict=True)
            )
            if moved:
                raise ConflictError(
                    "Start and end point follow the track", code="points_from_track"
                )
        else:
            setattr(tour, f"{prefix}_lat", point.lat if point else None)
            setattr(tour, f"{prefix}_lon", point.lon if point else None)
        setattr(tour, f"{prefix}_name", point.name if point else None)
    if not has_track:
        tour.points_source = POINTS_MANUAL if (data.start or data.end) else None
    history.record_change(db, tour, access.user, history.UPDATED)


# --- Output ---


def _base(tour: Tour, permission: str, names: dict) -> dict:
    owner = TourOwner(id=tour.owner_id, display_name=names.get(tour.owner_id))
    fields = set(TourBase.model_fields) - {"owner", "permission"}
    return {"owner": owner, "permission": permission} | {f: getattr(tour, f) for f in fields}


def _point(lat: float | None, lon: float | None, name: str | None) -> GeoPoint | None:
    if lat is None or lon is None:
        return None
    return GeoPoint(lat=lat, lon=lon, name=name)


def tour_out(db: Session, access: TourAccess) -> TourOut:
    tour = access.tour
    names = auth_service.get_display_names(db, {tour.owner_id})
    return TourOut(
        **_base(tour, access.permission, names),
        summary=tour.summary,
        duration_minutes=tour.duration_minutes,
        pack_weight_start_g=tour.pack_weight_start_g,
        calories_burned=tour.calories_burned,
        calories_burned_source=tour.calories_burned_source,
        computed=snapshots.computed_values(tour),
        start_point=_point(tour.start_lat, tour.start_lon, tour.start_name),
        end_point=_point(tour.end_lat, tour.end_lon, tour.end_name),
        points_source=tour.points_source,
        track_source=tour.track_source,
        track_stats=track_service.visible_stats(tour.track_stats, health=access.is_owner),
        photo_time_offset_seconds=tour.photo_time_offset_seconds,
        photo_count=len(tour.photos),
        weather=weather.weather_out(tour),
        weather_outdated=weather.is_outdated(db, tour),
        gear=snapshots.gear_list(tour),
        food=snapshots.food_list(tour),
        peaks=snapshots.peak_list(tour),
        partners=snapshots.partner_list(tour),
    )


# --- Waypoints ---


def get_waypoint(access: TourAccess, waypoint_id: uuid.UUID) -> TourWaypoint:
    for waypoint in access.tour.waypoints:
        if waypoint.id == waypoint_id:
            return waypoint
    raise NotFoundError("Waypoint not found")


def create_waypoint(db: Session, access: TourAccess, data: WaypointIn) -> TourWaypoint:
    _check_new_id(db, TourWaypoint, data.id)
    waypoint = TourWaypoint(**data.model_dump(exclude_none=True))
    access.tour.waypoints.append(waypoint)
    photos.locate_waypoint(db, access.tour, waypoint)
    history.record_change(db, access.tour, access.user, history.UPDATED)
    return waypoint


def update_waypoint(
    db: Session, access: TourAccess, waypoint: TourWaypoint, data: WaypointPatch
) -> TourWaypoint:
    changes = data.model_dump(exclude_unset=True)
    if any(changes.get(field, "") is None for field in ("name", "lat", "lon")):
        raise UnprocessableError("name, lat and lon cannot be empty")
    for field, value in changes.items():
        setattr(waypoint, field, value)
    if "lat" in changes or "lon" in changes:
        photos.locate_waypoint(db, access.tour, waypoint)
    history.record_change(db, access.tour, access.user, history.UPDATED)
    return waypoint


def delete_waypoint(db: Session, access: TourAccess, waypoint: TourWaypoint) -> None:
    for photo in access.tour.photos:
        if photo.waypoint_id == waypoint.id:
            photo.waypoint_id = None
    access.tour.waypoints.remove(waypoint)
    history.record_change(db, access.tour, access.user, history.UPDATED)


# --- History ---


def revision_items(db: Session, revisions: list, schema):
    names = auth_service.get_display_names(db, {r.author_user_id for r in revisions})
    items = []
    for revision in revisions:
        author = None
        if revision.author_user_id is not None:
            author = TourOwner(
                id=revision.author_user_id, display_name=names.get(revision.author_user_id)
            )
        fields = {f: getattr(revision, f) for f in schema.model_fields if f != "author"}
        items.append(schema(author=author, **fields))
    return items
