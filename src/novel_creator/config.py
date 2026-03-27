"""Application configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "NOVEL_", "env_file": ".env", "extra": "ignore"}

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # Models
    director_model: str = "gpt-4o"
    character_model: str = "gpt-4o-mini"
    writer_model: str = "gpt-4o"
    god_model: str = ""  # V3: God Agent model (defaults to director_model if empty)

    # Database
    db_path: str = "data/novel.db"

    # Embedding
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # Web
    web_host: str = "0.0.0.0"
    web_port: int = 8000

    @property
    def db_full_path(self) -> Path:
        return Path(self.db_path)


settings = Settings()
