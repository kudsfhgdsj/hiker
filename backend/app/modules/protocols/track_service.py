"""Tracks of tours: storing the GPX file, statistics, series and start/end point."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core import files
from app.core.db import utcnow
from app.core.errors import NotFoundError
from app.core.storage import Storage
from app.modules.auth import service as auth_service
from app.modules.auth.models import User
from app.modules.protocols import history, track
from app.modules.protocols.elevation import ElevationSource, ElevationSourceError, lookup_along
from app.modules.protocols.models import TRACK_NONE, Tour, TrackSeries
from app.modules.protocols.schemas import DrawnTrackIn, TrackOut
from app.modules.protocols.sharing import TourAccess
from app.modules.protocols.track import TrackPoint

logger = logging.getLogger(__name__)

GPX_MIME = "application/gpx+xml"
TRACK_DEVICE = "device"
TRACK_DRAWN = "drawn"
POINTS_FROM_GPX = "gpx"
# Radius cut off at both ends of the track when a public link hides the exact start.
HIDDEN_START_RADIUS_M = 500
# Heart rate is health data and only shown to the owner unless enabled explicitly.
HEALTH_STATS = ("heart_rate",)
HEALTH_COLUMNS = ("heart_rate",)


def _max_heart_rate(db: Session, user: User) -> int | None:
    """From the profile, otherwise the rule of thumb 220 minus age."""
    profile = auth_service.get_profile(db, user)
    if profile is None:
        return None
    if profile.max_heart_rate:
        return profile.max_heart_rate
    if profile.birth_year:
        return 220 - (utcnow().year - profile.birth_year)
    return None


def _fill_elevations(points: list[TrackPoint], source: ElevationSource) -> tuple[list, str | None]:
    """Use the elevations of the track; look them up only if the track has none at all."""
    if any(point.ele is not None for point in points):
        return points, "track"
    try:
        elevations = lookup_along(source, [(point.lat, point.lon) for point in points])
    except ElevationSourceError as exc:
        # Tolerant: the track is still usable, only its elevation statistics stay empty.
        logger.warning("Elevation lookup failed: %s", exc)
        return points, None
    if all(elevation is None for elevation in elevations):
        return points, None
    return track.with_elevations(points, elevations), "open-meteo"


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _derive(db: Session, tour: Tour, user: User, points: list[TrackPoint], elevation: str | None):
    """Write everything that is derived from the points of the track into the tour."""
    stats = track.compute_stats(points, _max_heart_rate(db, user))
    stats["elevation_source"] = elevation
    tour.track_stats = stats
    tour.start_lat, tour.start_lon, tour.start_name = points[0].lat, points[0].lon, None
    tour.end_lat, tour.end_lon, tour.end_name = points[-1].lat, points[-1].lon, None
    tour.points_source = POINTS_FROM_GPX
    series = db.get(TrackSeries, tour.id) or TrackSeries(tour_id=tour.id)
    series.data = track.build_series(points)
    series.point_count = len(series.data["lat"])
    db.add(series)
    return stats


def _store(
    db: Session,
    storage: Storage,
    access: TourAccess,
    data: bytes,
    points: list[TrackPoint],
    source: str,
    elevation: str | None,
) -> None:
    tour = access.tour
    stats = _derive(db, tour, access.user, points, elevation)
    # The time window of the tour follows the track if it has time stamps.
    if stats["start_time"] is not None:
        tour.start_time = _parse_time(stats["start_time"])
        tour.end_time = _parse_time(stats["end_time"])
    # Earlier files stay in the storage: revisions of the history refer to them.
    file = files.store_file(
        db, storage, owner_id=tour.owner_id, data=data, mime=GPX_MIME, extension="gpx"
    )
    tour.gpx_file_id = file.id
    tour.track_source = source
    history.record_change(db, tour, access.user, history.UPDATED)


def upload_gpx(
    db: Session, storage: Storage, elevations: ElevationSource, access: TourAccess, data: bytes
) -> None:
    """Store an uploaded GPX file unchanged and evaluate it."""
    points, elevation = _fill_elevations(track.parse_gpx(data), elevations)
    _store(db, storage, access, data, points, TRACK_DEVICE, elevation)


def save_drawn_track(
    db: Session,
    storage: Storage,
    elevations: ElevationSource,
    access: TourAccess,
    body: DrawnTrackIn,
) -> None:
    """Turn the points drawn on the map into a GPX file, with elevations looked up."""
    points = [TrackPoint(lat=p.lat, lon=p.lon, ele=p.elevation_m, time=p.time) for p in body.points]
    points, elevation = _fill_elevations(points, elevations)
    data = track.points_to_gpx(points, access.tour.title)
    _store(db, storage, access, data, points, TRACK_DRAWN, elevation)


def _clear(db: Session, tour: Tour) -> None:
    series = db.get(TrackSeries, tour.id)
    if series is not None:
        db.delete(series)
    tour.gpx_file_id = None
    tour.track_source = TRACK_NONE
    tour.track_stats = None
    if tour.points_source == POINTS_FROM_GPX:
        tour.start_lat = tour.start_lon = tour.start_name = None
        tour.end_lat = tour.end_lon = tour.end_name = None
        tour.points_source = None


def remove_track(db: Session, access: TourAccess) -> None:
    _clear(db, access.tour)
    history.record_change(db, access.tour, access.user, history.UPDATED)


def rebuild_from_file(db: Session, storage: Storage, tour: Tour, user: User) -> None:
    """Derive statistics and series again from the stored GPX file (after a restore)."""
    if tour.gpx_file_id is None:
        _clear(db, tour)
        return
    try:
        _file, data = files.load_file(db, storage, tour.gpx_file_id)
    except NotFoundError:
        _clear(db, tour)
        return
    points = track.parse_gpx(data)
    elevation = "track" if any(point.ele is not None for point in points) else None
    _derive(db, tour, user, points, elevation)


def gpx_file(db: Session, storage: Storage, tour: Tour) -> bytes:
    _file, data = files.load_file(db, storage, tour.gpx_file_id)
    return data


# --- Output ---


def visible_stats(stats: dict | None, *, health: bool) -> dict | None:
    if stats is None or health:
        return stats
    return {key: value for key, value in stats.items() if key not in HEALTH_STATS}


def track_out(db: Session, tour: Tour, *, health: bool, hide_ends: bool = False) -> TrackOut:
    series = db.get(TrackSeries, tour.id)
    data = dict(series.data) if series is not None else None
    if data is not None:
        if hide_ends:
            data = track.trim_series_ends(data, HIDDEN_START_RADIUS_M)
        if not health:
            data = data | dict.fromkeys(HEALTH_COLUMNS)
    return TrackOut(
        source=tour.track_source,
        stats=visible_stats(tour.track_stats, health=health),
        series=data,
    )
