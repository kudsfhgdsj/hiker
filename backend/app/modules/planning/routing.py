"""Routing along paths behind an adapter.

The waypoints of a planned route only go to the routing engine of the own
server (BRouter), never to a service of someone else.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Protocol

import httpx2
from fastapi import Depends

from app.core.config import get_settings
from app.core.errors import AppError, UnprocessableError

# BRouter computes on OpenStreetMap data; this must be named where routes are shown (ODbL).
ROUTING_ATTRIBUTION = "Wegführung: BRouter, Daten © OpenStreetMap-Mitwirkende (ODbL)"


@dataclass(frozen=True)
class RoutedPoint:
    lat: float
    lon: float
    ele: float | None = None


@dataclass(frozen=True)
class RouteOptions:
    """Which paths may be used."""

    # Hardest allowed path on the SAC hiking scale, 1 (T1) to 6 (T6); easier ones are included.
    max_difficulty: int = 3
    # Via ferratas are a category of their own and only used if asked for.
    via_ferrata: bool = False


class RoutingUnavailableError(AppError):
    """The routing engine is not set up or cannot be reached."""

    status_code = 502
    code = "routing_unavailable"


def no_route(message: str) -> UnprocessableError:
    return UnprocessableError(message, code="no_route")


class RoutingEngine(Protocol):
    name: str

    @property
    def available(self) -> bool:
        """False if the engine is not set up; routes can then only be straight lines."""

    def route(
        self, points: list[tuple[float, float]], profile: str, options: RouteOptions
    ) -> list[RoutedPoint]:
        """The line along paths through all (lat, lon) points, in their order."""


class DisabledRoutingEngine:
    name = "none"
    available = False

    def route(
        self, points: list[tuple[float, float]], profile: str, options: RouteOptions
    ) -> list[RoutedPoint]:
        raise RoutingUnavailableError("Routing along paths is not set up on this server")


class BRouterEngine:
    """BRouter's HTTP server: `GET /brouter?lonlats=…&profile=…&format=geojson`."""

    name = "brouter"
    available = True

    def __init__(
        self,
        url: str,
        profiles: dict[str, str],
        *,
        timeout: float = 30.0,
        transport: httpx2.BaseTransport | None = None,
    ):
        self._url = url.rstrip("/") + "/brouter"
        self._profiles = profiles
        self._client = httpx2.Client(timeout=timeout, transport=transport)

    def route(
        self, points: list[tuple[float, float]], profile: str, options: RouteOptions
    ) -> list[RoutedPoint]:
        params = {
            "lonlats": "|".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points),
            "profile": self._profiles[profile],
            "alternativeidx": "0",
            "format": "geojson",
            # Parameters of the profile hiker-hiking: nothing harder than the limit, and
            # demanding paths up to the limit are preferred slightly.
            "profile:SAC_scale_limit": str(options.max_difficulty),
            "profile:SAC_scale_preferred": str(options.max_difficulty),
            "profile:allow_via_ferrata": "1" if options.via_ferrata else "0",
        }
        try:
            response = self._client.get(self._url, params=params)
        except httpx2.HTTPError as exc:
            raise RoutingUnavailableError("The routing engine cannot be reached") from exc
        if response.status_code >= 500:
            raise RoutingUnavailableError("The routing engine answered with an error")
        if response.status_code != 200:
            # BRouter explains in plain text why there is no route, e.g. a point far from
            # any path or outside the installed data.
            reason = response.text.strip().splitlines()[0][:200] if response.text.strip() else ""
            raise no_route(f"No route found: {reason}" if reason else "No route found")
        try:
            coordinates = response.json()["features"][0]["geometry"]["coordinates"]
            line = [
                RoutedPoint(
                    lat=float(position[1]),
                    lon=float(position[0]),
                    ele=float(position[2]) if len(position) > 2 else None,
                )
                for position in coordinates
            ]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RoutingUnavailableError("Unexpected answer of the routing engine") from exc
        if len(line) < 2:
            raise no_route("No route found")
        return line


@lru_cache
def get_routing_engine() -> RoutingEngine:
    settings = get_settings()
    if not settings.brouter_url:
        return DisabledRoutingEngine()
    return BRouterEngine(settings.brouter_url, {"hiking": settings.brouter_profile_hiking})


Routing = Annotated[RoutingEngine, Depends(get_routing_engine)]
