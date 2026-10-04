#!/usr/bin/env python3
"""Smoke test for a running hiker stack (API and web frontend). Python standard library only.

    deploy/smoke_test.py --api http://127.0.0.1:8010 --web http://127.0.0.1:8011

Registers a throwaway user (or signs in with SMOKE_EMAIL / SMOKE_PASSWORD when the
registration is closed), walks through gear, food, a tour with GPX track and photo,
the history, a public link and the web pages, and removes its tour, gear and food
again. The throwaway user stays; use an existing account on a real server.
"""

import argparse
import base64
import datetime
import http.cookiejar
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

# A valid 1x1 JPEG.
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJ"
    "DRENDg8QEBEQCgwSExIQEw8QEBD/yQALCAABAAEBAREA/8wABgAQEAX/2gAIAQEAAD8A0s8g/9k="
)


class Failure(Exception):
    pass


def check(condition, message: str) -> None:
    if not condition:
        raise Failure(message)


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token: str | None = None
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(self, method: str, path: str, *, json_body=None, data=None, headers=None):
        """Returns (status, headers, body bytes); HTTP errors are returned, not raised."""
        headers = dict(headers or {})
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(request, timeout=60) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def json(self, method: str, path: str, body=None, expect: int | tuple = (200, 201, 204)):
        status, _headers, raw = self.request(method, path, json_body=body)
        expected = expect if isinstance(expect, tuple) else (expect,)
        check(status in expected, f"{method} {path} -> {status}: {raw[:300]!r}")
        return json.loads(raw) if raw else None

    def upload(self, method: str, path: str, field: str, filename: str, content: bytes, mime: str):
        boundary = uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
            f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        status, _headers, raw = self.request(method, path, data=body, headers=headers)
        check(status in (200, 201), f"{method} {path} -> {status}: {raw[:300]!r}")
        return json.loads(raw)


def sample_gpx() -> bytes:
    start = datetime.datetime(2026, 7, 1, 6, 0, tzinfo=datetime.UTC)
    points = []
    for index in range(60):
        angle = index / 60 * 2 * math.pi
        time = (start + datetime.timedelta(minutes=index * 3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        points.append(
            f'<trkpt lat="{47.249 + 0.02 * math.sin(angle):.5f}" '
            f'lon="{9.343 + 0.03 * math.cos(angle):.5f}">'
            f"<ele>{1400 + 1000 * math.sin(angle / 2):.0f}</ele><time>{time}</time></trkpt>"
        )
    return (
        '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><trkseg>{''.join(points)}</trkseg></trk></gpx>"
    ).encode()


def step(name: str) -> None:
    print(f"  ok  {name}")


def run(api_url: str, web_url: str) -> None:
    api = Client(api_url)
    web = Client(web_url)
    prefix = "/api/v1"

    status, _h, raw = api.request("GET", "/healthz")
    check(status == 200, f"API /healthz -> {status}")
    status, _h, raw = web.request("GET", "/healthz")
    check(status == 200, f"web /healthz -> {status}")
    modules = {module["name"] for module in api.json("GET", f"{prefix}/modules")}
    check({"auth", "gear", "nutrition", "protocols"} <= modules, f"modules missing: {modules}")
    step(f"both services answer; modules: {', '.join(sorted(modules))}")

    email, password = os.environ.get("SMOKE_EMAIL"), os.environ.get("SMOKE_PASSWORD")
    if email and password:
        auth = api.json("POST", f"{prefix}/auth/login", {"email": email, "password": password})
    else:
        email = f"smoke-{uuid.uuid4().hex[:10]}@example.org"
        password = uuid.uuid4().hex + "Aa1"
        body = {"email": email, "password": password, "display_name": "Smoke Test"}
        auth = api.json("POST", f"{prefix}/auth/register", body)
    api.token = auth["access_token"]
    step(f"signed in as {email}")

    created: list[str] = []
    try:
        gear = api.json(
            "POST", f"{prefix}/gear/items", {"name": "Smoke tent", "weight_g": 1500, "status": "active"}
        )
        created.append(f"{prefix}/gear/items/{gear['id']}")
        food = api.json(
            "POST", f"{prefix}/nutrition/foods", {"name": "Smoke bar", "kcal_per_100g": 400}
        )
        created.append(f"{prefix}/nutrition/foods/{food['id']}")
        title = f"Smoke tour {uuid.uuid4().hex[:6]}"
        tour = api.json(
            "POST",
            f"{prefix}/tours",
            {
                "title": title,
                "gear": [{"gear_item_id": gear["id"], "quantity": 1}],
                "food": [{"food_item_id": food["id"], "amount_g": 100, "eaten": True}],
            },
        )
        tour_path = f"{prefix}/tours/{tour['id']}"
        created.insert(0, tour_path)
        check(tour["computed"]["pack_weight_start_g"] == 1600, "pack weight is not 1600 g")
        check(tour["computed"]["calories_eaten"] == 400, "calories eaten are not 400 kcal")
        step("gear, food and a tour with snapshots (database works)")

        tour = api.upload("PUT", f"{tour_path}/gpx", "file", "smoke.gpx", sample_gpx(), "application/gpx+xml")
        stats = tour["track_stats"]
        check(stats and stats["distance_m"] > 5000, f"track statistics look wrong: {stats}")
        check(tour["start_time"] is not None, "start time was not taken from the track")
        photos = api.upload("POST", f"{tour_path}/photos", "files", "smoke.jpg", TINY_JPEG, "image/jpeg")
        status, headers, raw = api.request("GET", f"{tour_path}/photos/{photos[0]['id']}/image?size=thumb")
        check(status == 200 and raw[:2] == b"\xff\xd8", f"photo not readable: {status}")
        step(f"GPX evaluated ({stats['distance_m'] / 1000:.1f} km), photo stored (file storage works)")

        current = api.json("GET", tour_path)
        outdated = {**{k: current[k] for k in ("title", "summary")}, "version": current["version"] - 1}
        outdated.update(gear=[], food=[], peaks=[], partners=[])
        api.json("PUT", tour_path, outdated, expect=409)
        revisions = api.json("GET", f"{tour_path}/revisions")
        check(revisions["total"] >= 3, f"history too short: {revisions['total']}")
        step(f"conflict protection answers 409; history has {revisions['total']} versions")

        link = api.json("POST", f"{tour_path}/public-link", {})
        token = link["url"].rstrip("/").rsplit("/", 1)[1]
        status, headers, raw = web.request("GET", f"/p/{token}")
        page = raw.decode()
        check(status == 200 and title in page, f"public page -> {status}")
        check("noindex" in headers.get("X-Robots-Tag", ""), "public page lacks X-Robots-Tag")
        check(email not in page and tour["id"] not in page, "public page leaks e-mail or id")
        status, _h, raw = web.request("GET", f"/p/{token}/track.json")
        check(status == 200 and json.loads(raw)["series"], "public track missing")
        status, _h, raw = web.request("GET", f"/p/{token}/photos/0?size=thumb")
        check(status == 200 and raw[:2] == b"\xff\xd8", "public photo missing")
        api.json("DELETE", f"{tour_path}/public-link/{link['id']}")
        status, _h, _raw = web.request("GET", f"/p/{token}")
        check(status == 404, f"revoked link still answers {status}")
        step("public link page works without login and is gone after revoking")

        status, headers, raw = web.request("GET", "/login")
        check(status == 200, f"web /login -> {status}")
        check("default-src 'self'" in headers.get("Content-Security-Policy", ""), "CSP missing")
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', raw.decode())
        check(csrf, "login form has no CSRF token")
        status, _h, _raw = web.request("GET", "/static/vendor/maplibre-gl/maplibre-gl-csp.js")
        check(status == 200, "map library is not served")
        secure_only = any(cookie.secure for cookie in web.cookies)
        if secure_only and web_url.startswith("http://"):
            step("web pages and map library served (web login skipped: Secure cookie over HTTP)")
        else:
            form = urllib.parse.urlencode(
                {"email": email, "password": password, "csrf_token": csrf.group(1)}
            ).encode()
            status, _h, raw = web.request("POST", "/login", data=form)
            check(status == 200 and title in raw.decode(), f"web login or tour list failed ({status})")
            status, _h, raw = web.request("GET", f"/tours/{tour['id']}")
            check(status == 200 and "tour-data" in raw.decode(), "web tour page incomplete")
            step("web login, tour list and tour page")
    finally:
        for path in created:
            api.request("DELETE", path)
    status, _h, _raw = api.request("GET", created[0]) if created else (404, None, None)
    check(status == 404, "cleanup failed: the tour still exists")
    step("test data removed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default="http://127.0.0.1:8010", help="base URL of the API")
    parser.add_argument("--web", default="http://127.0.0.1:8011", help="base URL of the web frontend")
    arguments = parser.parse_args()
    try:
        run(arguments.api, arguments.web)
    except Failure as failure:
        print(f"FAILED: {failure}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"FAILED: not reachable: {error}", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
