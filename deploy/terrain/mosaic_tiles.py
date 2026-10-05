#!/usr/bin/env python3
"""Joins an elevation model that comes as many small GeoTIFFs into one coarser GeoTIFF.

Some surveying offices publish their model as one GeoTIFF per square kilometre, finer
than the tiles of the map need (Switzerland: 2 m, 52 GB in all). This tool fetches the
files of a list one after the other, reduces each to the wanted grid width (average)
and writes it into one raster that `build_terrain.py` then cuts into tiles. The files
themselves are not kept.

    mosaic_tiles.py --list https://…/files.csv --out /data/build/sources/switzerland-5m.tif --step 5

`--list` is a text file or address with one address per line, or an address that
answers with JSON `{"href": …}` pointing to such a list (swisstopo). The addresses must
hold the kilometre of the south-west corner (`…_2501-1120_…`); the extent is taken from
them and from `--size-km`. The addresses may as well be requests to a coverage service
(WCS) for one square each, with the corner in a parameter of no other meaning.

Runs in the GDAL container like `build_terrain.py`. An interrupted run goes on where
it stopped: next to the unfinished raster lies a list of the files already in it.
"""

import argparse
import json
import math
import os
import re
import sys
import urllib.request
from multiprocessing import Pool

import numpy as np
from osgeo import gdal, osr
from wanted import wanted_cells

gdal.UseExceptions()

NODATA = -9999.0
AGENT = {"User-Agent": "hiker terrain build"}
_step = 5.0


def read_address(address: str) -> bytes | None:
    request = urllib.request.Request(address, headers=AGENT)
    for _attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except OSError:
            continue
    return None


def read_list(source: str) -> list[str]:
    if "://" in source:
        text = read_address(source)
        if text is None:
            sys.exit(f"cannot read {source}")
        if text.lstrip().startswith(b"{"):
            text = read_address(json.loads(text)["href"])
    else:
        with open(source, "rb") as file:
            text = file.read()
    return [line.strip() for line in text.decode().splitlines() if line.strip()]


def start_worker(step: float) -> None:
    global _step
    _step = step


def reduce(address: str) -> tuple[str, float, float, np.ndarray | None]:
    """One file on the wanted grid: its address, west and north edge and the heights."""
    data = read_address(address)
    if data is None:
        return address, 0.0, 0.0, None
    name = f"/vsimem/{os.getpid()}.tif"
    gdal.FileFromMemBuffer(name, data)
    try:
        source = gdal.Open(name)
        left, width, _a, top, _b, height = source.GetGeoTransform()
        right, bottom = left + source.RasterXSize * width, top + source.RasterYSize * height
        # Snapped to the grid of the raster, which starts at whole multiples of the step.
        west, east = math.floor(left / _step) * _step, math.ceil(right / _step) * _step
        south, north = math.floor(bottom / _step) * _step, math.ceil(top / _step) * _step
        reduced = gdal.Warp(
            "",
            source,
            format="MEM",
            outputBounds=(west, south, east, north),
            xRes=_step,
            yRes=_step,
            resampleAlg="average",
            dstNodata=NODATA,
            outputType=gdal.GDT_Float32,
        )
        return address, west, north, reduced.GetRasterBand(1).ReadAsArray()
    except RuntimeError:
        return address, 0.0, 0.0, None
    finally:
        gdal.Unlink(name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--list", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--step", type=float, required=True, help="grid width in metres")
    parser.add_argument("--srs", required=True)
    parser.add_argument("--corner", default=r"_(\d{4})-(\d{4})_", help="kilometre of the south-west corner in an address")
    parser.add_argument("--size-km", type=int, default=1, help="edge of one file in kilometres")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--only-for", default="", help="a pack: fetch only what its wanted tiles need")
    arguments = parser.parse_args()

    addresses = read_list(arguments.list)
    print(f"{len(addresses)} files in the list", flush=True)
    corners = [re.search(arguments.corner, address) for address in addresses]
    if not all(corners):
        sys.exit("an address in the list does not hold the corner of its file")
    cells = wanted_cells(arguments.only_for, arguments.srs)
    if cells is not None:
        size = arguments.size_km
        keep = [
            any((int(corner.group(1)) + dx, int(corner.group(2)) + dy) in cells for dx in range(size) for dy in range(size))
            for corner in corners
        ]
        addresses = [address for address, kept in zip(addresses, keep) if kept]
        corners = [corner for corner, kept in zip(corners, keep) if kept]
        print(f"{len(addresses)} of them are needed for the tiles to cut anew", flush=True)
        if not addresses:
            sys.exit("nothing to fetch")
    eastings = [int(corner.group(1)) * 1000 for corner in corners]
    northings = [int(corner.group(2)) * 1000 for corner in corners]
    step = arguments.step
    edge = arguments.size_km * 1000
    west, east = min(eastings), max(eastings) + edge
    south, north = min(northings), max(northings) + edge
    width, height = round((east - west) / step), round((north - south) / step)
    print(f"raster: {width} x {height} cells of {step} m", flush=True)

    part, done_path = arguments.out + ".part", arguments.out + ".done"
    gdal.SetCacheMax(1024 * 1024 * 1024)
    done: set[str] = set()
    if os.path.isfile(part) and os.path.isfile(done_path):
        with open(done_path) as file:
            done = set(file.read().split())
        raster = gdal.Open(part, gdal.GA_Update)
        band = raster.GetRasterBand(1)
        print(f"{len(done)} files are in the raster already", flush=True)
    else:
        raster = gdal.GetDriverByName("GTiff").Create(
            part,
            width,
            height,
            1,
            gdal.GDT_Float32,
            options=["TILED=YES", "BLOCKXSIZE=512", "BLOCKYSIZE=512", "COMPRESS=DEFLATE", "PREDICTOR=3", "BIGTIFF=YES"],
        )
        reference = osr.SpatialReference()
        reference.SetFromUserInput(arguments.srs)
        raster.SetProjection(reference.ExportToWkt())
        raster.SetGeoTransform((west, step, 0, north, 0, -step))
        band = raster.GetRasterBand(1)
        band.SetNoDataValue(NODATA)
        band.Fill(NODATA)
        open(done_path, "w").close()

    failed, fresh = [], []
    jobs = [address for address in addresses if address not in done]

    def keep() -> None:
        # First the raster, then the note that the files are in it.
        raster.FlushCache()
        with open(done_path, "a") as file:
            file.writelines(address + "\n" for address in fresh)
        fresh.clear()

    with Pool(arguments.workers, initializer=start_worker, initargs=(step,)) as pool:
        for count, (address, left, top, heights) in enumerate(pool.imap_unordered(reduce, jobs, chunksize=4), 1):
            if heights is None:
                failed.append(address)
            else:
                column, row = round((left - west) / step), round((north - top) / step)
                # A file whose grid lies between the cells reaches a cell over the edge.
                heights = heights[max(0, -row) : height - row, max(0, -column) : width - column]
                column, row = max(0, column), max(0, row)
                if not heights.size:
                    fresh.append(address)
                    continue
                # Neighbours may share their edge: keep what is there where this one is empty.
                there = band.ReadAsArray(column, row, heights.shape[1], heights.shape[0])
                empty = heights <= NODATA + 1
                heights[empty] = there[empty]
                band.WriteArray(heights, column, row)
                fresh.append(address)
            if count % 1000 == 0:
                keep()
                print(f"{count} of {len(jobs)} files", flush=True)
    keep()
    raster = None
    if failed:
        print(f"{len(failed)} files could not be had, e.g. {failed[:3]}; run again", file=sys.stderr)
        sys.exit(1)
    os.replace(part, arguments.out)
    os.remove(done_path)
    print(arguments.out, flush=True)


if __name__ == "__main__":
    main()
