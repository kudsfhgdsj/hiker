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
    # Empty value disables the lookup at Open Food Facts.
    openfoodfacts_base_url: str = "https://world.openfoodfacts.org"
    openfoodfacts_cache_days: int = Field(default=30, gt=0)

    @property
    def module_names(self) -> list[str]:
        return [name.strip() for name in self.enabled_modules.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
