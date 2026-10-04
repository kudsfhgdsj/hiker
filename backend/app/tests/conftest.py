import os

# Fixed test configuration; must be set before the application is imported.
os.environ.update(
    {
        "SECRET_KEY": "test-secret-key-not-for-production-0123456789",
        "DATABASE_URL": "sqlite://",
        "PUBLIC_BASE_URL": "http://testserver",
        "ENABLED_MODULES": "auth,gear,nutrition,protocols,sync,maps,planning",
        # Most tests sign in with a password only; test_auth_security.py switches it on.
        "MFA_REQUIRED": "false",
        "REGISTRATION_MODE": "open",
        "ACCESS_TOKEN_TTL_MINUTES": "15",
        "REFRESH_TOKEN_TTL_DAYS": "30",
    }
)

from io import BytesIO  # noqa: E402

import pytest  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core import ratelimit, security  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, create_db_engine  # noqa: E402
from app.core.deps import get_db  # noqa: E402
from app.core.registry import import_all_models  # noqa: E402
from app.core.storage import get_storage  # noqa: E402
from app.core.storage.local_fs import LocalFsStorage  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.auth import service as auth_service  # noqa: E402
from app.modules.nutrition.deps import get_food_source  # noqa: E402
from app.modules.nutrition.sources import FoodData, FoodSourceError  # noqa: E402
from app.modules.planning.routing import (  # noqa: E402
    RoutedPoint,
    RoutingUnavailableError,
    get_routing_engine,
    no_route,
)
from app.modules.protocols.elevation import (  # noqa: E402
    ElevationSourceError,
    get_elevation_source,
)
from app.modules.protocols.places import PlaceSourceError, get_place_source  # noqa: E402
from app.modules.protocols.weather import (  # noqa: E402
    WeatherSourceError,
    WeatherValues,
    get_weather_source,
)


@pytest.fixture(autouse=True, scope="session")
def _fast_password_hashing():
    """Argon2 with minimal cost; the production parameters make the suite slow."""
    original = security._hasher
    security._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    yield
    security._hasher = original


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    ratelimit.reset()
    auth_service.reset_mfa_attempts()
    yield
    get_settings.cache_clear()


@pytest.fixture
def session_factory():
    import_all_models()
    engine = create_db_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def client(
    monkeypatch,
    session_factory,
    storage,
    food_source,
    elevation_source,
    weather_source,
    place_source,
    routing_engine,
):
    app = create_app()
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_food_source] = lambda: food_source
    app.dependency_overrides[get_elevation_source] = lambda: elevation_source
    app.dependency_overrides[get_weather_source] = lambda: weather_source
    app.dependency_overrides[get_place_source] = lambda: place_source
    app.dependency_overrides[get_routing_engine] = lambda: routing_engine
    # The offline sync has no request to take its dependencies from.
    monkeypatch.setattr("app.modules.planning.sync.get_routing_engine", lambda: routing_engine)
    monkeypatch.setattr("app.modules.planning.sync.get_elevation_source", lambda: elevation_source)

    def _get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as test_client:
        yield test_client


class FakeFoodSource:
    """Stands in for Open Food Facts; tests never touch the network."""

    def __init__(self):
        self.products: dict[str, FoodData] = {}
        self.calls: list[str] = []
        self.fail = False

    def fetch_by_barcode(self, barcode: str) -> FoodData | None:
        self.calls.append(barcode)
        if self.fail:
            raise FoodSourceError("unreachable")
        return self.products.get(barcode)


class FakeElevationSource:
    """Stands in for the Open-Meteo elevation API."""

    def __init__(self):
        self.calls: list[int] = []
        self.fail = False

    def elevations(self, coordinates):
        self.calls.append(len(coordinates))
        if self.fail:
            raise ElevationSourceError("unreachable")
        # A slope that depends on the latitude, so that tests get ascent.
        return [round(1000 + (lat - 47) * 10_000, 1) for lat, _ in coordinates]


@pytest.fixture
def elevation_source():
    return FakeElevationSource()


class FakeWeatherSource:
    """Stands in for the Open-Meteo weather services."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.fail = False
        self.no_data = False

    def values_at(self, lat, lon, elevation_m, time):
        self.calls.append((round(lat, 4), round(lon, 4), elevation_m, time))
        if self.fail:
            raise WeatherSourceError("unreachable")
        if self.no_data:
            return None
        # Colder with elevation, so that tests can tell the sample points apart.
        return WeatherValues(
            source="fake",
            temperature_c=round(25 - (elevation_m or 0) / 100, 1),
            wind_speed_kmh=10.0,
            cloud_cover_pct=40.0,
            weather_code=2,
        )


@pytest.fixture
def weather_source():
    return FakeWeatherSource()


class FakePlaceSource:
    """Stands in for the Overpass API of OpenStreetMap."""

    def __init__(self):
        self.places: list = []
        self.calls: list[tuple] = []
        self.fail = False

    def places_in(self, south, west, north, east):
        self.calls.append((south, west, north, east))
        if self.fail:
            raise PlaceSourceError("unreachable")
        return [p for p in self.places if south <= p.lat <= north and west <= p.lon <= east]


@pytest.fixture
def place_source():
    return FakePlaceSource()


class FakeRoutingEngine:
    """Stands in for BRouter; tests never touch the network."""

    name = "brouter"

    def __init__(self):
        self.calls: list[tuple] = []
        self.options: list = []
        self.available = True
        self.fail = False
        self.no_route = False

    def route(self, points, profile, options):
        self.calls.append((points, profile))
        self.options.append(options)
        if not self.available or self.fail:
            raise RoutingUnavailableError("unreachable")
        if self.no_route:
            raise no_route("No route found: target island detected")
        # A path with a bend between two points, with elevations of its own.
        line = []
        for (lat1, lon1), (lat2, lon2) in zip(points, points[1:], strict=False):
            middle = ((lat1 + lat2) / 2, (lon1 + lon2) / 2 + 0.002)
            for lat, lon in ((lat1, lon1), middle):
                line.append(RoutedPoint(lat, lon, round(1500 + (lat - 47) * 20_000, 1)))
        lat, lon = points[-1]
        line.append(RoutedPoint(lat, lon, round(1500 + (lat - 47) * 20_000, 1)))
        return line


@pytest.fixture
def routing_engine():
    return FakeRoutingEngine()


@pytest.fixture
def food_source():
    return FakeFoodSource()


@pytest.fixture
def storage(tmp_path):
    return LocalFsStorage(tmp_path / "files")


PASSWORD = "Correct-Horse-7"


def make_image(size=(64, 48), image_format="JPEG", mode="RGB", exif_gps=False) -> bytes:
    image = Image.new(mode, size, 1 if mode == "P" else (200, 120, 40, 128)[: len(mode)])
    exif = Image.Exif()
    if exif_gps:
        exif[0x8825] = {1: "N", 2: (46.0, 30.0, 0.0), 3: "E", 4: (8.0, 0.0, 0.0)}
    output = BytesIO()
    image.save(output, format=image_format, **({"exif": exif} if exif_gps else {}))
    return output.getvalue()


def register(client, email="anna@example.org", display_name="Anna", password=PASSWORD):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_header(tokens) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}
