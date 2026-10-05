import os
import re
from pathlib import Path

_KEY_RE = re.compile(r"^[a-z0-9]+(?:[/._-][a-z0-9]+)*$")


class LocalFsStorage:
    """Stores objects as files below a root directory."""

    def __init__(self, root: str | Path):
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        if not _KEY_RE.match(key):
            raise ValueError(f"invalid storage key: {key!r}")
        return self._root / key

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file first so that readers never see a partial object.
        temporary = path.with_name(path.name + ".part")
        temporary.write_bytes(data)
        os.replace(temporary, path)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()
