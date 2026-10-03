"""Server-side sessions: the browser only holds a random id in a signed cookie.

Access and refresh tokens never leave the server. Each session is a small JSON
file; that survives restarts and needs no extra service.
"""

import contextlib
import fcntl
import json
import os
import re
import secrets
import time
from pathlib import Path

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,}$")


class SessionStore:
    def __init__(self, directory: str | Path, max_age_seconds: float | None = None):
        self._max_age_seconds = max_age_seconds
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        os.chmod(self._directory, 0o700)

    def _path(self, session_id: str) -> Path | None:
        return self._directory / f"{session_id}.json" if _ID_RE.match(session_id or "") else None

    def create(self, data: dict) -> str:
        if self._max_age_seconds:
            self.purge(self._max_age_seconds)
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
            path.with_suffix(".lock").unlink(missing_ok=True)

    @contextlib.contextmanager
    def lock(self, session_id: str):
        """One holder at a time per session, across threads and worker processes."""
        path = self._path(session_id)
        if path is None:
            raise ValueError("invalid session id")
        with open(path.with_suffix(".lock"), "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def purge(self, max_age_seconds: float) -> int:
        """Remove sessions that were not used for longer than a refresh token lives."""
        limit = time.time() - max_age_seconds
        removed = 0
        for path in self._directory.glob("*.json"):
            with contextlib.suppress(OSError):
                if path.stat().st_mtime < limit:
                    path.unlink()
                    path.with_suffix(".lock").unlink(missing_ok=True)
                    removed += 1
        return removed
