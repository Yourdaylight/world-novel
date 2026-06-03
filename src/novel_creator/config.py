"""Application configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "NOVEL_", "env_file": ".env", "extra": "ignore"}

    # LLM Provider — supports: "openai", "openrouter", or custom base_url
    llm_provider: str = ""  # empty = legacy mode (uses openai_base_url directly)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # OpenRouter (when llm_provider="openrouter", these override defaults)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

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

    # Qdrant (optional)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    qdrant_enabled: bool = False

    # Neo4j (optional)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_enabled: bool = False

    # Authentication & Quota
    jwt_secret: str = "worldengine-dev-secret-change-in-production"
    admin_code_prefix: str = "admin"

    # Memory Decay (MemoryOS)
    memory_decay_factor: float = 0.92
    memory_access_bonus: float = 0.15
    memory_trauma_floor: float = 0.6
    memory_cold_threshold: float = 0.1
    memory_consolidate_count: int = 20

    @property
    def db_full_path(self) -> Path:
        return Path(self.db_path)

    @property
    def resolved_api_key(self) -> str:
        """Resolve API key based on active provider."""
        if self.llm_provider == "openrouter":
            return self.openrouter_api_key or self.openai_api_key
        return self.openai_api_key

    @property
    def resolved_base_url(self) -> str:
        """Resolve base URL based on active provider."""
        if self.llm_provider == "openrouter":
            return self.openrouter_base_url
        return self.openai_base_url


settings = Settings()
