"""Change history of tours.

Every change of a tour, including its lists and waypoints, must be finished
with `record_change`. It writes a `tour_revision` with a full snapshot and the
diff to the previous state. Revisions are only ever added, never changed or
removed; restoring an old state adds a new revision as well.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.db import utcnow
from app.core.errors import ConflictError, NotFoundError
from app.modules.auth.models import User
from app.modules.gear import service as gear_service
from app.modules.nutrition import service as nutrition_service
from app.modules.protocols.models import (
    Contact,
    Tour,
    TourFoodEntry,
    TourGear,
    TourPartner,
    TourPeak,
    TourRevision,
    TourWaypoint,
)
from app.modules.protocols.schemas import TourSnapshot
from app.modules.protocols.sharing import OWNER_ONLY_FIELDS, TourAccess, check_owner_only_fields
from app.modules.protocols.snapshots import LIST_FIELDS, SCALAR_FIELDS, build_snapshot

CREATED = "created"
UPDATED = "updated"
RESTORED = "restored"
DELETED = "deleted"


class VersionConflictError(ConflictError):
    """The change was based on an outdated version; carries the current tour."""

    code = "version_conflict"

    def __init__(self, current: dict | None = None):
        super().__init__("The tour was changed in the meantime")
        if current is not None:
            self.extra = {"current": current}


# --- Diff ---


def _diff_entries(old: list[dict], new: list[dict]) -> dict:
    old_by_id = {entry["id"]: entry for entry in old}
    new_by_id = {entry["id"]: entry for entry in new}
    changed = []
    for entry_id, entry in new_by_id.items():
        before = old_by_id.get(entry_id)
        if before is not None and before != entry:
            fields = {
                key: {"old": before.get(key), "new": value}
                for key, value in entry.items()
                if before.get(key) != value
            }
            changed.append({"id": entry_id, "name": entry.get("name"), "changes": fields})
    kept_old = [entry_id for entry_id in old_by_id if entry_id in new_by_id]
    kept_new = [entry_id for entry_id in new_by_id if entry_id in old_by_id]
    result = {
        "added": [entry for entry_id, entry in new_by_id.items() if entry_id not in old_by_id],
        "removed": [entry for entry_id, entry in old_by_id.items() if entry_id not in new_by_id],
        "changed": changed,
        "reordered": kept_old != kept_new,
    }
    return result if any(result.values()) else {}


def diff_snapshots(old: dict, new: dict) -> dict:
    """Field-wise difference: scalars as old/new, lists as added/removed/changed."""
    result = {}
    for field in SCALAR_FIELDS:
        if old.get(field) != new.get(field):
            result[field] = {"old": old.get(field), "new": new.get(field)}
    for field in LIST_FIELDS:
        entries = _diff_entries(old.get(field) or [], new.get(field) or [])
        if entries:
            result[field] = entries
    return result


# --- Recording ---


def _latest_snapshot(db: Session, tour: Tour) -> dict:
    snapshot = db.scalar(
        select(TourRevision.snapshot)
        .where(TourRevision.tour_id == tour.id)
        .order_by(TourRevision.version.desc())
        .limit(1)
    )
    return snapshot or {}


def record_change(
    db: Session, tour: Tour, author: User, kind: str, summary: str | None = None
) -> TourRevision | None:
    """Write the revision for the pending changes of the tour and commit them.

    An update that changes nothing is committed without a revision.
    """
    try:
        # Flush first: new entries get their ids, which the snapshot needs.
        db.flush()
        snapshot = build_snapshot(tour)
        diff = diff_snapshots(_latest_snapshot(db, tour), snapshot) if kind != CREATED else {}
        revision = None
        if diff or kind != UPDATED:
            tour.version += 1
            tour.updated_at = utcnow()
            revision = TourRevision(
                tour_id=tour.id,
                version=tour.version,
                author_user_id=author.id,
                kind=kind,
                change_summary=summary if summary is not None else ", ".join(diff),
                snapshot=snapshot,
                diff=diff,
            )
            db.add(revision)
        db.commit()
    except StaleDataError as exc:
        # Someone else changed the tour between our read and our write.
        db.rollback()
        raise VersionConflictError() from exc
    return revision


# --- Reading ---


def list_revisions(db: Session, tour: Tour, *, limit: int, offset: int):
    condition = TourRevision.tour_id == tour.id
    total = db.scalar(select(func.count()).select_from(TourRevision).where(condition))
    query = select(TourRevision).where(condition).order_by(TourRevision.version.desc())
    return list(db.scalars(query.limit(limit).offset(offset))), total


def get_revision(db: Session, tour: Tour, version: int) -> TourRevision:
    revision = db.scalar(
        select(TourRevision).where(TourRevision.tour_id == tour.id, TourRevision.version == version)
    )
    if revision is None:
        raise NotFoundError("Revision not found")
    return revision


# --- Restoring ---


def _restore_entries(model, current: list, entries: list, to_columns) -> list:
    """Rebuild a list from snapshot entries, reusing the rows that still exist."""
    by_id = {row.id: row for row in current}
    result = []
    for position, entry in enumerate(entries):
        row = by_id.get(entry.id) or model(id=entry.id)
        for column, value in to_columns(entry, position).items():
            setattr(row, column, value)
        result.append(row)
    return result


def restore(db: Session, access: TourAccess, revision: TourRevision) -> TourRevision | None:
    """Bring the tour back to the state of a revision; this adds a new revision."""
    tour, user = access.tour, access.user
    state = TourSnapshot.model_validate(revision.snapshot)
    check_owner_only_fields(access, {field: getattr(state, field) for field in OWNER_ONLY_FIELDS})

    for field in SCALAR_FIELDS:
        setattr(tour, field, getattr(state, field))

    # References to gear and food that no longer exist are dropped, the snapshot stays.
    gear_ids = gear_service.existing_item_ids(db, {e.gear_item_id for e in state.gear})
    food_ids = nutrition_service.existing_food_ids(db, {e.food_item_id for e in state.food})

    def gear_columns(entry, _position):
        return {
            "gear_item_id": entry.gear_item_id if entry.gear_item_id in gear_ids else None,
            "name_snapshot": entry.name,
            "brand_snapshot": entry.brand,
            "weight_g_snapshot": entry.weight_g,
            "quantity": entry.quantity,
            "carried": entry.carried,
        }

    def food_columns(entry, position):
        return {
            "food_item_id": entry.food_item_id if entry.food_item_id in food_ids else None,
            "name_snapshot": entry.name,
            "kcal_per_100g_snapshot": entry.kcal_per_100g,
            "amount_g": entry.amount_g,
            "kcal_snapshot": entry.kcal,
            "carried": entry.carried,
            "eaten": entry.eaten,
            "eaten_at": entry.eaten_at,
            "sort_order": position,
        }

    def peak_columns(entry, position):
        return entry.model_dump(exclude={"id"}) | {"sort_order": position}

    def waypoint_columns(entry, _position):
        return entry.model_dump(exclude={"id"})

    restored = {
        "gear": _restore_entries(TourGear, tour.gear, state.gear, gear_columns),
        "food": _restore_entries(TourFoodEntry, tour.food, state.food, food_columns),
        "peaks": _restore_entries(TourPeak, tour.peaks, state.peaks, peak_columns),
        "waypoints": _restore_entries(
            TourWaypoint, tour.waypoints, state.waypoints, waypoint_columns
        ),
    }
    current_partners = {partner.contact_id: partner for partner in tour.partners}
    partners = []
    for entry in state.partners:
        partner = current_partners.get(entry.id)
        # Contacts that no longer exist cannot be listed again.
        if partner is None and db.get(Contact, entry.id) is not None:
            partner = TourPartner(contact_id=entry.id, added_by=user.id)
        if partner is not None:
            partners.append(partner)
    restored["partners"] = partners
    for row in (*restored["gear"], *restored["food"]):
        if row.added_by is None:
            row.added_by = user.id
    # Remove the rows that are gone first, so that re-created entries cannot collide.
    for field, rows in restored.items():
        setattr(tour, field, [row for row in getattr(tour, field) if row in rows])
    db.flush()
    for field, rows in restored.items():
        setattr(tour, field, rows)
    return record_change(db, tour, user, RESTORED, f"version {revision.version}")
