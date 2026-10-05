import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.fields import Name, optional_text
from app.modules.protocols.schemas import Latitude, Longitude


class Totals(BaseModel):
    tours: int
    tours_with_track: int = Field(description="Only these count for distance and elevation")
    days: int = Field(description="Days with at least one tour")
    distance_m: float
    ascent_m: float
    descent_m: float
    moving_time_s: float = Field(description="Time in motion, where the track has times")
    peaks: int = Field(description="Different peaks reached")


class YearTotals(Totals):
    year: int


class SummaryOut(BaseModel):
    """What all own tours add up to; tours without a date count in the total only."""

    total: Totals
    years: list[YearTotals] = Field(description="Newest first")


class PeakVisit(BaseModel):
    tour_id: uuid.UUID
    title: str
    date: datetime | None


class ClimbedPeak(BaseModel):
    name: str
    elevation_m: int | None
    lat: float | None
    lon: float | None
    count: int
    first: datetime | None
    last: datetime | None
    visits: list[PeakVisit] = Field(description="Newest first")


class CalendarDay(BaseModel):
    date: date
    tours: int
    distance_m: float
    ascent_m: float
    tour_ids: list[uuid.UUID]


class CalendarOut(BaseModel):
    year: int
    years: list[int] = Field(description="All years that have tours, newest first")
    days: list[CalendarDay] = Field(description="Only days with a tour")


class WishPeakIn(BaseModel):
    name: Name
    elevation_m: int | None = Field(default=None, ge=-500, le=9000)
    lat: Latitude | None = None
    lon: Longitude | None = None
    note: optional_text(2000) = None


class WishPeakOut(WishPeakIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    climbed: bool = Field(
        default=False, description="A tour of the user reached a peak of that name or place"
    )
    climbed_on: datetime | None = None
