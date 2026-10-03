"""File storage behind an interface; the backend is chosen by configuration."""

from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class Storage(Protocol):
    def save(self, key: str, data: bytes) -> None: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None:
        """Remove the object; a missing key is not an error."""

    def exists(self, key: str) -> bool: ...


@lru_cache
def get_storage() -> Storage:
    from app.core.storage.local_fs import LocalFsStorage

    return LocalFsStorage(get_settings().storage_path)
