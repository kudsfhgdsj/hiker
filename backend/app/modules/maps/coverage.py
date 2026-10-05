"""Names the path-data tiles of BRouter that cover the maps of a folder.

Routing along paths needs path data for the same area the maps show. BRouter
keeps it in tiles of 5° x 5°, named after their south-west corner (`E5_N45`).
`deploy/brouter-segments.sh` asks this module which tiles the built maps need.

    python -m app.modules.maps.coverage /data
"""

import math
import sqlite3
import sys
from pathlib import Path

TILE_DEGREES = 5


def tile_name(lon: int, lat: int) -> str:
    east = f"E{lon}" if lon >= 0 else f"W{-lon}"
    north = f"N{lat}" if lat >= 0 else f"S{-lat}"
    return f"{east}_{north}"


def tiles_for(bounds: tuple[float, float, float, float]) -> set[str]:
    """The tiles that touch an area given as west, south, east, north."""
    west, south, east, north = bounds

    def corner(value: float) -> int:
        return math.floor(value / TILE_DEGREES) * TILE_DEGREES

    return {
        tile_name(lon, lat)
        for lon in range(corner(west), corner(east) + 1, TILE_DEGREES)
        for lat in range(corner(south), corner(north) + 1, TILE_DEGREES)
    }


def tiles_of_maps(folder: Path) -> list[str]:
    """The tiles all maps of the folder need together; unreadable files are skipped."""
    needed: set[str] = set()
    for path in sorted(folder.glob("*.mbtiles")):
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                row = db.execute("SELECT value FROM metadata WHERE name = 'bounds'").fetchone()
            west, south, east, north = (float(part) for part in row[0].split(","))
        except (sqlite3.Error, TypeError, ValueError):
            continue
        needed |= tiles_for((west, south, east, north))
    return sorted(needed)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(" ".join(tiles_of_maps(Path(sys.argv[1]))))
