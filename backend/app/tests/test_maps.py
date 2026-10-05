import os
import time

import httpx2
import pytest

from app.modules.maps.tiles import (
    FetchedTile,
    HttpTileSource,
    TileCache,
    TileSourceError,
    get_tile_cache,
    get_tile_source,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"tile-one"
PNG_NEW = b"\x89PNG\r\n\x1a\n" + b"tile-two"
TILE = "/api/v1/maps/tiles/12/2150/1440.png"


class FakeTileSource:
    """Stands in for the tile server; tests never touch the network."""

    def __init__(self):
        self.data: bytes | None = PNG
        self.etag: str | None = '"v1"'
        self.fail = False
        self.calls: list[tuple] = []

    def fetch(self, z, x, y, etag):
        self.calls.append((z, x, y, etag))
        if self.fail:
            raise TileSourceError("unreachable")
        if self.data is None:
            return None
        if etag is not None and etag == self.etag:
            return FetchedTile(None, etag)
        return FetchedTile(self.data, self.etag)


@pytest.fixture
def source():
    return FakeTileSource()


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "tiles"


@pytest.fixture
def maps(client, source, cache_dir):
    cache = TileCache(cache_dir, max_age_days=14, max_bytes=10_000_000)
    client.app.dependency_overrides[get_tile_source] = lambda: source
    client.app.dependency_overrides[get_tile_cache] = lambda: cache
    return client


def make_old(cache_dir, days: float) -> None:
    path = cache_dir / "12" / "2150" / "1440.png"
    past = time.time() - days * 86400
    os.utime(path, (past, past))


def test_tile_is_fetched_once_and_then_served_from_the_own_server(maps, source, cache_dir):
    first = maps.get(TILE)
    second = maps.get(TILE)

    assert first.status_code == 200 and first.content == PNG
    assert first.headers["content-type"] == "image/png"
    assert "max-age=86400" in first.headers["cache-control"]
    assert second.content == PNG
    assert source.calls == [(12, 2150, 1440, None)]
    assert (cache_dir / "12" / "2150" / "1440.png").read_bytes() == PNG


def test_tiles_need_no_login(maps):
    assert "authorization" not in maps.headers
    assert maps.get(TILE).status_code == 200


def test_old_tile_is_checked_with_its_etag_and_kept_if_unchanged(maps, source, cache_dir):
    maps.get(TILE)
    make_old(cache_dir, days=15)

    response = maps.get(TILE)
    again = maps.get(TILE)

    assert response.content == PNG and again.content == PNG
    # One conditional request; after it the tile counts as fresh for another period.
    assert source.calls == [(12, 2150, 1440, None), (12, 2150, 1440, '"v1"')]


def test_tile_that_is_not_old_yet_is_not_checked(maps, source, cache_dir):
    maps.get(TILE)
    make_old(cache_dir, days=13)

    maps.get(TILE)

    assert len(source.calls) == 1


def test_changed_tile_replaces_the_stored_one(maps, source, cache_dir):
    maps.get(TILE)
    make_old(cache_dir, days=15)
    source.data, source.etag = PNG_NEW, '"v2"'

    response = maps.get(TILE)

    assert response.content == PNG_NEW
    assert (cache_dir / "12" / "2150" / "1440.png").read_bytes() == PNG_NEW
    assert (cache_dir / "12" / "2150" / "1440.etag").read_text() == '"v2"'


def test_stored_tile_is_served_while_the_source_is_unreachable(maps, source, cache_dir):
    maps.get(TILE)
    make_old(cache_dir, days=100)
    source.fail = True

    assert maps.get(TILE).content == PNG


def test_unknown_tile_with_unreachable_source_is_a_502(maps, source):
    source.fail = True

    response = maps.get(TILE)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "source_unavailable"


def test_tiles_outside_of_the_grid_never_reach_the_source(maps, source):
    assert maps.get("/api/v1/maps/tiles/2/4/0.png").status_code == 404
    assert maps.get("/api/v1/maps/tiles/2/0/4.png").status_code == 404
    assert maps.get("/api/v1/maps/tiles/20/0/0.png").status_code == 422
    assert maps.get("/api/v1/maps/tiles/2/-1/0.png").status_code == 422
    assert maps.get("/api/v1/maps/tiles/2/..%2F..%2Fetc/0.png").status_code in (404, 422)
    assert source.calls == []


def test_tile_missing_at_the_source_is_a_404(maps, source):
    source.data = None

    assert maps.get(TILE).status_code == 404


def test_cache_drops_the_oldest_tiles_when_it_is_too_large(cache_dir, source):
    cache = TileCache(cache_dir, max_age_days=14, max_bytes=5 * len(PNG))
    for x in range(10):
        cache.get(source, 5, x, 0)
        past = time.time() - (10 - x) * 3600
        os.utime(cache_dir / "5" / str(x) / "0.png", (past, past))

    removed = cache.purge()

    left = sorted(int(path.parent.name) for path in cache_dir.glob("5/*/0.png"))
    assert removed == 6 and left == [6, 7, 8, 9]
    assert not (cache_dir / "5" / "0" / "0.etag").exists()


def test_info_names_the_own_tile_address_and_the_attribution(maps):
    info = maps.get("/api/v1/maps/info").json()

    assert info["tile_url"].endswith("/api/v1/maps/tiles/{z}/{x}/{y}.png")
    assert "OpenStreetMap" in info["attribution"] and info["cache_days"] >= 7


def test_http_source_identifies_itself_and_sends_the_etag():
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.headers.get("if-none-match") == '"v1"':
            return httpx2.Response(304)
        if request.url.path.endswith("/9/9/9.png"):
            return httpx2.Response(404)
        if request.url.path.endswith("/8/8/8.png"):
            return httpx2.Response(200, text="<html>blocked</html>")
        return httpx2.Response(
            200, content=PNG, headers={"content-type": "image/png", "etag": '"v1"'}
        )

    source = HttpTileSource(
        "https://tiles.example/{z}/{x}/{y}.png",
        "hiker/0.1 (self-hosted; https://hiker.example)",
        "https://hiker.example",
        transport=httpx2.MockTransport(handler),
    )

    assert source.fetch(12, 2150, 1440, None) == FetchedTile(PNG, '"v1"')
    assert source.fetch(12, 2150, 1440, '"v1"') == FetchedTile(None, '"v1"')
    assert source.fetch(9, 9, 9, None) is None
    with pytest.raises(TileSourceError):
        source.fetch(8, 8, 8, None)
    assert str(seen[0].url) == "https://tiles.example/12/2150/1440.png"
    assert seen[0].headers["user-agent"].startswith("hiker/")
    assert seen[0].headers["referer"] == "https://hiker.example"
