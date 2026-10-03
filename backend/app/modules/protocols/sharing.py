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
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.modules.auth import service as auth_service
from app.modules.auth.deps import CurrentUser
from app.modules.auth.models import User
from app.modules.protocols.models import PERMISSION_EDIT, PERMISSION_READ, Tour, TourShare
from app.modules.protocols.schemas import ShareOut, TourOwner

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


def require_permission(access: TourAccess, minimum: str) -> None:
    """The one place that decides whether a permission is enough for an action."""
    if _RANK[access.permission] < _RANK[minimum]:
        raise ForbiddenError(
            f"This action needs the '{minimum}' permission", code="insufficient_permission"
        )


def _require(minimum: str):
    def dependency(access: Annotated[TourAccess, Depends(get_tour_access)]) -> TourAccess:
        require_permission(access, minimum)
        return access

    return dependency


ReadableTour = Annotated[TourAccess, Depends(get_tour_access)]
EditableTour = Annotated[TourAccess, Depends(_require(PERMISSION_EDIT))]
OwnedTour = Annotated[TourAccess, Depends(_require(OWNER))]


def check_owner_only_fields(access: TourAccess, values: dict) -> None:
    """Reject a change of owner-only fields by anyone but the owner."""
    if access.is_owner:
        return
    changed = [field for field, value in values.items() if value != getattr(access.tour, field)]
    if changed:
        raise ForbiddenError(
            f"Only the owner can change: {', '.join(changed)}", code="owner_only_field"
        )


# --- Managing shares ---


def require_owner_or_self(access: TourAccess, user_id: uuid.UUID) -> None:
    """Shares are managed by the owner; everyone may give up their own share."""
    if not access.is_owner and user_id != access.user.id:
        raise ForbiddenError(
            "This action needs the 'owner' permission", code="insufficient_permission"
        )


def _share_out(share: TourShare, names: dict) -> ShareOut:
    user = TourOwner(id=share.user_id, display_name=names.get(share.user_id))
    return ShareOut(user=user, permission=share.permission, created_at=share.created_at)


def list_shares(db: Session, tour: Tour) -> list[ShareOut]:
    shares = db.scalars(
        select(TourShare).where(TourShare.tour_id == tour.id).order_by(TourShare.created_at)
    ).all()
    names = auth_service.get_display_names(db, {share.user_id for share in shares})
    return [_share_out(share, names) for share in shares]


def _get_share(db: Session, tour: Tour, user_id: uuid.UUID) -> TourShare:
    share = db.get(TourShare, (tour.id, user_id))
    if share is None:
        raise NotFoundError("Share not found")
    return share


def create_share(db: Session, tour: Tour, user_id: uuid.UUID, permission: str) -> ShareOut:
    names = auth_service.get_display_names(db, {user_id})
    if user_id not in names:
        raise UnprocessableError("Unknown user", code="unknown_user")
    if user_id == tour.owner_id:
        raise UnprocessableError("The owner already has full access", code="share_with_owner")
    if db.get(TourShare, (tour.id, user_id)) is not None:
        raise ConflictError("The tour is already shared with this user", code="already_shared")
    share = TourShare(tour_id=tour.id, user_id=user_id, permission=permission)
    db.add(share)
    db.commit()
    return _share_out(share, names)


def update_share(db: Session, tour: Tour, user_id: uuid.UUID, permission: str) -> ShareOut:
    share = _get_share(db, tour, user_id)
    share.permission = permission
    db.commit()
    return _share_out(share, auth_service.get_display_names(db, {user_id}))


def delete_share(db: Session, tour: Tour, user_id: uuid.UUID) -> None:
    """Takes effect at once: access is checked on every request."""
    db.delete(_get_share(db, tour, user_id))
    db.commit()
