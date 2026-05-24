"""配置中心 — 从环境变量读取所有敏感信息"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # --- LLM ---
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", ""))
    model: str = "deepseek-v4-pro"                # 小说生成推荐 deepseek-v4-pro / deepseek-v4-flash
    temperature: float = 0.85             # 创作需要一定随机性
    max_tokens_per_chapter: int = 4096    # 每章约 2000-3000 字

    # --- 故事配置 ---
    genre: str = "玄幻"
    target_words_per_chapter: int = 2500  # 每章目标字数
    chapters_per_day: int = 1             # 每天生成几章

    # --- 发布平台 ---
    platform: str = "fanqie"              # fanqie / feilu / qidian
    # 番茄小说作者后台
    fanqie_author_url: str = "https://mp.toutiao.com"
    # 登录态保存路径（cookie 持久化）
    auth_state_dir: str = field(default_factory=lambda: str(
        Path(__file__).parent.parent / "data" / "auth"
    ))

    # --- 数据路径 ---
    data_dir: str = field(default_factory=lambda: str(
        Path(__file__).parent.parent / "data"
    ))
    novels_dir: str = field(default_factory=lambda: str(
        Path(__file__).parent.parent / "data" / "novels"
    ))

    # --- 调度 ---
    daily_run_time: str = "09:00"         # 每天几点运行


config = Config()


def validate() -> list[str]:
    """检查必要配置是否齐全，返回缺失项列表"""
    missing = []
    if not config.openai_api_key:
        missing.append("OPENAI_API_KEY")
    return missing
