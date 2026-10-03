"""Configuration from environment variables; nothing here is a secret or a fixed domain."""

import os


def load_config() -> dict:
    return {
        # Signs the session cookie; required.
        "SECRET_KEY": os.environ.get("WEB_SECRET_KEY", ""),
        # Address of the hiker API as seen from this service, without /api/v1.
        "API_BASE_URL": os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        # Where the tokens of signed-in users are kept on the server.
        "SESSION_DIR": os.environ.get("WEB_SESSION_DIR", "./data/web-sessions"),
        "SESSION_COOKIE_SECURE": os.environ.get("WEB_COOKIE_SECURE", "true").lower() != "false",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_NAME": "hiker_session",
        "MAX_CONTENT_LENGTH": int(os.environ.get("MAX_UPLOAD_MB", "15")) * 1024 * 1024 * 21,
        # Tile source of the map; replaceable until the licences are settled.
        "MAP_TILE_URL": os.environ.get(
            "MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        ),
    }
