#!/usr/bin/env python3
"""Cuts a fine elevation model into elevation tiles for the own map.

Reads a digital terrain model of a region (GeoTIFF, any projection GDAL knows) and
writes elevation tiles in Terrarium encoding into `<name>.hires.sqlite`, the format
the API serves from (`layer_tiles(layer, z, x, y, data)`). The API prefers these
tiles to the coarser ones of the world-wide source.

    build_terrain.py --source /data/build/sources/DGM_R5.tif --out /data/austria.hires.sqlite \\
        --attribution "Höhendaten Österreich: © BEV, CC BY 4.0"

Runs in the GDAL container (see docker-compose.yml, service `terrainbuild`); it is not
part of the backend, which has no GDAL. Tiles that the model covers only partly (the
border of the region) are completed from the world-wide tiles, so that there is no
hole; tiles it does not touch are left out. An interrupted run goes on where it stopped.
"""

import argparse
import math
import sqlite3
import sys
import urllib.request
from multiprocessing import Pool

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

SIZE = 256
EARTH = 20037508.342789244
NODATA = -32000.0
FILL_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

_source = None
_arguments = None


def resolution(z: int) -> float:
    """Metres per pixel of a tile at the equator (Web Mercator)."""
    return 2 * EARTH / (SIZE * 2**z)


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    span = 2 * EARTH / 2**z
    west = -EARTH + x * span
    north = EARTH - y * span
    return west, north - span, west + span, north


def open_warped(path: str, max_zoom: int):
    """The model as a virtual raster on the pixel grid of the deepest tiles."""
    source = gdal.Open(path)
    step = resolution(max_zoom)
    probe = gdal.Warp("", source, format="VRT", dstSRS="EPSG:3857")
    left, _dx, _a, top, _b, dy = probe.GetGeoTransform()
    right, bottom = left + probe.RasterXSize * _dx, top + probe.RasterYSize * dy
    # Snapped outwards to whole tiles of the deepest level.
    span = step * SIZE
    west = math.floor((left + EARTH) / span) * span - EARTH
    east = math.ceil((right + EARTH) / span) * span - EARTH
    north = EARTH - math.floor((EARTH - top) / span) * span
    south = EARTH - math.ceil((EARTH - bottom) / span) * span
    warped = gdal.Warp(
        "",
        source,
        format="VRT",
        dstSRS="EPSG:3857",
        outputBounds=(west, south, east, north),
        xRes=step,
        yRes=step,
        resampleAlg="bilinear",
        dstNodata=NODATA,
        outputType=gdal.GDT_Float32,
    )
    return warped, (west, south, east, north)


def decode_terrarium(data: bytes) -> np.ndarray | None:
    name = "/vsimem/fill.png"
    gdal.FileFromMemBuffer(name, data)
    try:
        image = gdal.Open(name).ReadAsArray().astype(np.float32)
    except RuntimeError:
        return None
    finally:
        gdal.Unlink(name)
    if image.ndim != 3 or image.shape[1:] != (SIZE, SIZE):
        return None
    return image[0] * 256 + image[1] + image[2] / 256 - 32768


def encode_terrarium(elevation: np.ndarray) -> bytes:
    value = np.clip(elevation + 32768, 0, 65535.996)
    whole = np.floor(value)
    bands = np.stack(
        [whole // 256, whole % 256, np.floor((value - whole) * 256)]
    ).astype(np.uint8)
    memory = gdal.GetDriverByName("MEM").Create("", SIZE, SIZE, 3, gdal.GDT_Byte)
    memory.WriteArray(bands)
    name = "/vsimem/tile.png"
    gdal.GetDriverByName("PNG").CreateCopy(name, memory, options=["ZLEVEL=6"])
    data = gdal.VSIGetMemFileBuffer_unsafe(name)
    result = bytes(data)
    gdal.Unlink(name)
    return result


def fill_tile(z: int, x: int, y: int) -> np.ndarray | None:
    """The world-wide elevation tile, for the part the model does not cover."""
    if not _arguments.fill_url:
        return None
    address = _arguments.fill_url.format(z=z, x=x, y=y)
    request = urllib.request.Request(address, headers={"User-Agent": "hiker terrain build"})
    for _attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return decode_terrarium(response.read())
        except OSError:
            continue
    return None


def make_tile(job: tuple[int, int, int]) -> tuple[int, int, int, bytes | None]:
    z, x, y = job
    global _source
    if _source is None:
        _source = open_warped(_arguments.source, _arguments.max_zoom)
    warped, (west, _south, _east, north) = _source
    step = resolution(_arguments.max_zoom)
    tile_west, _tile_south, _tile_east, tile_north = tile_bounds(z, x, y)
    # The window of the tile on the grid of the deepest level; coarser tiles are read
    # reduced, with the average of what they cover.
    factor = 2 ** (_arguments.max_zoom - z)
    offset_x = round((tile_west - west) / step)
    offset_y = round((north - tile_north) / step)
    width = SIZE * factor
    if (
        offset_x < 0
        or offset_y < 0
        or offset_x + width > warped.RasterXSize
        or offset_y + width > warped.RasterYSize
    ):
        return z, x, y, None
    elevation = warped.GetRasterBand(1).ReadAsArray(
        offset_x,
        offset_y,
        width,
        width,
        buf_xsize=SIZE,
        buf_ysize=SIZE,
        buf_type=gdal.GDT_Float32,
        resample_alg=gdal.GRIORA_Average if factor > 1 else gdal.GRIORA_NearestNeighbour,
    )
    missing = elevation <= NODATA + 1
    if missing.all():
        return z, x, y, None
    if missing.any():
        other = fill_tile(z, x, y)
        if other is None:
            # No other source: the edge keeps the height next to it, never a hole.
            elevation[missing] = float(elevation[~missing].min())
        else:
            elevation[missing] = other[missing]
    return z, x, y, encode_terrarium(elevation)


def start_worker(arguments) -> None:
    global _arguments
    _arguments = arguments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-zoom", type=int, default=12)
    parser.add_argument("--max-zoom", type=int, default=14)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--attribution", default="")
    parser.add_argument("--fill-url", default=FILL_URL)
    arguments = parser.parse_args()
    start_worker(arguments)

    warped, (west, south, east, north) = open_warped(arguments.source, arguments.max_zoom)
    print(f"model: {warped.RasterXSize} x {warped.RasterYSize} px at zoom {arguments.max_zoom}", flush=True)

    part = arguments.out + ".part"
    # A finished file is completed in place; a new one grows under another name.
    import os

    target = arguments.out if os.path.isfile(arguments.out) else part
    db = sqlite3.connect(target)
    db.execute(
        "CREATE TABLE IF NOT EXISTS layer_tiles (layer TEXT, z INTEGER, x INTEGER, y INTEGER,"
        " data BLOB, PRIMARY KEY (layer, z, x, y)) WITHOUT ROWID"
    )
    db.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS seen (z INTEGER, x INTEGER, y INTEGER, PRIMARY KEY (z, x, y))")
    db.execute("INSERT OR REPLACE INTO metadata VALUES ('attribution', ?)", (arguments.attribution,))
    db.execute("INSERT OR REPLACE INTO metadata VALUES ('source', ?)", (os.path.basename(arguments.source),))
    db.commit()

    with Pool(arguments.workers, initializer=start_worker, initargs=(arguments,)) as pool:
        for z in range(arguments.max_zoom, arguments.min_zoom - 1, -1):
            span = 2 * EARTH / 2**z
            columns = range(int((west + EARTH) // span), int(math.ceil((east + EARTH) / span)))
            rows = range(int((EARTH - north) // span), int(math.ceil((EARTH - south) / span)))
            done = {(x, y) for x, y in db.execute("SELECT x, y FROM seen WHERE z = ?", (z,))}
            jobs = [(z, x, y) for y in rows for x in columns if (x, y) not in done]
            made = 0
            for count, (_z, x, y, data) in enumerate(pool.imap_unordered(make_tile, jobs, chunksize=16), 1):
                if data is not None:
                    db.execute("INSERT OR REPLACE INTO layer_tiles VALUES ('terrain', ?, ?, ?, ?)", (z, x, y, data))
                    made += 1
                # Also empty tiles are remembered, so that a resumed run skips them.
                db.execute("INSERT OR IGNORE INTO seen VALUES (?, ?, ?)", (z, x, y))
                if count % 1000 == 0:
                    db.commit()
                    print(f"zoom {z}: {count} of {len(jobs)} tiles looked at, {made} written", flush=True)
            db.commit()
            print(f"zoom {z}: {len(jobs)} tiles looked at, {made} written", flush=True)
    db.close()
    if target != arguments.out:
        os.replace(part, arguments.out)
    print(arguments.out, flush=True)


if __name__ == "__main__":
    sys.exit(main())
