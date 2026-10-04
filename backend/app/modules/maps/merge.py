"""Puts the layers of a second vector map into the first one.

The own map is built in two runs: the base map (OpenMapTiles schema) and the
paths with their difficulty (`deploy/map/hiking.yml`). A vector tile is a list
of layers, so two tiles of the same place are joined by putting their contents
one after the other. The result is one file per region, with plain MBTiles
tables.

    python -m app.modules.maps.merge base.mbtiles extra.mbtiles out.mbtiles
"""

import gzip
import json
import sqlite3
import sys
from pathlib import Path


def merge(base: Path, extra: Path, out: Path) -> int:
    """Writes `out` with all tiles of `base`, completed by `extra`. Returns the number
    of tiles that got layers of `extra`."""
    out.unlink(missing_ok=True)
    # Opened as a URI, so that the two maps can be attached read-only.
    db = sqlite3.connect(f"file:{out}", uri=True)
    try:
        db.execute("ATTACH DATABASE ? AS base", (f"file:{base}?mode=ro",))
        db.execute("ATTACH DATABASE ? AS extra", (f"file:{extra}?mode=ro",))
        db.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
        db.execute(
            "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER,"
            " tile_data BLOB, PRIMARY KEY (zoom_level, tile_column, tile_row)) WITHOUT ROWID"
        )
        db.execute(
            "INSERT INTO tiles SELECT zoom_level, tile_column, tile_row, tile_data FROM base.tiles"
        )
        merged = 0
        rows = db.execute(
            "SELECT zoom_level, tile_column, tile_row, tile_data FROM extra.tiles"
        ).fetchall()
        for z, x, y, data in rows:
            position = (z, x, y)
            where = "zoom_level = ? AND tile_column = ? AND tile_row = ?"
            found = db.execute(f"SELECT tile_data FROM tiles WHERE {where}", position).fetchone()
            if found is None:
                db.execute("INSERT INTO tiles VALUES (?, ?, ?, ?)", (*position, data))
            else:
                joined = gzip.compress(
                    gzip.decompress(found[0]) + gzip.decompress(data), compresslevel=6, mtime=0
                )
                db.execute(f"UPDATE tiles SET tile_data = ? WHERE {where}", (joined, *position))
            merged += 1
        metadata = dict(db.execute("SELECT name, value FROM base.metadata"))
        added = dict(db.execute("SELECT name, value FROM extra.metadata"))
        # The description of the layers names both maps.
        layers = json.loads(metadata.get("json", "{}")).get("vector_layers", [])
        layers += json.loads(added.get("json", "{}")).get("vector_layers", [])
        metadata["json"] = json.dumps({"vector_layers": layers})
        db.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
        db.commit()
        db.execute("DETACH DATABASE base")
        db.execute("DETACH DATABASE extra")
        db.execute("VACUUM")
        return merged
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    count = merge(*(Path(argument) for argument in sys.argv[1:]))
    print(f"{count} tiles completed with the layers of {sys.argv[2]}")
