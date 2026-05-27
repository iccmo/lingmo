"""
工位：配音引擎 (VoiceEngine)
为分镜脚本中的对白生成 TTS 配音音频。

输入：novel_id, chapter_num, db, output_dir
输出：每个镜头的配音音频文件路径列表

核心逻辑：
  1. 从 storyboards 表读取分镜
  2. 从 character_voices 表读取角色音色配置
  3. 为每个有 dialogue 的 shot 用 edge-tts 生成音频
  4. 可选：为无 dialogue 的 shot 生成旁白
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from pathlib import Path

from ..base import BaseStation

logger = logging.getLogger(__name__)


class VoiceEngine(BaseStation):
    """配音引擎 — 使用 edge-tts 为对白生成语音"""

    name = "voice_engine"
    required_every_chapter = False

    # 角色音色分类 → edge-tts voice ID
    DEFAULT_VOICES: dict[str, str] = {
        "male_young": "zh-CN-YunxiNeural",
        "male_mature": "zh-CN-YunjianNeural",
        "female_young": "zh-CN-XiaoxiaoNeural",
        "female_mature": "zh-CN-XiaoyiNeural",
        "narrator": "zh-CN-YunxiNeural",
    }

    # 角色名 → 音色分类（默认映射，可被 DB 配置覆盖）
    CHAR_VOICE_HINTS: dict[str, str] = {
        "顾栖岩": "male_young",
        "阿照": "female_young",
    }

    def run(self, ctx: dict) -> dict:
        """
        ctx: {
            novel_id: str,
            chapter_num: int,
            db: Database,
            output_dir: str,  # 音频输出目录
            with_narration: bool,  # 是否为无对白镜头生成旁白（默认 False）
        }
        """
        novel_id: str = ctx["novel_id"]
        chapter_num: int = ctx["chapter_num"]
        db = ctx["db"]
        output_dir: str = ctx.get("output_dir", f"data/voice/{novel_id}/ch{chapter_num:03d}")
        with_narration: bool = ctx.get("with_narration", False)

        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 1. 获取分镜
        sb_data = db.get_storyboard(novel_id, chapter_num)
        if not sb_data or not sb_data.get("shots"):
            return {"status": "error", "reason": "no storyboard found"}

        # 2. 获取角色音色配置
        voice_map = self._build_voice_map(novel_id, db)

        # 3. 为每个 shot 生成音频
        audio_files: list[dict] = []
        loop = asyncio.new_event_loop()

        for shot in sb_data["shots"]:
            shot_id = shot.get("shot_id", "")
            dialogue = shot.get("dialogue", "").strip()
            subject = shot.get("subject", "")

            # 确定要朗读的文本
            text = dialogue
            char_name = ""
            if not text and with_narration:
                text = subject  # 用主体描述作为旁白
                char_name = "narrator"

            if not text:
                continue

            # 确定音色
            if not char_name:
                char_name = self._detect_speaker(dialogue, shot.get("subject", ""), voice_map)
            voice_id, rate_str, pitch = self._get_voice_params(char_name, voice_map)

            # 输出文件
            filename = f"{shot_id}.mp3"
            output_path = os.path.join(output_dir, filename)

            # 生成 TTS
            try:
                loop.run_until_complete(
                    self._tts(text, voice_id, output_path, rate_str, pitch)
                )
                # 获取实际音频时长
                duration = self._get_audio_duration(output_path)
                audio_files.append({
                    "shot_id": shot_id,
                    "audio_path": output_path,
                    "duration_sec": duration,
                    "text": text,
                    "char_name": char_name,
                    "voice_id": voice_id,
                })
                logger.info("Voice generated: %s (%.1fs) → %s", shot_id, duration, output_path)
            except Exception as e:
                logger.error("Voice generation failed for %s: %s", shot_id, e)
                audio_files.append({
                    "shot_id": shot_id,
                    "audio_path": "",
                    "duration_sec": 0.0,
                    "text": text,
                    "char_name": char_name,
                    "error": str(e)[:200],
                })

        loop.close()

        total_duration = sum(a["duration_sec"] for a in audio_files)

        return {
            "status": "ok",
            "audio_files": audio_files,
            "count": len(audio_files),
            "total_duration": total_duration,
            "output_dir": output_dir,
        }

    def _build_voice_map(self, novel_id: str, db: Any) -> dict[str, dict]:
        """从 DB 构建角色音色映射"""
        voice_map: dict[str, dict] = {}
        try:
            rows = db.get_character_voices(novel_id)
            for row in rows:
                name = row.get("char_key", "")
                voice_map[name] = {
                    "voice_id": row.get("voice_id", ""),
                    "speed": float(row.get("speed", 1.0)),
                    "pitch": row.get("pitch", "+0Hz"),
                }
        except Exception:
            pass
        return voice_map

    def _detect_speaker(self, dialogue: str, subject: str, voice_map: dict[str, dict]) -> str:
        """从 subject 中检测说话角色名"""
        for name in voice_map:
            if name in subject:
                return name
        # 尝试常见角色名
        for name in self.CHAR_VOICE_HINTS:
            if name in subject:
                return name
        return "narrator"

    def _get_voice_params(
        self, char_name: str, voice_map: dict[str, dict]
    ) -> tuple[str, str, str]:
        """获取角色的 TTS 参数：(voice_id, rate_str, pitch)"""
        # 优先从 DB 配置获取
        if char_name in voice_map:
            cfg = voice_map[char_name]
            voice_id = cfg["voice_id"]
            speed = cfg["speed"]
            pitch = cfg["pitch"]
            if voice_id:
                rate = int((speed - 1.0) * 100)
                rate_str = f"+{rate}%" if rate >= 0 else f"{rate}%"
                return voice_id, rate_str, pitch

        # 从默认映射获取
        hint = self.CHAR_VOICE_HINTS.get(char_name, "narrator")
        voice_id = self.DEFAULT_VOICES.get(hint, self.DEFAULT_VOICES["narrator"])
        return voice_id, "+0%", "+0Hz"

    @staticmethod
    async def _tts(text: str, voice: str, output_path: str, rate: str, pitch: str) -> None:
        """调用 edge-tts 生成语音"""
        import edge_tts

        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)

    @staticmethod
    def _get_audio_duration(path: str) -> float:
        """用 ffprobe 获取音频时长"""
        import subprocess

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                capture_output=True, text=True, timeout=10,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0
