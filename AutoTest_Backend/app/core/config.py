from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AutoTest Agent"
    API_V1_PREFIX: str = "/api/v1"
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    MODEL_NAME: str = "deepseek-chat"
    SQLITE_DB_PATH: str = "data/app.db"
    VECTOR_STORE_DIR: str = "data/rag"
    KNOWLEDGE_BASE_DIR: str = "docs/knowledge"
    EXECUTIONS_DIR: str = "runs"
    EXECUTION_TIMEOUT_SECONDS: int = 60
    MAX_SELF_HEAL_ATTEMPTS: int = 1
    MAX_CONCURRENT_EXECUTIONS: int = 1
    FRONTEND_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        case_sensitive=True,
    )

    @property
    def backend_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def sqlite_db_path(self) -> Path:
        return self.backend_root / self.SQLITE_DB_PATH

    @property
    def vector_store_dir(self) -> Path:
        return self.backend_root / self.VECTOR_STORE_DIR

    @property
    def knowledge_base_dir(self) -> Path:
        return self.backend_root / self.KNOWLEDGE_BASE_DIR

    @property
    def agent_memory_dir(self) -> Path:
        return self.knowledge_base_dir / "agent_memory"

    @property
    def executions_dir(self) -> Path:
        return self.backend_root / self.EXECUTIONS_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
