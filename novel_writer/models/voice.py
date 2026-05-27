"""AI影视制片厂 — 配音/音轨 数据模型

用于 Voice Engine → Compositor 的多媒体管线。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CharacterVoice:
    """角色音色配置 — 从角色性格自动推导或手动配置"""
    name: str                  # 角色名
    voice_id: str = ""         # TTS 音色 ID（edge-tts: zh-CN-YunxiNeural）
    speed: float = 1.0         # 语速 0.8-1.2
    pitch: str = "+0Hz"        # 音调偏移
    emotion_default: str = "calm"  # 默认情绪

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "voice_id": self.voice_id,
            "speed": self.speed,
            "pitch": self.pitch,
            "emotion_default": self.emotion_default,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CharacterVoice:
        return cls(
            name=d["name"],
            voice_id=d.get("voice_id", ""),
            speed=float(d.get("speed", 1.0)),
            pitch=d.get("pitch", "+0Hz"),
            emotion_default=d.get("emotion_default", "calm"),
        )


@dataclass
class AudioTrack:
    """单条配音音轨 — 对应一个镜头的对白/旁白"""
    shot_id: str
    audio_path: str = ""       # 音频文件路径
    duration_sec: float = 0.0  # 音频实际时长
    text: str = ""             # 原始文本
    char_name: str = ""        # 角色名（空 = 旁白）

    def to_dict(self) -> dict:
        return {
            "shot_id": self.shot_id,
            "audio_path": self.audio_path,
            "duration_sec": self.duration_sec,
            "text": self.text,
            "char_name": self.char_name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AudioTrack:
        return cls(
            shot_id=d["shot_id"],
            audio_path=d.get("audio_path", ""),
            duration_sec=float(d.get("duration_sec", 0.0)),
            text=d.get("text", ""),
            char_name=d.get("char_name", ""),
        )
