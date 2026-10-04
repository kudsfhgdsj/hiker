"""Password rules, second factor, single sign-on and the administration of users."""

import json

import httpx2

from tests.conftest import USER, error

ADMIN = {**USER, "role": "admin", "mfa_enabled": True, "sso": False, "has_password": True}
OTHER = {
    "id": "22222222-2222-4222-8222-222222222222",
    "email": "ben@example.org",
    "display_name": "Ben",
    "role": "user",
    "mfa_enabled": False,
    "sso": True,
    "has_password": False,
    "last_login_at": None,
    "must_change_password": True,
}


def text(response) -> str:
    return response.get_data(as_text=True)


def sign_in_as(browser, fake_api, **auth):
    fake_api.route(
        "POST", "/auth/login", lambda r: httpx2.Response(200, json={**fake_api.auth(), **auth})
    )
    browser.login()
    fake_api.calls.clear()


# --- Registration and password rules ---


def test_registration_asks_for_the_password_twice(browser, fake_api):
    form = text(browser.get("/register"))
    response = browser.post(
        "/register",
        {
            "email": "anna@example.org",
            "display_name": "Anna",
            "password": "Correct-Horse-7",
            "password_repeat": "Correct-Horse-8",
        },
    )

    assert 'name="password_repeat"' in form and "Passwort wiederholen" in form
    assert "Mindestens 8 Zeichen" in form
    assert response.status_code == 200
    assert "Die beiden Passwörter stimmen nicht überein." in text(response)
    assert "POST /auth/register" not in fake_api.requested()


def test_weak_password_is_explained_with_the_reason_of_the_api(browser, fake_api):
    fake_api.route(
        "POST",
        "/auth/register",
        lambda r: httpx2.Response(
            422,
            json={"error": {"code": "weak_password", "message": "x"}, "reason": "too_simple"},
        ),
    )

    response = browser.post(
        "/register",
        {
            "email": "a@b.ch",
            "display_name": "A",
            "password": "einfach1",
            "password_repeat": "einfach1",
        },
    )

    assert "Zu einfach" in text(response) and "mindestens 20 Zeichen" in text(response)


# --- Second factor ---


def test_login_asks_for_the_code_on_a_second_page(browser, fake_api):
    fake_api.route(
        "POST",
        "/auth/login",
        lambda r: httpx2.Response(
            401,
            json={"error": {"code": "mfa_required", "message": "x"}, "mfa_token": "step-1-token"},
        ),
    )
    fake_api.route(
        "POST",
        "/auth/login/mfa",
        lambda r: (
            httpx2.Response(200, json=fake_api.auth())
            if json.loads(r.content)["code"] == "123456"
            else error(401, "invalid_mfa_code")
        ),
    )
    fake_api.route("GET", "/gear/items", {"items": [], "total": 0, "limit": 200, "offset": 0})
    fake_api.route("GET", "/gear/types", [])
    fake_api.route("GET", "/gear/tags", [])

    form = text(browser.get("/login"))
    first = browser.post("/login?next=/gear/", {"email": "anna@example.org", "password": "pw"})
    page = text(browser.get("/login/code"))
    wrong = browser.post("/login/code", {"code": "000000"})
    again = text(browser.get("/login/code"))
    right = browser.post("/login/code", {"code": " 123456 "})

    # The first page only asks for e-mail and password.
    assert 'name="code"' not in form
    assert first.headers["location"] == "/login/code"
    assert "Das Passwort stimmt." in page and 'name="code"' in page
    assert 'name="password"' not in page
    assert wrong.headers["location"] == "/login/code"
    assert "Der Code stimmt nicht" in again
    assert json.loads(fake_api.last("POST", "/auth/login/mfa").content) == {
        "mfa_token": "step-1-token",
        "code": "123456",
    }
    # On to the page the user wanted, signed in.
    assert right.headers["location"] == "/gear/"
    assert browser.get("/gear/").status_code == 200
    # The token of the first step is used up.
    assert browser.get("/login/code").headers["location"] == "/login"


def test_second_step_without_first_or_after_it_expired(browser, fake_api):
    assert browser.get("/login/code").headers["location"] == "/login"
    fake_api.route(
        "POST",
        "/auth/login",
        lambda r: httpx2.Response(
            401, json={"error": {"code": "mfa_required", "message": "x"}, "mfa_token": "old"}
        ),
    )
    fake_api.route("POST", "/auth/login/mfa", lambda r: error(401, "mfa_token_invalid"))
    browser.post("/login", {"email": "anna@example.org", "password": "pw"})

    expired = browser.post("/login/code", {"code": "123456"})

    assert expired.headers["location"] == "/login"
    assert "zu lange gedauert" in text(browser.get("/login"))


def test_session_without_second_factor_only_reaches_the_setup(browser, fake_api):
    sign_in_as(browser, fake_api, mfa_setup_required=True)
    fake_api.route(
        "POST",
        "/auth/mfa/setup",
        {
            "secret": "JBSWY3DPEHPK3PXP",
            "otpauth_uri": "otpauth://totp/hiker:anna?secret=JBSWY3DPEHPK3PXP",
        },
    )

    assert browser.get("/").headers["location"] == "/mfa/setup"
    assert browser.get("/gear/").headers["location"] == "/mfa/setup"
    assert browser.get("/profile").headers["location"] == "/mfa/setup"
    page = text(browser.get("/mfa/setup"))
    again = text(browser.get("/mfa/setup"))

    assert "ist ein zweiter Faktor Pflicht" in page and "JBSWY3DPEHPK3PXP" in page
    assert "<svg" in page and "Ausrüstung" not in page
    # Reloading the page keeps the secret, so that the scanned code stays valid.
    assert "JBSWY3DPEHPK3PXP" in again
    assert fake_api.requested().count("POST /auth/mfa/setup") == 1


def test_enabling_the_second_factor_shows_the_recovery_codes_once(browser, fake_api):
    sign_in_as(browser, fake_api, mfa_setup_required=True)
    fake_api.valid_tokens.add("access-mfa")
    fake_api.route("POST", "/auth/mfa/setup", {"secret": "S", "otpauth_uri": "otpauth://x"})
    fake_api.route(
        "POST",
        "/auth/mfa/enable",
        lambda r: (
            httpx2.Response(
                200,
                json={
                    **fake_api.auth(access="access-mfa", refresh="refresh-mfa"),
                    "mfa_setup_required": False,
                    "recovery_codes": ["abcde-12345", "fghij-67890"],
                },
            )
            if json.loads(r.content)["code"] == "654321"
            else error(422, "invalid_mfa_code")
        ),
    )
    fake_api.route("GET", "/me/profile", {})

    wrong = browser.post("/mfa/setup", {"code": "000000"})
    assert wrong.headers["location"] == "/mfa/setup"
    assert "Der Code stimmt nicht" in text(browser.get("/mfa/setup"))
    done = browser.post("/mfa/setup", {"code": "654321"})

    assert "abcde-12345" in text(done) and "nur dieses eine Mal" in text(done)
    # The session is complete now and uses the new tokens.
    assert browser.get("/profile").status_code == 200
    assert fake_api.last("GET", "/me/profile").headers["authorization"] == "Bearer access-mfa"


def test_api_refusal_leads_to_the_page_that_completes_the_sign_in(user, fake_api):
    fake_api.route("GET", "/gear/items", lambda r: error(403, "mfa_setup_required"))
    fake_api.route("GET", "/gear/types", [])
    fake_api.route("GET", "/gear/tags", [])

    assert user.get("/gear/").headers["location"] == "/mfa/setup"
    assert user.get("/profile").headers["location"] == "/mfa/setup"


def test_forced_password_change(browser, fake_api):
    sign_in_as(browser, fake_api, password_change_required=True)
    fake_api.route(
        "POST",
        "/auth/password",
        lambda r: (
            httpx2.Response(200, json=fake_api.auth())
            if json.loads(r.content)["current_password"] == "temp"
            else error(422, "wrong_password")
        ),
    )

    assert browser.get("/tours/").headers["location"] == "/password"
    assert browser.get("/mfa/setup").headers["location"] == "/password"
    page = text(browser.get("/password"))
    differ = browser.post(
        "/password", {"current_password": "temp", "new_password": "a", "password_repeat": "b"}
    )
    wrong = browser.post(
        "/password",
        {"current_password": "x", "new_password": "Neu-8-neu", "password_repeat": "Neu-8-neu"},
    )
    done = browser.post(
        "/password",
        {"current_password": "temp", "new_password": "Neu-8-neu", "password_repeat": "Neu-8-neu"},
    )

    assert "wurde zurückgesetzt" in page
    assert "stimmen nicht überein" in text(differ)
    assert "Das bisherige Passwort stimmt nicht." in text(wrong)
    assert done.headers["location"] == "/"
    assert json.loads(fake_api.last("POST", "/auth/password").content) == {
        "current_password": "temp",
        "new_password": "Neu-8-neu",
    }


def test_new_recovery_codes_need_a_code(user, fake_api):
    fake_api.route("POST", "/auth/mfa/recovery-codes", {"recovery_codes": ["aaaaa-bbbbb"]})

    response = user.post("/mfa/recovery-codes", {"code": "123456"})

    assert "aaaaa-bbbbb" in text(response)
    assert fake_api.body() == {"code": "123456"}


# --- Single sign-on ---


def test_single_sign_on_button_only_if_the_server_offers_it(browser, fake_api):
    assert "/login/sso" not in text(browser.get("/login"))
    fake_api.route("GET", "/auth/oidc", {"enabled": True, "name": "Authelia"})

    assert "Mit Authelia anmelden" in text(browser.get("/login"))


def test_single_sign_on_round_trip(browser, fake_api):
    fake_api.route(
        "POST",
        "/auth/oidc/start",
        {"authorization_url": "https://sso.example/auth?state=st-1", "state": "st-1"},
    )
    fake_api.route(
        "POST", "/auth/oidc/callback", lambda r: httpx2.Response(200, json=fake_api.auth())
    )
    fake_api.route("GET", "/me/profile", {})

    start = browser.get("/login/sso")
    forged = browser.get("/login/sso/callback?state=other&code=c")
    assert "POST /auth/oidc/callback" not in fake_api.requested()
    browser.get("/login/sso")
    back = browser.get("/login/sso/callback?state=st-1&code=the-code")

    assert start.headers["location"] == "https://sso.example/auth?state=st-1"
    assert forged.headers["location"] == "/login"
    assert back.headers["location"] == "/"
    assert json.loads(fake_api.last("POST", "/auth/oidc/callback").content) == {
        "state": "st-1",
        "code": "the-code",
    }
    assert browser.get("/profile").status_code == 200
    # The state works for one answer only.
    assert browser.get("/login/sso/callback?state=st-1&code=again").headers["location"] == "/login"


def test_single_sign_on_error_of_the_provider(browser, fake_api):
    fake_api.route("POST", "/auth/oidc/start", {"authorization_url": "https://s/", "state": "s"})
    browser.get("/login/sso")

    response = browser.get("/login/sso/callback?error=access_denied&state=s")

    assert response.headers["location"] == "/login"
    assert "hat nicht geklappt" in text(browser.get("/login"))


# --- Administration ---


def test_admin_page_lists_users_and_acts_on_them(browser, fake_api):
    sign_in_as(browser, fake_api, user=ADMIN)
    fake_api.route(
        "GET",
        "/admin/users",
        [{**ADMIN, "last_login_at": "2026-10-04T08:00:00Z", "must_change_password": False}, OTHER],
    )
    fake_api.route(
        "POST", "/admin/users/*/reset-password", {"temporary_password": "Temp-Pass-1234"}
    )
    fake_api.route("POST", "/admin/users/*/reset-mfa", lambda r: httpx2.Response(204))
    fake_api.route("DELETE", "/admin/users/*", lambda r: httpx2.Response(204))

    page = text(browser.get("/admin/users"))
    reset = text(browser.post(f"/admin/users/{OTHER['id']}/reset-password"))
    browser.post(f"/admin/users/{ADMIN['id']}/reset-mfa")
    deleted = browser.post(f"/admin/users/{OTHER['id']}/delete")

    assert "Verwaltung" in page and "ben@example.org" in page and "SSO" in page
    assert "muss Passwort ändern" in page and "kein 2. Faktor" in page
    # The own account has no button to remove it.
    assert f"/admin/users/{ADMIN['id']}/delete" not in page
    assert f"/admin/users/{OTHER['id']}/delete" in page
    assert "Temp-Pass-1234" in reset and "nur jetzt angezeigt" in reset
    assert f"POST /admin/users/{ADMIN['id']}/reset-mfa" in fake_api.requested()
    assert deleted.headers["location"] == "/admin/users"
    assert f"DELETE /admin/users/{OTHER['id']}" in fake_api.requested()


def test_admin_pages_are_the_decision_of_the_api(user, fake_api):
    fake_api.route("GET", "/admin/users", lambda r: error(403, "forbidden"))
    fake_api.route("GET", "/me/profile", {})

    assert "Verwaltung" not in text(user.get("/profile"))
    assert user.get("/admin/users").status_code == 403
