from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/


class Settings(BaseSettings):
    """Application config settings"""
    APP_NAME: str = "Bitza_backend"
    APP_VERSION: str = "0.1.0"
    DB_NAME: str = "bitza_1_dev.db"
    DB_PATH: str = "app/data"
    SECRET_KEY: str = "do not use this in prod. Ever."
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "auto" # auto | console | json
    LOG_FILE_NAME: str = "bitza_dev.log"
    LOG_MAX_BYTES: int = 5_000_000
    LOG_BACKUP_COUNT: int = 3
    DEBUG: bool = True # set to false in ../../.env for prod


    @property
    def DATABASE_URL(self) -> str:
        db_file = os.path.join(BASE_DIR, self.DB_PATH, self.DB_NAME)
        return f"sqlite:///{db_file}"
        
    model_config = SettingsConfigDict(
            env_file = ".env",
            env_file_encoding = "utf-8",
            extra = "ignore",
    )

    API_V1_PREFIX: str = "/api/v0_1"

@lru_cache()
def get_settings() -> Settings:
    return Settings()



settings = get_settings()
