"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "DialogueForge"
    secret_key: str = "change-this-to-a-random-secret-key"
    log_level: str = "INFO"
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # Database
    database_url: str = "postgresql+asyncpg://dialogueforge:changeme_in_production@postgres:5432/dialogueforge"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"

    # Processing
    max_concurrent_generations: int = 5
    upload_dir: str = "/app/uploads"
    output_dir: str = "/app/outputs"

    # Audio defaults
    default_sample_rate: int = 44100
    default_silence_ms: int = 500

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
