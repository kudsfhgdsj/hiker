import json
import logging
from pathlib import Path

import httpx2
import pytest

from hiker_web import create_app, formatting
from hiker_web.security import TokenRedactionFilter
from tests.conftest import USER, error


def text(response) -> str:
    return response.get_data(as_text=True)


def test_app_needs_a_secret_key(tmp_path):
    with pytest.raises(RuntimeError):
        create_app({"SECRET_KEY": "short", "SESSION_DIR": str(tmp_path)})


def test_pages_require_login(browser):
    response = browser.get("/profile")

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=")
    assert browser.get("/").headers["location"] == "/login"


def test_login_keeps_the_tokens_on_the_server(browser, fake_api, app):
    response = browser.login()

    assert response.headers["location"] == "/"
    assert fake_api.body(0) == {"email": "anna@example.org", "password": "secret-password"}
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    # The browser only gets a session id; the tokens stay in a file on the server.
    assert "access-1" not in cookie and "refresh-1" not in cookie
    [stored] = Path(app.config["SESSION_DIR"]).glob("*.json")
    data = json.loads(stored.read_text())
    assert (data["access"], data["refresh"]) == ("access-1", "refresh-1")
    assert data["user"]["display_name"] == "Anna"
    assert stored.stat().st_mode & 0o777 == 0o600


def test_wrong_credentials_show_a_german_message(browser, fake_api):
    fake_api.route("POST", "/auth/login", lambda r: error(401, "invalid_credentials"))

    response = browser.post("/login", {"email": "anna@example.org", "password": "wrong"})

    assert response.status_code == 200
    assert "E-Mail oder Passwort ist falsch." in text(response)
    assert 'value="anna@example.org"' in text(response)


def test_unreachable_api_is_explained(browser, fake_api):
    fake_api.offline = True

    response = browser.post("/login", {"email": "anna@example.org", "password": "x"})

    assert "Der Server ist gerade nicht erreichbar" in text(response)


def test_forms_without_csrf_token_are_rejected(browser, fake_api):
    response = browser.client.post("/login", data={"email": "anna@example.org", "password": "x"})
    wrong = browser.client.post(
        "/login", data={"email": "a@b.ch", "password": "x", "csrf_token": "nope"}
    )

    assert response.status_code == 400 and wrong.status_code == 400
    assert "Das Formular ist abgelaufen" in text(response)
    assert fake_api.calls == []


def test_login_only_follows_paths_of_this_site(browser):
    inside = browser.post("/login?next=/profile", {"email": "a@b.ch", "password": "x"})
    outside = browser.post(
        "/login?next=https://evil.example/", {"email": "a@b.ch", "password": "x"}
    )
    tricky = browser.post("/login?next=//evil.example/", {"email": "a@b.ch", "password": "x"})

    assert inside.headers["location"] == "/profile"
    assert outside.headers["location"] == "/" and tricky.headers["location"] == "/"


def test_registration_signs_in(browser, fake_api):
    fake_api.route("POST", "/auth/register", lambda r: httpx2.Response(201, json=fake_api.auth()))

    response = browser.post(
        "/register",
        {
            "email": "anna@example.org",
            "display_name": "Anna",
            "password": "Correct-Horse-7",
            "password_repeat": "Correct-Horse-7",
        },
    )

    assert response.status_code == 302
    assert fake_api.body(0)["display_name"] == "Anna"
    assert "password_repeat" not in fake_api.body(0)
    assert browser.get("/profile").status_code != 302


def test_closed_registration_is_explained(browser, fake_api):
    fake_api.route("POST", "/auth/register", lambda r: error(403, "registration_closed"))

    response = browser.post(
        "/register",
        {"email": "a@b.ch", "display_name": "A", "password": "x" * 10, "password_repeat": "x" * 10},
    )

    assert "keine neuen Konten" in text(response)


def test_navigation_shows_only_enabled_modules(browser, fake_api):
    fake_api.modules = ["auth", "gear"]
    fake_api.route("GET", "/me/profile", {})
    browser.login()

    page = text(browser.get("/profile"))

    assert "Ausrüstung" in page and "Profil" in page
    assert "Touren" not in page and ">Essen<" not in page


def test_profile_is_shown_and_saved(user, fake_api):
    fake_api.route(
        "GET",
        "/me/profile",
        {
            "weight_kg": 72.5,
            "birth_year": 1988,
            "sex": "female",
            "max_heart_rate": None,
            "resting_heart_rate": 52,
        },
    )
    fake_api.route("PUT", "/me/profile", lambda r: httpx2.Response(200, json=json.loads(r.content)))

    page = text(user.get("/profile"))
    response = user.post(
        "/profile",
        {
            "weight_kg": "70,5",
            "birth_year": "1988",
            "sex": "trans",
            "max_heart_rate": "",
            "resting_heart_rate": "50",
        },
    )

    assert "Angemeldet als Anna" in page and 'value="72.5"' in page
    assert '<option value="female" selected>' in page
    assert response.status_code == 302
    assert json.loads(fake_api.last("PUT", "/me/profile").content) == {
        "weight_kg": 70.5,
        "birth_year": 1988,
        "sex": "trans",
        "max_heart_rate": None,
        "resting_heart_rate": 50,
    }


def test_profile_rejects_text_in_number_fields(user, fake_api):
    fake_api.route("GET", "/me/profile", {})

    response = user.post("/profile", {"weight_kg": "viel"})

    assert "Die Eingaben wurden nicht angenommen" in text(response)
    assert "PUT /me/profile" not in fake_api.requested()


def test_expired_access_token_is_renewed_once(user, fake_api, app):
    fake_api.valid_tokens = {"access-2"}
    fake_api.route(
        "POST",
        "/auth/refresh",
        lambda r: httpx2.Response(
            200, json={"access_token": "access-2", "refresh_token": "refresh-2"}
        ),
    )
    fake_api.route("GET", "/me/profile", {})

    response = user.get("/profile")

    assert response.status_code == 200
    assert fake_api.requested() == ["GET /me/profile", "POST /auth/refresh", "GET /me/profile"]
    [stored] = Path(app.config["SESSION_DIR"]).glob("*.json")
    assert json.loads(stored.read_text())["refresh"] == "refresh-2"


def test_rejected_refresh_token_ends_the_session(user, fake_api, app):
    fake_api.valid_tokens = set()
    fake_api.route("POST", "/auth/refresh", lambda r: error(401, "invalid_refresh_token"))

    response = user.get("/profile")

    assert response.status_code == 302 and response.headers["location"] == "/login"
    assert list(Path(app.config["SESSION_DIR"]).glob("*.json")) == []
    assert "Die Anmeldung ist abgelaufen" in text(user.get("/login"))


def test_logout_revokes_the_token_and_removes_the_session(user, fake_api, app):
    fake_api.route("POST", "/auth/logout", lambda r: httpx2.Response(204))

    response = user.post("/logout")

    assert response.headers["location"] == "/login"
    assert fake_api.body() == {"refresh_token": "refresh-1"}
    assert list(Path(app.config["SESSION_DIR"]).glob("*.json")) == []
    assert user.get("/profile").status_code == 302


def test_client_address_is_passed_on_for_the_rate_limit(browser, fake_api):
    browser.post(
        "/login", {"email": "a@b.ch", "password": "x"}, headers={"X-Forwarded-For": "203.0.113.7"}
    )

    assert fake_api.calls[0].headers["x-forwarded-for"] == "203.0.113.7"


def test_security_headers_and_health(browser):
    response = browser.get("/healthz")

    assert response.json == {"status": "ok"}
    assert response.headers["X-Frame-Options"] == "DENY"
    assert browser.get("/gibt-es-nicht").status_code == 404


def test_tokens_of_public_links_never_reach_the_log():
    record = logging.LogRecord(
        "werkzeug",
        logging.INFO,
        __file__,
        1,
        '%s - "%s" %s',
        ("127.0.0.1", "GET /p/0b9d6c1e-1111-4222 HTTP/1.1", 200),
        None,
    )

    TokenRedactionFilter().filter(record)

    assert "0b9d6c1e" not in record.getMessage()
    assert "/p/[redacted]" in record.getMessage()


def test_german_formatting():
    assert formatting.weight(890) == "890 g"
    assert formatting.weight(1500) == "1,5 kg"
    assert formatting.weight(None) == "–"
    assert formatting.money(1234.5, "CHF") == "1.234,50 CHF"
    assert formatting.distance(12340) == "12,3 km"
    assert formatting.distance(450) == "450 m"
    assert formatting.meters(2502) == "2.502 m"
    assert formatting.duration(510) == "8 h 30 min"
    assert formatting.duration(45) == "45 min"
    assert formatting.date("2026-08-01T06:00:00Z") == "01.08.2026"
    assert USER["display_name"] == "Anna"


def test_renewal_uses_tokens_another_request_stored_meanwhile(user, fake_api, app):
    """A refresh token works once, and a page loads its images in parallel."""
    from flask import g

    from hiker_web.api import api

    fake_api.valid_tokens = {"access-2"}
    fake_api.route("GET", "/me/profile", {"ok": True})
    store = app.extensions["session_store"]
    session_id = next(iter(store._directory.glob("*.json"))).stem
    with user.client.session_transaction() as cookie_session:
        assert cookie_session["sid"] == session_id

    with app.test_request_context():
        from flask import session

        session["sid"] = session_id
        client = api()
        assert client.data["access"] == "access-1"
        # Meanwhile a parallel request renews and stores the tokens.
        store.save(session_id, {**client.data, "access": "access-2", "refresh": "r-2"})
        assert client.get("/me/profile") == {"ok": True}
        assert g.session_data["access"] == "access-2"

    assert "POST /auth/refresh" not in fake_api.requested()


def test_unused_sessions_are_removed(app, tmp_path):
    import os
    import time

    from hiker_web.sessions import SessionStore

    store = SessionStore(tmp_path / "s", max_age_seconds=3600)
    old = store.create({"access": "a"})
    fresh = store.create({"access": "b"})
    past = time.time() - 7200
    os.utime(tmp_path / "s" / f"{old}.json", (past, past))

    newest = store.create({"access": "c"})

    assert store.load(old) is None
    assert store.load(fresh) and store.load(newest)
