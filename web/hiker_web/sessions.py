"""Server-side sessions: the browser only holds a random id in a signed cookie.

Access and refresh tokens never leave the server. Each session is a small JSON
file; that survives restarts and needs no extra service.
"""

import json
import os
import re
import secrets
from pathlib import Path

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,}$")


class SessionStore:
    def __init__(self, directory: str | Path):
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        os.chmod(self._directory, 0o700)

    def _path(self, session_id: str) -> Path | None:
        return self._directory / f"{session_id}.json" if _ID_RE.match(session_id or "") else None

    def create(self, data: dict) -> str:
        session_id = secrets.token_urlsafe(32)
        self.save(session_id, data)
        return session_id

    def load(self, session_id: str | None) -> dict | None:
        path = self._path(session_id or "")
        if path is None or not path.is_file():
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return None

    def save(self, session_id: str, data: dict) -> None:
        path = self._path(session_id)
        if path is None:
            raise ValueError("invalid session id")
        temporary = path.with_suffix(".part")
        temporary.write_text(json.dumps(data))
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)

    def delete(self, session_id: str | None) -> None:
        path = self._path(session_id or "")
        if path is not None:
            path.unlink(missing_ok=True)
