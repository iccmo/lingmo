"""
工位：视觉圣经 (VisualBible)
从小说的角色数据自动生成视觉描述，用于 AI 绘图。

输入：novel_id, db
输出：VisualCharacter 列表

核心逻辑：
  1. 从 characters 表获取角色信息
  2. 对主要角色（主角/反派/导师），用 LLM 生成视觉描述
  3. 存入 visual_characters 表
  4. 自动记录视觉基线到 CharacterConsistencyMemory（E3）
  5. 可选：通过 ComfyUI 生成角色参考图（用于 IP-Adapter 一致性）
"""

from __future__ import annotations

import logging
from typing import Any

from ...models.shot import VisualCharacter
from ..base import BaseStation
from .character_memory import CharacterConsistencyMemory
from ..llm_mixin import LLMMixin

logger = logging.getLogger(__name__)


class VisualBible(BaseStation, LLMMixin):
    """视觉圣经工位 — 为小说角色生成视觉描述"""

    name = "visual_bible"
    required_every_chapter = False

    # 只为主要角色生成视觉描述
    PRIORITY_ROLES = {"主角", "反派", "导师"}

    def run(self, ctx: dict) -> dict:
        """
        ctx: {
            novel_id: str,
            db: Database,
            force: bool,  # 是否强制重新生成已有的角色
        }
        """
        novel_id: str = ctx["novel_id"]
        db = ctx["db"]
        force: bool = ctx.get("force", False)

        novel = db.get_novel(novel_id)
        if not novel:
            return {"status": "error", "reason": "novel not found"}

        static_chars = novel.get("characters", [])
        if not static_chars:
            return {"status": "error", "reason": "no characters defined"}

        # 筛选需要生成的角色
        existing = {vc["char_key"] for vc in db.get_visual_characters(novel_id)}
        targets = [
            c for c in static_chars
            if c.get("role") in self.PRIORITY_ROLES
            and (force or c.get("name", "") not in existing)
        ]

        if not targets:
            return {
                "status": "ok",
                "reason": "all visual characters already exist",
                "characters": db.get_visual_characters(novel_id),
            }

        # 获取 LLM providers
        providers = self.get_providers(db)
        if not providers:
            return {"status": "error", "reason": "no LLM provider available"}

        # 获取角色状态补充信息
        char_states = db.get_character_state(novel_id)
        latest_state: dict[str, dict] = {}
        for cs in char_states:
            name = cs.get("char_name", "")
            if name not in latest_state or cs.get("chapter_num", 0) > latest_state[name].get("chapter_num", 0):
                latest_state[name] = cs

        results: list[dict] = []
        for char in targets:
            name = char.get("name", "")
            state = latest_state.get(name, {})
            visual = self._generate_visual(char, state, providers, db)
            if visual:
                db.save_visual_character(novel_id, name, visual.to_dict())
                results.append(visual.to_dict())

        # 自动记录视觉基线到一致性记忆（E3）
        if results:
            memory = CharacterConsistencyMemory(db, novel_id)
            for vc_data in results:
                name = vc_data.get("name", "")
                if name:
                    memory.record_visual_state(
                        chapter_num=0,  # chapter 0 = 视觉基线
                        char_key=name,
                        attributes={
                            "costume": vc_data.get("costume", ""),
                            "injury_marks": vc_data.get("injury_marks", ""),
                            "mood_expression": vc_data.get("default_expression", ""),
                        },
                    )
                    logger.info("Recorded visual baseline: %s", name)

        return {
            "status": "ok",
            "characters": results,
            "generated": len(results),
            "total": len(targets),
        }

    def _generate_visual(
        self,
        char: dict,
        state: dict,
        providers: list[dict],
        db: Any,
    ) -> VisualCharacter | None:
        """用 LLM 为单个角色生成视觉描述"""
        name = char.get("name", "")
        role = char.get("role", "")
        personality = char.get("personality", "")
        background = char.get("background", "")
        status = char.get("status", "alive")
        power_level = char.get("power_level", "")

        emotion = state.get("emotion", "")
        physical = state.get("physical_state", "")
        location = state.get("location", "")

        prompt = f"""你是一位影视美术指导。根据以下角色信息，为其设计视觉形象。

角色名：{name}
定位：{role}
性格：{personality[:80]}
背景：{background[:80]}
修炼境界：{power_level}
当前状态：{status}
当前情绪：{emotion}
身体状态：{physical}
当前位置：{location}

请为该角色设计视觉形象，严格按JSON格式输出：

```json
{{
  "appearance": "详细外貌（年龄、体型、身高、发型、面部特征、肤色，30-50字）",
  "default_expression": "日常表情描述（10-20字）",
  "signature_pose": "标志性姿态/习惯动作（10-20字）",
  "color_palette": "代表色彩，用hex色值（如：#1a1a2e, #16213e）",
  "costume": "服装描述（包含颜色、材质、风格，20-40字）",
  "injury_marks": "伤痕/胎记/特殊标记（如无则写'无'）",
  "voice_character": "声音特征（音色、语速、习惯，10-20字）"
}}
```

要求：
1. 外貌要具体、可执行——AI绘图工具能直接使用
2. 避免模糊描述（如"英俊"），用具体特征（如"高颧骨，下颌线分明"）
3. 色彩要与角色气质匹配
4. 服装要符合角色身份和故事背景"""

        for provider in providers[:2]:
            try:
                result = self.call_llm(provider, prompt, db, max_tokens=1024)
                if result:
                    vc = self._parse_visual(name, result)
                    if vc:
                        return vc
            except Exception:
                continue

        return None

    def _parse_visual(self, name: str, raw: str) -> VisualCharacter | None:
        """从 LLM 输出中解析视觉描述"""
        data = self.parse_json_response(raw)
        if not data:
            return None

        return VisualCharacter(
            name=name,
            appearance=data.get("appearance", ""),
            default_expression=data.get("default_expression", ""),
            signature_pose=data.get("signature_pose", ""),
            color_palette=data.get("color_palette", ""),
            costume=data.get("costume", ""),
            injury_marks=data.get("injury_marks", ""),
            voice_character=data.get("voice_character", ""),
        )

    def generate_character_refs(
        self,
        novel_id: str,
        db: Any,
        comfyui_config: dict | None = None,
        count_per_char: int = 1,
    ) -> dict:
        """为角色生成参考图（通过 ComfyUI）。

        为每个角色生成 1-3 张正面参考图，用于 IP-Adapter 一致性生成。

        Args:
            novel_id: 小说 ID。
            db: 数据库实例。
            comfyui_config: ComfyUI 配置（url, checkpoint 等）。
            count_per_char: 每个角色生成几张参考图。

        Returns:
            {"status": "ok", "characters": {char_key: [path, ...]}}
        """
        import os
        from pathlib import Path

        visual_chars = db.get_visual_characters(novel_id)
        if not visual_chars:
            return {"status": "error", "reason": "no visual characters found"}

        config = comfyui_config or {}
        comfyui_url = config.get("url", "http://127.0.0.1:8188")

        # 解析 host:port
        from urllib.parse import urlparse
        parsed = urlparse(comfyui_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8188

        from ..drama.comfyui_client import ComfyUIClient
        from ..drama.comfyui_workflows import build_portrait_workflow

        client = ComfyUIClient(host=host, port=port)
        if not client.health_check():
            return {"status": "error", "reason": "ComfyUI is not available"}

        results: dict[str, list[str]] = {}
        base_dir = f"data/character_refs/{novel_id}"

        for vc in visual_chars:
            char_key = vc.get("char_key", "")
            appearance = vc.get("appearance", "")
            costume = vc.get("costume", "")
            expression = vc.get("default_expression", "")

            if not appearance:
                continue

            char_dir = os.path.join(base_dir, char_key)
            Path(char_dir).mkdir(parents=True, exist_ok=True)

            paths: list[str] = []
            for i in range(count_per_char):
                output_path = os.path.join(char_dir, f"ref_{i+1:02d}.png")

                # 跳过已存在的参考图
                if Path(output_path).exists():
                    paths.append(output_path)
                    continue

                workflow = build_portrait_workflow(
                    appearance=appearance,
                    costume=costume,
                    expression=expression,
                    checkpoint=config.get("checkpoint", "sd_xl_base_1.0.safetensors"),
                    steps=int(config.get("steps", 25)),
                    cfg=float(config.get("cfg", 7.0)),
                )

                success = client.generate_image(workflow, output_path, timeout=300)
                if success and Path(output_path).exists():
                    paths.append(output_path)
                    logger.info("Character ref generated: %s → %s", char_key, output_path)
                else:
                    logger.warning("Character ref generation failed: %s #%d", char_key, i + 1)

            if paths:
                results[char_key] = paths
                # 更新 visual_characters.reference_images
                updated = dict(vc)
                updated["reference_images"] = paths
                db.save_visual_character(novel_id, char_key, updated)

        return {
            "status": "ok",
            "characters": results,
            "count": sum(len(v) for v in results.values()),
        }
