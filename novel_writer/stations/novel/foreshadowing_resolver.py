"""
工位：伏笔回收检测
输入：novel_id, chapter_num, chapter_content, db
输出：检查是否有活跃伏笔在本章被回收，更新数据库并返回摘要
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ..base import BaseStation
from ..llm_mixin import LLMMixin

logger = logging.getLogger(__name__)


class ForeshadowingResolver(BaseStation, LLMMixin):
    name = "foreshadowing_resolver"
    required_every_chapter = True

    def run(self, ctx: dict) -> dict:
        """
        使用 LLM 检查本章内容是否回收了任何活跃伏笔。
        如果 LLM 不可用，回退到规则检测。
        """
        novel_id = ctx["novel_id"]
        chapter_num = ctx["chapter_num"]
        chapter_content = ctx.get("chapter_content", "")
        db = ctx["db"]

        if not chapter_content:
            return {"status": "no_content", "resolved": 0, "threads": []}

        active_threads = db.get_active_foreshadowing(novel_id)
        if not active_threads:
            return {"status": "skip", "resolved": 0, "threads": [], "message": "无活跃伏笔"}

        # Trim content for LLM
        content_snippet = chapter_content[:3000]

        # Try LLM resolution
        resolved = self._llm_check(novel_id, chapter_num, content_snippet, active_threads, db)

        if resolved is None:
            # Fallback: rules-based keyword detection
            resolved = self._rules_check(novel_id, chapter_num, content_snippet, active_threads, db)

        # Update DB for each resolved thread
        for thread in resolved:
            db.resolve_foreshadowing(
                thread["id"], chapter_num, thread.get("resolved_text", "")
            )

        return {
            "status": "ok",
            "resolved": len(resolved),
            "threads": resolved,
        }

    def _llm_check(
        self,
        novel_id: str,
        chapter_num: int,
        content: str,
        active_threads: list[dict],
        db: Any,
    ) -> list[dict] | None:
        """Use LLM to check which active threads are resolved in this chapter."""
        # Build concise thread summaries
        thread_list = "\n".join(
            f"  #{t['id']} (第{t['created_chapter']}章埋下): {t['description']}"
            for t in active_threads
        )

        prompt = f"""你是小说伏笔检测员。以下是活跃伏笔列表和本章正文。判断哪些伏笔在本章被回收或显著推进。

活跃伏笔：
{thread_list}

本章正文（前3000字）：
{content}

返回严格JSON格式，不要加任何解释：
{{
  "resolved": [
    {{"id": 伏笔ID数字, "resolved_text": "本章中回收该伏笔的关键句子(20字以内)"}}
  ]
}}

如果没有任何伏笔被回收，返回 {{"resolved": []}}。
判断标准：
- "回收"意味着读者得到了明确答案，疑问被解答
- "显著推进"意味着出现了重大线索，离答案很近
- 仅仅提到相关人物或地点不算回收
"""
        try:
            result = self.call_llm_with_fallback(prompt, db, max_tokens=1024)
            if not result:
                return None

            data = self.parse_json_response(result)
            if not data:
                return None

            resolved_items = data.get("resolved", [])
            if not isinstance(resolved_items, list):
                return None

            # Validate against actual active threads
            valid_ids = {t["id"] for t in active_threads}
            valid_resolved = [
                item for item in resolved_items
                if isinstance(item, dict) and item.get("id") in valid_ids
            ]
            if valid_resolved:
                logger.info(
                    "LLM resolved %d thread(s) in ch%d: %s",
                    len(valid_resolved), chapter_num, [r["id"] for r in valid_resolved],
                )
            return valid_resolved
        except Exception as e:
            logger.warning("LLM foreshadowing check failed: %s", e)
            return None

    def _rules_check(
        self,
        novel_id: str,
        chapter_num: int,
        content: str,
        active_threads: list[dict],
        db: Any,
    ) -> list[dict]:
        """Rules-based fallback: keyword proximity detection."""
        resolved = []

        resolution_signals = [
            "原来", "真相是", "终于明白", "揭开", "揭秘", "揭露",
            "原来如此", "竟然", "难怪", "怪不得", "果然是",
            "答案", "谜底", "真相大白",
        ]

        has_resolution_signal = any(s in content for s in resolution_signals)

        for thread in active_threads:
            # Extract key nouns from description as search terms
            desc = thread.get("description", "")
            hint = thread.get("hint_text", "")

            # Score: how many resolution signals appear near the thread's keywords
            score = 0
            if has_resolution_signal:
                keywords = self._extract_keywords(desc)
                for kw in keywords[:3]:
                    if kw and kw in content:
                        kw_pos = content.find(kw)
                        for sig in resolution_signals:
                            sig_pos = content.find(sig)
                            if sig_pos >= 0 and abs(kw_pos - sig_pos) < 200:
                                score += 1
                                break

            # Also check if due_by_chapter matches
            due_by = thread.get("due_by_chapter")
            if due_by and chapter_num >= due_by:
                score += 1

            if score >= 2:
                resolved.append({
                    "id": thread["id"],
                    "resolved_text": hint[:50] if hint else desc[:50],
                })

        if resolved:
            logger.info("Rules resolved %d thread(s) in ch%d", len(resolved), chapter_num)
        return resolved

    @staticmethod
    def _extract_keywords(description: str) -> list[str]:
        """Extract meaningful keywords (Chinese 2-4 char words) from description."""
        stop_words = {"的", "了", "是", "在", "和", "也", "就", "都", "而", "及", "与",
                      "着", "或", "一个", "没有", "我们", "你们", "他们", "这个", "那个"}
        parts = re.split(r"[，。！？、；：“”‘’（）\s]+", description)
        keywords = []
        for part in parts:
            part = part.strip()
            if 2 <= len(part) <= 6 and part not in stop_words:
                keywords.append(part)
        return list(dict.fromkeys(keywords))  # dedup preserve order
