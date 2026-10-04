"""The own map: vector tiles built from OpenStreetMap data.

`deploy/build-map.sh` builds one file per region (`<region>.mbtiles`, OpenMapTiles
schema) into `MAP_DATA_PATH`. This module serves single tiles from these files
and offers the files themselves for download, so that the app can show the map
without network. Unlike the tiles of the OpenStreetMap servers this map may be
taken along: it is made from the raw data (ODbL).
"""

import math
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from app.core.config import get_settings

REGION_NAME = r"^[a-z0-9][a-z0-9-]{0,39}$"
VECTOR_ATTRIBUTION = "© OpenStreetMap-Mitwirkende (ODbL) · Schema © OpenMapTiles"


@dataclass(frozen=True)
class VectorRegion:
    name: str
    path: Path
    size_bytes: int
    modified: datetime
    # west, south, east, north
    bounds: tuple[float, float, float, float]
    min_zoom: int
    max_zoom: int
    # The layer pack next to the map (elevation, slope, contour lines), if it was built.
    layers_path: Path | None = None
    layers_size_bytes: int | None = None


def _tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """West, south, east, north of a tile in degrees."""

    def lat(row: int) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * row / 2**z))))

    return (x / 2**z * 360 - 180, lat(y + 1), (x + 1) / 2**z * 360 - 180, lat(y))


class VectorMaps:
    """The map files of a folder. Files may be replaced while the server runs."""

    def __init__(self, folder: str):
        self._folder = Path(folder) if folder else None
        self._local = threading.local()
        self._lock = threading.Lock()
        self._known: dict[Path, tuple[float, VectorRegion]] = {}

    def _read(self, path: Path) -> VectorRegion | None:
        stat = path.stat()
        pack = path.with_name(path.stem + ".layers.sqlite")
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                meta = dict(db.execute("SELECT name, value FROM metadata"))
            if meta.get("format") != "pbf":
                return None
            bounds = tuple(float(part) for part in meta["bounds"].split(","))
            return VectorRegion(
                name=path.stem,
                path=path,
                size_bytes=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime, UTC),
                bounds=bounds,
                min_zoom=int(meta.get("minzoom", 0)),
                max_zoom=int(meta.get("maxzoom", 14)),
                layers_path=pack if pack.is_file() else None,
                layers_size_bytes=pack.stat().st_size if pack.is_file() else None,
            )
        except (sqlite3.Error, KeyError, ValueError):
            # Half-written or foreign file: not a map.
            return None

    def regions(self) -> list[VectorRegion]:
        """All maps, the largest first: it covers the most."""
        if self._folder is None or not self._folder.is_dir():
            return []
        found = []
        with self._lock:
            for path in self._folder.glob("*.mbtiles"):
                if not re.match(REGION_NAME, path.stem) or not path.is_file():
                    continue
                pack = path.with_name(path.stem + ".layers.sqlite")
                # A pack that appeared or changed makes the region new, too.
                modified = path.stat().st_mtime + (pack.stat().st_mtime if pack.is_file() else 0)
                known = self._known.get(path)
                if known is None or known[0] != modified:
                    region = self._read(path)
                    if region is None:
                        continue
                    self._known[path] = known = (modified, region)
                found.append(known[1])
        return sorted(found, key=lambda region: (-region.size_bytes, region.name))

    def region(self, name: str) -> VectorRegion | None:
        return next((region for region in self.regions() if region.name == name), None)

    def _connection(self, region: VectorRegion) -> sqlite3.Connection:
        # One connection per thread and file version; SQLite objects stay in their thread.
        connections = self._local.__dict__.setdefault("connections", {})
        key = (region.path, region.modified)
        if key not in connections:
            for old in [k for k in connections if k[0] == region.path]:
                connections.pop(old).close()
            connections[key] = sqlite3.connect(f"file:{region.path}?mode=ro", uri=True)
        return connections[key]

    def tile(self, z: int, x: int, y: int) -> bytes | None:
        """The gzip-compressed tile of the first map that has it."""
        west, south, east, north = _tile_bounds(z, x, y)
        for region in self.regions():
            left, bottom, right, top = region.bounds
            if not region.min_zoom <= z <= region.max_zoom:
                continue
            if east < left or west > right or north < bottom or south > top:
                continue
            try:
                row = (
                    self._connection(region)
                    .execute(
                        "SELECT tile_data FROM tiles"
                        " WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                        # MBTiles count rows from the south.
                        (z, x, 2**z - 1 - y),
                    )
                    .fetchone()
                )
            except sqlite3.Error:
                continue
            if row is not None:
                return row[0]
        return None

    def max_zoom(self) -> int:
        return max((region.max_zoom for region in self.regions()), default=14)


@lru_cache
def _maps(folder: str) -> VectorMaps:
    return VectorMaps(folder)


def get_vector_maps() -> VectorMaps:
    return _maps(get_settings().map_data_path)


Vectors = Annotated[VectorMaps, Depends(get_vector_maps)]
