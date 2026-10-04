"""Builds the layer pack of a region: elevation, slope and contour lines to take along.

The app shows these layers without network from one file per region, next to
the map itself (`<region>.mbtiles` → `<region>.layers.sqlite`). The pack holds,
for the area of the map:

- `terrain`: elevation tiles up to zoom 11 (enough for hillshading),
- `slope`: slope tiles for zoom 10 to 12,
- `contours`: contour lines for zoom 11 and 12.

Deeper zoom levels come from the server when it can be reached; without network
the map enlarges what the pack has. The elevation tiles are open data (see
`layers.py`) and may be fetched in bulk.

    python -m app.modules.maps.pack /data/switzerland.mbtiles
"""

import math
import sqlite3
import sys
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.modules.maps.contours import contour_tile
from app.modules.maps.layers import TERRAIN, slope_tile
from app.modules.maps.tiles import HttpTileSource, TileSourceError

PACK_SUFFIX = ".layers.sqlite"
TERRAIN_ZOOMS = range(7, 12)
SLOPE_ZOOMS = range(10, 13)
CONTOUR_ZOOMS = range(11, 13)
_ALL_ZOOMS = range(7, 13)


def pack_path(map_path: Path) -> Path:
    return map_path.with_name(map_path.stem + PACK_SUFFIX)


def tiles_in(bounds: tuple[float, float, float, float], z: int) -> Iterator[tuple[int, int]]:
    """All tiles of a zoom level that touch the area (west, south, east, north)."""
    west, south, east, north = bounds

    def column(lon: float) -> int:
        return min(2**z - 1, max(0, int((lon + 180) / 360 * 2**z)))

    def row(lat: float) -> int:
        radians = math.radians(max(-85.0, min(85.0, lat)))
        share = (1 - math.asinh(math.tan(radians)) / math.pi) / 2
        return min(2**z - 1, max(0, int(share * 2**z)))

    for x in range(column(west), column(east) + 1):
        for y in range(row(north), row(south) + 1):
            yield x, y


def build(
    map_path: Path,
    fetch: Callable[[int, int, int], bytes | None],
    *,
    workers: int = 6,
    report: Callable[[str], None] = print,
) -> Path:
    """Writes the layer pack next to the map. `fetch` returns an elevation tile or None."""
    with sqlite3.connect(f"file:{map_path}?mode=ro", uri=True) as source:
        meta = dict(source.execute("SELECT name, value FROM metadata"))
    bounds = tuple(float(part) for part in meta["bounds"].split(","))
    out = pack_path(map_path)
    part = out.with_suffix(".part")
    part.unlink(missing_ok=True)
    db = sqlite3.connect(part)
    db.execute(
        "CREATE TABLE layer_tiles (layer TEXT, z INTEGER, x INTEGER, y INTEGER, data BLOB,"
        " PRIMARY KEY (layer, z, x, y)) WITHOUT ROWID"
    )
    db.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    db.execute("INSERT INTO metadata VALUES ('bounds', ?)", (meta["bounds"],))

    def tiles_of(z: int, x: int, y: int) -> list[tuple[str, int, int, int, bytes]]:
        terrain = fetch(z, x, y)
        if terrain is None:
            return []
        made = []
        if z in TERRAIN_ZOOMS:
            made.append(("terrain", z, x, y, terrain))
        if z in SLOPE_ZOOMS:
            made.append(("slope", z, x, y, slope_tile(terrain, z, y)))
        if z in CONTOUR_ZOOMS:
            made.append(("contours", z, x, y, contour_tile(terrain, z)))
        return made

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for z in _ALL_ZOOMS:
                wanted = [(z, x, y) for x, y in tiles_in(bounds, z)]
                count = 0
                for made in pool.map(lambda tile: tiles_of(*tile), wanted):
                    db.executemany("INSERT INTO layer_tiles VALUES (?, ?, ?, ?, ?)", made)
                    count += bool(made)
                db.commit()
                report(f"zoom {z}: {count} of {len(wanted)} tiles")
        db.execute("VACUUM")
    finally:
        db.close()
    part.replace(out)
    return out


def _fetcher() -> Callable[[int, int, int], bytes | None]:
    source = HttpTileSource(TERRAIN.url, "hiker (self-hosted; layer pack)", "")

    def fetch(z: int, x: int, y: int) -> bytes | None:
        for attempt in range(3):
            try:
                tile = source.fetch(z, x, y, None)
                return None if tile is None else tile.data
            except TileSourceError:
                if attempt == 2:
                    # One missing tile must not end the build; the app asks the server for it.
                    return None
        return None

    return fetch


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    result = build(Path(sys.argv[1]), _fetcher())
    print(f"{result} ({result.stat().st_size // 1_000_000} MB)")
