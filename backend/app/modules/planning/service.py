"""Planned routes: the line and its key figures are computed from the waypoints."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.db import utcnow
from app.core.errors import ConflictError
from app.modules.auth.models import User
from app.modules.planning.estimate import PRESETS, Pace, walking_time_s
from app.modules.planning.models import PROFILE_DIRECT, PaceProfile, PlannedRoute
from app.modules.planning.routing import RoutedPoint, RouteOptions, RoutingEngine
from app.modules.planning.schemas import (
    PaceProfileCreate,
    PaceProfileIn,
    RouteCreate,
    RouteIn,
    RouteOut,
    RouteUpdate,
    RouteWaypoint,
)
from app.modules.protocols.elevation import ElevationSource, ElevationSourceError, lookup_along
from app.modules.protocols.track import (
    TrackPoint,
    build_series,
    compute_stats,
    haversine_m,
    points_to_gpx,
)

# Straight legs get a point about every 50 m, so that the elevation profile has a shape.
DIRECT_STEP_M = 50
ENGINE_DIRECT = "direct"
SERIES_COLUMNS = ("distance_m", "lat", "lon", "elevation_m")


class VersionConflictError(ConflictError):
    """The change was based on an outdated version; carries the current route."""

    code = "version_conflict"

    def __init__(self, current: dict | None = None):
        super().__init__("The route was changed in the meantime")
        if current is not None:
            self.extra = {"current": current}


@dataclass(frozen=True)
class ComputedRoute:
    engine: str
    series: dict
    distance_m: float
    ascent_m: float | None
    descent_m: float | None
    min_elevation_m: float | None
    max_elevation_m: float | None
    duration_s: int


# --- Computing the line ---


def _straight(start: RouteWaypoint | RoutedPoint, end: RouteWaypoint) -> list[RoutedPoint]:
    """A straight leg with evenly spread points; elevations are filled in later."""
    length = haversine_m(start.lat, start.lon, end.lat, end.lon)
    steps = max(1, round(length / DIRECT_STEP_M))
    return [
        RoutedPoint(
            lat=start.lat + (end.lat - start.lat) * step / steps,
            lon=start.lon + (end.lon - start.lon) * step / steps,
        )
        for step in range(steps + 1)
    ]


def _join(line: list[RoutedPoint], leg: list[RoutedPoint]) -> None:
    """Append a leg; its first point is the last one of the line so far."""
    line.extend(leg[1:] if line else leg)


def _fill_elevations(line: list[RoutedPoint], source: ElevationSource) -> list[RoutedPoint]:
    """Look up the elevation of the points that have none; a failure leaves them empty."""
    missing = [index for index, point in enumerate(line) if point.ele is None]
    if not missing:
        return line
    try:
        found = lookup_along(source, [(line[index].lat, line[index].lon) for index in missing])
    except ElevationSourceError:
        return line
    filled = list(line)
    for index, elevation in zip(missing, found, strict=True):
        filled[index] = RoutedPoint(line[index].lat, line[index].lon, elevation)
    return filled


def compute_route(
    waypoints: list[RouteWaypoint],
    profile: str,
    options: RouteOptions,
    engine: RoutingEngine,
    elevations: ElevationSource,
    pace: Pace = PRESETS["dav"],
) -> ComputedRoute:
    """The line through all waypoints: along paths, except for legs marked as direct."""
    line: list[RoutedPoint] = []
    used: set[str] = set()
    # Consecutive legs along paths go to the engine in one request.
    pending: list[RouteWaypoint] = [waypoints[0]]

    def flush() -> None:
        if len(pending) > 1:
            points = [(point.lat, point.lon) for point in pending]
            _join(line, engine.route(points, profile, options))
            used.add(engine.name)

    for waypoint in waypoints[1:]:
        if profile == PROFILE_DIRECT or waypoint.direct:
            flush()
            _join(line, _straight(line[-1] if line else pending[-1], waypoint))
            used.add(ENGINE_DIRECT)
            pending = [waypoint]
        else:
            pending.append(waypoint)
    flush()

    line = _fill_elevations(line, elevations)
    points = [TrackPoint(lat=point.lat, lon=point.lon, ele=point.ele) for point in line]
    stats = compute_stats(points)
    series = build_series(points)
    return ComputedRoute(
        engine="+".join(sorted(used)),
        series={column: series[column] for column in SERIES_COLUMNS},
        distance_m=stats["distance_m"],
        ascent_m=stats["ascent_m"],
        descent_m=stats["descent_m"],
        min_elevation_m=stats["min_elevation_m"],
        max_elevation_m=stats["max_elevation_m"],
        duration_s=walking_time_s(stats["distance_m"], stats["ascent_m"], stats["descent_m"], pace),
    )


# --- Stored routes ---


def _apply(
    route: PlannedRoute, data: RouteIn, engine: RoutingEngine, elevations: ElevationSource
) -> None:
    waypoints = [waypoint.model_dump() for waypoint in data.waypoints]
    # The line is only computed again if something changed that it depends on.
    course = (waypoints, data.profile, data.max_difficulty, data.via_ferrata)
    if route.series is None or course != (
        route.waypoints,
        route.profile,
        route.max_difficulty,
        route.via_ferrata,
    ):
        options = RouteOptions(data.max_difficulty, data.via_ferrata)
        computed = compute_route(data.waypoints, data.profile, options, engine, elevations)
        route.series = computed.series
        route.engine = computed.engine
        for field in (
            "distance_m",
            "ascent_m",
            "descent_m",
            "min_elevation_m",
            "max_elevation_m",
            "duration_s",
        ):
            setattr(route, field, getattr(computed, field))
    # The walking time follows the pace; a new pace needs no new line.
    pace = data.pace.resolved()
    route.pace_preset = pace.preset
    route.pace_name = data.pace.name if pace.preset == "custom" else None
    route.pace_ascent_m_per_h = pace.ascent_m_per_h
    route.pace_descent_m_per_h = pace.descent_m_per_h
    route.pace_distance_km_per_h = pace.distance_km_per_h
    route.duration_s = walking_time_s(
        route.distance_m, route.ascent_m, route.descent_m, data.pace.as_pace()
    )
    route.title = data.title
    route.description = data.description
    route.planned_date = data.planned_date
    route.profile = data.profile
    route.max_difficulty = data.max_difficulty
    route.via_ferrata = data.via_ferrata
    route.waypoints = waypoints


def _flush(db: Session) -> None:
    try:
        db.commit()
    except StaleDataError as exc:
        # Someone else changed the route between our read and our write.
        db.rollback()
        raise VersionConflictError() from exc


def create_route(
    db: Session, user: User, data: RouteCreate, engine: RoutingEngine, elevations: ElevationSource
) -> PlannedRoute:
    if data.id is not None and db.get(PlannedRoute, data.id) is not None:
        raise ConflictError("A route with this id already exists", code="id_taken")
    route = PlannedRoute(owner_id=user.id, version=1)
    if data.id is not None:
        route.id = data.id
    _apply(route, data, engine, elevations)
    db.add(route)
    _flush(db)
    return route


def update_route(
    db: Session,
    route: PlannedRoute,
    data: RouteUpdate,
    engine: RoutingEngine,
    elevations: ElevationSource,
) -> PlannedRoute:
    if data.version != route.version:
        current = RouteOut.model_validate(route).model_dump(mode="json")
        raise VersionConflictError(current)
    _apply(route, data, engine, elevations)
    route.version += 1
    _flush(db)
    return route


def delete_route(db: Session, route: PlannedRoute) -> None:
    """Soft delete, so that the offline sync can pass it on."""
    route.deleted_at = utcnow()
    route.version += 1
    _flush(db)


def list_routes(db: Session, user: User, *, q: str | None, limit: int, offset: int):
    conditions = [PlannedRoute.owner_id == user.id, PlannedRoute.deleted_at.is_(None)]
    if q:
        conditions.append(PlannedRoute.title.icontains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(PlannedRoute).where(*conditions))
    query = (
        select(PlannedRoute)
        .where(*conditions)
        .order_by(PlannedRoute.updated_at.desc(), PlannedRoute.id)
    )
    return list(db.scalars(query.limit(limit).offset(offset))), total


def route_gpx(route: PlannedRoute) -> bytes:
    """The line as a GPX track; the named waypoints are part of the description of a tour."""
    series = route.series
    elevations = series.get("elevation_m") or [None] * len(series["lat"])
    points = [
        TrackPoint(lat=lat, lon=lon, ele=ele)
        for lat, lon, ele in zip(series["lat"], series["lon"], elevations, strict=True)
    ]
    return points_to_gpx(points, route.title)


# --- Saved paces ---


def list_paces(db: Session, user: User) -> list[PaceProfile]:
    query = (
        select(PaceProfile)
        .where(PaceProfile.owner_id == user.id, PaceProfile.deleted_at.is_(None))
        .order_by(func.lower(PaceProfile.name))
    )
    return list(db.scalars(query))


def get_pace(db: Session, user: User, pace_id) -> PaceProfile | None:
    pace = db.get(PaceProfile, pace_id)
    # Paces of others answer like missing ones.
    if pace is None or pace.owner_id != user.id or pace.deleted_at is not None:
        return None
    return pace


def create_pace(db: Session, user: User, data: PaceProfileCreate) -> PaceProfile:
    if data.id is not None and db.get(PaceProfile, data.id) is not None:
        raise ConflictError("A pace with this id already exists", code="id_taken")
    pace = PaceProfile(owner_id=user.id, **data.model_dump(exclude={"id"}))
    if data.id is not None:
        pace.id = data.id
    db.add(pace)
    db.commit()
    return pace


def update_pace(db: Session, pace: PaceProfile, data: PaceProfileIn) -> PaceProfile:
    for field, value in data.model_dump().items():
        setattr(pace, field, value)
    db.commit()
    return pace


def delete_pace(db: Session, pace: PaceProfile) -> None:
    """Routes keep the values they were computed with; only the saved name goes."""
    pace.deleted_at = utcnow()
    db.commit()
