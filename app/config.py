"""Application configuration settings."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings for the Sales Platform application."""

    PROJECT_NAME: str = "Sales Platform API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "sales-platform-axe")
    FIRESTORE_COLLECTION_PRODUCTS: str = os.getenv("FIRESTORE_COLLECTION_PRODUCTS", "products")
    USE_IN_MEMORY_DB: bool = os.getenv("USE_IN_MEMORY_DB", "false").lower() == "true"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
