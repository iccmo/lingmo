"""
工位：Prompt生成器 (PromptGenerator)
将分镜脚本中的镜头描述转化为 AI 绘图工具可消费的英文 Prompt。

输入：novel_id, chapter_num, db, knowledge（可选，来自上游工位）
输出：每个镜头的 {prompt, negative_prompt, aspect_ratio, ...}

核心逻辑：纯规则，不用 LLM。
  1. 从 storyboards 表读取分镜
  2. 从 visual_characters 表读取角色视觉描述
  3. 从 knowledge（AI Director 决策）提取风格线索
  4. 从 CharacterConsistencyMemory 获取角色视觉一致性约束
  5. 每个 Shot → 组合英文 prompt
"""

from __future__ import annotations

from ...models.shot import Shot
from ..base import BaseStation
from .character_memory import CharacterConsistencyMemory


class PromptGenerator(BaseStation):
    """Prompt 生成器 — 将镜头描述转化为 AI 绘图 prompt"""

    name = "prompt_generator"
    required_every_chapter = False

    # 情绪 → 风格关键词映射
    EMOTION_STYLE: dict[str, str] = {
        "紧张": "tense atmosphere, dramatic shadows, high contrast",
        "恐惧": "horror lighting, deep shadows, desaturated, eerie",
        "悲伤": "melancholic, muted colors, soft diffused light, blue tones",
        "愤怒": "aggressive red tones, harsh lighting, intense contrast",
        "平静": "soft natural light, warm tones, gentle atmosphere",
        "孤独": "isolated subject, empty space, cold blue tones, minimal",
        "希望": "warm golden light, rising sun, bright highlights, uplifting",
        "震惊": "high contrast, frozen motion, sharp focus, dramatic",
        "压抑": "heavy atmosphere, dark muted palette, claustrophobic framing",
        "温暖": "warm amber tones, soft bokeh, intimate lighting",
        "悬疑": "noir lighting, deep shadows, single light source, mysterious",
        "爆发": "dynamic composition, motion blur, intense lighting, powerful",
    }

    # 镜头类型 → 构图关键词
    SHOT_COMPOSITION: dict[str, str] = {
        "close-up": "extreme close-up shot, shallow depth of field, face detail",
        "medium": "medium shot, waist up, balanced composition",
        "wide": "wide shot, full body visible, environmental context",
        "extreme-wide": "extreme wide shot, establishing shot, vast environment",
    }

    # 镜头角度 → 视角关键词
    ANGLE_STYLE: dict[str, str] = {
        "eye-level": "eye-level angle, natural perspective",
        "low": "low angle shot, looking up, imposing, powerful",
        "high": "high angle shot, looking down, vulnerable, small",
        "dutch": "dutch angle, tilted frame, unsettling, disoriented",
        "overhead": "overhead shot, bird's eye view, top-down",
    }

    # 运动 → 静态画面暗示
    MOVE_STYLE: dict[str, str] = {
        "static": "static composition, centered subject",
        "slow_zoom": "tight framing, focused detail, intimate",
        "pan": "wide horizontal composition, panoramic",
        "tracking": "dynamic framing, motion implied",
        "handheld": "slightly off-center, raw, documentary feel",
    }

    def run(self, ctx: dict) -> dict:
        """
        ctx: {
            novel_id: str,
            chapter_num: int,
            db: Database,
            style: str,  # 可选风格锚定（如 "cinematic", "anime"）
            knowledge: list[dict],  # 可选，上游工位决策知识
        }
        """
        novel_id: str = ctx["novel_id"]
        chapter_num: int = ctx["chapter_num"]
        db = ctx["db"]
        style_anchor: str = ctx.get("style", "cinematic, photorealistic, 4K")
        knowledge: list[dict] = ctx.get("knowledge", [])

        # 1. 从上游知识提取风格增强（E2: 知识消费）
        mood_hint = self._extract_mood_from_knowledge(knowledge)
        if mood_hint:
            self.add_knowledge(
                f"从上游获取情绪基调: {mood_hint}",
                "AI Director 决策知识",
            )

        # 2. 获取分镜
        sb_data = db.get_storyboard(novel_id, chapter_num)
        if not sb_data or not sb_data.get("shots"):
            return {"status": "error", "reason": "no storyboard found"}

        # 3. 获取视觉角色描述
        visual_chars = db.get_visual_characters(novel_id)
        vc_map: dict[str, dict] = {vc["char_key"]: vc for vc in visual_chars}

        # 4. 构建角色一致性记忆（E3）
        consistency = CharacterConsistencyMemory(db, novel_id)

        # 5. 为每个镜头生成 prompt
        prompts: list[dict] = []
        for shot_dict in sb_data["shots"]:
            shot = Shot.from_dict(shot_dict)
            prompt_data = self._build_prompt(
                shot, vc_map, style_anchor,
                mood_hint=mood_hint,
                consistency_memory=consistency,
                chapter_num=chapter_num,
            )
            prompts.append(prompt_data)

        return {
            "status": "ok",
            "prompts": prompts,
            "count": len(prompts),
            "knowledge": self.get_knowledge(),
        }

    def _build_prompt(
        self,
        shot: Shot,
        vc_map: dict[str, dict],
        style_anchor: str,
        mood_hint: str = "",
        consistency_memory: CharacterConsistencyMemory | None = None,
        chapter_num: int = 0,
    ) -> dict:
        """为单个镜头构建 AI 绘图 prompt。

        Args:
            shot: 镜头数据。
            vc_map: 视觉角色映射。
            style_anchor: 全局风格锚定。
            mood_hint: 上游知识提取的情绪风格提示（E2）。
            consistency_memory: 角色一致性记忆（E3）。
            chapter_num: 当前章节号（E3）。
        """
        parts: list[str] = []

        # 1. 角色描述（从视觉圣经获取）+ 收集参考图
        char_desc = self._resolve_character_desc(shot.subject, vc_map)
        if char_desc:
            parts.append(char_desc)

        # 1.5 收集角色参考图路径
        ref_images: list[str] = []
        for char_key, vc in vc_map.items():
            if char_key in shot.subject:
                ref_images = vc.get("reference_images", [])
                break

        # 1.6 角色一致性记忆注入（E3）
        if consistency_memory and chapter_num > 0:
            for char_key in vc_map:
                if char_key in shot.subject:
                    consistency = consistency_memory.build_consistency_prompt(
                        char_key, chapter_num,
                    )
                    if consistency:
                        parts.append(consistency)
                    break

        # 2. 主体动作/状态
        if shot.subject:
            # 去掉已解析的角色名，保留动作描述
            action = self._extract_action(shot.subject, vc_map)
            if action:
                parts.append(action)

        # 3. 背景环境
        if shot.background:
            parts.append(shot.background)

        # 4. 光线
        if shot.lighting:
            parts.append(shot.lighting)

        # 5. 镜头构图
        composition = self.SHOT_COMPOSITION.get(shot.shot_type, "")
        if composition:
            parts.append(composition)

        # 6. 角度
        angle = self.ANGLE_STYLE.get(shot.camera_angle, "")
        if angle:
            parts.append(angle)

        # 7. 运动暗示
        move = self.MOVE_STYLE.get(shot.camera_move, "")
        if move:
            parts.append(move)

        # 8. 情绪风格（优先使用上游知识的 mood，否则用镜头自带的 emotion）
        if mood_hint:
            parts.append(mood_hint)
        else:
            emotion_style = self._match_emotion(shot.emotion)
            if emotion_style:
                parts.append(emotion_style)

        # 9. 全局风格锚定
        parts.append(style_anchor)

        prompt = ", ".join(p for p in parts if p)

        return {
            "shot_id": shot.shot_id,
            "prompt": prompt,
            "negative_prompt": "cartoon, anime, bright cheerful colors, blurry, low quality, watermark, text, multiple heads, deformed hands",
            "aspect_ratio": "9:16",
            "duration_sec": shot.duration_sec,
            "camera_move": shot.camera_move,
            "dialogue": shot.dialogue,
            "transition": shot.transition,
            "reference_images": ref_images,
        }

    def _resolve_character_desc(self, subject: str, vc_map: dict[str, dict]) -> str:
        """从 subject 中匹配角色名，返回视觉描述"""
        for char_key, vc in vc_map.items():
            if char_key in subject:
                parts: list[str] = []
                if vc.get("appearance"):
                    parts.append(vc["appearance"])
                if vc.get("costume"):
                    parts.append(vc["costume"])
                if vc.get("default_expression"):
                    parts.append(vc["default_expression"])
                if vc.get("injury_marks") and vc["injury_marks"] != "无":
                    parts.append(vc["injury_marks"])
                return ", ".join(parts)
        return ""

    def _extract_action(self, subject: str, vc_map: dict[str, dict]) -> str:
        """从 subject 中提取动作描述（去掉角色名）"""
        action = subject
        for char_key in vc_map:
            action = action.replace(char_key, "").strip()
        # 清理多余标点
        action = action.strip("，,、：:。. ")
        return action

    def _match_emotion(self, emotion: str) -> str:
        """模糊匹配情绪关键词到风格描述"""
        if not emotion:
            return ""
        for key, style in self.EMOTION_STYLE.items():
            if key in emotion:
                return style
        # 默认
        return "cinematic mood, atmospheric"

    def _extract_mood_from_knowledge(self, knowledge: list[dict]) -> str:
        """从上游知识中提取情绪/调色提示（E2: 知识消费）。

        AI Director 的 knowledge 包含 "整体情绪基调" 和 "调色方向" 两个条目，
        从中提取可用的风格描述注入 prompt。
        """
        for kb in knowledge:
            decision = kb.get("decision", "")
            rationale = kb.get("rationale", "")
            # 匹配情绪基调（如 "压抑" → "heavy atmosphere"）
            if "情绪" in decision or "基调" in decision or "mood" in decision.lower():
                if rationale:
                    for key, style in self.EMOTION_STYLE.items():
                        if key in rationale:
                            return style
            # 匹配调色（如 "冷蓝调" → "cold blue tones"）
            if "调色" in decision or "color" in decision.lower():
                if rationale:
                    return f"{rationale} color grading"
        return ""
