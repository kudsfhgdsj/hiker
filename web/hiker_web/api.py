"""Client of the hiker REST API. The web frontend has no data or logic of its own."""

import httpx2
from flask import current_app, g, request, session

API_PREFIX = "/api/v1"


class ApiError(Exception):
    """An error answer of the API, or `network` if it cannot be reached."""

    def __init__(self, status: int, code: str, message: str = "", body: dict | None = None):
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code
        self.message = message
        self.body = body or {}


def _error(response: httpx2.Response) -> ApiError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    detail = body.get("error") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        return ApiError(
            response.status_code, detail.get("code", "unknown"), detail.get("message", ""), body
        )
    code = "validation" if response.status_code == 422 else "unknown"
    return ApiError(response.status_code, code, "", body if isinstance(body, dict) else {})


class Api:
    """Requests on behalf of the signed-in user; renews the access token once."""

    def __init__(self):
        self._client: httpx2.Client = current_app.extensions["api_client"]
        self._store = current_app.extensions["session_store"]

    # --- session ---

    @property
    def session_id(self) -> str | None:
        return session.get("sid")

    @property
    def data(self) -> dict | None:
        if "session_data" not in g:
            g.session_data = self._store.load(self.session_id)
        return g.session_data

    def sign_in(self, auth: dict, modules: list[str]) -> None:
        data = {
            "access": auth["access_token"],
            "refresh": auth["refresh_token"],
            "user": auth["user"],
            "modules": modules,
        }
        self._store.delete(self.session_id)
        session.clear()
        session["sid"] = self._store.create(data)
        g.session_data = data

    def sign_out(self) -> None:
        self._store.delete(self.session_id)
        session.clear()
        g.session_data = None

    # --- requests ---

    def _send(self, method: str, path: str, token: str | None, **kwargs) -> httpx2.Response:
        headers = dict(kwargs.pop("headers", None) or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # The API limits requests per client address: pass on the browser's, not ours.
        if request and request.remote_addr:
            headers["X-Forwarded-For"] = request.remote_addr
        try:
            return self._client.request(method, f"{API_PREFIX}{path}", headers=headers, **kwargs)
        except httpx2.HTTPError as exc:
            raise ApiError(503, "network", str(exc)) from exc

    def request(self, method: str, path: str, *, auth: bool = True, **kwargs) -> httpx2.Response:
        data = self.data if auth else None
        response = self._send(method, path, data["access"] if data else None, **kwargs)
        if response.status_code == 401 and data:
            refreshed = self._send(
                "POST", "/auth/refresh", None, json={"refresh_token": data["refresh"]}
            )
            if refreshed.status_code != 200:
                # The refresh token is no longer valid: the user has to sign in again.
                self.sign_out()
                raise ApiError(401, "session_expired")
            tokens = refreshed.json()
            data = {**data, "access": tokens["access_token"], "refresh": tokens["refresh_token"]}
            self._store.save(self.session_id, data)
            g.session_data = data
            response = self._send(method, path, data["access"], **kwargs)
        if response.status_code >= 400:
            raise _error(response)
        return response

    def get(self, path: str, **params):
        params = {key: value for key, value in params.items() if value not in (None, "", [])}
        return self.request("GET", path, params=params).json()

    def send(self, method: str, path: str, json=None, **kwargs):
        response = self.request(method, path, json=json, **kwargs)
        return response.json() if response.content else None

    def pages(self, path: str, **params) -> list[dict]:
        """All items of a paged list."""
        items: list[dict] = []
        while True:
            page = self.get(path, limit=200, offset=len(items), **params)
            items.extend(page["items"])
            if len(page["items"]) < 200 or len(items) >= page["total"]:
                return items


def api() -> Api:
    if "api" not in g:
        g.api = Api()
    return g.api
