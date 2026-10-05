#!/usr/bin/env python3
"""Joins an elevation model that comes as many small text files into one GeoTIFF.

Some surveying offices publish their model as thousands of zipped files `x y z` (one
per square kilometre) with a Metalink list of them. This tool fetches the files of the
list that are not there yet, checks their SHA-256 and writes one raster that
`build_terrain.py` then cuts into tiles.

    mosaic_xyz.py --metalink https://…/09.meta4 --dir /data/build/sources/bayern-dgm5 \\
        --out /data/build/sources/bayern-dgm5.tif --srs EPSG:25832 --step 5

Runs in the GDAL container like `build_terrain.py`. An interrupted download goes on
where it stopped; the raster is written under another name until it is complete.
"""

import argparse
import hashlib
import io
import os
import sys
import urllib.request
import xml.etree.ElementTree as ElementTree
import zipfile
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool

import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()

NAMESPACE = {"m": "urn:ietf:params:xml:ns:metalink"}
NODATA = -9999.0
AGENT = {"User-Agent": "hiker terrain build"}


def read_metalink(source: str) -> list[tuple[str, str, list[str]]]:
    """Name, SHA-256 and addresses of every file of the list."""
    if "://" in source:
        with urllib.request.urlopen(urllib.request.Request(source, headers=AGENT), timeout=120) as response:
            text = response.read()
    else:
        with open(source, "rb") as file:
            text = file.read()
    files = []
    for entry in ElementTree.fromstring(text).findall("m:file", NAMESPACE):
        digest = entry.find("m:hash[@type='sha-256']", NAMESPACE)
        addresses = [url.text for url in entry.findall("m:url", NAMESPACE)]
        files.append((os.path.basename(entry.get("name")), digest.text if digest is not None else "", addresses))
    return files


def fetch(job: tuple[str, str, list[str], str]) -> str | None:
    """Fetches one file unless it is there already; the name if it could not be had."""
    name, digest, addresses, directory = job
    path = os.path.join(directory, name)
    if os.path.isfile(path):
        return None
    for attempt in range(4):
        address = addresses[attempt % len(addresses)]
        try:
            with urllib.request.urlopen(urllib.request.Request(address, headers=AGENT), timeout=60) as response:
                data = response.read()
        except OSError:
            continue
        if digest and hashlib.sha256(data).hexdigest() != digest:
            continue
        with open(path + ".part", "wb") as file:
            file.write(data)
        os.replace(path + ".part", path)
        return None
    return name


def read_points(path: str) -> np.ndarray:
    """The points of one zipped file as rows `x y z`."""
    with zipfile.ZipFile(path) as archive:
        parts = [archive.read(member) for member in archive.namelist() if not member.endswith("/")]
    values = np.fromstring(b"\n".join(parts).decode("ascii", "replace"), dtype=np.float64, sep=" ")
    points = values[: len(values) // 3 * 3].reshape(-1, 3)
    # Cells outside the region are in the files too, with a height such as -9999.
    return points[points[:, 2] > -1000]


def bounds_of(path: str) -> tuple[float, float, float, float] | None:
    points = read_points(path)
    if not len(points):
        return None
    return points[:, 0].min(), points[:, 1].min(), points[:, 0].max(), points[:, 1].max()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--metalink", required=True)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--srs", required=True)
    parser.add_argument("--step", type=float, required=True, help="grid width in metres")
    parser.add_argument("--downloads", type=int, default=6)
    parser.add_argument("--workers", type=int, default=3)
    arguments = parser.parse_args()

    files = read_metalink(arguments.metalink)
    os.makedirs(arguments.dir, exist_ok=True)
    print(f"{len(files)} files in the list", flush=True)
    jobs = [(name, digest, addresses, arguments.dir) for name, digest, addresses in files]
    failed = []
    with ThreadPoolExecutor(arguments.downloads) as pool:
        for count, name in enumerate(pool.map(fetch, jobs), 1):
            if name:
                failed.append(name)
            if count % 2000 == 0:
                print(f"download: {count} of {len(jobs)}", flush=True)
    if failed:
        print(f"{len(failed)} files could not be fetched, e.g. {failed[:5]}; run again", file=sys.stderr)
        sys.exit(1)

    paths = sorted(os.path.join(arguments.dir, name) for name, _digest, _addresses in files)
    step = arguments.step
    with Pool(arguments.workers) as pool:
        # First the extent: the points are cell centres.
        boxes = [box for box in pool.imap_unordered(bounds_of, paths, chunksize=64) if box]
        west = min(box[0] for box in boxes) - step / 2
        south = min(box[1] for box in boxes) - step / 2
        east = max(box[2] for box in boxes) + step / 2
        north = max(box[3] for box in boxes) + step / 2
        width, height = round((east - west) / step), round((north - south) / step)
        print(f"raster: {width} x {height} cells of {step} m", flush=True)

        gdal.SetCacheMax(1024 * 1024 * 1024)
        part = arguments.out + ".part"
        raster = gdal.GetDriverByName("GTiff").Create(
            part,
            width,
            height,
            1,
            gdal.GDT_Float32,
            options=[
                "TILED=YES",
                "BLOCKXSIZE=512",
                "BLOCKYSIZE=512",
                "COMPRESS=DEFLATE",
                "PREDICTOR=3",
                "BIGTIFF=YES",
                "SPARSE_OK=TRUE",
            ],
        )
        reference = osr.SpatialReference()
        reference.SetFromUserInput(arguments.srs)
        raster.SetProjection(reference.ExportToWkt())
        raster.SetGeoTransform((west, step, 0, north, 0, -step))
        band = raster.GetRasterBand(1)
        band.SetNoDataValue(NODATA)
        band.Fill(NODATA)

        for count, points in enumerate(pool.imap(read_points, paths, chunksize=16), 1):
            if len(points):
                column = np.floor((points[:, 0] - west) / step).astype(np.int64)
                row = np.floor((north - points[:, 1]) / step).astype(np.int64)
                left, top = int(column.min()), int(row.min())
                block = np.full((int(row.max()) - top + 1, int(column.max()) - left + 1), NODATA, np.float32)
                # A file may be only partly filled (the border): keep what is there already.
                block[:] = band.ReadAsArray(left, top, block.shape[1], block.shape[0])
                block[row - top, column - left] = points[:, 2]
                band.WriteArray(block, left, top)
            if count % 2000 == 0:
                print(f"raster: {count} of {len(paths)} files", flush=True)
    raster.FlushCache()
    raster = None
    os.replace(part, arguments.out)
    print(arguments.out, flush=True)


if __name__ == "__main__":
    main()
