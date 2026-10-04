from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Annual Report Analyst"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://analyst:analyst@localhost:5440/analyst"
    raw_dir: Path = Path("../data/raw")
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    retrieval_mode: Literal["vector", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    expand_pages: bool = True
    llm_model: str = "gemini-3.5-flash"
    pipeline: Literal["baseline", "agent"] = "agent"
    max_rewrites: int = 2
    google_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
