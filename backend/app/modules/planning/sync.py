"""Offline sync of the planning module: the user's planned routes.

A route drafted offline consists of its waypoints only; the line is computed
here when the change arrives. If no path connects the points the operation
fails with `no_route` and the draft stays on the client.
"""

from datetime import datetime

from sqlalchemy import select

from app.core.errors import NotFoundError
from app.core.sync import SyncChanges, SyncConflictError, SyncContext, SyncOperation, SyncSource
from app.modules.planning import service
from app.modules.planning.models import PaceProfile, PlannedRoute
from app.modules.planning.routing import get_routing_engine
from app.modules.planning.schemas import (
    PaceProfileCreate,
    PaceProfileIn,
    PaceProfileOut,
    RouteCreate,
    RouteOut,
    RouteUpdate,
)
from app.modules.protocols.elevation import get_elevation_source


def _route_json(route: PlannedRoute) -> dict:
    return RouteOut.model_validate(route).model_dump(mode="json")


def _changes(context: SyncContext, since: datetime | None) -> SyncChanges:
    query = select(PlannedRoute).where(PlannedRoute.owner_id == context.user.id)
    if since is not None:
        query = query.where(PlannedRoute.updated_at > since)
    routes = list(context.db.scalars(query))
    return SyncChanges(
        changed=[_route_json(route) for route in routes if route.deleted_at is None],
        deleted=[route.id for route in routes if route.deleted_at is not None and since],
    )


def _push(context: SyncContext, operation: SyncOperation) -> dict | None:
    db, user = context.db, context.user
    engine, elevations = get_routing_engine(), get_elevation_source()
    route = db.get(PlannedRoute, operation.id)
    usable = route is not None and route.owner_id == user.id and route.deleted_at is None
    if operation.op == "delete":
        if usable:
            service.delete_route(db, route)
        return None
    if route is None:
        data = RouteCreate.model_validate({**(operation.data or {}), "id": operation.id})
        return _route_json(service.create_route(db, user, data, engine, elevations))
    if not usable:
        raise NotFoundError("Route not found")
    document = {**(operation.data or {}), "version": operation.base_version or route.version}
    try:
        service.update_route(db, route, RouteUpdate.model_validate(document), engine, elevations)
    except service.VersionConflictError as conflict:
        raise SyncConflictError(
            (conflict.extra or {}).get("current") or _route_json(route)
        ) from conflict
    return _route_json(route)


def _pace_json(pace: PaceProfile) -> dict:
    return PaceProfileOut.model_validate(pace).model_dump(mode="json")


def _pace_changes(context: SyncContext, since: datetime | None) -> SyncChanges:
    query = select(PaceProfile).where(PaceProfile.owner_id == context.user.id)
    if since is not None:
        query = query.where(PaceProfile.updated_at > since)
    paces = list(context.db.scalars(query))
    return SyncChanges(
        changed=[_pace_json(pace) for pace in paces if pace.deleted_at is None],
        deleted=[pace.id for pace in paces if pace.deleted_at is not None and since],
    )


def _pace_push(context: SyncContext, operation: SyncOperation) -> dict | None:
    db, user = context.db, context.user
    pace = service.get_pace(db, user, operation.id)
    if operation.op == "delete":
        if pace is not None:
            service.delete_pace(db, pace)
        return None
    if pace is None:
        if db.get(PaceProfile, operation.id) is not None:
            raise NotFoundError("Pace not found")
        data = PaceProfileCreate.model_validate({**(operation.data or {}), "id": operation.id})
        return _pace_json(service.create_pace(db, user, data))
    data = PaceProfileIn.model_validate(operation.data or {})
    return _pace_json(service.update_pace(db, pace, data))


SOURCES = [SyncSource("routes", _changes, _push), SyncSource("paces", _pace_changes, _pace_push)]
