"""Photos of a tour: upload, EXIF, position along the track, cover and waypoints.

How a photo gets its position (`position_source`):
- `exif_gps`:  the photo carries GPS coordinates; it is attached to the nearest
               point of the track (if that is closer than MAX_DISTANCE_TO_TRACK_M).
- `exif_time`: no GPS, but a capture time inside the time span of the track
               (plus TIME_TOLERANCE_S); the position is interpolated on the track.
               The tour's time offset is added to the capture time first, to
               correct a camera clock that is off or set to local time.
- `manual`:    set by a user on the map (lat/lon) or on the elevation profile
               (distance along the track).
- `none`:      no position yet.

Uploads are validated and re-encoded, which also removes all EXIF data from the
stored images. Capture times without a time zone are taken as UTC.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO

from PIL import Image
from sqlalchemy.orm import Session

from app.core import files
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.images import reencode_image
from app.core.storage import Storage
from app.modules.protocols import history, track
from app.modules.protocols.models import Tour, TourPhoto, TourWaypoint, TrackSeries
from app.modules.protocols.schemas import PhotoOut, PhotoPatch
from app.modules.protocols.sharing import TourAccess

logger = logging.getLogger(__name__)

THUMBNAIL_EDGE_PX = 400
MAX_PHOTOS_PER_UPLOAD = 20
MAX_PHOTOS_PER_TOUR = 500
MAX_DISTANCE_TO_TRACK_M = 1000
TIME_TOLERANCE_S = 600
# Photos closer together than this become one waypoint in "from photos".
WAYPOINT_GROUP_RADIUS_M = 30

EXIF_GPS = "exif_gps"
EXIF_TIME = "exif_time"
MANUAL = "manual"
NONE = "none"

_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
_DATETIME = 0x0132
_DATETIME_ORIGINAL = 0x9003
_OFFSET_TIME_ORIGINAL = 0x9011


# --- EXIF ---


@dataclass(frozen=True)
class ExifInfo:
    taken_at: datetime | None = None
    lat: float | None = None
    lon: float | None = None
    altitude: float | None = None


def _degrees(values, reference) -> float | None:
    degrees, minutes, seconds = (float(value) for value in values)
    result = degrees + minutes / 60 + seconds / 3600
    if isinstance(reference, bytes):
        reference = reference.decode(errors="ignore")
    return -result if str(reference).strip().upper() in ("S", "W") else result


def _capture_time(exif) -> datetime | None:
    details = exif.get_ifd(_EXIF_IFD)
    text = details.get(_DATETIME_ORIGINAL) or exif.get(_DATETIME)
    if not text:
        return None
    time = datetime.strptime(str(text).strip()[:19], "%Y:%m:%d %H:%M:%S")
    offset = str(details.get(_OFFSET_TIME_ORIGINAL) or "").strip()
    if len(offset) == 6 and offset[0] in "+-":
        sign = -1 if offset[0] == "-" else 1
        delta = timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6]))
        return (time - sign * delta).replace(tzinfo=UTC)
    return time.replace(tzinfo=UTC)


def _gps(exif) -> tuple[float | None, float | None, float | None]:
    gps = exif.get_ifd(_GPS_IFD)
    if not gps or 2 not in gps or 4 not in gps:
        return None, None, None
    lat, lon = _degrees(gps[2], gps.get(1, "N")), _degrees(gps[4], gps.get(3, "E"))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None, None, None
    altitude = None
    if 6 in gps:
        altitude = float(gps[6])
        if gps.get(5) in (1, b"\x01"):
            altitude = -altitude
        if not -500 <= altitude <= 9000:
            altitude = None
    return lat, lon, altitude


def read_exif(data: bytes) -> ExifInfo:
    """Capture time and GPS position of an image; anything unreadable is left empty."""
    try:
        with Image.open(BytesIO(data)) as image:
            exif = image.getexif()
    except Exception:  # noqa: BLE001 - the image itself is validated when it is re-encoded
        return ExifInfo()
    taken_at = lat = lon = altitude = None
    try:
        taken_at = _capture_time(exif)
    except (ValueError, TypeError, OverflowError):
        pass
    try:
        lat, lon, altitude = _gps(exif)
    except (ValueError, TypeError, ZeroDivisionError, KeyError):
        pass
    return ExifInfo(taken_at=taken_at, lat=lat, lon=lon, altitude=altitude)


# --- Position along the track ---


def _series(db: Session, tour: Tour) -> dict | None:
    series = db.get(TrackSeries, tour.id)
    return series.data if series is not None else None


def _attach_to_track(photo: TourPhoto, series: dict | None, fallback_elevation=None) -> None:
    """Distance along the track and elevation for the current lat/lon of the photo."""
    photo.track_distance_m = None
    photo.elevation_m = fallback_elevation
    if series is None or photo.lat is None:
        return
    position = track.nearest_on_series(series, photo.lat, photo.lon)
    if position is not None and position.offset_m <= MAX_DISTANCE_TO_TRACK_M:
        photo.track_distance_m = position.distance_m
        if position.elevation_m is not None:
            photo.elevation_m = position.elevation_m


def locate(photo: TourPhoto, series: dict | None, time_offset_s: int) -> None:
    """Find the position of a photo automatically; manual positions are kept."""
    if photo.position_source == MANUAL:
        _attach_to_track(photo, series, photo.exif_altitude)
        return
    if photo.exif_lat is not None:
        photo.lat, photo.lon = photo.exif_lat, photo.exif_lon
        photo.position_source = EXIF_GPS
        _attach_to_track(photo, series, photo.exif_altitude)
        return
    photo.lat = photo.lon = photo.track_distance_m = photo.elevation_m = None
    photo.position_source = NONE
    if series is None or photo.taken_at is None:
        return
    moment = photo.taken_at + timedelta(seconds=time_offset_s)
    position = track.position_at_time(series, moment, TIME_TOLERANCE_S)
    if position is not None:
        photo.lat, photo.lon = position.lat, position.lon
        photo.track_distance_m = position.distance_m
        photo.elevation_m = position.elevation_m
        photo.position_source = EXIF_TIME


def relocate_all(db: Session, tour: Tour) -> None:
    """Called when the track or the time offset changed. Does not commit."""
    series = _series(db, tour)
    for photo in tour.photos:
        locate(photo, series, tour.photo_time_offset_seconds)


def locate_waypoint(db: Session, tour: Tour, waypoint: TourWaypoint) -> None:
    series = _series(db, tour)
    waypoint.track_distance_m = None
    if series is None:
        return
    position = track.nearest_on_series(series, waypoint.lat, waypoint.lon)
    if position is not None and position.offset_m <= MAX_DISTANCE_TO_TRACK_M:
        waypoint.track_distance_m = position.distance_m
        if waypoint.elevation_m is None:
            waypoint.elevation_m = position.elevation_m


# --- Output ---


def ordered(tour: Tour) -> list[TourPhoto]:
    """Gallery order: along the track, photos without position at the end."""
    far_future = datetime.max.replace(tzinfo=UTC)
    return sorted(
        tour.photos,
        key=lambda photo: (
            photo.track_distance_m is None,
            photo.track_distance_m or 0,
            photo.taken_at or far_future,
            photo.sort_order,
            str(photo.id),
        ),
    )


def photo_out(tour: Tour, photo: TourPhoto) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        caption=photo.caption,
        taken_at=photo.taken_at,
        lat=photo.lat,
        lon=photo.lon,
        position_source=photo.position_source,
        track_distance_m=photo.track_distance_m,
        elevation_m=photo.elevation_m,
        waypoint_id=photo.waypoint_id,
        is_cover=tour.cover_photo_id == photo.id,
    )


def photos_out(tour: Tour) -> list[PhotoOut]:
    return [photo_out(tour, photo) for photo in ordered(tour)]


def get_photo(tour: Tour, photo_id: uuid.UUID) -> TourPhoto:
    for photo in tour.photos:
        if photo.id == photo_id:
            return photo
    raise NotFoundError("Photo not found")


def image(db: Session, storage: Storage, photo: TourPhoto, size: str):
    file_id = photo.thumb_file_id if size == "thumb" else photo.file_id
    return files.load_file(db, storage, file_id)


# --- Changes ---


def add_photos(
    db: Session, storage: Storage, access: TourAccess, uploads: list[bytes]
) -> list[TourPhoto]:
    tour = access.tour
    if not uploads:
        raise UnprocessableError("No file was sent")
    if len(uploads) > MAX_PHOTOS_PER_UPLOAD:
        raise UnprocessableError(
            f"At most {MAX_PHOTOS_PER_UPLOAD} photos per request", code="too_many_photos"
        )
    if len(tour.photos) + len(uploads) > MAX_PHOTOS_PER_TOUR:
        raise ConflictError(
            f"A tour holds at most {MAX_PHOTOS_PER_TOUR} photos", code="too_many_photos"
        )
    max_edge = get_settings().image_max_edge_px
    # Check and encode everything first, so that one bad file rejects the whole upload.
    prepared = []
    for data in uploads:
        exif = read_exif(data)
        full, mime = reencode_image(data, max_edge=max_edge)
        thumb, _ = reencode_image(full, max_edge=THUMBNAIL_EDGE_PX)
        prepared.append((exif, full, thumb, mime))

    series = _series(db, tour)
    next_order = max((photo.sort_order for photo in tour.photos), default=-1) + 1
    added = []
    for position, (exif, full, thumb, mime) in enumerate(prepared):
        store = {"owner_id": tour.owner_id, "mime": mime, "extension": "jpg"}
        photo = TourPhoto(
            id=uuid.uuid4(),
            file_id=files.store_file(db, storage, data=full, **store).id,
            thumb_file_id=files.store_file(db, storage, data=thumb, **store).id,
            added_by=access.user.id,
            taken_at=exif.taken_at,
            exif_lat=exif.lat,
            exif_lon=exif.lon,
            exif_altitude=exif.altitude,
            position_source=NONE,
            sort_order=next_order + position,
        )
        locate(photo, series, tour.photo_time_offset_seconds)
        tour.photos.append(photo)
        added.append(photo)
    history.record_change(db, tour, access.user, history.UPDATED)
    return added


def update_photo(db: Session, access: TourAccess, photo: TourPhoto, data: PhotoPatch) -> None:
    tour = access.tour
    changes = data.model_dump(exclude_unset=True)
    series = _series(db, tour)
    if "caption" in changes:
        photo.caption = changes["caption"]
    if "waypoint_id" in changes:
        waypoint_id = changes["waypoint_id"]
        if waypoint_id is not None and not any(w.id == waypoint_id for w in tour.waypoints):
            raise UnprocessableError("Unknown waypoint", code="unknown_waypoint")
        photo.waypoint_id = waypoint_id
    if changes.get("lat") is not None:
        photo.lat, photo.lon = changes["lat"], changes["lon"]
        photo.position_source = MANUAL
        _attach_to_track(photo, series, photo.exif_altitude)
    elif changes.get("track_distance_m") is not None:
        position = (
            track.position_at_distance(series, changes["track_distance_m"]) if series else None
        )
        if position is None:
            raise UnprocessableError("The tour has no track", code="no_track")
        photo.lat, photo.lon = position.lat, position.lon
        photo.track_distance_m, photo.elevation_m = position.distance_m, position.elevation_m
        photo.position_source = MANUAL
    elif changes.get("auto_position"):
        photo.position_source = NONE
        locate(photo, series, tour.photo_time_offset_seconds)
    if changes.get("is_cover") is True:
        tour.cover_photo_id = photo.id
    elif changes.get("is_cover") is False and tour.cover_photo_id == photo.id:
        tour.cover_photo_id = None
    history.record_change(db, tour, access.user, history.UPDATED)


def _delete_files(db: Session, storage: Storage, file_ids: list) -> None:
    for file_id in file_ids:
        files.delete_file(db, storage, file_id)


def delete_photo(db: Session, storage: Storage, access: TourAccess, photo: TourPhoto) -> None:
    """Remove the photo and its files; the history keeps only its metadata."""
    tour = access.tour
    file_ids = [photo.file_id, photo.thumb_file_id]
    if tour.cover_photo_id == photo.id:
        tour.cover_photo_id = None
    tour.photos.remove(photo)
    history.record_change(db, tour, access.user, history.UPDATED)
    _delete_files(db, storage, file_ids)


def delete_all_files(db: Session, storage: Storage, tour: Tour) -> None:
    """Remove all photos of a tour including their files (when the tour is deleted)."""
    file_ids = [
        file_id for photo in tour.photos for file_id in (photo.file_id, photo.thumb_file_id)
    ]
    tour.photos = []
    tour.cover_photo_id = None
    db.commit()
    _delete_files(db, storage, file_ids)


def set_time_offset(db: Session, access: TourAccess, seconds: int) -> None:
    access.tour.photo_time_offset_seconds = seconds
    relocate_all(db, access.tour)
    history.record_change(db, access.tour, access.user, history.UPDATED)


def waypoints_from_photos(db: Session, access: TourAccess) -> list[TourWaypoint]:
    """Create waypoints from photos with GPS that are not attached to a waypoint yet."""
    tour = access.tour
    created: list[TourWaypoint] = []
    candidates = [
        photo
        for photo in ordered(tour)
        if photo.position_source == EXIF_GPS and photo.waypoint_id is None
    ]
    for photo in candidates:
        waypoint = next(
            (
                w
                for w in created
                if track.haversine_m(w.lat, w.lon, photo.lat, photo.lon) <= WAYPOINT_GROUP_RADIUS_M
            ),
            None,
        )
        if waypoint is None:
            waypoint = TourWaypoint(
                id=uuid.uuid4(),
                name=photo.caption or f"Foto {len(created) + 1}",
                icon="photo",
                lat=photo.lat,
                lon=photo.lon,
                elevation_m=photo.elevation_m,
                track_distance_m=photo.track_distance_m,
            )
            tour.waypoints.append(waypoint)
            created.append(waypoint)
            # The waypoint must exist before a photo can refer to it.
            db.flush()
        photo.waypoint_id = waypoint.id
    if created:
        history.record_change(db, tour, access.user, history.UPDATED)
    return created
