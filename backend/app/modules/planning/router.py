from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import DbSession
from app.core.errors import error_responses
from app.core.pagination import Page, Paging
from app.core.ratelimit import rate_limit
from app.modules.auth.deps import CurrentUser
from app.modules.planning import service
from app.modules.planning.deps import OwnedRoute
from app.modules.planning.models import PROFILE_DIRECT, PROFILES, SAC_SCALE
from app.modules.planning.routing import ROUTING_ATTRIBUTION, RouteOptions, Routing
from app.modules.planning.schemas import (
    MAX_WAYPOINTS,
    DifficultyInfo,
    PlanningInfo,
    ProfileInfo,
    RouteCreate,
    RouteOut,
    RoutePreviewIn,
    RoutePreviewOut,
    RouteSummary,
    RouteUpdate,
)
from app.modules.protocols.elevation import Elevations

router = APIRouter(responses=error_responses(401))

GPX_MIME = "application/gpx+xml"
# Computing a route costs the routing engine time; previews follow every moved point.
ROUTING_LIMIT = Depends(rate_limit("routing", limit=120))


@router.get("/info", response_model=PlanningInfo)
def read_info(_user: CurrentUser, engine: Routing):
    """Which profiles can be planned with on this server."""
    return PlanningInfo(
        routing_available=engine.available,
        profiles=[
            ProfileInfo(id=profile, available=profile == PROFILE_DIRECT or engine.available)
            for profile in PROFILES
        ],
        difficulties=[
            DifficultyInfo(level=level, code=f"T{level}", sac_scale=value)
            for level, value in enumerate(SAC_SCALE, start=1)
        ],
        attribution=ROUTING_ATTRIBUTION if engine.available else None,
        max_waypoints=MAX_WAYPOINTS,
    )


@router.post(
    "/preview",
    response_model=RoutePreviewOut,
    responses=error_responses(422, 429, 502),
    dependencies=[ROUTING_LIMIT],
)
def preview(body: RoutePreviewIn, _user: CurrentUser, engine: Routing, elevations: Elevations):
    """Line, key figures and walking time for the waypoints; nothing is stored.

    422 `no_route`: no path connects the points. 502 `routing_unavailable`: routing
    along paths is not set up or cannot be reached; straight lines still work.
    """
    options = RouteOptions(body.max_difficulty, body.via_ferrata)
    return service.compute_route(body.waypoints, body.profile, options, engine, elevations)


@router.get("/routes", response_model=Page[RouteSummary])
def list_routes(
    user: CurrentUser,
    db: DbSession,
    paging: Paging,
    q: Annotated[str | None, Query(max_length=100, description="Search in the title")] = None,
):
    """The user's own routes without their lines, newest change first."""
    items, total = service.list_routes(db, user, q=q, limit=paging.limit, offset=paging.offset)
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.post(
    "/routes",
    response_model=RouteOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409, 422, 429, 502),
    dependencies=[ROUTING_LIMIT],
)
def create_route(
    body: RouteCreate, user: CurrentUser, db: DbSession, engine: Routing, elevations: Elevations
):
    """Store a route; the server computes the line from the waypoints."""
    return service.create_route(db, user, body, engine, elevations)


@router.get("/routes/{route_id}", response_model=RouteOut, responses=error_responses(404))
def read_route(route: OwnedRoute):
    return route


@router.put(
    "/routes/{route_id}",
    response_model=RouteOut,
    responses=error_responses(404, 409, 422, 429, 502),
    dependencies=[ROUTING_LIMIT],
)
def update_route(
    body: RouteUpdate, route: OwnedRoute, db: DbSession, engine: Routing, elevations: Elevations
):
    """Change a route. 409 `version_conflict` carries the current route as `current`."""
    return service.update_route(db, route, body, engine, elevations)


@router.delete(
    "/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
def delete_route(route: OwnedRoute, db: DbSession):
    service.delete_route(db, route)


@router.get(
    "/routes/{route_id}/gpx",
    response_class=Response,
    responses={200: {"content": {GPX_MIME: {}}}, **error_responses(404)},
)
def download_gpx(route: OwnedRoute):
    """The route as a GPX file with one track."""
    return Response(
        service.route_gpx(route),
        media_type=GPX_MIME,
        headers={"Content-Disposition": f'attachment; filename="route-{route.id}.gpx"'},
    )
