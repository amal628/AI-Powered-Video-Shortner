# backend/app/core/config.py

from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    """
    Application configuration settings.
    Automatically reads from .env file if available.
    """

    # --------------------------------------------------
    # BASIC APP SETTINGS
    # --------------------------------------------------
    APP_NAME: str = "AI Powered Video Shortener"
    DEBUG: bool = True

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        """
        Accept common non-boolean env values like 'release'/'prod'
        to avoid startup failures from misconfigured environments.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"1", "true", "yes", "on", "debug", "dev"}:
                return True
            if v in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value

    # --------------------------------------------------
    # DATABASE CONFIGURATION
    # --------------------------------------------------
    DATABASE_URL: str = "sqlite:///./app.db"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 0
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    # --------------------------------------------------
    # SECURITY CONFIGURATION
    # --------------------------------------------------
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --------------------------------------------------
    # CACHE CONFIGURATION
    # --------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 3600  # 1 hour

    # --------------------------------------------------
    # CELERY CONFIGURATION
    # --------------------------------------------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # --------------------------------------------------
    # CLOUD STORAGE CONFIGURATION
    # --------------------------------------------------
    CLOUD_STORAGE_ENABLED: bool = False
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = ""

    # --------------------------------------------------
    # RATE LIMITING CONFIGURATION
    # --------------------------------------------------
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # --------------------------------------------------
    # FILE UPLOAD CONFIGURATION
    # --------------------------------------------------
    MAX_VIDEO_SIZE: int = 500 * 1024 * 1024  # 500MB

    # --------------------------------------------------
    # BASE DIRECTORY (Backend Root)
    # --------------------------------------------------
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    # --------------------------------------------------
    # STATIC & STORAGE DIRECTORIES
    # --------------------------------------------------
    STATIC_DIR: Path = BASE_DIR / "app" / "static"

    UPLOAD_DIR: Path = STATIC_DIR / "uploads"
    AUDIO_DIR: Path = STATIC_DIR / "audio"
    CLIPS_DIR: Path = STATIC_DIR / "clips"
    OUTPUTS_DIR: Path = STATIC_DIR / "outputs"

    # --------------------------------------------------
    # ENVIRONMENT CONFIG
    # --------------------------------------------------
    class Config:
        env_file = ".env"
        case_sensitive = True  # Prevent attribute confusion


# Create single settings instance
settings = Settings()


# --------------------------------------------------
# AUTO CREATE DIRECTORIES IF NOT EXIST
# --------------------------------------------------
def create_directories():
    directories = [
        settings.STATIC_DIR,
        settings.UPLOAD_DIR,
        settings.AUDIO_DIR,
        settings.CLIPS_DIR,
        settings.OUTPUTS_DIR,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


create_directories()
