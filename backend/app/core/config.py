import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Read APP_ENV before Settings is instantiated so we can select the right .env file.
# This allows `APP_ENV=prod python -m uvicorn ...` to load .env.prod automatically.
_APP_ENV: str = os.getenv("APP_ENV", "dev")


class Settings(BaseSettings):
    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    APP_ENV: Literal["dev", "test", "uat", "prod"] = "dev"
    APP_NAME: str = "Bitza asset management API"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # -------------------------------------------------------------------------
    # Database — each environment uses its own SQLite file.
    # Override DATABASE_URL in the environment's .env file.
    # -------------------------------------------------------------------------
    DATABASE_URL: str = f"sqlite:///./data/{_APP_ENV}.db"

    # -------------------------------------------------------------------------
    # JWT
    # -------------------------------------------------------------------------
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_generate_with_openssl_rand_hex_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # -------------------------------------------------------------------------
    # Password policy
    # -------------------------------------------------------------------------
    # Set to True in .env.prod for public-facing deployments.
    # When enabled, passwords are checked against the HIBP k-anonymity API.
    CHECK_PWNED_PASSWORDS: bool = False


    # -------------------------------------------------------------------------
    # File uploads — stored on the server filesystem, path recorded in DB.
    # -------------------------------------------------------------------------
    UPLOAD_DIR: str = "./data/uploads"
    model_config = SettingsConfigDict(
        # Load the environment-specific .env file (e.g. .env.prod)
        env_file=f".env.{_APP_ENV}",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton — import and call this everywhere."""
    return Settings()
