import uuid
from datetime import timedelta

import jwt
import pytest
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.security import JWT_ALGORITHM
from app.modules.auth.models import RefreshToken, User
from app.tests.conftest import PASSWORD, auth_header, register


def test_register_returns_user_and_tokens(client):
    data = register(client, email="  Anna@Example.org ", display_name="  Anna  ")

    assert data["user"]["email"] == "anna@example.org"
    assert data["user"]["display_name"] == "Anna"
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 15 * 60
    assert data["access_token"] and data["refresh_token"]
    assert "password" not in str(data)


def test_password_is_stored_hashed(client, db):
    register(client)

    user = db.scalar(select(User))

    assert user.password_hash.startswith("$argon2")
    assert PASSWORD not in user.password_hash


def test_first_user_becomes_admin_later_users_do_not(client):
    first = register(client, email="first@example.org")
    second = register(client, email="second@example.org")

    assert first["user"]["role"] == "admin"
    assert second["user"]["role"] == "user"


def test_register_rejects_duplicate_email(client):
    register(client)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "ANNA@example.org", "display_name": "Other", "password": PASSWORD},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "display_name": "Anna", "password": PASSWORD},
        {"email": "anna@example.org", "display_name": "Anna", "password": "short"},
        {"email": "anna@example.org", "display_name": "   ", "password": PASSWORD},
    ],
)
def test_register_validates_input(client, payload):
    assert client.post("/api/v1/auth/register", json=payload).status_code == 422


def test_register_is_forbidden_when_registration_is_closed(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "closed")
    get_settings.cache_clear()

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "anna@example.org", "display_name": "Anna", "password": PASSWORD},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "registration_closed"


def test_login_works_while_registration_is_closed(client, monkeypatch):
    register(client)
    monkeypatch.setenv("REGISTRATION_MODE", "closed")
    get_settings.cache_clear()

    response = client.post(
        "/api/v1/auth/login", json={"email": "anna@example.org", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "anna@example.org"


@pytest.mark.parametrize(
    ("email", "password"),
    [("anna@example.org", "wrong-password-123"), ("nobody@example.org", PASSWORD)],
)
def test_login_rejects_wrong_credentials_without_revealing_which(client, email, password):
    register(client)

    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "invalid_credentials",
        "message": "Wrong e-mail address or password",
    }


def test_me_requires_valid_access_token(client):
    tokens = register(client)

    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    response = client.get("/api/v1/me", headers=auth_header(tokens))
    assert response.status_code == 200
    assert response.json()["email"] == "anna@example.org"


def _forge(user_id: str, *, key=None, token_type="access", expires_in=60) -> str:
    now = utcnow()
    payload = {"sub": user_id, "type": token_type, "exp": now + timedelta(seconds=expires_in)}
    return jwt.encode(payload, key or get_settings().secret_key, algorithm=JWT_ALGORITHM)


@pytest.mark.parametrize(
    "overrides",
    [
        {"expires_in": -1},
        {"key": "another-secret-key-with-enough-length-000"},
        {"token_type": "refresh"},
    ],
)
def test_expired_or_forged_access_token_is_rejected(client, overrides):
    user_id = register(client)["user"]["id"]

    token = _forge(user_id, **overrides)

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_access_token_of_deleted_user_is_rejected(client, db):
    tokens = register(client)
    db.delete(db.get(User, uuid.UUID(tokens["user"]["id"])))
    db.commit()

    assert client.get("/api/v1/me", headers=auth_header(tokens)).status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client):
    tokens = register(client)

    response = client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )

    assert response.status_code == 401


def test_refresh_rotates_the_token(client):
    tokens = register(client)

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    renewed = response.json()
    assert renewed["refresh_token"] != tokens["refresh_token"]
    assert client.get("/api/v1/me", headers=auth_header(renewed)).status_code == 200


def test_refresh_token_is_stored_hashed(client, db):
    tokens = register(client)

    stored = db.scalar(select(RefreshToken))

    assert stored.token_hash != tokens["refresh_token"]
    assert len(stored.token_hash) == 64


def test_reusing_a_refresh_token_revokes_all_sessions(client):
    tokens = register(client)
    renewed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).json()

    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    follow_up = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": renewed["refresh_token"]}
    )

    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "invalid_refresh_token"
    assert follow_up.status_code == 401


def test_expired_refresh_token_is_rejected(client, db):
    tokens = register(client)
    db.execute(update(RefreshToken).values(expires_at=utcnow() - timedelta(seconds=1)))
    db.commit()

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 401


def test_unknown_refresh_token_is_rejected(client):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "unknown"})

    assert response.status_code == 401


def test_logout_revokes_only_the_given_refresh_token(client):
    first = register(client)
    second = client.post(
        "/api/v1/auth/login", json={"email": "anna@example.org", "password": PASSWORD}
    ).json()

    response = client.post("/api/v1/auth/logout", json={"refresh_token": first["refresh_token"]})

    assert response.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
        ).status_code
        == 200
    )


def test_refresh_after_logout_is_rejected(client):
    tokens = register(client)
    client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 401


def test_lookup_finds_user_by_exact_email_without_exposing_more(client):
    anna = register(client)
    bea = register(client, email="bea@example.org", display_name="Bea")

    response = client.get(
        "/api/v1/users/lookup", params={"email": "BEA@example.org"}, headers=auth_header(anna)
    )

    assert response.status_code == 200
    assert response.json() == {"id": bea["user"]["id"], "display_name": "Bea"}


def test_lookup_requires_login_and_returns_404_for_unknown_email(client):
    tokens = register(client)

    anonymous = client.get("/api/v1/users/lookup", params={"email": "anna@example.org"})
    unknown = client.get(
        "/api/v1/users/lookup", params={"email": "nobody@example.org"}, headers=auth_header(tokens)
    )
    partial = client.get(
        "/api/v1/users/lookup", params={"email": "anna@example"}, headers=auth_header(tokens)
    )

    assert anonymous.status_code == 401
    assert unknown.status_code == 404
    assert partial.status_code == 422


def test_login_attempts_are_rate_limited(client):
    register(client)
    wrong = {"email": "anna@example.org", "password": "wrong-password-123"}

    statuses = [client.post("/api/v1/auth/login", json=wrong).status_code for _ in range(21)]

    assert statuses == [401] * 19 + [429] * 2
    limited = client.post("/api/v1/auth/login", json=wrong)
    assert limited.json()["error"]["code"] == "rate_limited"
    assert 0 < int(limited.headers["retry-after"]) <= 60


def test_rate_limit_can_be_switched_off(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()
    wrong = {"email": "anna@example.org", "password": "wrong-password-123"}

    statuses = {client.post("/api/v1/auth/login", json=wrong).status_code for _ in range(25)}

    assert statuses == {401}
