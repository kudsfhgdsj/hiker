from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app.core.db import Base, create_db_engine
from app.core.registry import import_all_models

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_healthz(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_lists_versioned_auth_and_profile_endpoints(client):
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths["/api/v1/auth/register"]) == {"post"}
    assert set(paths["/api/v1/auth/login"]) == {"post"}
    assert set(paths["/api/v1/auth/refresh"]) == {"post"}
    assert set(paths["/api/v1/users/lookup"]) == {"get"}
    assert set(paths["/api/v1/me/profile"]) == {"get", "put"}


def _alembic_config(tmp_path) -> tuple[Config, str]:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["skip_logging"] = True
    return config, url


def test_migrations_build_the_schema_of_the_models(tmp_path):
    config, url = _alembic_config(tmp_path)

    command.upgrade(config, "heads")

    import_all_models()
    engine = create_db_engine(url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []


def test_migrations_seed_the_standard_gear_types(tmp_path):
    config, url = _alembic_config(tmp_path)

    command.upgrade(config, "heads")

    engine = create_db_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT name, owner_id FROM gear_type")).all()
    engine.dispose()
    assert len(rows) == 12
    assert {"Rucksack", "Sonstiges"} <= {name for name, _ in rows}
    assert all(owner_id is None for _, owner_id in rows)


def test_migrations_can_be_rolled_back(tmp_path):
    config, url = _alembic_config(tmp_path)
    command.upgrade(config, "heads")

    command.downgrade(config, "base")

    engine = create_db_engine(url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert tables == {"alembic_version"}
