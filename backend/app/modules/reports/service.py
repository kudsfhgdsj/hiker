"""Adds up the own tours of a user. Tours shared by others do not count: these are
the user's own days out."""

import math
import unicodedata
import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import NotFoundError
from app.modules.auth.models import User
from app.modules.protocols.models import Tour, TourPeak, TrackSeries
from app.modules.reports.models import WishPeak
from app.modules.reports.schemas import WishPeakIn

# Two entries are the same peak if they lie this close, whatever they are called.
SAME_PEAK_M = 300
# Points of one track on the map of all tracks.
TRACK_POINTS = 150
# A tour counts for at most this many days in the calendar.
MAX_TOUR_DAYS = 60


def _tours(db: Session, user: User) -> list[Tour]:
    return list(
        db.scalars(
            select(Tour)
            .where(Tour.owner_id == user.id, Tour.deleted_at.is_(None))
            .order_by(Tour.start_time)
        )
    )


def _fold(name: str) -> str:
    text = unicodedata.normalize("NFKD", name.casefold().replace("ß", "ss"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    east = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(lat2 - lat1, east) * 111_320


def _days_of(tour: Tour) -> list[date]:
    """The days a tour covers: from its start to its end."""
    if tour.start_time is None:
        return []
    first = tour.start_time.date()
    last = tour.end_time.date() if tour.end_time else first
    count = min(max((last - first).days, 0), MAX_TOUR_DAYS - 1)
    return [first + timedelta(days=offset) for offset in range(count + 1)]


def _figure(tour: Tour, name: str) -> float:
    value = (tour.track_stats or {}).get(name)
    return float(value) if isinstance(value, (int, float)) else 0.0


def climbed_peaks(db: Session, user: User) -> list[dict]:
    """The peaks of all own tours, each once: entries of the same name or the same
    place are one peak. The highest first."""
    tours = {tour.id: tour for tour in _tours(db, user)}
    if not tours:
        return []
    entries = db.scalars(select(TourPeak).where(TourPeak.tour_id.in_(tours))).all()
    peaks: list[dict] = []
    for entry in entries:
        tour = tours[entry.tour_id]
        when = entry.reached_at or tour.start_time
        located = entry.lat is not None and entry.lon is not None
        known = None
        for peak in peaks:
            same_name = peak["_key"] == _fold(entry.name)
            both = located and peak["lat"] is not None
            near = (
                both and _distance_m(entry.lat, entry.lon, peak["lat"], peak["lon"]) <= SAME_PEAK_M
            )
            # The same name far apart is another mountain (there are many "Hochkopf").
            if near or (same_name and not both):
                known = peak
                break
        if known is None:
            known = {
                "_key": _fold(entry.name),
                "name": entry.name,
                "elevation_m": entry.elevation_m,
                "lat": entry.lat,
                "lon": entry.lon,
                "visits": {},
            }
            peaks.append(known)
        if known["elevation_m"] is None:
            known["elevation_m"] = entry.elevation_m
        if known["lat"] is None and located:
            known["lat"], known["lon"] = entry.lat, entry.lon
        # Twice on the same tour is one visit.
        known["visits"].setdefault(tour.id, {"tour_id": tour.id, "title": tour.title, "date": when})
    result = []
    for peak in peaks:
        visits = sorted(
            peak["visits"].values(),
            key=lambda visit: (visit["date"] is not None, visit["date"]),
            reverse=True,
        )
        dates = [visit["date"] for visit in visits if visit["date"] is not None]
        result.append(
            {
                "name": peak["name"],
                "elevation_m": peak["elevation_m"],
                "lat": peak["lat"],
                "lon": peak["lon"],
                "count": len(visits),
                "first": min(dates) if dates else None,
                "last": max(dates) if dates else None,
                "visits": visits,
            }
        )
    return sorted(result, key=lambda peak: (-(peak["elevation_m"] or 0), peak["name"]))


def summary(db: Session, user: User) -> dict:
    tours = _tours(db, user)
    peaks = climbed_peaks(db, user)

    def totals(chosen: list[Tour], year: int | None) -> dict:
        days = {day for tour in chosen for day in _days_of(tour) if year in (None, day.year)}
        reached = [
            peak
            for peak in peaks
            if year is None
            or any(
                visit["date"] is not None and visit["date"].year == year for visit in peak["visits"]
            )
        ]
        return {
            "tours": len(chosen),
            "tours_with_track": sum(tour.track_stats is not None for tour in chosen),
            "days": len(days),
            "distance_m": round(sum(_figure(tour, "distance_m") for tour in chosen)),
            "ascent_m": round(sum(_figure(tour, "ascent_m") for tour in chosen)),
            "descent_m": round(sum(_figure(tour, "descent_m") for tour in chosen)),
            "moving_time_s": round(sum(_figure(tour, "moving_time_s") for tour in chosen)),
            "peaks": len(reached),
        }

    by_year: dict[int, list[Tour]] = defaultdict(list)
    for tour in tours:
        if tour.start_time is not None:
            by_year[tour.start_time.year].append(tour)
    return {
        "total": totals(tours, None),
        "years": [
            {"year": year, **totals(by_year[year], year)} for year in sorted(by_year, reverse=True)
        ],
    }


def calendar(db: Session, user: User, year: int | None) -> dict:
    """The days with tours of one year; without a year the newest one that has any."""
    tours = _tours(db, user)
    years = sorted({day.year for tour in tours for day in _days_of(tour)}, reverse=True)
    if year is None:
        year = years[0] if years else utcnow().year
    days: dict[date, dict] = {}
    for tour in tours:
        covered = _days_of(tour)
        for day in covered:
            if day.year != year:
                continue
            entry = days.setdefault(
                day, {"date": day, "tours": 0, "distance_m": 0.0, "ascent_m": 0.0, "tour_ids": []}
            )
            entry["tours"] += 1
            entry["tour_ids"].append(tour.id)
            # A tour of several days spreads its figures evenly over them.
            entry["distance_m"] += _figure(tour, "distance_m") / len(covered)
            entry["ascent_m"] += _figure(tour, "ascent_m") / len(covered)
    for entry in days.values():
        entry["distance_m"] = round(entry["distance_m"])
        entry["ascent_m"] = round(entry["ascent_m"])
    return {"year": year, "years": years, "days": [days[day] for day in sorted(days)]}


def tracks(db: Session, user: User) -> dict:
    """All own tracks as GeoJSON lines, thinned out: for one map of everything walked."""
    tours = {tour.id: tour for tour in _tours(db, user)}
    features = []
    if tours:
        rows = db.scalars(select(TrackSeries).where(TrackSeries.tour_id.in_(tours))).all()
        for series in rows:
            lat, lon = series.data.get("lat") or [], series.data.get("lon") or []
            if len(lat) < 2:
                continue
            step = max(1, math.ceil(len(lat) / TRACK_POINTS))
            picked = list(range(0, len(lat), step))
            if picked[-1] != len(lat) - 1:
                picked.append(len(lat) - 1)
            tour = tours[series.tour_id]
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "tour_id": str(tour.id),
                        "title": tour.title,
                        "date": tour.start_time.date().isoformat() if tour.start_time else None,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[round(lon[i], 5), round(lat[i], 5)] for i in picked],
                    },
                }
            )
    return {"type": "FeatureCollection", "features": features}


# --- Wish peaks ---


def list_wishes(db: Session, user: User) -> list[dict]:
    """The wished-for peaks, with a mark where a tour already reached one of them."""
    climbed = climbed_peaks(db, user)
    wishes = db.scalars(
        select(WishPeak)
        .where(WishPeak.owner_id == user.id, WishPeak.deleted_at.is_(None))
        .order_by(WishPeak.name)
    ).all()
    result = []
    for wish in wishes:
        match = None
        for peak in climbed:
            both = wish.lat is not None and wish.lon is not None and peak["lat"] is not None
            if both:
                same = _distance_m(wish.lat, wish.lon, peak["lat"], peak["lon"]) <= SAME_PEAK_M
            else:
                same = _fold(peak["name"]) == _fold(wish.name)
            if same:
                match = peak
                break
        result.append(
            {
                "id": wish.id,
                "name": wish.name,
                "elevation_m": wish.elevation_m,
                "lat": wish.lat,
                "lon": wish.lon,
                "note": wish.note,
                "created_at": wish.created_at,
                "climbed": match is not None,
                "climbed_on": match["last"] if match else None,
            }
        )
    # Still to do first, the highest on top.
    return sorted(result, key=lambda w: (w["climbed"], -(w["elevation_m"] or 0), w["name"]))


def get_wish(db: Session, user: User, wish_id: uuid.UUID) -> WishPeak:
    wish = db.get(WishPeak, wish_id)
    if wish is None or wish.owner_id != user.id or wish.deleted_at is not None:
        raise NotFoundError("Wish peak not found")
    return wish


def save_wish(db: Session, user: User, data: WishPeakIn, wish: WishPeak | None = None) -> WishPeak:
    if wish is None:
        wish = WishPeak(owner_id=user.id)
        db.add(wish)
    for name, value in data.model_dump().items():
        setattr(wish, name, value)
    db.commit()
    return wish


def delete_wish(db: Session, wish: WishPeak) -> None:
    wish.deleted_at = utcnow()
    db.commit()
