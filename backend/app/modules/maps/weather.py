"""Weather forecast and snow depth as a map layer.

Open-Meteo has no map tiles. This module asks it for the forecast at a small
grid of places per tile and writes them as points of a vector tile (layer
`weather`): one label per day (`day0` = today, `day1`, `day2`) and the snow
depth now (`snow`, in cm). A tile is kept for three hours, so that moving the
map around costs few requests.
"""

import gzip
import logging
import math
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Annotated, Protocol

import httpx2
from fastapi import Depends

from app import __version__
from app.core.config import get_settings

logger = logging.getLogger(__name__)

WEATHER_MIN_ZOOM = 8
WEATHER_MAX_ZOOM = 10
WEATHER_ATTRIBUTION = "Wetter und Schneehöhe: Open-Meteo (CC BY 4.0), Modellvorhersage"
DAYS = 3
EXTENT = 4096
# Places per tile: a grid of 3 x 3, in the middle of nine equal fields.
_GRID = (1 / 6, 3 / 6, 5 / 6)
# WMO weather codes in a few words.
_WORDS = (
    ((0,), "sonnig"),
    ((1, 2), "heiter"),
    ((3,), "bedeckt"),
    ((45, 48), "Nebel"),
    ((51, 53, 55, 56, 57), "Niesel"),
    ((61, 63, 65, 66, 67, 80, 81, 82), "Regen"),
    ((71, 73, 75, 77, 85, 86), "Schnee"),
    ((95, 96, 99), "Gewitter"),
)


class ForecastSourceError(Exception):
    """The weather service could not be reached or answered with garbage."""


class ForecastSource(Protocol):
    def forecast(self, places: list[tuple[float, float]], day: date | None = None) -> list[dict]:
        """Per (lat, lon) the answer of the weather service with `daily` and `hourly`:
        the next days, or the one day in the past that is asked for."""


class OpenMeteoForecast:
    def __init__(
        self,
        url: str,
        user_agent: str,
        *,
        archive_url: str = "",
        transport: httpx2.BaseTransport | None = None,
    ):
        self._url = url
        self._archive_url = archive_url
        self._client = httpx2.Client(
            headers={"User-Agent": user_agent}, timeout=10.0, transport=transport
        )

    def forecast(self, places: list[tuple[float, float]], day: date | None = None) -> list[dict]:
        url = self._url
        params = {
            "latitude": ",".join(f"{lat:.3f}" for lat, _ in places),
            "longitude": ",".join(f"{lon:.3f}" for _, lon in places),
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,snowfall_sum",
            "hourly": "snow_depth",
            "timezone": "UTC",
        }
        if day is None:
            params["forecast_days"] = str(DAYS)
        else:
            params["start_date"] = params["end_date"] = day.isoformat()
            # The forecast service keeps about three months; older days are in the archive.
            if (datetime.now(UTC).date() - day).days > 80 and self._archive_url:
                url = self._archive_url
        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            raise ForecastSourceError(str(exc)) from exc
        # One place is answered as an object, several as a list.
        answers = data if isinstance(data, list) else [data]
        if len(answers) != len(places):
            raise ForecastSourceError("unexpected answer of the weather service")
        return answers


def word_for(code) -> str:
    return next((word for codes, word in _WORDS if code in codes), "")


def _number(value) -> str:
    """-3.4 → "-3". The plain hyphen: the fonts of the map carry no other minus sign."""
    return str(round(value))


def day_label(daily: dict, day: int) -> str | None:
    """ "Regen\\n8°/1° · 12 mm", or with new snow "Schnee\\n-2°/-9° · 15 cm neu"."""
    try:
        high, low = daily["temperature_2m_max"][day], daily["temperature_2m_min"][day]
        if high is None or low is None:
            return None
        text = f"{_number(high)}°/{_number(low)}°"
        snowfall = daily["snowfall_sum"][day] or 0
        rain = daily["precipitation_sum"][day] or 0
        if snowfall >= 0.5:
            text += f" · {round(snowfall)} cm neu"
        elif rain >= 1:
            text += f" · {round(rain)} mm"
        word = word_for(daily["weather_code"][day])
        return f"{word}\n{text}" if word else text
    except (KeyError, IndexError, TypeError):
        return None


def snow_depth_cm(hourly: dict, now: datetime) -> int | None:
    """Snow on the ground at the current hour, in whole centimetres."""
    try:
        index = hourly["time"].index(now.strftime("%Y-%m-%dT%H:00"))
        depth = hourly["snow_depth"][index]
    except (KeyError, ValueError, IndexError):
        return None
    return None if depth is None else round(depth * 100)


def places_of(z: int, x: int, y: int) -> list[tuple[float, float, int, int]]:
    """The grid of a tile: latitude, longitude and the position inside the tile."""
    result = []
    for fy in _GRID:
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + fy) / 2**z))))
        for fx in _GRID:
            lon = (x + fx) / 2**z * 360 - 180
            result.append((lat, lon, round(fx * EXTENT), round(fy * EXTENT)))
    return result


# --- Vector tile with points and text attributes (see contours.py for the format) ---


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _bytes_field(number: int, data: bytes) -> bytes:
    return _varint(number << 3 | 2) + _varint(len(data)) + data


def _zigzag(value: int) -> int:
    return (value << 1) ^ (value >> 63)


def encode_points(layer: str, points: list[tuple[int, int, dict[str, str]]]) -> bytes:
    """One layer of point features; all attributes are texts."""
    keys: list[str] = []
    values: list[str] = []
    features = b""
    for x, y, attributes in points:
        tags = b""
        for key, value in attributes.items():
            if key not in keys:
                keys.append(key)
            if value not in values:
                values.append(value)
            tags += _varint(keys.index(key)) + _varint(values.index(value))
        geometry = _varint(1 << 3 | 1) + _varint(_zigzag(x)) + _varint(_zigzag(y))
        features += _bytes_field(
            2,
            _bytes_field(2, tags) + _varint(3 << 3) + _varint(1) + _bytes_field(4, geometry),
        )
    body = (
        _varint(15 << 3)
        + _varint(2)
        + _bytes_field(1, layer.encode())
        + features
        + b"".join(_bytes_field(3, key.encode()) for key in keys)
        + b"".join(_bytes_field(4, _bytes_field(1, value.encode())) for value in values)
        + _varint(5 << 3)
        + _varint(EXTENT)
    )
    return _bytes_field(3, body)


def weather_tile(
    source: ForecastSource,
    z: int,
    x: int,
    y: int,
    now: datetime | None,
    day: date | None = None,
) -> bytes:
    """The gzip-compressed vector tile with the forecast at the places of the tile; for
    a day in the past with the weather of that day (`day0`) and its snow depth at noon."""
    moment = now or datetime.now(UTC)
    if day is not None:
        moment = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    places = places_of(z, x, y)
    answers = source.forecast([(lat, lon) for lat, lon, _, _ in places], day)
    points = []
    for (_lat, _lon, px, py), answer in zip(places, answers, strict=True):
        attributes = {}
        for day in range(DAYS):
            label = day_label(answer.get("daily", {}), day)
            if label:
                attributes[f"day{day}"] = label
        depth = snow_depth_cm(answer.get("hourly", {}), moment)
        # Where no snow lies there is nothing to say.
        if depth:
            attributes["snow"] = f"{depth} cm"
        if attributes:
            points.append((px, py, attributes))
    return gzip.compress(encode_points("weather", points), compresslevel=6, mtime=0)


@lru_cache
def _source(url: str, archive_url: str, public_base_url: str) -> ForecastSource:
    return OpenMeteoForecast(
        url, f"hiker/{__version__} ({public_base_url})", archive_url=archive_url
    )


def get_forecast_source() -> ForecastSource | None:
    settings = get_settings()
    if not settings.open_meteo_forecast_url or not settings.weather_layers_enabled:
        return None
    return _source(
        settings.open_meteo_forecast_url, settings.open_meteo_archive_url, settings.public_base_url
    )


Forecast = Annotated[ForecastSource | None, Depends(get_forecast_source)]
