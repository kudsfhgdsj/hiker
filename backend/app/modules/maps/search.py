"""Search for places in the own map: summits, huts, towns, lakes and the like by name.

The index of a region is made from its vector map (`<region>.mbtiles` →
`<region>.search.sqlite`): every named point of the layers `place`,
`mountain_peak`, `poi` and `water_name` at the deepest zoom level. So the search
knows exactly what the map shows, asks no foreign service, and the app can take
the file along with the map.

    python -m app.modules.maps.search /data/switzerland.mbtiles
"""

import gzip
import math
import sqlite3
import struct
import sys
import unicodedata
import zlib
from pathlib import Path

from app.modules.maps.join import TileFormatError, _fields, _read_varint

SEARCH_SUFFIX = ".search.sqlite"
MAX_RESULTS = 30

# Smaller is more important; decides the order among equally good matches.
_PLACE_RANK = {"city": 1, "town": 2, "village": 3, "hamlet": 5}
_HUTS = {"alpine_hut", "wilderness_hut"}
# Points of interest a walker looks for; shops and the like stay out of the index.
_POI_KINDS = {
    "shelter",
    "viewpoint",
    "camp_site",
    "station",
    "halt",
    "parking",
    "attraction",
    "castle",
    "ruins",
    "cave_entrance",
    "waterfall",
    "spring",
}
_POINT = 1


def search_path(map_path: Path) -> Path:
    return map_path.with_name(map_path.stem + SEARCH_SUFFIX)


def fold(text: str) -> str:
    """Lower case without accents, so that "saentis" and "Säntis" meet halfway:
    "Säntis" → "santis", "Großglockner" → "grossglockner"."""
    text = text.casefold().replace("ß", "ss")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).strip()


def _value(data: bytes):
    """A value of a layer: text or number."""
    for number, wire, value, _raw in _fields(data):
        if number == 1:
            return value.decode("utf-8", "replace")
        if number == 2:
            return struct.unpack("<f", value)[0]
        if number == 3:
            return struct.unpack("<d", value)[0]
        if number in (4, 5):
            return value
        if number == 6:
            return (value >> 1) ^ -(value & 1)
        if number == 7 and wire == 0:
            return bool(value)
    return None


def _kind(layer: str, attributes: dict) -> tuple[str, int] | None:
    """What a feature is for the search, and how important; None: not searched."""
    group = attributes.get("class")
    if layer == "place":
        return str(group or "place"), _PLACE_RANK.get(group, 6)
    if layer == "mountain_peak":
        return ("peak", 4) if group in (None, "peak") else (str(group), 5)
    if layer == "water_name":
        return "lake", 4
    if layer == "poi":
        detail = attributes.get("subclass")
        if detail in _HUTS:
            return "hut", 4
        for name in (detail, group):
            if name in _POI_KINDS:
                return str(name), 7
    return None


def places_of(tile: bytes, z: int, x: int, y: int):
    """The named points of a tile: (name, kind, rank, lat, lon, elevation)."""
    for number, _wire, layer, _raw in _fields(tile):
        if number != 3:
            continue
        name, keys, values, features, extent = "", [], [], [], 4096
        for field, _w, content, _r in _fields(layer):
            if field == 1:
                name = content.decode()
            elif field == 2:
                features.append(content)
            elif field == 3:
                keys.append(content.decode())
            elif field == 4:
                values.append(content)
            elif field == 5:
                extent = content
        if name not in ("place", "mountain_peak", "poi", "water_name"):
            continue
        decoded: dict[int, object] = {}
        for feature in features:
            tags = geometry = b""
            shape = 0
            for field, _w, content, _r in _fields(feature):
                if field == 2:
                    tags = content
                elif field == 3:
                    shape = content
                elif field == 4:
                    geometry = content
            if shape != _POINT or not geometry:
                continue
            attributes = {}
            position = 0
            while position < len(tags):
                key, position = _read_varint(tags, position)
                item, position = _read_varint(tags, position)
                if key >= len(keys) or item >= len(values):
                    raise TileFormatError("tag")
                if item not in decoded:
                    decoded[item] = _value(values[item])
                attributes[keys[key]] = decoded[item]
            title = attributes.get("name")
            kind = _kind(name, attributes)
            if not isinstance(title, str) or not title.strip() or kind is None:
                continue
            # A point: "move to" once, then the two coordinates, zigzag encoded.
            _command, position = _read_varint(geometry, 0)
            dx, position = _read_varint(geometry, position)
            dy, position = _read_varint(geometry, position)
            px, py = (dx >> 1) ^ -(dx & 1), (dy >> 1) ^ -(dy & 1)
            if not (0 <= px <= extent and 0 <= py <= extent):
                # In the margin of the tile: the neighbour has it inside.
                continue
            lon = (x + px / extent) / 2**z * 360 - 180
            lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py / extent) / 2**z))))
            elevation = attributes.get("ele")
            yield (
                title.strip(),
                kind[0],
                kind[1],
                round(lat, 5),
                round(lon, 5),
                float(elevation) if isinstance(elevation, (int, float)) else None,
            )


def build_index(map_path: Path) -> int:
    """Writes the search index next to the map; returns the number of places."""
    target = search_path(map_path)
    part = target.with_name(target.name + ".part")
    part.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{map_path}?mode=ro", uri=True)
    out = sqlite3.connect(part)
    try:
        out.execute(
            "CREATE TABLE places (name TEXT, folded TEXT, kind TEXT, rank INTEGER,"
            " lat REAL, lon REAL, elevation_m REAL)"
        )
        zoom = source.execute("SELECT max(zoom_level) FROM tiles").fetchone()[0]
        seen: set[tuple] = set()
        rows = source.execute(
            "SELECT tile_column, tile_row, tile_data FROM tiles WHERE zoom_level = ?", (zoom,)
        )
        for x, row, data in rows:
            try:
                found = list(places_of(gzip.decompress(data), zoom, x, 2**zoom - 1 - row))
            except (OSError, EOFError, zlib.error, TileFormatError, struct.error, IndexError):
                continue
            for name, kind, rank, lat, lon, elevation in found:
                folded = fold(name)
                # The same place drawn in two tiles or twice in the data.
                key = (folded, kind, round(lat, 3), round(lon, 3))
                if not folded or key in seen:
                    continue
                seen.add(key)
                out.execute(
                    "INSERT INTO places VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, folded, kind, rank, lat, lon, elevation),
                )
        out.execute("CREATE INDEX places_folded ON places (folded)")
        out.commit()
        out.execute("VACUUM")
    finally:
        out.close()
        source.close()
    # Only a finished index gets the name the server looks for.
    part.replace(target)
    return len(seen)


def search(
    indexes: list[Path], query: str, near: tuple[float, float] | None = None, limit: int = 10
) -> list[dict]:
    """Places whose name contains the query, the best first: the name itself, then names
    that start with it (the shortest first), then by importance and, if `near` is given,
    by distance."""
    folded = fold(query)
    if len(folded) < 2:
        return []
    pattern = "%" + folded.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    lat, lon = near if near is not None else (0.0, 0.0)
    squeeze = math.cos(math.radians(lat)) if near is not None else 0.0
    found: dict[tuple, tuple] = {}
    for index in indexes:
        try:
            with sqlite3.connect(f"file:{index}?mode=ro", uri=True) as db:
                rows = db.execute(
                    "SELECT name, kind, rank, lat, lon, elevation_m, folded FROM places"
                    " WHERE folded LIKE ? ESCAPE '\\' LIMIT 2000",
                    (pattern,),
                ).fetchall()
        except sqlite3.Error:
            continue
        for name, kind, rank, place_lat, place_lon, elevation, text in rows:
            distance = (
                math.hypot(place_lat - lat, (place_lon - lon) * squeeze) if near is not None else 0
            )
            starts = text.startswith(folded)
            # Among names that start with the query the one closest to it comes first
            # ("zugspitz" means the Zugspitze, not the Zugspitzeck).
            rest = len(text) - len(folded) if starts else 0
            order = (text != folded, not starts, rank, rest, distance, len(text))
            # Two regions know the places along their border.
            key = (text, kind, round(place_lat, 3), round(place_lon, 3))
            if key not in found or order < found[key][0]:
                result = {
                    "name": name,
                    "kind": kind,
                    "lat": place_lat,
                    "lon": place_lon,
                    "elevation_m": elevation,
                }
                found[key] = (order, result)
    ranked = sorted(found.values(), key=lambda entry: entry[0])
    return [result for _order, result in ranked[: min(limit, MAX_RESULTS)]]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    count = build_index(Path(sys.argv[1]))
    print(f"{count} places in {search_path(Path(sys.argv[1])).name}")
