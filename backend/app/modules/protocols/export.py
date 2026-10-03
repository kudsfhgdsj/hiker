"""JSON export of a tour in a versioned format."""

import re
import unicodedata

from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.modules.auth import service as auth_service
from app.modules.protocols import photos, snapshots, track_service
from app.modules.protocols.schemas import ExportedTour, ExportedTrack, GeoPoint, TourExport
from app.modules.protocols.sharing import TourAccess

# Version 1: tour, partners, peaks, waypoints, gear, food, track statistics.
# Weather and photos are present as empty lists until those features exist.
SCHEMA_VERSION = 1


def _point(lat, lon, name) -> GeoPoint | None:
    if lat is None or lon is None:
        return None
    return GeoPoint(lat=lat, lon=lon, name=name)


def export_tour(db: Session, access: TourAccess) -> TourExport:
    tour = access.tour
    computed = snapshots.computed_values(tour)
    duration = tour.duration_minutes
    pack_weight = tour.pack_weight_start_g
    return TourExport(
        schema_version=SCHEMA_VERSION,
        exported_at=utcnow(),
        tour=ExportedTour(
            id=tour.id,
            title=tour.title,
            summary=tour.summary,
            owner_name=auth_service.get_display_names(db, {tour.owner_id}).get(tour.owner_id),
            start_time=tour.start_time,
            end_time=tour.end_time,
            duration_minutes=duration if duration is not None else computed.duration_minutes,
            pack_weight_start_g=pack_weight
            if pack_weight is not None
            else computed.pack_weight_start_g,
            calories_eaten=computed.calories_eaten,
            calories_burned=tour.calories_burned,
            calories_burned_source=tour.calories_burned_source,
            start_point=_point(tour.start_lat, tour.start_lon, tour.start_name),
            end_point=_point(tour.end_lat, tour.end_lon, tour.end_name),
            points_source=tour.points_source,
            version=tour.version,
            created_at=tour.created_at,
            updated_at=tour.updated_at,
        ),
        partners=[partner.display_name for partner in snapshots.partner_list(tour)],
        peaks=snapshots.peak_list(tour),
        waypoints=snapshots.waypoint_list(tour),
        gear=snapshots.gear_list(tour),
        food=snapshots.food_list(tour),
        track=ExportedTrack(
            source=tour.track_source,
            stats=track_service.visible_stats(tour.track_stats, health=access.is_owner),
            file=None,
        ),
        weather=[],
        photos=photos.photos_out(tour),
    )


def export_filename(title: str) -> str:
    """An ASCII file name derived from the title, safe for a Content-Disposition header."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:60]
    return f"tour-{slug or 'export'}.json"
