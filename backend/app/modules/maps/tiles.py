"""Map tiles, kept on the own server.

A tile is fetched from the tile source (by default the tile server of
OpenStreetMap) the first time someone looks at it and stored as a file. Later
requests are answered from the file. Only after `TILE_CACHE_DAYS` the source is
asked again, with the stored ETag: if the tile is unchanged the answer carries
no data and the file is kept.

This follows the tile usage policy of OpenStreetMap: tiles are cached for at
least seven days, requests carry a User-Agent that names this installation, and
nothing is downloaded in advance. If the source cannot be reached, a stored
tile is served even when it is old, so that known areas keep working offline.
"""

import contextlib
import logging
import os
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Protocol

import httpx2
from fastapi import Depends

from app import __version__
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError

logger = logging.getLogger(__name__)

OSM_ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
# Look at the size of the cache after this many new tiles.
_PURGE_EVERY = 500


class TileSourceError(Exception):
    """The tile source could not be reached or answered with an error."""


class TileUnavailableError(AppError):
    status_code = 502
    code = "source_unavailable"


@dataclass(frozen=True)
class FetchedTile:
    """Answer of the source: `data` is None if the stored tile is still current."""

    data: bytes | None
    etag: str | None = None


class TileSource(Protocol):
    def fetch(self, z: int, x: int, y: int, etag: str | None) -> FetchedTile | None:
        """The tile, `FetchedTile(None)` if `etag` is still current, None if there is none."""


class DisabledTileSource:
    def fetch(self, z, x, y, etag) -> FetchedTile | None:
        return None


class HttpTileSource:
    def __init__(
        self,
        url_template: str,
        user_agent: str,
        referer: str,
        *,
        timeout: float = 15.0,
        transport: httpx2.BaseTransport | None = None,
    ):
        self._template = url_template
        self._client = httpx2.Client(
            headers={"User-Agent": user_agent, "Referer": referer},
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
        )

    def fetch(self, z: int, x: int, y: int, etag: str | None) -> FetchedTile | None:
        url = self._template.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
        try:
            response = self._client.get(url, headers={"If-None-Match": etag} if etag else None)
        except httpx2.HTTPError as exc:
            raise TileSourceError(str(exc)) from exc
        if response.status_code == 304:
            return FetchedTile(None, etag)
        if response.status_code == 404:
            return None
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200 or not content_type.startswith("image/"):
            raise TileSourceError(f"status {response.status_code}, type {content_type!r}")
        return FetchedTile(response.content, response.headers.get("etag"))


class TileCache:
    """Tiles as files below `directory`: `<z>/<x>/<y>.png` and the ETag next to it.

    The modification time of the file is the moment the source was last asked.
    """

    def __init__(self, directory: str | Path, max_age_days: float, max_bytes: int):
        self._directory = Path(directory)
        self._max_age_seconds = max_age_days * 86400
        self._max_bytes = max_bytes
        self._new_tiles = 0
        self._lock = threading.Lock()

    def _path(self, z: int, x: int, y: int) -> Path:
        return self._directory / str(z) / str(x) / f"{y}.png"

    def get(self, source: TileSource, z: int, x: int, y: int) -> bytes:
        path = self._path(z, x, y)
        etag_path = path.with_suffix(".etag")
        stored = self._read(path)
        if stored is not None and time.time() - path.stat().st_mtime < self._max_age_seconds:
            return stored
        etag = self._read_text(etag_path) if stored is not None else None
        try:
            fetched = source.fetch(z, x, y, etag)
        except TileSourceError as exc:
            if stored is not None:
                logger.info("Tile source unreachable, serving stored tile: %s", exc)
                return stored
            logger.warning("Tile source unreachable: %s", exc)
            raise TileUnavailableError("The tile source could not be reached") from exc
        if fetched is None:
            if stored is not None:
                return stored
            raise NotFoundError("No such tile")
        if fetched.data is None:
            # Unchanged at the source: keep the file and ask again after the next period.
            if stored is None:
                raise TileUnavailableError("The tile source sent no data")
            with contextlib.suppress(OSError):
                os.utime(path)
            return stored
        self._write(path, etag_path, fetched)
        return fetched.data

    @staticmethod
    def _read(path: Path) -> bytes | None:
        try:
            return path.read_bytes()
        except OSError:
            return None

    @staticmethod
    def _read_text(path: Path) -> str | None:
        try:
            return path.read_text().strip() or None
        except OSError:
            return None

    def _write(self, path: Path, etag_path: Path, fetched: FetchedTile) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(f".{threading.get_ident()}.part")
            temporary.write_bytes(fetched.data)
            os.replace(temporary, path)
            if fetched.etag:
                etag_path.write_text(fetched.etag)
            else:
                etag_path.unlink(missing_ok=True)
        except OSError as exc:
            # A full or read-only disk must not break the map.
            logger.warning("Could not store tile %s: %s", path, exc)
            return
        with self._lock:
            self._new_tiles += 1
            due = self._new_tiles >= _PURGE_EVERY
            if due:
                self._new_tiles = 0
        if due:
            self.purge()

    def purge(self) -> int:
        """Remove the tiles that were not refreshed for the longest time if the cache is
        larger than allowed. Returns the number of removed tiles."""
        tiles = []
        total = 0
        for path in self._directory.glob("*/*/*.png"):
            with contextlib.suppress(OSError):
                stat = path.stat()
                tiles.append((stat.st_mtime, stat.st_size, path))
                total += stat.st_size
        if total <= self._max_bytes:
            return 0
        removed = 0
        # Down to 90 %, so that not every new tile triggers the next round.
        for _mtime, size, path in sorted(tiles, key=lambda tile: tile[0]):
            if total <= self._max_bytes * 0.9:
                break
            with contextlib.suppress(OSError):
                path.unlink()
                path.with_suffix(".etag").unlink(missing_ok=True)
                total -= size
                removed += 1
        return removed


@lru_cache
def _http_source(url: str, user_agent: str, referer: str) -> HttpTileSource:
    return HttpTileSource(url, user_agent, referer)


def get_tile_source() -> TileSource:
    settings = get_settings()
    if not settings.tile_source_url:
        return DisabledTileSource()
    user_agent = f"hiker/{__version__} (self-hosted; {settings.public_base_url})"
    return _http_source(settings.tile_source_url, user_agent, settings.public_base_url)


@lru_cache
def _cache(directory: str, days: int, max_mb: int) -> TileCache:
    return TileCache(directory, days, max_mb * 1024 * 1024)


def get_tile_cache() -> TileCache:
    settings = get_settings()
    return _cache(settings.tile_cache_path, settings.tile_cache_days, settings.tile_cache_max_mb)


Tiles = Annotated[TileSource, Depends(get_tile_source)]
Cache = Annotated[TileCache, Depends(get_tile_cache)]
