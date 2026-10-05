"""Offline sync of the protocols module: tours.

Conflicts follow the rule of the history: a change based on an outdated
version is answered with the current tour, and the client merges field by
field. Photos and GPX files are not part of the sync; clients upload them
through the normal endpoints from their own queue.
"""

from datetime import datetime

from sqlalchemy import or_, select

from app.core.errors import NotFoundError
from app.core.sync import SyncChanges, SyncConflictError, SyncContext, SyncOperation, SyncSource
from app.modules.protocols import history, service
from app.modules.protocols.models import PERMISSION_EDIT, Tour, TourShare
from app.modules.protocols.schemas import TourCreate, TourUpdate
from app.modules.protocols.sharing import OWNER, TourAccess, permission_for, require_permission


def _tour_json(context: SyncContext, tour: Tour, permission: str) -> dict:
    access = TourAccess(tour=tour, user=context.user, permission=permission)
    return service.tour_out(context.db, access).model_dump(mode="json")


def _changes(context: SyncContext, since: datetime | None) -> SyncChanges:
    db, user = context.db, context.user
    shares = dict(
        db.execute(
            select(TourShare.tour_id, TourShare.permission).where(TourShare.user_id == user.id)
        ).all()
    )
    visible = or_(Tour.owner_id == user.id, Tour.id.in_(shares.keys()))
    tours = list(db.scalars(select(Tour).where(visible)))
    alive = [tour for tour in tours if tour.deleted_at is None]
    recent = [tour for tour in alive if since is None or tour.updated_at > since]
    return SyncChanges(
        changed=[
            _tour_json(context, tour, OWNER if tour.owner_id == user.id else shares[tour.id])
            for tour in recent
        ],
        deleted=[
            tour.id
            for tour in tours
            if tour.deleted_at is not None and since is not None and tour.updated_at > since
        ],
        # A share can be taken away at any time: the client drops what is not listed.
        ids=[tour.id for tour in alive],
    )


def _push(context: SyncContext, operation: SyncOperation) -> dict | None:
    db, user = context.db, context.user
    tour = db.get(Tour, operation.id)
    if tour is None:
        if operation.op == "delete":
            return None
        data = TourCreate.model_validate({**(operation.data or {}), "id": operation.id})
        return _tour_json(context, service.create_tour(db, user, data), OWNER)
    permission = None if tour.deleted_at is not None else permission_for(db, tour, user)
    if permission is None:
        raise NotFoundError("Tour not found")
    access = TourAccess(tour=tour, user=user, permission=permission)
    if operation.op == "delete":
        require_permission(access, OWNER)
        service.delete_tour(db, context.storage, access)
        return None
    require_permission(access, PERMISSION_EDIT)
    document = {**(operation.data or {}), "version": operation.base_version or tour.version}
    try:
        service.update_tour(db, access, TourUpdate.model_validate(document))
    except history.VersionConflictError as conflict:
        current = (conflict.extra or {}).get("current") or _tour_json(context, tour, permission)
        raise SyncConflictError(current) from conflict
    return _tour_json(context, tour, permission)


SOURCES = [SyncSource("tours", _changes, _push)]
