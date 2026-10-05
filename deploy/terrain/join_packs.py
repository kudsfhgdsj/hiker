#!/usr/bin/env python3
"""Joins the elevation tiles that two fine elevation models share at their border.

`build_terrain.py` completes a tile that a model covers only partly from the world-wide
tiles. Where two regions meet, both packs hold such a tile, each fine on its own side
only, and the server answers with one of them. This tool puts both fine halves into
one tile and writes it into every pack that holds the tile.

    join_packs.py /data/austria.hires.sqlite /data/bayern.hires.sqlite

What comes from a model is told from what was filled in by comparing with the
world-wide tile: filled pixels are the same to the bit. Where both models have a height
(some reach beyond their border with coarser data, e.g. the Austrian one), the pack
with the higher `priority` in its metadata wins; a model that ends exactly at its
border gets the higher one. Slope and contours of a changed
tile are removed from `<region>.derived.hires.sqlite`, so that the next `--derive`
makes them again. Running it twice changes nothing. Runs in the GDAL container.
"""

import argparse
import os
import sqlite3
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

SIZE = 256
FILL_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def read_bands(data: bytes, name: str = "/vsimem/join-in.png") -> np.ndarray | None:
    """Red, green and blue of an elevation tile, as they are stored."""
    gdal.FileFromMemBuffer(name, data)
    try:
        image = gdal.Open(name).ReadAsArray()
    except RuntimeError:
        return None
    finally:
        gdal.Unlink(name)
    if image.ndim != 3 or image.shape[0] < 3 or image.shape[1:] != (SIZE, SIZE):
        return None
    return image[:3].astype(np.uint8)


def write_bands(bands: np.ndarray) -> bytes:
    memory = gdal.GetDriverByName("MEM").Create("", SIZE, SIZE, 3, gdal.GDT_Byte)
    memory.WriteArray(bands)
    name = "/vsimem/join-out.png"
    gdal.GetDriverByName("PNG").CreateCopy(name, memory, options=["ZLEVEL=6"])
    data = bytes(gdal.VSIGetMemFileBuffer_unsafe(name))
    gdal.Unlink(name)
    return data


def real(bands: np.ndarray, world: np.ndarray) -> np.ndarray:
    """Where a tile holds heights of its model and not what was filled in.

    Filled pixels are the same as the world-wide tile to the bit. But here and there a
    height of the model is by chance the same too; such a pixel lies among others that
    differ, whereas what was filled in is a whole area. So a pixel also counts as the
    model's if most of the 5 x 5 around it differ.
    """
    differs = (bands != world).any(axis=0)
    padded = np.pad(differs, 2, mode="edge").astype(np.uint8)
    around = np.zeros(differs.shape, np.uint8)
    for dy in range(5):
        for dx in range(5):
            around += padded[dy : dy + SIZE, dx : dx + SIZE]
    return differs | (around >= 18)


def join(world: np.ndarray, tiles: list[np.ndarray]) -> np.ndarray:
    """The world-wide tile with everything on it that any of the packs really has;
    later tiles win over earlier ones."""
    joined = world.copy()
    for bands in tiles:
        own = real(bands, world)
        joined[:, own] = bands[:, own]
    return joined


def fetch(address: str) -> bytes | None:
    request = urllib.request.Request(address, headers={"User-Agent": "hiker terrain build"})
    for _attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except OSError:
            continue
    return None


def derived_of(pack: str) -> str:
    return pack.removesuffix(".hires.sqlite") + ".derived.hires.sqlite"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("packs", nargs="+")
    parser.add_argument("--fill-url", default=FILL_URL)
    parser.add_argument(
        "--forget-shared",
        action="store_true",
        help="remove the shared tiles of the packs with a priority above 0 instead of joining,"
        " so that build_terrain.py cuts them anew from the model",
    )
    arguments = parser.parse_args()

    packs = {path: sqlite3.connect(path) for path in arguments.packs if os.path.isfile(path)}
    holders: dict[tuple[int, int, int], list[str]] = {}
    priority = {}
    for path, db in packs.items():
        row = db.execute("SELECT value FROM metadata WHERE name = 'priority'").fetchone()
        priority[path] = int(row[0]) if row else 0
    # Lowest priority first, so that the tiles of the highest are laid on last.
    for path, db in sorted(packs.items(), key=lambda item: (priority[item[0]], item[0])):
        for tile in db.execute("SELECT z, x, y FROM layer_tiles WHERE layer = 'terrain'"):
            holders.setdefault(tile, []).append(path)
    shared = sorted(tile for tile, paths in holders.items() if len(paths) > 1)
    print(f"{len(shared)} tiles are in more than one pack", flush=True)
    if arguments.forget_shared:
        # For packs whose shared tiles were joined by an older, less careful rule.
        for path, db in packs.items():
            mine = [tile for tile in shared if path in holders[tile] and priority[path] > 0]
            # Noted, so that only the files of the model that touch them are fetched again.
            db.execute("CREATE TABLE IF NOT EXISTS wanted (z INTEGER, x INTEGER, y INTEGER, PRIMARY KEY (z, x, y))")
            db.executemany("INSERT OR IGNORE INTO wanted VALUES (?, ?, ?)", mine)
            db.executemany("DELETE FROM layer_tiles WHERE layer = 'terrain' AND z = ? AND x = ? AND y = ?", mine)
            db.executemany("DELETE FROM seen WHERE z = ? AND x = ? AND y = ?", mine)
            db.commit()
            db.close()
            derived = derived_of(path)
            if mine and os.path.isfile(derived):
                with sqlite3.connect(derived) as other:
                    other.executemany(
                        "DELETE FROM layer_tiles WHERE layer IN ('slope', 'contours') AND z = ? AND x = ? AND y = ?",
                        mine,
                    )
            print(f"{path}: {len(mine)} shared tiles removed", flush=True)
        return

    select = "SELECT data FROM layer_tiles WHERE layer = 'terrain' AND z = ? AND x = ? AND y = ?"
    changed: dict[str, list[tuple[int, int, int]]] = {path: [] for path in packs}
    skipped = 0
    with ThreadPoolExecutor(6) as pool:
        addresses = [arguments.fill_url.format(z=z, x=x, y=y) for z, x, y in shared]
        for count, (tile, data) in enumerate(zip(shared, pool.map(fetch, addresses)), 1):
            world = read_bands(data) if data else None
            stored = {path: read_bands(packs[path].execute(select, tile).fetchone()[0]) for path in holders[tile]}
            if world is None or any(bands is None for bands in stored.values()):
                skipped += 1
                continue
            joined = join(world, list(stored.values()))
            encoded = None
            for path, bands in stored.items():
                if not np.array_equal(bands, joined):
                    encoded = encoded or write_bands(joined)
                    packs[path].execute(
                        "UPDATE layer_tiles SET data = ? WHERE layer = 'terrain' AND z = ? AND x = ? AND y = ?",
                        (encoded, *tile),
                    )
                    changed[path].append(tile)
            if count % 200 == 0:
                # Short transactions: the server reads these files meanwhile.
                for db in packs.values():
                    db.commit()
                print(f"{count} of {len(shared)} tiles looked at", flush=True)
    for path, db in packs.items():
        db.commit()
        db.close()
        derived = derived_of(path)
        if changed[path] and os.path.isfile(derived):
            with sqlite3.connect(derived) as db:
                db.executemany(
                    "DELETE FROM layer_tiles WHERE layer IN ('slope', 'contours') AND z = ? AND x = ? AND y = ?",
                    changed[path],
                )
        print(f"{path}: {len(changed[path])} tiles joined", flush=True)
    if skipped:
        print(f"{skipped} tiles left as they were (no world-wide tile); run again", file=sys.stderr)


if __name__ == "__main__":
    main()
