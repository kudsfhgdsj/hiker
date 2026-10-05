#!/usr/bin/env python3
"""Fetches an elevation model that comes as zipped GeoTIFFs linked from a web page.

Reads the page, takes the links that match, fetches each archive, cleans the GeoTIFF
inside and keeps it compressed; in the end one virtual raster (VRT) names them all, and
`build_terrain.py` cuts that into tiles.

    fetch_tiffs.py --index https://tinitaly.pi.ingv.it/Download_Area1_1.html \\
        --match 'data_1\\.1/w(48|49|5[0-2])\\d{3}_s10/[^"]+\\.zip' \\
        --dir /data/build/sources/tinitaly --out /data/build/sources/tinitaly.vrt --voids

`--voids`: some models mark single missing cells with the height 0 in the middle of the
mountains. A cell of exactly 0 within 150 m of ground higher than 30 m is taken as missing; the
tiles get it from the world-wide data then. The sea and the plain at its level stay.

Runs in the GDAL container. Files that are there already are not fetched again.
"""

import argparse
import os
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from multiprocessing import Pool

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

AGENT = {"User-Agent": "hiker terrain build"}
_arguments = None


def read_address(address: str) -> bytes | None:
    request = urllib.request.Request(address, headers=AGENT)
    for _attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.read()
        except OSError:
            continue
    return None


def without_voids(heights: np.ndarray, nodata: float, reach: int = 15) -> int:
    """Marks cells of exactly 0 near clearly higher ground as missing; how many. Near
    means within `reach` cells, so that also the middle of a small patch is found."""
    zero = heights == 0
    if not zero.any():
        return 0
    highest = np.where(heights == nodata, 0, heights)
    # The highest ground around every cell: first along the rows, then along the columns.
    for axis in (0, 1):
        spread = highest.copy()
        for shift in range(1, reach + 1):
            for sign in (1, -1):
                moved = np.roll(highest, sign * shift, axis=axis)
                # What rolls in from the other edge does not count.
                edge = [slice(None), slice(None)]
                edge[axis] = slice(0, shift) if sign == 1 else slice(-shift, None)
                moved[tuple(edge)] = 0
                np.maximum(spread, moved, out=spread)
        highest = spread
    void = zero & (highest > 30)
    heights[void] = nodata
    return int(void.sum())


def fetch(address: str) -> tuple[str, str | None]:
    """One archive: the path of its cleaned GeoTIFF, or why there is none."""
    name = os.path.basename(urllib.parse.urlparse(address).path).removesuffix(".zip")
    path = os.path.join(_arguments.dir, name + ".tif")
    if os.path.isfile(path):
        return path, None
    data = read_address(address)
    if data is None:
        return path, "not reachable"
    archive = path + ".zip"
    with open(archive, "wb") as file:
        file.write(data)
    del data
    try:
        with zipfile.ZipFile(archive) as packed:
            members = [member for member in packed.namelist() if member.lower().endswith(".tif")]
            if len(members) != 1:
                return path, f"{len(members)} GeoTIFFs inside"
            source = gdal.Open(f"/vsizip/{archive}/{members[0]}")
            band = source.GetRasterBand(1)
            nodata = band.GetNoDataValue()
            heights = band.ReadAsArray().astype(np.float32)
            voids = without_voids(heights, nodata) if _arguments.voids and nodata is not None else 0
            made = gdal.GetDriverByName("GTiff").Create(
                path + ".part",
                source.RasterXSize,
                source.RasterYSize,
                1,
                gdal.GDT_Float32,
                options=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=3"],
            )
            made.SetProjection(source.GetProjection())
            made.SetGeoTransform(source.GetGeoTransform())
            if nodata is not None:
                made.GetRasterBand(1).SetNoDataValue(nodata)
            made.GetRasterBand(1).WriteArray(heights)
            made = None
    except (RuntimeError, zipfile.BadZipFile) as error:
        return path, str(error)
    finally:
        os.remove(archive)
    os.replace(path + ".part", path)
    print(f"{name}: {voids} cells without height" if voids else name, flush=True)
    return path, None


def start_worker(arguments) -> None:
    global _arguments
    _arguments = arguments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--index", required=True)
    parser.add_argument("--match", required=True, help="regular expression for the links to take")
    parser.add_argument("--dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--voids", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    arguments = parser.parse_args()
    start_worker(arguments)

    page = read_address(arguments.index)
    if page is None:
        sys.exit(f"cannot read {arguments.index}")
    links = sorted({match.group(0) for match in re.finditer(arguments.match, page.decode("utf-8", "replace"))})
    addresses = [urllib.parse.urljoin(arguments.index, link) for link in links]
    print(f"{len(addresses)} files on the page match", flush=True)
    if not addresses:
        sys.exit(1)
    os.makedirs(arguments.dir, exist_ok=True)
    with Pool(arguments.workers, initializer=start_worker, initargs=(arguments,)) as pool:
        results = list(pool.imap_unordered(fetch, addresses))
    failed = [(path, why) for path, why in results if why]
    if failed:
        print(f"{len(failed)} files failed, e.g. {failed[:3]}; run again", file=sys.stderr)
        sys.exit(1)
    # The list is written when the object is let go.
    listed = gdal.BuildVRT(arguments.out + ".part", sorted(path for path, _why in results))
    listed = None  # noqa: F841
    os.replace(arguments.out + ".part", arguments.out)
    print(arguments.out, flush=True)


if __name__ == "__main__":
    main()
