"""Routes and tours: a tour started from a plan, plan and track side by side, and a
GPX file taken over as a route.

`planning` uses the public services of `protocols` here; `protocols` knows nothing of
routes. Which tour belongs to which route is kept on this side (`route_tour`).
"""

import math
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.planning.models import PlannedRoute, RouteTour
from app.modules.planning.schemas import MAX_WAYPOINTS
from app.modules.protocols import service as tours
from app.modules.protocols.models import Tour, TrackSeries
from app.modules.protocols.schemas import TourCreate
from app.modules.protocols.sharing import TourAccess, permission_for
from app.modules.protocols.track import TrackPoint, parse_gpx

# A track point this close to the planned line counts as "on the plan".
ON_PLAN_M = 50
# How many points of the track are measured against the plan.
_SAMPLES = 400
_EARTH_RADIUS_M = 6_371_000


def tour_from_route(db: Session, user: User, route: PlannedRoute) -> Tour:
    """A new tour of the user with title, description and start of the route."""
    tour = tours.create_tour(
        db,
        user,
        TourCreate(title=route.title, summary=route.description, start_time=route.start_time),
    )
    db.add(RouteTour(tour_id=tour.id, route_id=route.id))
    db.commit()
    return tour


def linked_tours(db: Session, user: User, route: PlannedRoute) -> list[dict]:
    """The tours made from the route that the user can still see, newest first."""
    rows = db.scalars(
        select(Tour)
        .join(RouteTour, RouteTour.tour_id == Tour.id)
        .where(RouteTour.route_id == route.id, Tour.deleted_at.is_(None))
        .order_by(Tour.created_at.desc())
    ).all()
    return [
        {
            "tour_id": tour.id,
            "title": tour.title,
            "start_time": tour.start_time,
            "has_track": tour.track_stats is not None,
        }
        for tour in rows
        if permission_for(db, tour, user) is not None
    ]


def _thin(values: list, count: int) -> list[int]:
    """Indexes of at most `count` entries, evenly spread, with both ends."""
    if len(values) <= count:
        return list(range(len(values)))
    return sorted({round(i * (len(values) - 1) / (count - 1)) for i in range(count)})


def _deviation(plan: dict, track: dict) -> dict | None:
    """How far the walked track lies from the planned line, measured at points of the
    track against the points of the plan."""
    if not plan.get("lat") or not track.get("lat"):
        return None
    latitude = math.radians(plan["lat"][0])
    # Flat approximation around the route: metres per degree.
    north = math.pi / 180 * _EARTH_RADIUS_M
    east = north * math.cos(latitude)
    line = [(lon * east, lat * north) for lat, lon in zip(plan["lat"], plan["lon"], strict=True)]

    def to_line(x: float, y: float) -> float:
        best = math.inf
        for (ax, ay), (bx, by) in zip(line, line[1:], strict=False):
            dx, dy = bx - ax, by - ay
            length = dx * dx + dy * dy
            share = (
                0.0 if length == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length))
            )
            distance = (x - ax - share * dx) ** 2 + (y - ay - share * dy) ** 2
            best = min(best, distance)
        return math.sqrt(best)

    distances = [
        to_line(track["lon"][index] * east, track["lat"][index] * north)
        for index in _thin(track["lat"], _SAMPLES)
    ]
    return {
        "mean_m": round(sum(distances) / len(distances)),
        "max_m": round(max(distances)),
        "on_plan_share": round(sum(d <= ON_PLAN_M for d in distances) / len(distances), 2),
    }


def comparison(db: Session, route: PlannedRoute, access: TourAccess) -> dict:
    """Plan and walked track side by side: key figures, both lines, the distance between
    them. Without a track only the plan is filled."""
    tour = access.tour
    stats = tour.track_stats
    series = db.get(TrackSeries, tour.id)
    track = series.data if series is not None else None
    actual = None
    if stats is not None:
        actual = {
            "distance_m": stats.get("distance_m"),
            "ascent_m": stats.get("ascent_m"),
            "descent_m": stats.get("descent_m"),
            # Walking time without breaks, like the estimate; the whole time next to it.
            "duration_s": stats.get("moving_time_s"),
            "total_time_s": stats.get("total_time_s"),
        }
    return {
        "route_id": route.id,
        "tour_id": tour.id,
        "tour_title": tour.title,
        "planned": {
            "distance_m": route.distance_m,
            "ascent_m": route.ascent_m,
            "descent_m": route.descent_m,
            "duration_s": route.duration_s,
            "total_time_s": None,
        },
        "actual": actual,
        "deviation": _deviation(route.series, track) if track else None,
        "track": (
            {column: track.get(column) for column in ("distance_m", "lat", "lon", "elevation_m")}
            if track
            else None
        ),
    }


# --- A GPX file as a route ---


def _simplify(points: list[TrackPoint], tolerance_m: float) -> list[TrackPoint]:
    """Douglas-Peucker: the points that keep the shape of the line within the tolerance."""
    latitude = math.radians(points[0].lat)
    north = math.pi / 180 * _EARTH_RADIUS_M
    east = north * math.cos(latitude)
    flat = [(point.lon * east, point.lat * north) for point in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (ax, ay), (bx, by) = flat[first], flat[last]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        worst, at = 0.0, None
        for index in range(first + 1, last):
            x, y = flat[index]
            distance = (
                math.hypot(x - ax, y - ay)
                if length == 0
                else abs(dy * (x - ax) - dx * (y - ay)) / length
            )
            if distance > worst:
                worst, at = distance, index
        if at is not None and worst > tolerance_m:
            keep[at] = True
            stack += [(first, at), (at, last)]
    return [point for point, kept in zip(points, keep, strict=True) if kept]


def waypoints_from_gpx(data: bytes) -> list[dict]:
    """The track of a GPX file as waypoints of a route: as few points as keep its shape,
    connected by straight lines, so that the route follows the file and not the paths
    the routing would choose. Raises 422 `invalid_gpx` for anything that is not GPX."""
    points = parse_gpx(data)
    if len(points) == 1:
        points = points * 2
    tolerance = 10.0
    kept = _simplify(points, tolerance)
    # A long or winding track: allow more distance until it fits into one route.
    while len(kept) > MAX_WAYPOINTS:
        tolerance *= 1.6
        kept = _simplify(points, tolerance)
    return [
        {
            "lat": round(point.lat, 6),
            "lon": round(point.lon, 6),
            "name": None,
            "direct": index > 0,
        }
        for index, point in enumerate(kept)
    ]


def route_id_of(db: Session, tour_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(select(RouteTour.route_id).where(RouteTour.tour_id == tour_id))
