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

The server itself gets a second, deeper pack (`<region>.server.sqlite`): the levels
below those of the app, built once ahead, so that it never has to fetch or compute
elevation, slope or contour lines while someone looks at the map.

    python -m app.modules.maps.pack /data/switzerland.mbtiles --server --max-zoom=13
"""

import math
import sqlite3
import sys
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
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


# --- The deeper pack for the server ---

SERVER_SUFFIX = ".server.sqlite"
HIRES_SUFFIX = ".hires.sqlite"
SERVER_MAX_ZOOM = 13
# Deepest levels the server ever serves (see layers.py and contours.py).
_SLOPE_LIMIT = 14
_CONTOUR_LIMIT = 13

_worker_fetch: Callable[[int, int, int], bytes | None] | None = None


def server_pack_path(map_path: Path) -> Path:
    return map_path.with_name(map_path.stem + SERVER_SUFFIX)


def server_plan(max_zoom: int) -> dict[str, range]:
    """Which levels the server pack holds: what lies below the pack for the app."""
    return {
        "terrain": range(TERRAIN_ZOOMS.stop, max_zoom + 1),
        "slope": range(SLOPE_ZOOMS.stop, min(max_zoom, _SLOPE_LIMIT) + 1),
        "contours": range(CONTOUR_ZOOMS.stop, min(max_zoom, _CONTOUR_LIMIT) + 1),
    }


def _server_tiles(job: tuple[int, int, int, bool, bool]) -> list[tuple]:
    """One tile of the server pack, made in a worker process: the elevation tile and
    what is computed from it."""
    z, x, y, with_slope, with_contours = job
    global _worker_fetch
    if _worker_fetch is None:
        _worker_fetch = _fetcher()
    terrain = _worker_fetch(z, x, y)
    if terrain is None:
        return []
    made = [("terrain", z, x, y, terrain)]
    if with_slope:
        made.append(("slope", z, x, y, slope_tile(terrain, z, y)))
    if with_contours:
        made.append(("contours", z, x, y, contour_tile(terrain, z)))
    return made


def build_server_pack(
    map_path: Path,
    make: Callable[[tuple[int, int, int, bool, bool]], list[tuple]] = _server_tiles,
    *,
    max_zoom: int = SERVER_MAX_ZOOM,
    workers: int = 3,
    report: Callable[[str], None] = print,
) -> Path:
    """Builds elevation, slope and contour tiles of a region ahead, down to `max_zoom`,
    so that the server never has to fetch or compute them while someone looks at the map.

    Computing takes most of the time (a contour tile about 0.4 s), so the work is spread
    over processes. A build that was interrupted goes on where it stopped. Tiles that the
    pack of another region already holds (regions overlap) are not made again.
    """
    with sqlite3.connect(f"file:{map_path}?mode=ro", uri=True) as source:
        meta = dict(source.execute("SELECT name, value FROM metadata"))
    bounds = tuple(float(part) for part in meta["bounds"].split(","))
    out = server_pack_path(map_path)
    part = out.with_name(out.name + ".part")
    # A finished pack is completed in place (e.g. for a deeper level); a new one grows
    # under another name until it is whole.
    target = out if out.is_file() else part
    db = sqlite3.connect(target)
    db.execute(
        "CREATE TABLE IF NOT EXISTS layer_tiles (layer TEXT, z INTEGER, x INTEGER, y INTEGER,"
        " data BLOB, PRIMARY KEY (layer, z, x, y)) WITHOUT ROWID"
    )
    others = [
        sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for path in sorted(map_path.parent.glob(f"*{SERVER_SUFFIX}"))
        if path != out
    ]
    exists = "SELECT 1 FROM layer_tiles WHERE layer = 'terrain' AND z = ? AND x = ? AND y = ?"

    def missing(tile: tuple[int, int, int]) -> bool:
        return not any(store.execute(exists, tile).fetchone() for store in (db, *others))

    plan = server_plan(max_zoom)
    try:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for z in plan["terrain"]:
                jobs = [
                    (z, x, y, z in plan["slope"], z in plan["contours"])
                    for x, y in tiles_in(bounds, z)
                    if missing((z, x, y))
                ]
                done = 0
                for made in pool.map(make, jobs, chunksize=8):
                    db.executemany(
                        "INSERT OR REPLACE INTO layer_tiles VALUES (?, ?, ?, ?, ?)", made
                    )
                    done += 1
                    # Kept on disk now and then: an interrupted build loses little.
                    if done % 500 == 0:
                        db.commit()
                        report(f"zoom {z}: {done} of {len(jobs)} tiles")
                db.commit()
                report(f"zoom {z}: {len(jobs)} tiles made")
    finally:
        db.close()
        for store in others:
            store.close()
    # Only a finished pack gets the name the server looks for.
    if target != out:
        part.replace(out)
    return out


# --- Slope and contours from a fine elevation model ---


def _derived_tiles(job: tuple[int, int, int, bytes, bool, bool]) -> list[tuple]:
    z, x, y, terrain, with_slope, with_contours = job
    made = []
    if with_slope:
        made.append(("slope", z, x, y, slope_tile(terrain, z, y)))
    if with_contours:
        made.append(("contours", z, x, y, contour_tile(terrain, z)))
    return made


def derived_path(pack: Path) -> Path:
    """Where the slope and contour tiles of an elevation pack go: a file of their own
    next to it, which the server reads like any pack."""
    stem = pack.name.removesuffix(HIRES_SUFFIX)
    return pack.with_name(f"{stem}.derived{HIRES_SUFFIX}")


def derive(pack: Path, *, workers: int = 3, report: Callable[[str], None] = print) -> int:
    """Computes slope and contour tiles from the elevation tiles of a pack (e.g. a fine
    elevation model cut by deploy/terrain/build_terrain.py).

    They are written into a file of their own (`<region>.derived.hires.sqlite`), not into
    the pack: the server reads the pack while this runs, and a file that is being written
    would keep it waiting. What is there already is not made again; an interrupted run
    goes on where it stopped. Returns how many elevation tiles were worked on.
    """
    out = derived_path(pack)
    part = out.with_name(out.name + ".part")
    target = out if out.is_file() else part
    source = sqlite3.connect(f"file:{pack}?mode=ro", uri=True)
    db = sqlite3.connect(target)
    db.execute(
        "CREATE TABLE IF NOT EXISTS layer_tiles (layer TEXT, z INTEGER, x INTEGER, y INTEGER,"
        " data BLOB, PRIMARY KEY (layer, z, x, y)) WITHOUT ROWID"
    )
    exists = "SELECT 1 FROM layer_tiles WHERE layer = ? AND z = ? AND x = ? AND y = ?"
    wanted = source.execute(
        "SELECT z, x, y FROM layer_tiles WHERE layer = 'terrain' AND z >= ? AND z <= ?",
        (min(SLOPE_ZOOMS.start, CONTOUR_ZOOMS.start), _SLOPE_LIMIT),
    ).fetchall()

    def jobs():
        for z, x, y in wanted:
            slope = SLOPE_ZOOMS.start <= z <= _SLOPE_LIMIT
            contours = CONTOUR_ZOOMS.start <= z <= _CONTOUR_LIMIT
            slope = slope and not db.execute(exists, ("slope", z, x, y)).fetchone()
            contours = contours and not db.execute(exists, ("contours", z, x, y)).fetchone()
            if slope or contours:
                (terrain,) = source.execute(
                    "SELECT data FROM layer_tiles"
                    " WHERE layer = 'terrain' AND z = ? AND x = ? AND y = ?",
                    (z, x, y),
                ).fetchone()
                yield z, x, y, terrain, slope, contours

    done = 0
    try:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            # Jobs carry their elevation tile along; they are handed out in portions,
            # so that not all of them wait in memory at once.
            batch: list[tuple] = []

            def flush() -> None:
                nonlocal done
                for made in pool.map(_derived_tiles, batch, chunksize=8):
                    db.executemany(
                        "INSERT OR REPLACE INTO layer_tiles VALUES (?, ?, ?, ?, ?)", made
                    )
                done += len(batch)
                db.commit()
                report(f"{done} tiles derived")
                batch.clear()

            for job in jobs():
                batch.append(job)
                if len(batch) >= 600:
                    flush()
            if batch:
                flush()
    finally:
        db.close()
        source.close()
    if target != out:
        part.replace(out)
    return done


if __name__ == "__main__":
    arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
    options = dict(
        argument.removeprefix("--").partition("=")[::2]
        for argument in sys.argv[1:]
        if argument.startswith("--")
    )
    if len(arguments) != 1 or set(options) - {"server", "derive", "max-zoom", "workers"}:
        sys.exit(__doc__)
    if "derive" in options:
        count = derive(Path(arguments[0]), workers=int(options.get("workers") or 3))
        print(f"{arguments[0]}: slope and contours for {count} tiles")
        sys.exit(0)
    if "server" in options:
        result = build_server_pack(
            Path(arguments[0]),
            max_zoom=int(options.get("max-zoom") or SERVER_MAX_ZOOM),
            workers=int(options.get("workers") or 3),
        )
    else:
        result = build(Path(arguments[0]), _fetcher())
    print(f"{result} ({result.stat().st_size // 1_000_000} MB)")
