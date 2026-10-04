from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Annual Report Analyst"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://analyst:analyst@localhost:5440/analyst"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    llm_model: str = "gemini-3.5-flash"
    google_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
