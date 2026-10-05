"""Which square kilometres of a model are needed to cut the tiles a pack still lacks.

`join_packs.py --forget-shared` notes the tiles it removes in the table `wanted` of a
pack. To cut them anew, only the files of the model that touch them have to be fetched,
not the whole model; the tools that fetch a model ask here.
"""

import math
import os
import sqlite3

from osgeo import osr

EARTH = 20037508.342789244


def wanted_cells(pack: str, srs: str) -> set[tuple[int, int]] | None:
    """The kilometre cells (east, north in km, in the model's own coordinates) that the
    wanted tiles of the pack touch; None if the pack wants nothing in particular."""
    if not pack or not os.path.isfile(pack):
        return None
    with sqlite3.connect(f"file:{pack}?mode=ro", uri=True) as db:
        try:
            tiles = db.execute("SELECT z, x, y FROM wanted").fetchall()
        except sqlite3.Error:
            return None
    if not tiles:
        return None
    mercator, own = osr.SpatialReference(), osr.SpatialReference()
    mercator.ImportFromEPSG(3857)
    own.SetFromUserInput(srs)
    for reference in (mercator, own):
        reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    turn = osr.CoordinateTransformation(mercator, own)
    cells: set[tuple[int, int]] = set()
    for z, x, y in tiles:
        span = 2 * EARTH / 2**z
        west, north = -EARTH + x * span, EARTH - y * span
        corners = [
            turn.TransformPoint(px, py)[:2]
            for px in (west, west + span)
            for py in (north, north - span)
        ]
        # A rim of one kilometre: the tile is not upright in the model's coordinates.
        east_from = math.floor(min(c[0] for c in corners) / 1000) - 1
        east_to = math.floor(max(c[0] for c in corners) / 1000) + 1
        north_from = math.floor(min(c[1] for c in corners) / 1000) - 1
        north_to = math.floor(max(c[1] for c in corners) / 1000) + 1
        for east in range(east_from, east_to + 1):
            for up in range(north_from, north_to + 1):
                cells.add((east, up))
    return cells
