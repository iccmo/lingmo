"""
工位：技法顾问 (TechniqueAdvisor)
不是技法库，是判断力。

输入：场景上下文（大纲、上章钩子、类型、约束）
输出：简短技法指导（50-100字中文）

核心理念：
  不枚举技法令牌，而是让 AI 像编辑一样看场景本质——
  这段戏需要什么？冷一点还是热一点？快一点还是慢一点？
  然后给出一个具体的写作指令。
"""
from typing import Any


class TechniqueAdvisor:
    name = "technique_advisor"
    required_every_chapter = True

    def run(self, ctx: dict) -> dict:
        """
        ctx: {
            novel_id, chapter_num, db,
            outline: list[dict],        # upcoming chapter outlines
            prev_hook: str,             # previous chapter ending hook
            genre: str,                 # 悬疑/言情/官场/...
            style_profile: dict | None, # optional style profile
            constraints: str,           # hard constraints for this chapter
        }
        """
        # Build a compact scene description for the LLM to analyze
        scene_desc = self._build_scene_desc(ctx)
        if not scene_desc:
            return {"status": "skipped", "guidance": "", "reason": "no context"}

        # LLM analysis: what does this scene need?
        guidance = self._analyze_scene(ctx, scene_desc)
        if not guidance:
            return {"status": "skipped", "guidance": "", "reason": "llm failed"}

        return {
            "status": "ok",
            "guidance": guidance,
            "scene_type": self._classify_scene(ctx),
        }

    def _build_scene_desc(self, ctx: dict) -> str:
        parts: list[str] = []

        genre = ctx.get("genre", "")
        if genre:
            parts.append(f"类型：{genre}")

        prev_hook = ctx.get("prev_hook", "")
        if prev_hook:
            parts.append(f"上章结尾：{prev_hook[:200]}")

        outline = ctx.get("outline", [])
        if outline:
            next_ch = outline[0] if outline else {}
            title = next_ch.get("title", "")
            summary = next_ch.get("summary", "")
            if title or summary:
                parts.append(f"本章大纲：{title} — {summary[:150]}")

        constraints = ctx.get("constraints", "")
        if constraints:
            # Just note that constraints exist, not the full text
            parts.append("有硬约束需遵守")

        return "\n".join(parts) if parts else ""

    def _analyze_scene(self, ctx: dict, scene_desc: str) -> str:
        """Ask LLM: what does this scene need, in literary terms?
        Tries all enabled providers in priority order."""
        db = ctx.get("db")
        if not db:
            return ""

        try:
            from ..config import Config
            from ..generator import Generator

            providers = _get_all_providers(db)
            if not providers:
                return ""

            prompt = f"""你是一位资深文学编辑。分析以下小说场景，给出一个具体的写作指导。

{scene_desc}

不要泛泛而谈。不要列举技法名称。直接给出一个可操作的写作指令，50-100字。
像编辑对作者说话那样——具体、直接、只有一个重点。

例如（仅供参考，不要照抄）：
- "这段用动作推情绪。砍掉所有心理描写，只写他做了什么。让读者从行为里读心。"
- "物件先行。不写她难过，写她反复擦那只杯子。写杯沿的裂口。情绪全在物上。"
- "冷处理。这段揭露很重要但克制写。不多解释，不铺垫。像新闻一样陈述事实。震撼来自信息本身。"

只输出指令，不要解释为什么。"""

            # Try each provider until one works
            for provider in providers[:3]:  # max 3 attempts
                try:
                    models = provider.get("models", ["gpt-4o"])
                    model = models[0]  # Use primary model (v4-flash returns empty)
                    cfg = Config(
                        openai_api_key=provider.get("api_key", ""),
                        openai_base_url=provider.get("base_url", ""),
                        model=model,
                    )
                    gen = Generator(cfg)
                    result = gen._call_llm_with_retry(
                        [{"role": "user", "content": prompt}],
                        max_tokens=512,  # Higher for v4 reasoning overhead
                    )
                    if result and len(result.strip()) > 5:
                        lines = [l.strip().strip('"').strip("'").strip("。")
                                for l in result.strip().split("\n") if l.strip()]
                        guidance = "。".join(lines[:2])
                        if len(guidance) > 10:
                            return guidance[:150]
                except Exception:
                    continue
        except Exception:
            pass

        return ""

    def _classify_scene(self, ctx: dict) -> str:
        """Quick heuristic classification for logging."""
        outline = ctx.get("outline", [])
        if not outline:
            return "unknown"
        summary = outline[0].get("summary", "") if outline else ""
        prev_hook = ctx.get("prev_hook", "")

        combined = summary + prev_hook
        if any(w in combined for w in ["对峙", "战斗", "追杀", "逃", "冲突", "枪"]):
            return "conflict"
        if any(w in combined for w in ["回忆", "过去", "往事", "记忆", "梦"]):
            return "reflection"
        if any(w in combined for w in ["揭示", "真相", "发现", "秘密", "揭开"]):
            return "revelation"
        if any(w in combined for w in ["对话", "谈话", "说", "问"]):
            return "dialogue"
        if any(w in combined for w in ["场景", "环境", "氛围", "房间", "城市"]):
            return "atmosphere"
        return "narrative"


def _get_all_providers(db) -> list[dict]:
    """Get all enabled providers with API keys, sorted by priority (highest first)."""
    try:
        providers = db.list_providers()
        enabled = [p for p in providers if p.get("is_enabled") and p.get("api_key")]
        enabled.sort(key=lambda p: p.get("priority", 0), reverse=True)
        return enabled
    except Exception:
        return []
