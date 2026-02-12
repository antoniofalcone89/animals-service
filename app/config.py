"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    API_KEY: str = "changeme"
    FIREBASE_CREDENTIALS: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    RATE_LIMIT: str = "100/minute"
    CACHE_TTL: int = 3600
    DEBUG: bool = False

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
