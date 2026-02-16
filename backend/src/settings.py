from __future__ import annotations
import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    """
    Centralized configuration for GSC Radar.
    Loads from .env file or environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database
    DATABASE_URL: str = "postgresql://user:pass@host:port/dbname"

    # Application URLs
    FRONTEND_URL: str = "https://dashboard.yourdomain.com"
    BACKEND_URL: str = "https://api.yourdomain.com"

    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    # CORS
    ALLOWED_ORIGINS_STR: str = "https://dashboard.yourdomain.com"

    # SendGrid Configuration
    SENDGRID_API_KEY: str
    SENDGRID_FROM_EMAIL: str

    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        """Dynamically derived redirect URI"""
        return f"{self.BACKEND_URL}/api/auth/google/callback"

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        """Parse comma-separated origins into a list"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS_STR.split(",") if origin.strip()]

settings = Settings()
