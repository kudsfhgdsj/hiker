"""Access to tours. Every endpoint gets its tour through the dependencies below.

- owner: everything
- edit:  text fields, lists (gear, food, peaks, waypoints) and photos
- read:  read only

Not allowed with `edit`: times and numbers of the tour, GPX/track, start and
end point, managing shares and links, deleting the tour.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import DbSession
from app.core.errors import ForbiddenError, NotFoundError
from app.modules.auth.deps import CurrentUser
from app.modules.auth.models import User
from app.modules.protocols.models import PERMISSION_EDIT, PERMISSION_READ, Tour, TourShare

OWNER = "owner"
_RANK = {PERMISSION_READ: 1, PERMISSION_EDIT: 2, OWNER: 3}

# Fields of the tour document that only the owner may change.
OWNER_ONLY_FIELDS = (
    "start_time",
    "end_time",
    "duration_minutes",
    "pack_weight_start_g",
    "calories_burned",
)


@dataclass(frozen=True)
class TourAccess:
    tour: Tour
    user: User
    permission: str

    @property
    def is_owner(self) -> bool:
        return self.permission == OWNER


def permission_for(db: Session, tour: Tour, user: User) -> str | None:
    if tour.owner_id == user.id:
        return OWNER
    return db.scalar(
        select(TourShare.permission).where(
            TourShare.tour_id == tour.id, TourShare.user_id == user.id
        )
    )


def get_tour_access(tour_id: uuid.UUID, user: CurrentUser, db: DbSession) -> TourAccess:
    tour = db.get(Tour, tour_id)
    permission = None
    if tour is not None and tour.deleted_at is None:
        permission = permission_for(db, tour, user)
    # Tours without any access answer like missing ones, so that ids cannot be probed.
    if permission not in _RANK:
        raise NotFoundError("Tour not found")
    return TourAccess(tour=tour, user=user, permission=permission)


def _require(minimum: str):
    def dependency(access: Annotated[TourAccess, Depends(get_tour_access)]) -> TourAccess:
        if _RANK[access.permission] < _RANK[minimum]:
            raise ForbiddenError(
                f"This action needs the '{minimum}' permission", code="insufficient_permission"
            )
        return access

    return dependency


ReadableTour = Annotated[TourAccess, Depends(get_tour_access)]
EditableTour = Annotated[TourAccess, Depends(_require(PERMISSION_EDIT))]
OwnedTour = Annotated[TourAccess, Depends(_require(OWNER))]


def check_owner_only_fields(access: TourAccess, values: dict) -> None:
    """Reject a change of owner-only fields by anyone but the owner."""
    if access.is_owner:
        return
    changed = [field for field in OWNER_ONLY_FIELDS if values[field] != getattr(access.tour, field)]
    if changed:
        raise ForbiddenError(
            f"Only the owner can change: {', '.join(changed)}", code="owner_only_field"
        )
