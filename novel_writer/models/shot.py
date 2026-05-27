"""AI影视制片厂 — 镜头/分镜/角色视觉 数据模型

用于 AI Director → Prompt Generator → 画面生成 的完整管线。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VisualCharacter:
    """角色视觉描述 — 从故事圣经自动推导，用于 AI 绘图"""
    name: str
    appearance: str = ""           # "30岁男性，瘦削，黑色短发略长"
    default_expression: str = ""   # "眉头微蹙，嘴唇紧抿"
    signature_pose: str = ""       # "右手插兜，微微驼背"
    color_palette: str = ""        # "#1a1a2e, #16213e"
    costume: str = ""              # "灰色卫衣，黑色工装裤"
    injury_marks: str = ""         # "左臂缠绷带（第15章受伤）"
    voice_character: str = ""      # "低沉，语速慢，每句不超过15字"
    reference_images: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "appearance": self.appearance,
            "default_expression": self.default_expression,
            "signature_pose": self.signature_pose,
            "color_palette": self.color_palette,
            "costume": self.costume,
            "injury_marks": self.injury_marks,
            "voice_character": self.voice_character,
            "reference_images": self.reference_images,
        }

    @classmethod
    def from_dict(cls, d: dict) -> VisualCharacter:
        return cls(
            name=d["name"],
            appearance=d.get("appearance", ""),
            default_expression=d.get("default_expression", ""),
            signature_pose=d.get("signature_pose", ""),
            color_palette=d.get("color_palette", ""),
            costume=d.get("costume", ""),
            injury_marks=d.get("injury_marks", ""),
            voice_character=d.get("voice_character", ""),
            reference_images=d.get("reference_images", []),
        )


@dataclass
class Shot:
    """单个镜头"""
    shot_id: str
    shot_type: str = "medium"          # close-up / medium / wide / extreme-wide
    camera_angle: str = "eye-level"    # eye-level / low / high / dutch / overhead
    camera_move: str = "static"        # static / slow_zoom / pan / tracking / handheld
    subject: str = ""                   # 主体描述
    background: str = ""               # 背景描述
    lighting: str = ""                 # "暖色台灯，窗外冷蓝月光"
    emotion: str = ""                  # "压抑→爆发前的平静"
    character_state: dict = field(default_factory=dict)
    dialogue: str = ""                 # 对白（如有）
    subtext: str = ""                  # 潜台词
    duration_sec: float = 3.0          # 时长
    sfx: list[str] = field(default_factory=list)
    music_cue: str = ""                # 配乐指示
    transition: str = "cut"            # 转场方式

    def to_dict(self) -> dict:
        return {
            "shot_id": self.shot_id,
            "shot_type": self.shot_type,
            "camera_angle": self.camera_angle,
            "camera_move": self.camera_move,
            "subject": self.subject,
            "background": self.background,
            "lighting": self.lighting,
            "emotion": self.emotion,
            "character_state": self.character_state,
            "dialogue": self.dialogue,
            "subtext": self.subtext,
            "duration_sec": self.duration_sec,
            "sfx": self.sfx,
            "music_cue": self.music_cue,
            "transition": self.transition,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Shot:
        return cls(
            shot_id=d["shot_id"],
            shot_type=d.get("shot_type", "medium"),
            camera_angle=d.get("camera_angle", "eye-level"),
            camera_move=d.get("camera_move", "static"),
            subject=d.get("subject", ""),
            background=d.get("background", ""),
            lighting=d.get("lighting", ""),
            emotion=d.get("emotion", ""),
            character_state=d.get("character_state", {}),
            dialogue=d.get("dialogue", ""),
            subtext=d.get("subtext", ""),
            duration_sec=d.get("duration_sec", 3.0),
            sfx=d.get("sfx", []),
            music_cue=d.get("music_cue", ""),
            transition=d.get("transition", "cut"),
        )


@dataclass
class Storyboard:
    """一章的完整分镜"""
    chapter_num: int
    title: str = ""
    total_duration_sec: float = 60.0
    shots: list[Shot] = field(default_factory=list)
    overall_mood: str = ""             # 本章整体情绪基调
    pacing: str = "building"           # slow-burn / building / climax / release
    color_grade: str = ""              # 整体调色方向
    music_theme: str = ""              # 本章主旋律描述

    def to_dict(self) -> dict:
        return {
            "chapter_num": self.chapter_num,
            "title": self.title,
            "total_duration_sec": self.total_duration_sec,
            "shots": [s.to_dict() for s in self.shots],
            "overall_mood": self.overall_mood,
            "pacing": self.pacing,
            "color_grade": self.color_grade,
            "music_theme": self.music_theme,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Storyboard:
        return cls(
            chapter_num=d["chapter_num"],
            title=d.get("title", ""),
            total_duration_sec=d.get("total_duration_sec", 60.0),
            shots=[Shot.from_dict(s) for s in d.get("shots", [])],
            overall_mood=d.get("overall_mood", ""),
            pacing=d.get("pacing", "building"),
            color_grade=d.get("color_grade", ""),
            music_theme=d.get("music_theme", ""),
        )
