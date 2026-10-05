import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import DbSession
from app.core.errors import error_responses
from app.modules.auth.deps import CurrentUser
from app.modules.reports import service
from app.modules.reports.schemas import (
    CalendarOut,
    ClimbedPeak,
    SummaryOut,
    WishPeakIn,
    WishPeakOut,
)

router = APIRouter()


@router.get("/summary", response_model=SummaryOut)
def read_summary(user: CurrentUser, db: DbSession):
    """Distance, ascent, descent, days and peaks of all own tours, in total and per year.

    Distance and elevation come from the tracks; a tour without a track counts as a tour
    and a day only.
    """
    return service.summary(db, user)


@router.get("/peaks", response_model=list[ClimbedPeak])
def read_peaks(user: CurrentUser, db: DbSession):
    """The peaks reached on own tours, each once, with every visit. Highest first."""
    return service.climbed_peaks(db, user)


@router.get("/calendar", response_model=CalendarOut)
def read_calendar(
    user: CurrentUser,
    db: DbSession,
    year: Annotated[int | None, Query(ge=1900, le=2200)] = None,
):
    """The days with tours of a year (default: the newest year that has any)."""
    return service.calendar(db, user, year)


@router.get("/tracks")
def read_tracks(user: CurrentUser, db: DbSession) -> dict:
    """All own tracks as one GeoJSON FeatureCollection of thinned-out lines, for a map
    that shows where the user has been (properties: `tour_id`, `title`, `date`)."""
    return service.tracks(db, user)


@router.get("/wishes", response_model=list[WishPeakOut])
def list_wishes(user: CurrentUser, db: DbSession):
    """The peaks the user wishes for. `climbed` is set where an own tour reached a peak
    of that place (within 300 m) or, without coordinates, of that name."""
    return service.list_wishes(db, user)


@router.post("/wishes", response_model=WishPeakOut, status_code=status.HTTP_201_CREATED)
def create_wish(body: WishPeakIn, user: CurrentUser, db: DbSession):
    return service.save_wish(db, user, body)


@router.put("/wishes/{wish_id}", response_model=WishPeakOut, responses=error_responses(404))
def update_wish(wish_id: uuid.UUID, body: WishPeakIn, user: CurrentUser, db: DbSession):
    return service.save_wish(db, user, body, service.get_wish(db, user, wish_id))


@router.delete(
    "/wishes/{wish_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
def delete_wish(wish_id: uuid.UUID, user: CurrentUser, db: DbSession):
    service.delete_wish(db, service.get_wish(db, user, wish_id))
