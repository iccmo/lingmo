"""
工位：AI导演 (AIDirector)
将小说章节转化为漫剧分镜脚本。

输入：novel_id, chapter_num, content, db
输出：storyboard (Shot序列 + 整体元数据)

核心逻辑：
  1. 从 Story Bible 获取角色状态、伏笔、世界观
  2. 场景分析（think-before-act，借鉴 Devin/Kiro Spec）
  3. 基于分析结果生成镜头序列
  4. 组装 Storyboard 并存入 DB
"""

from __future__ import annotations

import logging
from typing import Any

from ...models.shot import Shot, Storyboard
from ..base import BaseStation
from ..llm_mixin import LLMMixin

logger = logging.getLogger(__name__)


class AIDirector(BaseStation, LLMMixin):
    """AI导演工位 — 从章节内容生成漫剧分镜脚本"""

    name = "ai_director"
    required_every_chapter = False

    def run(self, ctx: dict) -> dict:
        """
        ctx: {
            novel_id: str,
            chapter_num: int,
            db: Database,
            content: str,         # 章节正文（可选，会从DB读取）
        }
        """
        novel_id: str = ctx["novel_id"]
        chapter_num: int = ctx["chapter_num"]
        db = ctx["db"]

        # 1. 获取章节内容
        content = ctx.get("content", "")
        if not content:
            chapter = db.get_chapter(novel_id, chapter_num)
            if not chapter:
                return {"status": "error", "reason": "chapter not found"}
            content = chapter.get("content", "")
        if not content:
            return {"status": "error", "reason": "empty content"}

        # 2. 获取角色状态上下文
        char_context = self._build_character_context(novel_id, chapter_num, db)

        # 3. 获取伏笔上下文
        foreshadowing_ctx = self._build_foreshadowing_context(novel_id, db)

        # 4. 获取视觉一致性约束
        visual_consistency = self._build_visual_consistency_block(novel_id, db)

        # 5. Think-before-act: 场景分析
        content_excerpt = content[:3000]
        analysis = self._think_scene_analysis(
            content_excerpt, char_context, foreshadowing_ctx, visual_consistency, db,
        )

        # 6. 基于分析结果生成分镜
        storyboard = self._generate_storyboard(
            novel_id, chapter_num, content_excerpt,
            char_context, foreshadowing_ctx, visual_consistency, analysis, db,
        )
        if not storyboard:
            return {"status": "error", "reason": "llm generation failed"}

        # 7. 存入 DB
        db.save_storyboard(novel_id, chapter_num, storyboard.to_dict())

        # 8. 构建决策知识（传递给下游工位）
        shot_types = [s.shot_type for s in storyboard.shots]
        knowledge: list[dict] = [
            {
                "station": self.name,
                "decision": f"生成{len(storyboard.shots)}个镜头",
                "rationale": storyboard.overall_mood,
            },
            {
                "station": self.name,
                "decision": f"节奏: {storyboard.pacing}",
                "rationale": "",
            },
            {
                "station": self.name,
                "decision": f"调色: {storyboard.color_grade}",
                "rationale": storyboard.music_theme,
            },
            {
                "station": self.name,
                "decision": f"镜头分布: {dict((t, shot_types.count(t)) for t in set(shot_types))}",
                "rationale": "",
            },
        ]

        return {
            "status": "ok",
            "storyboard": storyboard.to_dict(),
            "shots_count": len(storyboard.shots),
            "total_duration": storyboard.total_duration_sec,
            "knowledge": knowledge,
        }

    # ── 场景分析 (think-before-act) ──────────────────────────────────

    def _think_scene_analysis(
        self,
        content: str,
        char_context: str,
        foreshadowing_ctx: str,
        visual_consistency: str,
        db: Any,
    ) -> str:
        """Step 1: 场景分析 — 不生成分镜，只分析结构。

        借鉴 Devin 的 think 工具和 Kiro 的 Spec 需求分析阶段：
        先理解章节结构，再设计镜头。
        """
        providers = self.get_providers(db)
        if not providers:
            return ""

        prompt = f"""你是一位资深影视导演。请分析这个章节的结构，不要生成分镜。

【章节内容】
{content}

【角色信息】
{char_context}

{f"【伏笔】{foreshadowing_ctx}" if foreshadowing_ctx else ""}
{visual_consistency}

请用简洁的中文输出以下分析：

1. **场景拆分**：列出每个场景的地点、时间、参与角色
2. **情绪弧线**：本章从什么情绪开始，到什么情绪结束，中间的转折点
3. **关键画面**：最有视觉冲击力的 2-3 个瞬间（适合做特写镜头）
4. **节奏建议**：哪里应该快（短镜头），哪里应该慢（长镜头）
5. **开场钩子**：前3秒如何抓住观众"""

        for provider in providers[:1]:
            try:
                result = self.call_llm(provider, prompt, db, max_tokens=1024)
                if result:
                    return result
            except Exception:
                continue
        return ""

    # ── 视觉一致性约束 ──────────────────────────────────────────────

    def _build_visual_consistency_block(self, novel_id: str, db: Any) -> str:
        """构建视觉一致性约束（从 visual_characters 读取）。

        借鉴 Windsurf Memory 的 "proactively inject context" 策略：
        自动将角色视觉描述注入到导演 prompt 中，确保分镜遵守视觉设定。
        """
        visual_chars = db.get_visual_characters(novel_id)
        if not visual_chars:
            return ""

        lines = ["【视觉一致性约束 — 角色外观必须遵守以下描述】"]
        for vc in visual_chars:
            name = vc.get("char_key", "")
            appearance = vc.get("appearance", "")
            costume = vc.get("costume", "")
            expression = vc.get("default_expression", "")
            if name and appearance:
                line = f"- {name}: {appearance}"
                if costume:
                    line += f"，{costume}"
                if expression:
                    line += f"（默认表情：{expression}）"
                lines.append(line)
        return "\n".join(lines) if len(lines) > 1 else ""

    # ── 角色上下文 ──────────────────────────────────────────────────

    def _build_character_context(self, novel_id: str, chapter_num: int, db: Any) -> str:
        """构建角色上下文摘要"""
        chars = db.get_character_state(novel_id, chapter_num)
        if not chars:
            chars = db.get_character_state(novel_id)

        lines: list[str] = []
        for c in chars[:8]:  # 最多8个角色
            name = c.get("char_name", "")
            emotion = c.get("emotion", "")
            location = c.get("location", "")
            state = c.get("physical_state", "")
            line = f"- {name}"
            if emotion:
                line += f"（情绪：{emotion}）"
            if location:
                line += f"，在{location}"
            if state:
                line += f"，状态：{state}"
            lines.append(line)

        # 也加上静态角色信息
        novel = db.get_novel(novel_id) or {}
        static_chars = novel.get("characters", [])
        for sc in static_chars:
            name = sc.get("name", "")
            if name and not any(name in line for line in lines):
                lines.append(f"- {name}（{sc.get('role', '')}）：{sc.get('personality', '')[:30]}")

        return "\n".join(lines) if lines else "无角色信息"

    def _build_foreshadowing_context(self, novel_id: str, db: Any) -> str:
        """构建伏笔上下文"""
        fs = db.get_active_foreshadowing(novel_id)
        if not fs:
            return ""
        lines = []
        for f in fs[:5]:
            desc = f.get("description", "")[:40]
            lines.append(f"- 伏笔：{desc}")
        return "\n".join(lines)

    # ── 分镜生成 (基于分析结果) ──────────────────────────────────────

    def _generate_storyboard(
        self,
        novel_id: str,
        chapter_num: int,
        content: str,
        char_context: str,
        foreshadowing_ctx: str,
        visual_consistency: str,
        analysis: str,
        db: Any,
    ) -> Storyboard | None:
        """Step 2: 基于场景分析结果生成分镜脚本。

        增强 prompt 包含：
        - 场景分析结果（from step 1）
        - 视觉一致性约束（from visual_characters）
        - EARS 风格镜头需求
        """
        providers = self.get_providers(db)
        if not providers:
            return None

        # 构建增强 prompt
        analysis_block = ""
        if analysis:
            analysis_block = f"""
【场景分析（前置思考）】
{analysis}

请基于以上分析设计分镜。"""

        prompt = f"""你是一位专业的影视导演，擅长漫剧（竖屏短剧）分镜设计。

请根据以下小说章节内容，生成漫剧分镜脚本。

【章节内容】
{content}

【角色信息】
{char_context}

【伏笔】{foreshadowing_ctx if foreshadowing_ctx else "无"}

{visual_consistency}

{analysis_block}

请严格按以下JSON格式输出分镜脚本，不要输出任何其他内容：

```json
{{
  "title": "章节标题",
  "overall_mood": "本章整体情绪基调（如：压抑、温暖、紧张）",
  "pacing": "节奏类型（slow-burn/building/climax/release）",
  "color_grade": "调色方向（如：冷蓝调、暖黄调、高对比黑白）",
  "music_theme": "配乐主题描述",
  "shots": [
    {{
      "shot_id": "s01",
      "shot_type": "wide/medium/close-up/extreme-wide",
      "camera_angle": "eye-level/low/high/dutch/overhead",
      "camera_move": "static/slow_zoom/pan/tracking/handheld",
      "subject": "主体描述（中文）",
      "background": "背景环境描述",
      "lighting": "光线描述",
      "emotion": "此刻情绪",
      "dialogue": "对白（如有，无则空字符串）",
      "subtext": "潜台词（角色真正想说的）",
      "duration_sec": 3.0,
      "sfx": ["音效1", "音效2"],
      "music_cue": "配乐指示",
      "transition": "cut/dissolve/fade/flash"
    }}
  ]
}}
```

要求：
1. 生成 6-10 个镜头，总时长控制在 55-65 秒
2. 开头必须是钩子（3秒内抓住注意力）
3. 结尾必须有悬念（诱导看下一集）
4. 漫剧用静态图+动效，不是电影——描述要适合AI绘图生成静态画面
5. 对白简短有力，每句不超过20字
6. subject 用中文描述，方便后续角色匹配
7. 角色外观必须严格遵守【视觉一致性约束】中的描述
8. 关键情绪转折点使用 close-up 或 extreme-close-up 镜头"""

        for provider in providers[:3]:
            try:
                result = self.call_llm(provider, prompt, db, max_tokens=4096)
                if result:
                    storyboard = self._parse_storyboard(chapter_num, result)
                    if storyboard and storyboard.shots:
                        return storyboard
            except Exception:
                continue

        return None

    def _parse_storyboard(self, chapter_num: int, raw: str) -> Storyboard | None:
        """从 LLM 输出中解析 JSON 分镜脚本"""
        data = self.parse_json_response(raw)
        if not data:
            return None

        shots: list[Shot] = []
        for i, s in enumerate(data.get("shots", [])):
            shot = Shot(
                shot_id=s.get("shot_id", f"s{i+1:02d}"),
                shot_type=s.get("shot_type", "medium"),
                camera_angle=s.get("camera_angle", "eye-level"),
                camera_move=s.get("camera_move", "static"),
                subject=s.get("subject", ""),
                background=s.get("background", ""),
                lighting=s.get("lighting", ""),
                emotion=s.get("emotion", ""),
                dialogue=s.get("dialogue", ""),
                subtext=s.get("subtext", ""),
                duration_sec=float(s.get("duration_sec", 3.0)),
                sfx=s.get("sfx", []),
                music_cue=s.get("music_cue", ""),
                transition=s.get("transition", "cut"),
            )
            shots.append(shot)

        total_duration = sum(s.duration_sec for s in shots)

        return Storyboard(
            chapter_num=chapter_num,
            title=data.get("title", ""),
            total_duration_sec=total_duration,
            shots=shots,
            overall_mood=data.get("overall_mood", ""),
            pacing=data.get("pacing", "building"),
            color_grade=data.get("color_grade", ""),
            music_theme=data.get("music_theme", ""),
        )
