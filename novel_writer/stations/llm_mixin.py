"""
LLMMixin — 共享 LLM 调用逻辑，给需要 LLM 的 Station 复用。

消除 ai_director、visual_bible、foreshadowing_resolver 中重复的
_get_providers / _call_llm / _parse_json 代码。
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..database import Database

logger = logging.getLogger(__name__)


class LLMMixin:
    """给需要 LLM 的 Station 提供统一调用接口。"""

    def call_llm(
        self,
        provider: dict,
        prompt: str,
        db: Database,
        max_tokens: int = 4096,
        system_prompt: str = "",
    ) -> str | None:
        """调用单个 provider 的 LLM。

        Args:
            provider: provider 字典（来自 list_providers()）。
            prompt: 用户消息。
            db: 数据库实例。
            max_tokens: 最大输出 token 数。
            system_prompt: 可选系统消息。

        Returns:
            LLM 输出文本，失败返回 None。
        """
        from ..config import Config
        from ..generator import Generator

        models = provider.get("models", [])
        if not models:
            return None

        full_provider = db.get_provider(provider["id"])
        if not full_provider:
            return None

        cfg = Config(
            openai_api_key=full_provider.get("api_key", ""),
            openai_base_url=full_provider.get("base_url", ""),
            model=models[0],
        )
        gen = Generator(cfg)

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            return gen._call_llm_with_retry(messages, max_tokens=max_tokens)
        except Exception as e:
            logger.warning("LLM call failed (provider=%s): %s", provider.get("id", "?"), e)
            return None

    def call_llm_with_fallback(
        self,
        prompt: str,
        db: Database,
        max_tokens: int = 4096,
        system_prompt: str = "",
        max_providers: int = 3,
    ) -> str | None:
        """按优先级依次尝试多个 provider，返回第一个成功的结果。

        Args:
            prompt: 用户消息。
            db: 数据库实例。
            max_tokens: 最大输出 token 数。
            system_prompt: 可选系统消息。
            max_providers: 最多尝试几个 provider。

        Returns:
            LLM 输出文本，全部失败返回 None。
        """
        from .base import BaseStation
        providers = BaseStation.get_providers(db)
        for provider in providers[:max_providers]:
            result = self.call_llm(provider, prompt, db, max_tokens, system_prompt)
            if result:
                return result
        return None

    async def call_llm_async(
        self,
        provider: dict,
        prompt: str,
        db: Database,
        max_tokens: int = 4096,
        system_prompt: str = "",
    ) -> str | None:
        """异步调用单个 provider 的 LLM（使用 aiohttp）。"""
        import aiohttp

        full_provider = db.get_provider(provider["id"])
        if not full_provider:
            return None

        models = provider.get("models", [])
        if not models:
            return None

        url = f"{full_provider['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {full_provider['api_key']}",
            "Content-Type": "application/json",
        }

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": models[0],
            "messages": messages,
            "max_tokens": max_tokens,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning("LLM async HTTP %d: %s", resp.status, body[:200])
                        return None
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning("LLM async call failed (provider=%s): %s", provider.get("id", "?"), e)
            return None

    async def call_llm_with_fallback_async(
        self,
        prompt: str,
        db: Database,
        max_tokens: int = 4096,
        system_prompt: str = "",
        max_providers: int = 3,
    ) -> str | None:
        """异步按优先级依次尝试多个 provider。"""
        from .base import BaseStation
        providers = BaseStation.get_providers(db)
        for provider in providers[:max_providers]:
            result = await self.call_llm_async(provider, prompt, db, max_tokens, system_prompt)
            if result:
                return result
        return None

    @staticmethod
    def parse_json_response(raw: str) -> dict | None:
        """从 LLM 输出中提取并解析 JSON。

        支持 ```json ... ``` 代码块和裸 JSON 对象。

        Returns:
            解析后的 dict，失败返回 None。
        """
        # 优先尝试 ```json 代码块
        json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试裸 JSON 对象
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                return None

        # 清理 trailing commas
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
