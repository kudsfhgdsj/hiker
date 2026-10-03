import os

# Fixed test configuration; must be set before the application is imported.
os.environ.update(
    {
        "SECRET_KEY": "test-secret-key-not-for-production-0123456789",
        "DATABASE_URL": "sqlite://",
        "PUBLIC_BASE_URL": "http://testserver",
        "ENABLED_MODULES": "auth",
        "REGISTRATION_MODE": "open",
        "ACCESS_TOKEN_TTL_MINUTES": "15",
        "REFRESH_TOKEN_TTL_DAYS": "30",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, create_db_engine  # noqa: E402
from app.core.deps import get_db  # noqa: E402
from app.core.registry import import_all_models  # noqa: E402
from app.main import create_app  # noqa: E402


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
def client(session_factory):
    app = create_app()

    def _get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as test_client:
        yield test_client


PASSWORD = "correct-horse-battery"


def register(client, email="anna@example.org", display_name="Anna", password=PASSWORD):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_header(tokens) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}
