from __future__ import annotations
import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    """
    Centralized configuration for GSC Quick View.
    Loads from .env file or environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database
    DATABASE_URL: str = "postgresql://localhost/gsc_quickview"

    # Application URLs
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"

    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    # CORS
    ALLOWED_ORIGINS_STR: str = "http://localhost:5173"

    # SMTP Configuration
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        """Dynamically derived redirect URI"""
        return f"{self.BACKEND_URL}/api/auth/google/callback"

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        """Parse comma-separated origins into a list"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS_STR.split(",") if origin.strip()]

settings = Settings()
