import json
import re

import httpx2
import pytest

from hiker_web import create_app

USER = {
    "id": "11111111-1111-4111-8111-111111111111",
    "email": "anna@example.org",
    "display_name": "Anna",
    "role": "user",
}
ALL_MODULES = ["auth", "gear", "nutrition", "protocols", "sync", "planning", "maps", "reports"]


def error(status: int, code: str) -> httpx2.Response:
    return httpx2.Response(status, json={"error": {"code": code, "message": code}})


class FakeApi:
    """Stands in for the hiker API: a table of `METHOD /path` → handler."""

    def __init__(self):
        self.routes: dict[str, object] = {}
        self.calls: list[httpx2.Request] = []
        self.modules = list(ALL_MODULES)
        self.offline = False
        self.valid_tokens = {"access-1"}
        self.route("POST", "/auth/login", lambda r: httpx2.Response(200, json=self.auth()))
        self.route("GET", "/auth/oidc", {"enabled": False, "name": "SSO"})
        self.route(
            "GET",
            "/modules",
            lambda r: httpx2.Response(
                200, json=[{"name": name, "version": "0.1.0"} for name in self.modules]
            ),
        )

    def auth(self, access="access-1", refresh="refresh-1") -> dict:
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": 900,
            "user": USER,
        }

    def route(self, method: str, path: str, handler) -> None:
        """`path` may contain `*` for one path segment. A handler can also be plain JSON data."""
        self.routes[f"{method} {path}"] = handler

    def requested(self) -> list[str]:
        return [f"{r.method} {r.url.path.removeprefix('/api/v1')}" for r in self.calls]

    def body(self, index: int = -1):
        return json.loads(self.calls[index].content or b"null")

    def last(self, method: str, path: str) -> httpx2.Request:
        return [r for r in self.calls if r.method == method and r.url.path == f"/api/v1{path}"][-1]

    def _handler(self, request: httpx2.Request) -> httpx2.Response:
        self.calls.append(request)
        if self.offline:
            raise httpx2.ConnectError("offline")
        path = request.url.path.removeprefix("/api/v1")
        public = path.startswith(("/auth/", "/public/", "/maps/")) or path == "/modules"
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        if not public and token not in self.valid_tokens:
            return error(401, "invalid_token")
        for key, handler in self.routes.items():
            method, pattern = key.split(" ", 1)
            regex = "^" + re.escape(pattern).replace(r"\*", "[^/]+") + "$"
            if method == request.method and re.match(regex, path):
                if callable(handler):
                    return handler(request)
                return httpx2.Response(200, json=handler)
        return error(404, "not_found")

    @property
    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self._handler)


@pytest.fixture
def fake_api():
    return FakeApi()


@pytest.fixture
def app(fake_api, tmp_path):
    return create_app(
        {
            "SECRET_KEY": "test-secret-key-not-for-production-0123456789",
            "SESSION_DIR": str(tmp_path / "sessions"),
            "SESSION_COOKIE_SECURE": False,
            "API_TRANSPORT": fake_api.transport,
            "TESTING": True,
        }
    )


class Browser:
    """A test client that sends the CSRF token like a real form would."""

    def __init__(self, app):
        self.client = app.test_client()

    def get(self, path, **kwargs):
        return self.client.get(path, **kwargs)

    def csrf(self) -> str:
        # A real browser gets the token with the form; the tests put it into the session.
        with self.client.session_transaction() as session:
            return session.setdefault("csrf", "test-csrf-token")

    def post(self, path, data=None, **kwargs):
        data = {**(data or {}), "csrf_token": self.csrf()}
        return self.client.post(path, data=data, **kwargs)

    def login(self):
        response = self.post("/login", {"email": "anna@example.org", "password": "secret-password"})
        assert response.status_code == 302, response.get_data(as_text=True)
        return response


@pytest.fixture
def browser(app):
    return Browser(app)


@pytest.fixture
def user(browser, fake_api):
    """A browser that is signed in."""
    browser.login()
    fake_api.calls.clear()
    return browser
