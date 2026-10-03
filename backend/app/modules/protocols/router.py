import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status
from pydantic import AwareDatetime

from app.core.deps import DbSession
from app.core.errors import error_responses
from app.core.pagination import Page, Paging
from app.modules.auth.deps import CurrentUser
from app.modules.protocols import service
from app.modules.protocols.schemas import (
    TourCreate,
    TourIn,
    TourListItem,
    TourOut,
    WaypointIn,
    WaypointOut,
    WaypointPatch,
)
from app.modules.protocols.sharing import (
    OWNER,
    EditableTour,
    OwnedTour,
    ReadableTour,
    TourAccess,
)

router = APIRouter(responses=error_responses(401))


@router.get("/tours", response_model=Page[TourListItem])
def list_tours(
    user: CurrentUser,
    db: DbSession,
    paging: Paging,
    scope: Annotated[
        Literal["all", "mine", "shared"], Query(description="Own tours, tours shared with me")
    ] = "all",
    q: Annotated[
        str | None, Query(max_length=100, description="Search in title and summary")
    ] = None,
    start_from: Annotated[AwareDatetime | None, Query(description="start_time not before")] = None,
    start_to: Annotated[AwareDatetime | None, Query(description="start_time not after")] = None,
):
    items, total = service.list_tours(
        db,
        user,
        scope=scope,
        q=q,
        start_from=start_from,
        start_to=start_to,
        limit=paging.limit,
        offset=paging.offset,
    )
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.post(
    "/tours",
    response_model=TourOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
def create_tour(body: TourCreate, user: CurrentUser, db: DbSession):
    tour = service.create_tour(db, user, body)
    return service.tour_out(db, TourAccess(tour=tour, user=user, permission=OWNER))


@router.get("/tours/{tour_id}", response_model=TourOut, responses=error_responses(404))
def read_tour(access: ReadableTour, db: DbSession):
    return service.tour_out(db, access)


@router.put("/tours/{tour_id}", response_model=TourOut, responses=error_responses(403, 404, 409))
def update_tour(body: TourIn, access: EditableTour, db: DbSession):
    """Replace the tour document including its lists.

    With `edit` permission the owner-only fields (times, duration, pack weight,
    calories burned) must be sent back unchanged.
    """
    service.update_tour(db, access, body)
    return service.tour_out(db, access)


@router.delete(
    "/tours/{tour_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(403, 404),
)
def delete_tour(access: OwnedTour, db: DbSession):
    service.delete_tour(db, access)


# --- Waypoints ---


@router.get(
    "/tours/{tour_id}/waypoints", response_model=list[WaypointOut], responses=error_responses(404)
)
def list_waypoints(access: ReadableTour):
    return access.tour.waypoints


@router.post(
    "/tours/{tour_id}/waypoints",
    response_model=WaypointOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(403, 404, 409),
)
def create_waypoint(body: WaypointIn, access: EditableTour, db: DbSession):
    return service.create_waypoint(db, access, body)


@router.patch(
    "/tours/{tour_id}/waypoints/{waypoint_id}",
    response_model=WaypointOut,
    responses=error_responses(403, 404),
)
def update_waypoint(
    waypoint_id: uuid.UUID, body: WaypointPatch, access: EditableTour, db: DbSession
):
    waypoint = service.get_waypoint(access, waypoint_id)
    return service.update_waypoint(db, access, waypoint, body)


@router.delete(
    "/tours/{tour_id}/waypoints/{waypoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(403, 404),
)
def delete_waypoint(waypoint_id: uuid.UUID, access: EditableTour, db: DbSession):
    service.delete_waypoint(db, access, service.get_waypoint(access, waypoint_id))
