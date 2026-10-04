"""Joins vector tiles of the same place from several maps into one.

Each region is a map of its own, cut at the edge of its OpenStreetMap extract.
A tile on a border is therefore only half filled in each of them. The layers of
such tiles are joined: features of layers with the same name end up in one
layer, with one shared table of keys and values, and a feature that both maps
carry (the same geometry with the same attributes) is kept once.

Only what the joining needs is read of the tile format (Mapbox Vector Tile 2):
layers, their key and value tables and the tags of the features. Geometries
are passed on as they are.
"""

_VARINT, _FIXED64, _BYTES, _FIXED32 = 0, 1, 2, 5
# Fields of a tile, a layer and a feature.
_LAYER = 3
_NAME, _FEATURE, _KEY, _VALUE, _EXTENT, _VERSION = 1, 2, 3, 4, 5, 15
_TAGS = 2


class TileFormatError(ValueError):
    """The data is not a vector tile."""


def _varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _read_varint(data: bytes, position: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        if position >= len(data) or shift > 63:
            raise TileFormatError("varint")
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7


def _fields(data: bytes):
    """The fields of a message: number, wire type, value (int or bytes), raw bytes."""
    position = 0
    while position < len(data):
        start = position
        tag, position = _read_varint(data, position)
        number, wire = tag >> 3, tag & 7
        if wire == _VARINT:
            value, position = _read_varint(data, position)
        elif wire == _BYTES:
            length, position = _read_varint(data, position)
            value = data[position : position + length]
            position += length
        elif wire in (_FIXED64, _FIXED32):
            width = 8 if wire == _FIXED64 else 4
            value = data[position : position + width]
            position += width
        else:
            raise TileFormatError("wire type")
        if position > len(data):
            raise TileFormatError("length")
        yield number, wire, value, data[start:position]


def _bytes_field(number: int, payload: bytes) -> bytes:
    return _varint(number << 3 | _BYTES) + _varint(len(payload)) + payload


class _Layer:
    """A layer being put together from the layers of that name of several tiles."""

    def __init__(self, name: bytes):
        self.name = name
        self.extent: int | None = None
        self.version = 2
        self.keys: dict[bytes, int] = {}
        self.values: dict[bytes, int] = {}
        self.features: dict[bytes, None] = {}

    def add(self, layer: bytes) -> None:
        keys: list[bytes] = []
        values: list[bytes] = []
        features: list[bytes] = []
        extent, version = 4096, 1
        for number, _wire, value, _raw in _fields(layer):
            if number == _KEY:
                keys.append(value)
            elif number == _VALUE:
                values.append(value)
            elif number == _FEATURE:
                features.append(value)
            elif number == _EXTENT:
                extent = value
            elif number == _VERSION:
                version = value
        if self.extent is None:
            self.extent, self.version = extent, version
        elif extent != self.extent:
            # Another grid: its coordinates would land in the wrong place.
            return
        # Where the keys and values of this layer are in the shared tables.
        key_at = [self.keys.setdefault(key, len(self.keys)) for key in keys]
        value_at = [self.values.setdefault(value, len(self.values)) for value in values]
        for feature in features:
            parts = []
            for number, wire, value, raw in _fields(feature):
                if number == _TAGS and wire == _BYTES:
                    tags = bytearray()
                    position = 0
                    while position < len(value):
                        key, position = _read_varint(value, position)
                        item, position = _read_varint(value, position)
                        if key >= len(key_at) or item >= len(value_at):
                            raise TileFormatError("tag")
                        tags += _varint(key_at[key]) + _varint(value_at[item])
                    parts.append(_bytes_field(_TAGS, bytes(tags)))
                else:
                    parts.append(raw)
            # The same feature from two maps is the same bytes now: kept once.
            self.features.setdefault(b"".join(parts))

    def encode(self) -> bytes:
        body = b"".join(
            [
                _varint(_VERSION << 3 | _VARINT) + _varint(self.version),
                _bytes_field(_NAME, self.name),
                *(_bytes_field(_FEATURE, feature) for feature in self.features),
                *(_bytes_field(_KEY, key) for key in self.keys),
                *(_bytes_field(_VALUE, value) for value in self.values),
                _varint(_EXTENT << 3 | _VARINT) + _varint(self.extent or 4096),
            ]
        )
        return _bytes_field(_LAYER, body)


def join_tiles(tiles: list[bytes]) -> bytes:
    """One tile with everything the given (uncompressed) tiles hold.

    Raises `TileFormatError` if one of them cannot be read.
    """
    if len(tiles) == 1:
        return tiles[0]
    layers: dict[bytes, _Layer] = {}
    for tile in tiles:
        for number, wire, value, _raw in _fields(tile):
            if number != _LAYER or wire != _BYTES:
                continue
            name = next((v for n, _w, v, _r in _fields(value) if n == _NAME), b"")
            layers.setdefault(name, _Layer(name)).add(value)
    return b"".join(layer.encode() for layer in layers.values())
