"""Pydantic Settings — 环境变量驱动配置，带验证。"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置。所有值可通过环境变量覆盖（大写，如 LLM_MODEL=gpt-4o）。"""

    # ── LLM ──
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-pro"
    llm_temperature: float = 0.85
    llm_max_tokens_per_chapter: int = 4096
    llm_timeout: int = 300  # seconds

    # ── Story defaults ──
    default_genre: str = "玄幻"
    default_words_per_chapter: int = 2500
    default_chapters_per_day: int = 1

    # ── Platform ──
    platform: str = "fanqie"

    # ── Paths ──
    data_dir: str = str(Path(__file__).parent.parent / "data")
    db_path: str = ""  # Computed after data_dir

    # ── Server ──
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # ── Daily schedule ──
    daily_run_time: str = "09:00"

    model_config = {
        "env_prefix": "LINGMO_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.db_path:
            self.db_path = str(Path(self.data_dir) / "novel_writer.db")


# Singleton
settings = Settings()


# ── Backward compat: Config-like access for legacy code ──

from dataclasses import dataclass, field


@dataclass
class Config:
    """Compatibility shim — mirrors old Config interface using Pydantic settings."""
    openai_api_key: str = field(default_factory=lambda: settings.llm_api_key)
    openai_base_url: str = field(default_factory=lambda: settings.llm_base_url)
    model: str = field(default_factory=lambda: settings.llm_model)
    temperature: float = field(default_factory=lambda: settings.llm_temperature)
    max_tokens_per_chapter: int = field(default_factory=lambda: settings.llm_max_tokens_per_chapter)
    genre: str = field(default_factory=lambda: settings.default_genre)
    target_words_per_chapter: int = field(default_factory=lambda: settings.default_words_per_chapter)
    chapters_per_day: int = field(default_factory=lambda: settings.default_chapters_per_day)
    platform: str = field(default_factory=lambda: settings.platform)
    data_dir: str = field(default_factory=lambda: settings.data_dir)
    novels_dir: str = field(default_factory=lambda: str(Path(settings.data_dir) / "novels"))
    fanqie_author_url: str = "https://mp.toutiao.com"
    auth_state_dir: str = field(default_factory=lambda: str(Path(settings.data_dir) / "auth"))
    daily_run_time: str = field(default_factory=lambda: settings.daily_run_time)
