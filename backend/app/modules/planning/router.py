import re
import uuid
from datetime import UTC, datetime
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Path, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import DbSession
from app.core.errors import NotFoundError, PayloadTooLargeError, error_responses
from app.core.pagination import Page, Paging
from app.core.ratelimit import rate_limit
from app.modules.auth.deps import CurrentUser
from app.modules.planning import service, tours
from app.modules.planning.deps import OwnedRoute
from app.modules.planning.estimate import PRESETS
from app.modules.planning.models import PROFILE_DIRECT, PROFILES, SAC_SCALE, PaceProfile
from app.modules.planning.routing import ROUTING_ATTRIBUTION, RouteOptions, Routing
from app.modules.planning.schemas import (
    MAX_WAYPOINTS,
    ComparisonOut,
    DifficultyInfo,
    PacePreset,
    PaceProfileCreate,
    PaceProfileIn,
    PaceProfileOut,
    PlanningInfo,
    ProfileInfo,
    RouteCreate,
    RouteOut,
    RoutePreviewIn,
    RoutePreviewOut,
    RouteSummary,
    RouteTourOut,
    RouteUpdate,
    SegmentInfo,
)
from app.modules.protocols.elevation import Elevations
from app.modules.protocols.sharing import ReadableTour

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
        paces=[
            PacePreset(
                id=name,
                ascent_m_per_h=pace.ascent_m_per_h,
                descent_m_per_h=pace.descent_m_per_h,
                distance_km_per_h=pace.distance_km_per_h,
            )
            for name, pace in PRESETS.items()
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
    return service.compute_route(
        body.waypoints,
        body.profile,
        options,
        engine,
        elevations,
        body.pace.as_pace(),
        body.start_time,
    )


@router.get("/routes", response_model=Page[RouteSummary])
def list_routes(
    user: CurrentUser,
    db: DbSession,
    paging: Paging,
    q: Annotated[str | None, Query(max_length=100, description="Search in the title")] = None,
    tag: Annotated[
        str | None, Query(max_length=40, description="Only routes with this tag")
    ] = None,
):
    """The user's own routes without their lines, newest change first."""
    items, total = service.list_routes(
        db, user, q=q, tag=tag, limit=paging.limit, offset=paging.offset
    )
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


@router.post(
    "/routes/import",
    response_model=RouteOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(413, 422),
    dependencies=[ROUTING_LIMIT],
)
def import_route(
    file: UploadFile,
    user: CurrentUser,
    db: DbSession,
    engine: Routing,
    elevations: Elevations,
    title: Annotated[str | None, Form(max_length=200)] = None,
):
    """A GPX file (multipart field `file`) as a new route.

    The track is reduced to as few waypoints as keep its shape (at most 100); they are
    connected by straight lines, so that the route follows the file. Legs can be changed
    to follow the paths afterwards. 422 `invalid_gpx`: not a GPX file or without points.
    """
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLargeError(f"File is larger than {get_settings().max_upload_mb} MB")
    name = (title or "").strip() or re.sub(r"\.gpx$", "", file.filename or "", flags=re.I).strip()
    body = RouteCreate(
        title=name[:200] or "GPX",
        profile=PROFILE_DIRECT,
        waypoints=tours.waypoints_from_gpx(data),
    )
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


# --- Saved paces: only their owner sees them ---


# --- Tours made from a route ---


class TourFromRoute(BaseModel):
    tour_id: uuid.UUID


@router.post(
    "/routes/{route_id}/tour",
    response_model=TourFromRoute,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404),
)
def create_tour_from_route(route: OwnedRoute, user: CurrentUser, db: DbSession):
    """Start a tour from the route: title, description and start are taken over. The
    track of the tour is what was really walked and is uploaded to the tour later."""
    return TourFromRoute(tour_id=tours.tour_from_route(db, user, route).id)


@router.get(
    "/routes/{route_id}/tours", response_model=list[RouteTourOut], responses=error_responses(404)
)
def list_route_tours(route: OwnedRoute, user: CurrentUser, db: DbSession):
    """The tours started from the route, newest first."""
    return tours.linked_tours(db, user, route)


@router.get(
    "/routes/{route_id}/comparison/{tour_id}",
    response_model=ComparisonOut,
    responses=error_responses(404),
)
def compare_with_tour(route: OwnedRoute, access: ReadableTour, db: DbSession):
    """Plan and walked track side by side, for any tour the user may read.

    `deviation` measures the track against the planned line. Without a track `actual`,
    `deviation` and `track` are null.
    """
    return tours.comparison(db, route, access)


@router.get("/paces", response_model=list[PaceProfileOut])
def list_paces(user: CurrentUser, db: DbSession):
    """The user's own paces for the walking time, by name."""
    return service.list_paces(db, user)


@router.post(
    "/paces",
    response_model=PaceProfileOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
def create_pace(body: PaceProfileCreate, user: CurrentUser, db: DbSession):
    return service.create_pace(db, user, body)


def _own_pace(pace_id: uuid.UUID, user: CurrentUser, db: DbSession):
    pace = service.get_pace(db, user, pace_id)
    if pace is None:
        raise NotFoundError("Pace not found")
    return pace


OwnPace = Annotated[PaceProfile, Depends(_own_pace)]


@router.put("/paces/{pace_id}", response_model=PaceProfileOut, responses=error_responses(404))
def update_pace(body: PaceProfileIn, pace: OwnPace, db: DbSession):
    return service.update_pace(db, pace, body)


@router.delete(
    "/paces/{pace_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
def delete_pace(pace: OwnPace, db: DbSession):
    service.delete_pace(db, pace)


# --- Path data for planning without network (the app routes on the device) ---

SEGMENT_NAME = r"^[EW]\d{1,3}_[NS]\d{1,2}$"


def _segment_files() -> dict[str, FilePath]:
    folder = get_settings().brouter_segments_path
    if not folder or not FilePath(folder).is_dir():
        return {}
    return {
        file.stem: file
        for file in sorted(FilePath(folder).glob("*.rd5"))
        if re.match(SEGMENT_NAME, file.stem) and file.is_file()
    }


@router.get("/segments", response_model=list[SegmentInfo])
def list_segments(_user: CurrentUser):
    """The path data this server offers for download; empty if none is installed."""
    return [
        SegmentInfo(
            name=name,
            size_bytes=file.stat().st_size,
            modified=datetime.fromtimestamp(file.stat().st_mtime, UTC),
        )
        for name, file in _segment_files().items()
    ]


@router.get(
    "/segments/{name}",
    response_class=FileResponse,
    responses={200: {"content": {"application/octet-stream": {}}}, **error_responses(404, 429)},
    dependencies=[Depends(rate_limit("segments", limit=30))],
)
def download_segment(name: Annotated[str, Path(pattern=SEGMENT_NAME)], _user: CurrentUser):
    """One tile of path data (100 to 300 MB). Supports range requests to resume a download."""
    file = _segment_files().get(name)
    if file is None:
        raise NotFoundError("No such path data")
    return FileResponse(file, media_type="application/octet-stream", filename=f"{name}.rd5")
