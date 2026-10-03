"""Weather of a tour at start, summit and end, from Open-Meteo behind an adapter.

Sample points:
- start / end: start and end point of the tour at its start and end time
- summit:      the highest point of the track at the time the track reached it;
               without a track, the first peak of the tour that has coordinates
- manual:      a point and time given by the user

Open-Meteo has two services: the archive for the past and the forecast for
recent days and the future. The archive lags a few days behind, so it is used
for dates older than ARCHIVE_AFTER_DAYS. Weather is derived data and not part
of the tour history.
"""

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Protocol

import httpx2
from fastapi import Depends
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError, UnprocessableError
from app.modules.protocols.models import Tour, TourWeather, TrackSeries
from app.modules.protocols.schemas import ManualWeatherIn, WeatherOut

logger = logging.getLogger(__name__)

ARCHIVE_AFTER_DAYS = 5
START, SUMMIT, END, MANUAL = "start", "summit", "end", "manual"
AUTOMATIC_SAMPLES = (START, SUMMIT, END)

# Open-Meteo variable -> our field
HOURLY_FIELDS = {
    "temperature_2m": "temperature_c",
    "apparent_temperature": "apparent_temperature_c",
    "wind_speed_10m": "wind_speed_kmh",
    "wind_gusts_10m": "wind_gusts_kmh",
    "precipitation": "precipitation_mm",
    "cloud_cover": "cloud_cover_pct",
    "weather_code": "weather_code",
}
# Only the forecast service knows the freezing level.
FORECAST_FIELDS = {"freezing_level_height": "freezing_level_m"}


class WeatherUnavailableError(AppError):
    status_code = 502
    code = "source_unavailable"


class WeatherSourceError(Exception):
    """The weather service could not be reached or answered with garbage."""


@dataclass(frozen=True)
class WeatherValues:
    source: str
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    wind_speed_kmh: float | None = None
    wind_gusts_kmh: float | None = None
    precipitation_mm: float | None = None
    cloud_cover_pct: float | None = None
    freezing_level_m: float | None = None
    weather_code: int | None = None


class WeatherSource(Protocol):
    def values_at(
        self, lat: float, lon: float, elevation_m: float | None, time: datetime
    ) -> WeatherValues | None:
        """Weather for the hour of `time`; None if the service has no data for it."""


class DisabledWeatherSource:
    def values_at(self, lat, lon, elevation_m, time) -> WeatherValues | None:
        raise WeatherSourceError("weather lookup is disabled")


class OpenMeteoWeatherSource:
    def __init__(
        self,
        forecast_url: str,
        archive_url: str,
        user_agent: str,
        *,
        timeout: float = 5.0,
        transport: httpx2.BaseTransport | None = None,
    ):
        self._forecast_url = forecast_url
        self._archive_url = archive_url
        self._client = httpx2.Client(
            headers={"User-Agent": user_agent}, timeout=timeout, transport=transport
        )

    def values_at(
        self, lat: float, lon: float, elevation_m: float | None, time: datetime
    ) -> WeatherValues | None:
        time = time.astimezone(UTC)
        use_archive = time.date() < (utcnow() - timedelta(days=ARCHIVE_AFTER_DAYS)).date()
        fields = HOURLY_FIELDS if use_archive else HOURLY_FIELDS | FORECAST_FIELDS
        params = {
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "hourly": ",".join(fields),
            "start_date": time.date().isoformat(),
            "end_date": time.date().isoformat(),
            "timezone": "UTC",
        }
        if elevation_m is not None:
            # Temperatures are corrected to the real elevation of the point.
            params["elevation"] = f"{elevation_m:.0f}"
        url = self._archive_url if use_archive else self._forecast_url
        try:
            response = self._client.get(url, params=params)
            if response.status_code == 400:
                # Date outside the range the service covers.
                return None
            response.raise_for_status()
            hourly = response.json()["hourly"]
            index = hourly["time"].index(time.strftime("%Y-%m-%dT%H:00"))
            values = {ours: hourly[theirs][index] for theirs, ours in fields.items()}
        except (httpx2.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
            raise WeatherSourceError(str(exc)) from exc
        if values.get("temperature_c") is None:
            return None
        if values.get("weather_code") is not None:
            values["weather_code"] = int(values["weather_code"])
        source = "open-meteo-archive" if use_archive else "open-meteo-forecast"
        return WeatherValues(source=source, **values)


@lru_cache
def get_weather_source() -> WeatherSource:
    settings = get_settings()
    if not settings.open_meteo_forecast_url or not settings.open_meteo_archive_url:
        return DisabledWeatherSource()
    return OpenMeteoWeatherSource(
        settings.open_meteo_forecast_url,
        settings.open_meteo_archive_url,
        f"hiker/{__version__} ({settings.public_base_url})",
    )


Weather = Annotated[WeatherSource, Depends(get_weather_source)]


# --- Sample points ---


@dataclass(frozen=True)
class Sample:
    kind: str
    lat: float
    lon: float
    elevation_m: float | None
    time: datetime


def _middle(tour: Tour) -> datetime | None:
    if tour.start_time and tour.end_time:
        return tour.start_time + (tour.end_time - tour.start_time) / 2
    return tour.start_time or tour.end_time


def _summit(tour: Tour, series: dict | None) -> Sample | None:
    elevations = (series or {}).get("elevation_m")
    if elevations and any(elevation is not None for elevation in elevations):
        index = max(
            range(len(elevations)),
            key=lambda i: elevations[i] if elevations[i] is not None else float("-inf"),
        )
        times = series.get("time")
        time = _middle(tour)
        if times and times[index]:
            time = datetime.fromisoformat(times[index].replace("Z", "+00:00"))
        if time is None:
            return None
        return Sample(SUMMIT, series["lat"][index], series["lon"][index], elevations[index], time)
    for peak in tour.peaks:
        time = peak.reached_at or _middle(tour)
        if peak.lat is not None and time is not None:
            return Sample(SUMMIT, peak.lat, peak.lon, peak.elevation_m, time)
    return None


def samples(db: Session, tour: Tour) -> list[Sample]:
    """The automatic sample points that can be derived from the tour right now."""
    series_row = db.get(TrackSeries, tour.id)
    series = series_row.data if series_row is not None else None
    elevations = (series or {}).get("elevation_m") or [None]
    result = []
    if tour.start_lat is not None and tour.start_time is not None:
        result.append(Sample(START, tour.start_lat, tour.start_lon, elevations[0], tour.start_time))
    summit = _summit(tour, series)
    if summit is not None:
        result.append(summit)
    if tour.end_lat is not None and tour.end_time is not None:
        result.append(Sample(END, tour.end_lat, tour.end_lon, elevations[-1], tour.end_time))
    return result


def _matches(row: TourWeather, sample: Sample) -> bool:
    return (
        abs(row.lat - sample.lat) < 1e-5
        and abs(row.lon - sample.lon) < 1e-5
        and row.time == sample.time
    )


def is_outdated(db: Session, tour: Tour) -> bool:
    """True if points or times changed since the weather was fetched (offer a new fetch)."""
    rows = {row.sample_point: row for row in tour.weather if row.sample_point != MANUAL}
    current = {sample.kind: sample for sample in samples(db, tour)}
    if set(rows) != set(current):
        return bool(rows) or bool(current)
    return any(not _matches(rows[kind], sample) for kind, sample in current.items())


# --- Fetching ---


def _store(tour: Tour, sample: Sample, values: WeatherValues) -> None:
    row = next((row for row in tour.weather if row.sample_point == sample.kind), None)
    if row is None:
        row = TourWeather(id=uuid.uuid4(), sample_point=sample.kind)
        tour.weather.append(row)
    row.lat, row.lon, row.elevation_m, row.time = (
        sample.lat,
        sample.lon,
        sample.elevation_m,
        sample.time,
    )
    for field, value in asdict(values).items():
        setattr(row, field, value)
    row.fetched_at = utcnow()


def fetch(
    db: Session, source: WeatherSource, tour: Tour, manual: ManualWeatherIn | None = None
) -> None:
    """Fetch the weather for all sample points again and replace what is stored."""
    wanted = samples(db, tour)
    if manual is not None:
        wanted.append(Sample(MANUAL, manual.lat, manual.lon, manual.elevation_m, manual.time))
    if not wanted:
        raise UnprocessableError(
            "The tour needs a start or end point with a time first", code="no_sample_points"
        )
    try:
        results = [(s, source.values_at(s.lat, s.lon, s.elevation_m, s.time)) for s in wanted]
    except WeatherSourceError as exc:
        logger.warning("Weather lookup failed: %s", exc)
        raise WeatherUnavailableError("The weather service cannot be reached") from exc
    kept = {sample.kind for sample, values in results if values is not None}
    # A manual sample stays until it is replaced; automatic ones follow the tour.
    tour.weather = [
        row for row in tour.weather if row.sample_point in kept or row.sample_point == MANUAL
    ]
    for sample, values in results:
        if values is not None:
            _store(tour, sample, values)
    db.commit()


def auto_fetch(db: Session, source: WeatherSource, tour: Tour) -> None:
    """After saving: fetch once, as soon as the tour has sample points and no weather yet.

    Later changes of points or times do not fetch again; the tour is then marked
    as `weather_outdated` and the client offers a new fetch. Failures are tolerated.
    """
    if tour.weather or not samples(db, tour):
        return
    try:
        fetch(db, source, tour)
    except AppError as exc:
        logger.info("Automatic weather fetch skipped: %s", exc.message)


# --- Output ---

_ORDER = {START: 0, SUMMIT: 1, END: 2, MANUAL: 3}


def weather_out(tour: Tour) -> list[WeatherOut]:
    rows = sorted(tour.weather, key=lambda row: _ORDER.get(row.sample_point, 9))
    return [WeatherOut.model_validate(row) for row in rows]
