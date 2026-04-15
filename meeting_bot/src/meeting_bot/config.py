"""应用配置 - pydantic-settings 从环境变量加载。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """所有运行时配置集中在这里, 方便测试注入。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 飞书自建应用 ----------
    feishu_app_id: str = Field(..., description="飞书自建应用 App ID")
    feishu_app_secret: SecretStr = Field(..., description="飞书自建应用 App Secret")

    # ---------- 事件订阅 ----------
    feishu_event_encrypt_key: SecretStr = Field(..., description="事件订阅加密 Key (AES-256)")
    feishu_event_verification_token: SecretStr | None = Field(
        default=None, description="旧版 Verification Token (V2 可留空)"
    )

    # ---------- 飞书资源 ----------
    feishu_bitable_app_token: str = Field(..., description="Bitable 应用 token")
    feishu_bitable_table_id: str = Field(..., description="Bitable 会议索引表 ID")
    feishu_doc_template_token: str = Field(..., description="会议纪要模板文档 token")
    feishu_summary_chat_id: str = Field(..., description="飞书群聊 chat_id")

    # ---------- SMTP ----------
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from_address: str = "Meeting Bot <bot@example.com>"
    smtp_use_tls: bool = True

    # ---------- 服务 ----------
    app_base_url: str = "http://localhost:8000"
    app_log_level: str = "INFO"
    app_sqlite_path: Path = Path("./data/dedup.sqlite")
    app_workers: int = 2


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内缓存, 避免反复读 .env。"""
    return Settings()
