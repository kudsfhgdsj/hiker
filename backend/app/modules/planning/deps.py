"""Central access check of the planning module: routes belong to their owner."""

import uuid
from typing import Annotated

from fastapi import Depends

from app.core.deps import DbSession
from app.core.errors import NotFoundError
from app.modules.auth.deps import CurrentUser
from app.modules.planning.models import PlannedRoute


def get_owned_route(route_id: uuid.UUID, user: CurrentUser, db: DbSession) -> PlannedRoute:
    route = db.get(PlannedRoute, route_id)
    # Foreign routes answer like missing ones, so that ids cannot be probed.
    if route is None or route.owner_id != user.id or route.deleted_at is not None:
        raise NotFoundError("Route not found")
    return route


OwnedRoute = Annotated[PlannedRoute, Depends(get_owned_route)]
