"""Public links: management by the owner and the view without login."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import NotFoundError, UnprocessableError
from app.modules.auth import service as auth_service
from app.modules.auth.models import User
from app.modules.protocols import snapshots, track_service
from app.modules.protocols.models import Tour, TourPublicLink
from app.modules.protocols.schemas import (
    PublicFood,
    PublicGear,
    PublicLinkIn,
    PublicLinkOut,
    PublicPeak,
    PublicPoint,
    PublicTourOut,
    PublicWaypoint,
    TrackOut,
)

# Path of the public page in the client and of the API behind it; both carry the token.
PUBLIC_PAGE_PATH = "/p/"
PUBLIC_API_PATH = "/public/tours/"

# Two decimal places are roughly one kilometre.
APPROXIMATE_DECIMALS = 2


def _is_active(link: TourPublicLink) -> bool:
    return link.revoked_at is None and (link.expires_at is None or link.expires_at > utcnow())


def link_out(link: TourPublicLink) -> PublicLinkOut:
    base_url = get_settings().public_base_url.rstrip("/")
    return PublicLinkOut(
        id=link.id,
        url=f"{base_url}{PUBLIC_PAGE_PATH}{link.token}",
        active=_is_active(link),
        created_at=link.created_at,
        expires_at=link.expires_at,
        revoked_at=link.revoked_at,
        hide_exact_start=link.hide_exact_start,
        strip_photo_gps=link.strip_photo_gps,
        show_health_data=link.show_health_data,
    )


def list_links(db: Session, tour: Tour) -> list[TourPublicLink]:
    query = select(TourPublicLink).where(TourPublicLink.tour_id == tour.id)
    return list(db.scalars(query.order_by(TourPublicLink.created_at.desc(), TourPublicLink.id)))


def create_link(db: Session, tour: Tour, user: User, data: PublicLinkIn) -> TourPublicLink:
    if data.expires_at is not None and data.expires_at <= utcnow():
        raise UnprocessableError("expires_at must be in the future")
    link = TourPublicLink(tour_id=tour.id, created_by=user.id, **data.model_dump())
    db.add(link)
    db.commit()
    return link


def revoke_link(db: Session, tour: Tour, link_id: uuid.UUID) -> None:
    link = db.get(TourPublicLink, link_id)
    if link is None or link.tour_id != tour.id:
        raise NotFoundError("Public link not found")
    if link.revoked_at is None:
        link.revoked_at = utcnow()
        db.commit()


def _point(lat, lon, name, approximate: bool) -> PublicPoint | None:
    if lat is None or lon is None:
        return None
    if approximate:
        lat, lon = round(lat, APPROXIMATE_DECIMALS), round(lon, APPROXIMATE_DECIMALS)
    return PublicPoint(
        lat=lat, lon=lon, name=None if approximate else name, approximate=approximate
    )


def _resolve(db: Session, token: str) -> tuple[TourPublicLink, Tour]:
    """Link and tour for a token; every failure looks the same to the caller."""
    not_found = NotFoundError("This link does not exist or is no longer valid")
    try:
        token_value = uuid.UUID(token)
    except ValueError:
        raise not_found from None
    link = db.scalar(select(TourPublicLink).where(TourPublicLink.token == token_value))
    if link is None or not _is_active(link):
        raise not_found
    tour = db.get(Tour, link.tour_id)
    if tour is None or tour.deleted_at is not None:
        raise not_found
    return link, tour


def public_track(db: Session, token: str) -> TrackOut:
    link, tour = _resolve(db, token)
    return track_service.track_out(
        db, tour, health=link.show_health_data, hide_ends=link.hide_exact_start
    )


def public_tour(db: Session, token: str) -> PublicTourOut:
    link, tour = _resolve(db, token)

    computed = snapshots.computed_values(tour)
    health = link.show_health_data
    hide = link.hide_exact_start
    return PublicTourOut(
        title=tour.title,
        summary=tour.summary,
        owner_name=auth_service.get_display_names(db, {tour.owner_id}).get(tour.owner_id),
        start_time=tour.start_time,
        end_time=tour.end_time,
        duration_minutes=tour.duration_minutes
        if tour.duration_minutes is not None
        else computed.duration_minutes,
        pack_weight_start_g=tour.pack_weight_start_g
        if tour.pack_weight_start_g is not None
        else computed.pack_weight_start_g,
        calories_eaten=computed.calories_eaten,
        calories_burned=tour.calories_burned if health else None,
        calories_burned_source=tour.calories_burned_source if health else None,
        start_point=_point(tour.start_lat, tour.start_lon, tour.start_name, hide),
        end_point=_point(tour.end_lat, tour.end_lon, tour.end_name, hide),
        track_source=tour.track_source,
        track_stats=track_service.visible_stats(tour.track_stats, health=health),
        partners=[partner.display_name for partner in snapshots.partner_list(tour)],
        peaks=[PublicPeak(**peak.model_dump(exclude={"id"})) for peak in snapshots.peak_list(tour)],
        waypoints=[
            PublicWaypoint(**waypoint.model_dump(exclude={"id", "track_distance_m"}))
            for waypoint in snapshots.waypoint_list(tour)
        ],
        gear=[
            PublicGear(**entry.model_dump(exclude={"id", "gear_item_id"}))
            for entry in snapshots.gear_list(tour)
        ],
        food=[
            PublicFood(
                name=entry.name,
                amount_g=entry.amount_g,
                kcal=entry.kcal,
                carried=entry.carried,
                eaten=entry.eaten,
            )
            for entry in snapshots.food_list(tour)
        ],
    )
