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

    # Lista de origens (domínios) autorizadas a consumir a API via CORS,
    # separadas por vírgula na env var ALLOWED_ORIGINS. Em desenvolvimento,
    # sem a variável definida, libera tudo ("*") para não travar testes
    # locais. Em produção, SEMPRE defina explicitamente (ver deploy.sh) —
    # nunca deixe "*" em produção com allow_credentials=True.
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins_list(self) -> list[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()
