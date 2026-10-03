import os

# Fixed test configuration; must be set before the application is imported.
os.environ.update(
    {
        "SECRET_KEY": "test-secret-key-not-for-production-0123456789",
        "DATABASE_URL": "sqlite://",
        "PUBLIC_BASE_URL": "http://testserver",
        "ENABLED_MODULES": "auth,gear,nutrition",
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

from app.core import security  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, create_db_engine  # noqa: E402
from app.core.deps import get_db  # noqa: E402
from app.core.registry import import_all_models  # noqa: E402
from app.core.storage import get_storage  # noqa: E402
from app.core.storage.local_fs import LocalFsStorage  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.nutrition.deps import get_food_source  # noqa: E402
from app.modules.nutrition.sources import FoodData, FoodSourceError  # noqa: E402


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
def client(session_factory, storage, food_source):
    app = create_app()
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_food_source] = lambda: food_source

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


@pytest.fixture
def food_source():
    return FakeFoodSource()


@pytest.fixture
def storage(tmp_path):
    return LocalFsStorage(tmp_path / "files")


PASSWORD = "correct-horse-battery"


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
