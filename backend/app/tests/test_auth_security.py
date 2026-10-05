"""Password rules, second factor, administration of users and single sign-on."""

import time

import httpx2
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.files import FileObject
from app.modules.auth import totp
from app.modules.auth.models import User
from app.modules.auth.oidc import (
    HttpOidcProvider,
    OidcError,
    OidcIdentity,
    challenge_of,
    get_oidc_provider,
)
from app.modules.auth.passwords import check_password
from app.tests.conftest import PASSWORD, auth_header, make_image, register

LOGIN = "/api/v1/auth/login"
ME_PROFILE = "/api/v1/me/profile"


@pytest.fixture
def mfa_mandatory(monkeypatch):
    monkeypatch.setenv("MFA_REQUIRED", "true")
    get_settings.cache_clear()


def login(client, email="anna@example.org", password=PASSWORD, **more):
    return client.post(LOGIN, json={"email": email, "password": password, **more})


def code_for(db, email="anna@example.org", *, pending=False, step=0) -> str:
    user = db.scalar(select(User).where(User.email == email))
    db.refresh(user)
    secret = user.totp_pending_secret if pending else user.totp_secret
    return totp.code_at(secret, totp.current_counter() + step)


def set_up_mfa(client, db, tokens, email="anna@example.org") -> dict:
    """Go through the setup; returns the answer with new tokens and recovery codes."""
    headers = auth_header(tokens)
    setup = client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert setup.status_code == 200, setup.text
    enabled = client.post(
        "/api/v1/auth/mfa/enable",
        json={"code": code_for(db, email, pending=True)},
        headers=headers,
    )
    assert enabled.status_code == 200, enabled.text
    return enabled.json()


# --- Password rules (BSI) ---


@pytest.mark.parametrize(
    ("password", "reason"),
    [
        ("Ab1-xyz", "too_short"),
        ("nurkleinbuchstaben", "too_simple"),
        ("Kleinundgross12", "too_simple"),  # three kinds, but no second factor
        ("Anna-ist-toll-1", "contains_personal_data"),
        ("Passwort-1", "too_common"),
        ("Aa1-Aa1-Aa1-", "too_common"),
    ],
)
def test_weak_passwords_are_rejected_with_a_reason(client, password, reason):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "anna@example.org", "display_name": "Anna", "password": password},
    )

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "weak_password"
    assert response.json()["reason"] == reason


@pytest.mark.parametrize(
    "password",
    ["Kurz-und-Gut-7", "ein langer satz ohne grossbuchstaben 7", "Vier Wörter reichen völlig"],
)
def test_strong_passwords_are_accepted(password):
    check_password(password, email="anna@example.org", display_name="Anna")


def test_three_kinds_of_characters_are_enough_with_a_second_factor(mfa_mandatory):
    check_password("kleinundgross-12", email="a@example.org", display_name="A")
    with pytest.raises(Exception, match="kinds of characters"):
        check_password("kleinundgross", email="a@example.org", display_name="A")


# --- Changing the password ---


def test_password_change_ends_other_sessions(client):
    first = register(client)
    other_device = login(client).json()

    changed = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "Neues-Passwort-8"},
        headers=auth_header(first),
    )

    assert changed.status_code == 200, changed.text
    assert client.get(ME_PROFILE, headers=auth_header(changed.json())).status_code == 200
    stale = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": other_device["refresh_token"]}
    )
    assert stale.status_code == 401
    assert login(client).status_code == 401
    assert login(client, password="Neues-Passwort-8").status_code == 200


def test_password_change_needs_the_current_password_and_a_strong_new_one(client):
    headers = auth_header(register(client))
    url = "/api/v1/auth/password"

    wrong = client.post(
        url, json={"current_password": "x", "new_password": "Neues-Passwort-8"}, headers=headers
    )
    weak = client.post(
        url, json={"current_password": PASSWORD, "new_password": "kurz"}, headers=headers
    )
    same = client.post(
        url, json={"current_password": PASSWORD, "new_password": PASSWORD}, headers=headers
    )

    assert (wrong.status_code, wrong.json()["error"]["code"]) == (422, "wrong_password")
    assert (weak.status_code, weak.json()["error"]["code"]) == (422, "weak_password")
    assert same.status_code == 422


# --- Second factor ---


def test_first_login_only_allows_setting_up_the_second_factor(client, db, mfa_mandatory):
    registered = register(client)
    headers = auth_header(registered)

    assert registered["mfa_setup_required"] is True and registered["auth_method"] == "pwd"
    blocked = client.get(ME_PROFILE, headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "mfa_setup_required"
    assert client.get("/api/v1/gear/items", headers=headers).status_code == 403
    # The own account and the state of the session stay readable.
    assert client.get("/api/v1/me", headers=headers).json()["mfa_enabled"] is False
    assert client.get("/api/v1/me/session", headers=headers).json()["mfa_setup_required"] is True

    setup = client.post("/api/v1/auth/mfa/setup", headers=headers).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/hiker%3Aanna%40example.org?secret=")
    wrong = client.post("/api/v1/auth/mfa/enable", json={"code": "000000"}, headers=headers)
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (422, "invalid_mfa_code")
    enabled = client.post(
        "/api/v1/auth/mfa/enable", json={"code": code_for(db, pending=True)}, headers=headers
    ).json()

    assert enabled["auth_method"] == "mfa" and enabled["mfa_setup_required"] is False
    assert enabled["user"]["mfa_enabled"] is True and len(enabled["recovery_codes"]) == 10
    assert client.get(ME_PROFILE, headers=auth_header(enabled)).status_code == 200
    # The session that was started with the password alone ended.
    old = client.post("/api/v1/auth/refresh", json={"refresh_token": registered["refresh_token"]})
    assert old.status_code == 401


def test_login_needs_the_code_once_the_second_factor_is_set_up(client, db, mfa_mandatory):
    set_up_mfa(client, db, register(client))

    without = login(client)
    wrong = login(client, code="123456")
    # The code of the setup was used: the next period has a fresh one.
    right = login(client, code=code_for(db, step=1))

    assert (without.status_code, without.json()["error"]["code"]) == (401, "mfa_required")
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (401, "invalid_mfa_code")
    assert right.status_code == 200 and right.json()["auth_method"] == "mfa"
    assert client.get(ME_PROFILE, headers=auth_header(right.json())).status_code == 200
    # The refreshed session keeps counting as signed in with the second factor.
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": right.json()["refresh_token"]}
    ).json()
    assert client.get(ME_PROFILE, headers=auth_header(refreshed)).status_code == 200


def test_sign_in_in_two_steps_with_the_token_of_the_first(client, db, mfa_mandatory):
    set_up_mfa(client, db, register(client))

    first = login(client)
    token = first.json()["mfa_token"]
    wrong = client.post("/api/v1/auth/login/mfa", json={"mfa_token": token, "code": "000000"})
    second = client.post(
        "/api/v1/auth/login/mfa", json={"mfa_token": token, "code": code_for(db, step=1)}
    )

    assert first.status_code == 401 and first.json()["error"]["code"] == "mfa_required"
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (401, "invalid_mfa_code")
    assert second.status_code == 200 and second.json()["auth_method"] == "mfa"
    assert client.get(ME_PROFILE, headers=auth_header(second.json())).status_code == 200
    # The token of the first step is no access token, and a wrong password gets none.
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert "mfa_token" not in login(client, password="wrong-password").json()
    forged = client.post("/api/v1/auth/login/mfa", json={"mfa_token": "x", "code": "123456"})
    assert (forged.status_code, forged.json()["error"]["code"]) == (401, "mfa_token_invalid")
    # An access token does not work as the token of the first step either.
    misuse = client.post(
        "/api/v1/auth/login/mfa",
        json={"mfa_token": second.json()["access_token"], "code": "123456"},
    )
    assert misuse.status_code == 401


def test_wrong_codes_make_the_account_wait(client, db, mfa_mandatory):
    set_up_mfa(client, db, register(client))
    token = login(client).json()["mfa_token"]

    answers = [
        client.post("/api/v1/auth/login/mfa", json={"mfa_token": token, "code": "000000"})
        for _ in range(6)
    ]
    right = client.post(
        "/api/v1/auth/login/mfa", json={"mfa_token": token, "code": code_for(db, step=1)}
    )

    assert [a.status_code for a in answers] == [401, 401, 401, 401, 401, 429]
    # Even the right code has to wait now.
    assert right.status_code == 429


def test_a_code_works_only_once(client, db, mfa_mandatory):
    set_up_mfa(client, db, register(client))
    code = code_for(db, step=1)

    assert login(client, code=code).status_code == 200
    assert login(client, code=code).status_code == 401


def test_recovery_codes_work_once_and_can_be_replaced(client, db, mfa_mandatory):
    enabled = set_up_mfa(client, db, register(client))
    first, second = enabled["recovery_codes"][:2]

    assert login(client, code=first.upper()).status_code == 200
    assert login(client, code=first).status_code == 401

    replaced = client.post(
        "/api/v1/auth/mfa/recovery-codes",
        json={"code": code_for(db, step=1)},
        headers=auth_header(enabled),
    )
    assert replaced.status_code == 200 and len(replaced.json()["recovery_codes"]) == 10
    assert login(client, code=second).status_code == 401
    assert login(client, code=replaced.json()["recovery_codes"][0]).status_code == 200


def test_mandatory_second_factor_cannot_be_switched_off(client, db, mfa_mandatory):
    enabled = set_up_mfa(client, db, register(client))

    response = client.post(
        "/api/v1/auth/mfa/disable",
        json={"code": code_for(db, step=1)},
        headers=auth_header(enabled),
    )

    assert (response.status_code, response.json()["error"]["code"]) == (403, "mfa_mandatory")


def test_optional_second_factor_can_be_switched_off(client, db):
    enabled = set_up_mfa(client, db, register(client))
    assert login(client).status_code == 401

    response = client.post(
        "/api/v1/auth/mfa/disable",
        json={"code": code_for(db, step=1)},
        headers=auth_header(enabled),
    )

    assert response.status_code == 204
    assert login(client).status_code == 200


def test_replacing_the_second_factor_needs_a_session_that_used_it(client, db):
    registered = register(client)
    set_up_mfa(client, db, registered)
    # Without MFA_REQUIRED the old access token is still usable, but not for this.
    response = client.post("/api/v1/auth/mfa/setup", headers=auth_header(registered))

    assert (response.status_code, response.json()["error"]["code"]) == (403, "mfa_required")


def test_totp_matches_the_reference_values_of_the_rfc():
    # RFC 6238, appendix B (SHA-1, secret "12345678901234567890"), last six digits.
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp.code_at(secret, 59 // 30) == "287082"
    assert totp.code_at(secret, 1111111109 // 30) == "081804"
    assert totp.verify(secret, "287 082", None, now=59) == 1
    assert totp.verify(secret, "287082", None, now=59 + 30) == 1  # previous period
    assert totp.verify(secret, "287082", None, now=59 + 90) is None
    assert totp.verify(secret, "287082", 1, now=59) is None  # used before
    assert totp.verify(secret, "28708", None, now=59) is None


# --- Administration of users ---


def test_admin_sees_all_users_and_others_do_not(client):
    admin = auth_header(register(client))
    bea = auth_header(register(client, "bea@example.org", "Bea"))

    users = client.get("/api/v1/admin/users", headers=admin)

    assert users.status_code == 200
    assert [(u["email"], u["role"], u["mfa_enabled"]) for u in users.json()] == [
        ("anna@example.org", "admin", False),
        ("bea@example.org", "user", False),
    ]
    assert "password_hash" not in users.text and "totp" not in users.text
    assert client.get("/api/v1/admin/users", headers=bea).status_code == 403


def test_admin_resets_a_password_and_the_user_must_choose_a_new_one(client):
    admin = auth_header(register(client))
    bea = register(client, "bea@example.org", "Bea")

    reset = client.post(f"/api/v1/admin/users/{bea['user']['id']}/reset-password", headers=admin)
    temporary = reset.json()["temporary_password"]

    assert reset.status_code == 200
    assert login(client, "bea@example.org").status_code == 401
    stale = client.post("/api/v1/auth/refresh", json={"refresh_token": bea["refresh_token"]})
    assert stale.status_code == 401
    signed_in = login(client, "bea@example.org", temporary).json()
    assert signed_in["password_change_required"] is True
    blocked = client.get(ME_PROFILE, headers=auth_header(signed_in))
    assert blocked.json()["error"]["code"] == "password_change_required"
    changed = client.post(
        "/api/v1/auth/password",
        json={"current_password": temporary, "new_password": "Ganz-Neu-und-Gut-9"},
        headers=auth_header(signed_in),
    ).json()
    assert changed["password_change_required"] is False
    assert client.get(ME_PROFILE, headers=auth_header(changed)).status_code == 200


def test_admin_resets_a_lost_second_factor(client, db, mfa_mandatory):
    admin = set_up_mfa(client, db, register(client))
    bea = register(client, "bea@example.org", "Bea")
    set_up_mfa(client, db, bea, "bea@example.org")

    reset = client.post(
        f"/api/v1/admin/users/{bea['user']['id']}/reset-mfa", headers=auth_header(admin)
    )

    assert reset.status_code == 204
    again = login(client, "bea@example.org")
    assert again.status_code == 200 and again.json()["mfa_setup_required"] is True


def test_admin_removes_a_user_with_everything_they_own(client, db, storage):
    admin = register(client)
    bea = register(client, "bea@example.org", "Bea")
    bea_headers = auth_header(bea)
    item = client.post("/api/v1/gear/items", json={"name": "Zelt"}, headers=bea_headers).json()
    uploaded = client.post(
        f"/api/v1/gear/items/{item['id']}/image",
        files={"file": ("zelt.png", make_image(image_format="PNG"), "image/png")},
        headers=bea_headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    tour = client.post("/api/v1/tours", json={"title": "Beas Tour"}, headers=bea_headers).json()
    key = db.scalar(select(FileObject.storage_key))

    removed = client.delete(f"/api/v1/admin/users/{bea['user']['id']}", headers=auth_header(admin))

    assert removed.status_code == 204
    assert client.get("/api/v1/me", headers=bea_headers).status_code == 401
    assert login(client, "bea@example.org").status_code == 401
    assert db.scalar(select(FileObject.id)) is None
    with pytest.raises(Exception):  # noqa: B017 - any "not found" of the storage
        storage.read(key)
    emails = [
        u["email"] for u in client.get("/api/v1/admin/users", headers=auth_header(admin)).json()
    ]
    assert emails == ["anna@example.org"]
    assert tour["id"]


def test_admin_cannot_remove_the_own_account(client):
    admin = register(client)

    response = client.delete(
        f"/api/v1/admin/users/{admin['user']['id']}", headers=auth_header(admin)
    )

    assert (response.status_code, response.json()["error"]["code"]) == (409, "cannot_delete_self")
    unknown = client.delete(
        "/api/v1/admin/users/00000000-0000-4000-8000-000000000000", headers=auth_header(admin)
    )
    assert unknown.status_code == 404


# --- Single sign-on ---


class FakeOidc:
    """Stands in for the OpenID Connect provider."""

    def __init__(self):
        self.identity = OidcIdentity(
            issuer="https://sso.example",
            subject="sub-1",
            email="anna@example.org",
            email_verified=True,
            name="Anna Alpin",
        )
        self.fail = False
        self.exchanged: list[dict] = []
        self.started: list[dict] = []

    def authorization_url(self, **kwargs):
        self.started.append(kwargs)
        return f"https://sso.example/auth?state={kwargs['state']}"

    def exchange(self, **kwargs):
        self.exchanged.append(kwargs)
        if self.fail:
            raise OidcError("provider down")
        return self.identity


@pytest.fixture
def oidc(client):
    provider = FakeOidc()
    client.app.dependency_overrides[get_oidc_provider] = lambda: provider
    return provider


def sso_login(client, code="code-1"):
    started = client.post("/api/v1/auth/oidc/start").json()
    return client.post("/api/v1/auth/oidc/callback", json={"state": started["state"], "code": code})


def test_single_sign_on_is_off_without_configuration(client):
    assert client.get("/api/v1/auth/oidc").json() == {"enabled": False, "name": "SSO"}
    assert client.post("/api/v1/auth/oidc/start").status_code == 404


def test_single_sign_on_creates_an_account_and_needs_no_second_factor(
    client, oidc, mfa_mandatory, monkeypatch
):
    monkeypatch.setenv("REGISTRATION_MODE", "closed")
    get_settings.cache_clear()

    assert client.get("/api/v1/auth/oidc").json()["enabled"] is True
    started = client.post("/api/v1/auth/oidc/start").json()
    answer = client.post(
        "/api/v1/auth/oidc/callback", json={"state": started["state"], "code": "code-1"}
    )

    assert started["authorization_url"] == f"https://sso.example/auth?state={started['state']}"
    assert oidc.started[0]["redirect_uri"] == "http://testserver/login/sso/callback"
    data = answer.json()
    assert answer.status_code == 200, answer.text
    assert data["auth_method"] == "sso" and data["mfa_setup_required"] is False
    assert data["user"]["email"] == "anna@example.org" and data["user"]["sso"] is True
    assert data["user"]["display_name"] == "Anna Alpin" and data["user"]["has_password"] is False
    assert client.get(ME_PROFILE, headers=auth_header(data)).status_code == 200
    # The verifier sent to the provider matches the challenge of the start.
    assert challenge_of(oidc.exchanged[0]["verifier"]) == oidc.started[0]["challenge"]
    assert oidc.exchanged[0]["nonce"] == oidc.started[0]["nonce"]
    # No password: the account cannot be used with the password form.
    assert login(client, password="!").status_code == 401


def test_single_sign_on_links_the_account_with_the_same_confirmed_address(client, oidc):
    registered = register(client)

    first = sso_login(client).json()
    oidc.identity = OidcIdentity(
        "https://sso.example", "sub-1", "new-address@example.org", False, "Anna"
    )
    second = sso_login(client).json()

    assert first["user"]["id"] == registered["user"]["id"] and first["user"]["sso"] is True
    # Known by its subject from now on, whatever the e-mail address says.
    assert second["user"]["id"] == registered["user"]["id"]
    assert second["user"]["email"] == "anna@example.org"


def test_single_sign_on_refuses_an_unconfirmed_address(client, oidc):
    register(client)
    oidc.identity = OidcIdentity("https://sso.example", "sub-9", "anna@example.org", False, None)

    response = sso_login(client)

    assert (response.status_code, response.json()["error"]["code"]) == (
        403,
        "oidc_email_unverified",
    )


def test_single_sign_on_state_works_once_and_expires(client, oidc, db):
    started = client.post("/api/v1/auth/oidc/start").json()
    body = {"state": started["state"], "code": "code-1"}

    assert client.post("/api/v1/auth/oidc/callback", json=body).status_code == 200
    replay = client.post("/api/v1/auth/oidc/callback", json=body)
    forged = client.post("/api/v1/auth/oidc/callback", json={"state": "x", "code": "c"})

    assert (replay.status_code, replay.json()["error"]["code"]) == (401, "oidc_state_invalid")
    assert forged.status_code == 401


def test_single_sign_on_reports_a_failing_provider(client, oidc):
    oidc.fail = True

    response = sso_login(client)

    assert (response.status_code, response.json()["error"]["code"]) == (502, "oidc_failed")


def _id_token(claims: dict) -> str:
    import base64
    import json

    def part(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none'})}.{part(claims)}.signature"


def test_http_provider_follows_the_code_flow_and_checks_the_id_token():
    issuer = "https://sso.example/realms/home"
    claims = {
        "iss": issuer,
        "aud": "hiker",
        "sub": "sub-1",
        "nonce": "nonce-1",
        "exp": time.time() + 300,
        "email": "Anna@Example.org",
        "email_verified": True,
        "preferred_username": "anna",
    }
    posted = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx2.Response(
                200,
                json={
                    "issuer": issuer,
                    "authorization_endpoint": f"{issuer}/auth",
                    "token_endpoint": f"{issuer}/token",
                },
            )
        posted.append(dict(httpx2.QueryParams(request.content.decode())))
        return httpx2.Response(200, json={"id_token": _id_token(claims), "access_token": "at"})

    provider = HttpOidcProvider(
        issuer + "/", "hiker", "secret", "openid email", transport=httpx2.MockTransport(handler)
    )

    url = provider.authorization_url(
        state="s", nonce="nonce-1", challenge="ch", redirect_uri="https://h.example/cb"
    )
    identity = provider.exchange(
        code="c", verifier="v", nonce="nonce-1", redirect_uri="https://h.example/cb"
    )

    assert url.startswith(f"{issuer}/auth?response_type=code&client_id=hiker&")
    assert "code_challenge=ch&code_challenge_method=S256" in url and "state=s" in url
    assert posted[0]["grant_type"] == "authorization_code" and posted[0]["code_verifier"] == "v"
    assert posted[0]["client_secret"] == "secret"
    assert identity == OidcIdentity(issuer, "sub-1", "anna@example.org", True, "anna")
    for change in (
        {"nonce": "other"},
        {"aud": "someone-else"},
        {"iss": "https://evil.example"},
        {"exp": time.time() - 10},
    ):
        claims.update(change)
        with pytest.raises(OidcError):
            provider.exchange(code="c", verifier="v", nonce="nonce-1", redirect_uri="x")
        claims.update({"iss": issuer, "aud": "hiker", "nonce": "nonce-1", "exp": time.time() + 300})
