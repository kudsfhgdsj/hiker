from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_PREFIX = "/api/v1"


class Settings(BaseSettings):
    """Application configuration, read from environment variables (or a local `.env`)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./hiker-dev.db"
    secret_key: str = Field(min_length=32)
    public_base_url: str = "http://localhost:8000"
    enabled_modules: str = "auth"
    registration_mode: Literal["open", "closed"] = "open"
    access_token_ttl_minutes: int = Field(default=15, gt=0)
    refresh_token_ttl_days: int = Field(default=30, gt=0)
    storage_path: str = "./data/files"
    max_upload_mb: int = Field(default=15, gt=0)
    image_max_edge_px: int = Field(default=2000, ge=200)
    rate_limit_enabled: bool = True
    # Sign-in with password needs a second factor (TOTP); it is set up after the first login.
    mfa_required: bool = True
    # Single sign-on through OpenID Connect; empty issuer or client id = switched off.
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_name: str = "SSO"
    oidc_scopes: str = "openid email profile"
    # Accounts are linked and created by e-mail address only if the provider confirmed it.
    oidc_require_verified_email: bool = True
    # Empty value disables the lookup at Open Food Facts.
    openfoodfacts_base_url: str = "https://world.openfoodfacts.org"
    openfoodfacts_cache_days: int = Field(default=30, gt=0)
    # Empty value disables the elevation lookup for tracks without elevation.
    open_meteo_elevation_url: str = "https://api.open-meteo.com/v1/elevation"
    # Peaks and passes along a track come from OpenStreetMap; empty disables the lookup.
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    # How close a place of the map must be to the track line to count as passed.
    place_max_distance_m: float = Field(default=10, gt=0, le=500)
    # Empty values disable the weather lookup.
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"

    # Routing along paths for planned routes: the BRouter of the own server.
    # Empty: only straight lines can be planned.
    brouter_url: str = ""
    brouter_profile_hiking: str = "hiker-hiking"
    # Folder with BRouter's path data (*.rd5). The app downloads it from here to plan
    # routes without network. Empty: no path data is offered.
    brouter_segments_path: str = ""

    # Map tiles are cached on this server (module maps); empty disables fetching new ones.
    tile_source_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    tile_cache_path: str = "./data/tiles"
    # After this many days the source is asked whether a tile changed (at least 7: OSM policy).
    tile_cache_days: int = Field(default=14, ge=7)
    tile_cache_max_mb: int = Field(default=2000, gt=0)

    @property
    def module_names(self) -> list[str]:
        return [name.strip() for name in self.enabled_modules.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
