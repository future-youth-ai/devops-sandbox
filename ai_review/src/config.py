"""全局配置 - 通过环境变量注入."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置, 从环境变量加载."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = Field(default="ai-review", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # LLM provider (stub, 具体 provider 按部署方决定)
    llm_api_key: SecretStr | None = Field(default=None, alias="LLM_API_KEY")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    # RAG
    chunk_size: int = Field(default=800, alias="RAG_CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, alias="RAG_CHUNK_OVERLAP")
    top_k: int = Field(default=8, alias="RAG_TOP_K")

    # 审核上限 - 防止单文档消耗过多资源
    max_doc_mb: int = Field(default=50, alias="REVIEW_MAX_DOC_MB")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """按进程缓存一次 Settings, 避免重复读 env."""
    return Settings()
