"""Contour lines as vector tiles, computed from the elevation tiles.

The lines are traced with marching squares on a thinned-out grid of the
elevation tile and written as a Mapbox Vector Tile with one layer `contour`.
Every line carries its elevation `ele` and `index` (1 for every fifth line,
which is drawn stronger and labelled).
"""

import gzip
import io
import math

from PIL import Image

CONTOUR_MIN_ZOOM = 9
CONTOUR_MAX_ZOOM = 13
EXTENT = 4096
# Distance between two lines in metres, by zoom level.
_INTERVALS = {9: 200, 10: 200, 11: 100, 12: 50, 13: 20}
# Every second pixel is enough: the elevation data is coarser than the tile.
_STEP = 2


def interval_for(z: int) -> int:
    return _INTERVALS[min(max(z, CONTOUR_MIN_ZOOM), CONTOUR_MAX_ZOOM)]


def _grid(terrain_png: bytes) -> tuple[list[list[float]], int]:
    """Elevations in metres on a square grid whose edges lie on the tile edges."""
    image = Image.open(io.BytesIO(terrain_png)).convert("RGB")
    size = image.size[0]
    pixels = image.tobytes()
    indexes = sorted({*range(0, size, _STEP), size - 1})
    grid = []
    for row in indexes:
        offset = row * size * 3
        grid.append(
            [
                # Terrarium: metres = red * 256 + green + blue / 256 - 32768
                pixels[offset + column * 3] * 256
                + pixels[offset + column * 3 + 1]
                + pixels[offset + column * 3 + 2] / 256
                - 32768
                for column in indexes
            ]
        )
    return grid, len(indexes)


def trace(grid: list[list[float]], count: int, interval: int) -> dict[int, list[list[tuple]]]:
    """Lines per elevation, in grid coordinates (column, row)."""
    segments: dict[int, list[tuple]] = {}
    for row in range(count - 1):
        upper, lower = grid[row], grid[row + 1]
        for column in range(count - 1):
            a, b, c, d = upper[column], upper[column + 1], lower[column + 1], lower[column]
            low, high = min(a, b, c, d), max(a, b, c, d)
            level = math.floor(low / interval) * interval + interval
            while level <= high:
                # A corner exactly on a line counts as above it.
                case = (a >= level) | (b >= level) << 1 | (c >= level) << 2 | (d >= level) << 3
                if case not in (0, 15):
                    top = (column + (level - a) / (b - a), row) if a != b else None
                    right = (column + 1, row + (level - b) / (c - b)) if b != c else None
                    bottom = (column + (level - d) / (c - d), row + 1) if c != d else None
                    left = (column, row + (level - a) / (d - a)) if a != d else None
                    pairs = {
                        1: ((left, top),),
                        2: ((top, right),),
                        3: ((left, right),),
                        4: ((right, bottom),),
                        5: ((left, top), (right, bottom)),
                        6: ((top, bottom),),
                        7: ((left, bottom),),
                        8: ((bottom, left),),
                        9: ((bottom, top),),
                        10: ((top, right), (bottom, left)),
                        11: ((bottom, right),),
                        12: ((right, left),),
                        13: ((right, top),),
                        14: ((top, left),),
                    }[case]
                    for start, end in pairs:
                        if start is not None and end is not None and start != end:
                            segments.setdefault(level, []).append((start, end))
                level += interval
    return {level: _join(parts) for level, parts in segments.items()}


def _join(segments: list[tuple]) -> list[list[tuple]]:
    """Chain single segments into lines, so that the tile stays small and labels fit."""

    def key(point: tuple) -> tuple:
        return (round(point[0], 4), round(point[1], 4))

    ends: dict[tuple, list[int]] = {}
    for index, (start, end) in enumerate(segments):
        ends.setdefault(key(start), []).append(index)
        ends.setdefault(key(end), []).append(index)
    used = [False] * len(segments)
    lines = []
    for index, segment in enumerate(segments):
        if used[index]:
            continue
        used[index] = True
        line = [segment[0], segment[1]]
        # Grow the line at its end, then at its start.
        for at_end in (True, False):
            while True:
                tip = line[-1] if at_end else line[0]
                follower = next((i for i in ends[key(tip)] if not used[i]), None)
                if follower is None:
                    break
                used[follower] = True
                start, end = segments[follower]
                point = end if key(start) == key(tip) else start
                if at_end:
                    line.append(point)
                else:
                    line.insert(0, point)
        lines.append(line)
    return lines


# --- Mapbox Vector Tile (protobuf), written by hand: no further dependency ---


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field(number: int, wire_type: int, payload: bytes) -> bytes:
    return _varint(number << 3 | wire_type) + payload


def _bytes_field(number: int, data: bytes) -> bytes:
    return _field(number, 2, _varint(len(data)) + data)


def _zigzag(value: int) -> int:
    return (value << 1) ^ (value >> 63)


def _geometry(lines: list[list[tuple[int, int]]]) -> bytes:
    out = bytearray()
    x = y = 0
    for line in lines:
        out += _varint(1 << 3 | 1)  # MoveTo, one point
        out += _varint(_zigzag(line[0][0] - x)) + _varint(_zigzag(line[0][1] - y))
        x, y = line[0]
        out += _varint((len(line) - 1) << 3 | 2)  # LineTo
        for px, py in line[1:]:
            out += _varint(_zigzag(px - x)) + _varint(_zigzag(py - y))
            x, y = px, py
    return bytes(out)


def encode(contours: dict[int, list[list[tuple[int, int]]]], interval: int) -> bytes:
    """One layer `contour`; one feature per elevation with all its lines."""
    levels = sorted(contours)
    # Values: the elevations, then 0 and 1 for `index`.
    values = [_bytes_field(4, _field(6, 0, _varint(_zigzag(level)))) for level in levels]
    values += [_bytes_field(4, _field(5, 0, _varint(flag))) for flag in (0, 1)]
    features = b""
    for position, level in enumerate(levels):
        index = len(levels) + (1 if level % (interval * 5) == 0 else 0)
        tags = _varint(0) + _varint(position) + _varint(1) + _varint(index)
        feature = (
            _bytes_field(2, tags)
            + _field(3, 0, _varint(2))  # LINESTRING
            + _bytes_field(4, _geometry(contours[level]))
        )
        features += _bytes_field(2, feature)
    layer = (
        _field(15, 0, _varint(2))
        + _bytes_field(1, b"contour")
        + features
        + _bytes_field(3, b"ele")
        + _bytes_field(3, b"index")
        + b"".join(values)
        + _field(5, 0, _varint(EXTENT))
    )
    return _bytes_field(3, layer)


def contour_tile(terrain_png: bytes, z: int) -> bytes:
    """The gzip-compressed vector tile with the contour lines of an elevation tile."""
    interval = interval_for(z)
    grid, count = _grid(terrain_png)
    scale = EXTENT / (count - 1)
    contours = {}
    for level, lines in trace(grid, count, interval).items():
        scaled = []
        for line in lines:
            points = []
            for column, row in line:
                point = (round(column * scale), round(row * scale))
                if not points or points[-1] != point:
                    points.append(point)
            if len(points) > 1:
                scaled.append(points)
        if scaled:
            contours[level] = scaled
    return gzip.compress(encode(contours, interval), compresslevel=6, mtime=0)
