"""
工位：合成引擎 (Compositor)
将画面、配音、配乐合成为最终视频。

输入：novel_id, chapter_num, db, image_dir, voice_dir, music_path, output_dir
输出：最终 MP4 视频文件

核心逻辑：
  1. 从 storyboards 读取分镜
  2. 为每个 shot 生成视频片段（含 Ken Burns 动效）
  3. 将配音音频分配到对应 shot
  4. 拼接所有 shot → 混合配音 + 背景音乐
  5. 添加字幕（对白 overlay）
  6. 画面后处理（色调、锐化、暗角）
  7. 输出 9:16 竖屏 MP4

E4 增强：
  - Ken Burns 动效：静态图添加缩放/平移，营造镜头运动感
  - 转场支持：cut/dissolve/fade/flash
  - 画面后处理：统一色调、锐化、暗角
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from ..base import BaseStation

logger = logging.getLogger(__name__)

# shot_type → Ken Burns zoompan 参数（E4: 动效增强）
KEN_BURNS_PARAMS: dict[str, dict] = {
    "close-up": {
        "desc": "缓慢推进（zoom in 1.0→1.15）",
        "z": "min(zoom+0.001,1.15)",
        "x": "iw/2-(iw/zoom/2)",
        "y": "ih/2-(ih/zoom/2)",
    },
    "medium": {
        "desc": "轻微左→右平移",
        "z": "1.05",
        "x": "(iw-iw/zoom)*on/{frames}",
        "y": "ih/2-(ih/zoom/2)",
    },
    "wide": {
        "desc": "缓慢拉远（zoom out 1.1→1.0）",
        "z": "if(eq(on,1),1.1,max(zoom-0.001,1.0))",
        "x": "iw/2-(iw/zoom/2)",
        "y": "ih/2-(ih/zoom/2)",
    },
    "extreme-wide": {
        "desc": "缓慢上移（tilt up）",
        "z": "1.05",
        "x": "iw/2-(iw/zoom/2)",
        "y": "(ih-ih/zoom)*on/{frames}",
    },
}

# camera_move → Ken Burns 覆盖
CAMERA_MOVE_OVERRIDE: dict[str, str] = {
    "slow_zoom": "close-up",
    "pan": "medium",
    "static": "",  # 不加动效
}

# color_grade → FFmpeg 后处理滤镜（E4: 后处理）
# 使用 colorbalance（FFmpeg 8.x 兼容，不依赖 curves 多通道语法）
COLOR_PROFILES: dict[str, str] = {
    "冷蓝调": "colorbalance=rs=-0.03:gs=-0.01:bs=0.08,eq=brightness=0.02",
    "暖黄调": "colorbalance=rs=0.08:gs=0.03:bs=-0.05,eq=brightness=0.02",
    "高对比黑白": "hue=s=0,eq=contrast=1.3:brightness=-0.05",
}

# 通用后处理滤镜
POST_PROCESS_FILTERS = [
    "unsharp=5:5:0.8:3:3:0.4",   # 锐化
    "vignette=PI/5",              # 暗角（较柔和）
    "eq=saturation=1.08",         # 轻微增加饱和度
]


class Compositor(BaseStation):
    """合成引擎 — 用 FFmpeg 组装最终视频"""

    name = "compositor"
    required_every_chapter = False

    # 竖屏漫剧分辨率
    WIDTH = 1080
    HEIGHT = 1920
    FPS = 24

    # 镜头类型 → 背景色（占位模式）
    SHOT_COLORS: dict[str, str] = {
        "close-up": "0x2c1810",
        "medium": "0x1a1a2e",
        "wide": "0x0d1b2a",
        "extreme-wide": "0x0a0a14",
    }

    # 转场时长（秒）
    TRANSITION_DURATION = 0.5

    def run(self, ctx: dict) -> dict:
        """
        ctx: {
            novel_id: str,
            chapter_num: int,
            db: Database,
            image_dir: str | None,
            voice_dir: str | None,
            music_path: str | None,
            output_dir: str,
            subtitle_style: dict | None,
        }
        """
        novel_id: str = ctx["novel_id"]
        chapter_num: int = ctx["chapter_num"]
        db = ctx["db"]
        image_dir: str | None = ctx.get("image_dir")
        voice_dir: str | None = ctx.get("voice_dir")
        music_path: str | None = ctx.get("music_path")
        output_dir: str = ctx.get("output_dir", f"data/video/{novel_id}")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 1. 获取分镜
        sb_data = db.get_storyboard(novel_id, chapter_num)
        if not sb_data or not sb_data.get("shots"):
            return {"status": "error", "reason": "no storyboard found"}

        shots = sb_data["shots"]
        title = sb_data.get("title", f"Chapter {chapter_num}")
        color_grade = sb_data.get("color_grade", "")

        # 2. 建立配音文件映射
        voice_map = self._build_voice_map(voice_dir)

        # 3. 为每个 shot 生成视频片段（含 Ken Burns 动效）
        subtitle_style: dict = ctx.get("subtitle_style", {})
        skipped_shots: list[str] = []

        with tempfile.TemporaryDirectory(prefix="compositor_") as tmp_dir:
            shot_files: list[str] = []
            for i, shot in enumerate(shots):
                shot_id = shot.get("shot_id", f"s{i+1:02d}")
                duration = float(shot.get("duration_sec", 3.0))
                dialogue = shot.get("dialogue", "")
                subject = shot.get("subject", "")
                shot_type = shot.get("shot_type", "medium")
                camera_move = shot.get("camera_move", "static")

                # 查找配音文件
                voice_file = voice_map.get(shot_id, "")

                # 查找画面图片
                image_file = self._find_image(image_dir, shot_id) if image_dir else None

                # 生成单个 shot 视频（E4: 传入 camera_move 启用 Ken Burns）
                shot_path = os.path.join(tmp_dir, f"{shot_id}.ts")
                success = self._render_shot(
                    shot_path=shot_path,
                    duration=duration,
                    subject=subject,
                    dialogue=dialogue,
                    shot_type=shot_type,
                    image_file=image_file,
                    voice_file=voice_file,
                    subtitle=(dialogue if dialogue else ""),
                    subtitle_style=subtitle_style,
                    camera_move=camera_move,
                )
                if success:
                    shot_files.append(shot_path)
                    logger.info("Shot rendered: %s (%.1fs, move=%s)", shot_id, duration, camera_move)
                else:
                    skipped_shots.append(shot_id)
                    logger.warning("Shot render failed (skipped): %s", shot_id)

            if not shot_files:
                return {"status": "error", "reason": "no shots rendered"}

            # 4. 拼接所有 shot
            concat_path = os.path.join(tmp_dir, "concat.mp4")
            if not self._concat_shots(shot_files, concat_path):
                return {"status": "error", "reason": "concat failed"}

            # 5. E4: 画面后处理（色调统一 + 锐化 + 暗角）
            postprocess_path = os.path.join(tmp_dir, "postprocess.mp4")
            if self._apply_post_processing(concat_path, postprocess_path, color_grade):
                processed_path = postprocess_path
            else:
                processed_path = concat_path  # 后处理失败时用原始拼接

            # 6. 混合背景音乐
            final_path = os.path.join(output_dir, f"ch{chapter_num:03d}_video.mp4")
            if music_path and Path(music_path).exists():
                if not self._mix_music(processed_path, music_path, final_path, shots):
                    return {"status": "error", "reason": "music mix failed"}
            else:
                subprocess.run(["cp", processed_path, final_path], check=True)

            # 7. 验证最终文件
            if not Path(final_path).exists() or Path(final_path).stat().st_size < 1000:
                return {"status": "error", "reason": "final video file missing or empty"}

        # 获取最终视频信息
        file_size = Path(final_path).stat().st_size / (1024 * 1024)
        duration = self._get_duration(final_path)

        return {
            "status": "ok",
            "video_path": final_path,
            "duration_sec": duration,
            "file_size_mb": round(file_size, 2),
            "shots_count": len(shot_files),
            "skipped_shots": skipped_shots,
            "title": title,
            "color_grade": color_grade,
            "ken_burns": True,
        }

    def _build_voice_map(self, voice_dir: str | None) -> dict[str, str]:
        """构建 shot_id → 音频文件路径映射"""
        voice_map: dict[str, str] = {}
        if not voice_dir or not Path(voice_dir).exists():
            return voice_map
        for f in Path(voice_dir).iterdir():
            if f.suffix in (".mp3", ".wav", ".ogg"):
                shot_id = f.stem  # e.g. "s01"
                voice_map[shot_id] = str(f)
        return voice_map

    @staticmethod
    def _find_image(image_dir: str | None, shot_id: str) -> str | None:
        """查找 shot 对应的图片文件"""
        if not image_dir:
            return None
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            path = os.path.join(image_dir, f"{shot_id}{ext}")
            if Path(path).exists():
                return path
        return None

    def _render_shot(
        self,
        shot_path: str,
        duration: float,
        subject: str,
        dialogue: str,
        shot_type: str,
        image_file: str | None,
        voice_file: str,
        subtitle: str,
        subtitle_style: dict | None = None,
        camera_move: str = "static",
    ) -> bool:
        """渲染单个 shot 为视频片段。

        E4 增强：当有图片时自动添加 Ken Burns 动效。

        Args:
            camera_move: 镜头运动类型（决定 Ken Burns 效果）。
        """
        try:
            color = self.SHOT_COLORS.get(shot_type, "0x1a1a2e")
            total_frames = int(duration * self.FPS)

            # 构建视频源
            if image_file:
                # 先缩放到略大的尺寸（zoompan 需要余量）
                src_w = int(self.WIDTH * 1.2)
                src_h = int(self.HEIGHT * 1.2)
                input_args = ["-loop", "1", "-i", image_file]
                vf = (
                    f"scale={src_w}:{src_h}:force_original_aspect_ratio=decrease,"
                    f"pad={src_w}:{src_h}:(ow-iw)/2:(oh-ih)/2,"
                    f"setsar=1"
                )

                # E4: Ken Burns 动效
                kb_key = CAMERA_MOVE_OVERRIDE.get(camera_move, shot_type)
                if kb_key and kb_key in KEN_BURNS_PARAMS:
                    kb = KEN_BURNS_PARAMS[kb_key]
                    vf += (
                        f",zoompan=z='{kb['z']}':"
                        f"x='{kb['x']}':"
                        f"y='{kb['y']}':"
                        f"d={total_frames}:s={self.WIDTH}x{self.HEIGHT}:fps={self.FPS}"
                    )
                else:
                    # static 或无匹配：直接缩放到目标尺寸
                    vf += f",scale={self.WIDTH}:{self.HEIGHT}"
            else:
                input_args = ["-f", "lavfi", "-i", f"color=c={color}:s={self.WIDTH}x{self.HEIGHT}:d={duration}:r={self.FPS}"]
                vf = "null"

            # 淡入淡出
            fade_in_end = min(0.5, duration * 0.15)
            fade_out_start = max(0, duration - 0.5)
            if vf == "null":
                vf = f"fade=t=in:st=0:d={fade_in_end},fade=t=out:st={fade_out_start}:d=0.5"
            else:
                vf += f",fade=t=in:st=0:d={fade_in_end},fade=t=out:st={fade_out_start}:d=0.5"

            # 字幕 overlay（Pillow 渲染 → FFmpeg overlay）
            # filter_complex 模式需要显式流标签
            input_args_extra: list[str] = []
            if subtitle:
                sub_img = self._render_subtitle(subtitle, self.WIDTH, self.HEIGHT, subtitle_style or {})
                if sub_img:
                    input_args_extra = ["-i", sub_img]
                    vf = f"[0:v]{vf}[v];[v][1:v]overlay=0:0:format=auto"
                else:
                    vf = f"[0:v]{vf}"
            else:
                vf = f"[0:v]{vf}"

            cmd = ["ffmpeg", "-y"] + input_args + input_args_extra

            # 音频输入（计算已有 -i 参数数量来确定音频索引）
            num_inputs_before_audio = cmd.count("-i")
            if voice_file and Path(voice_file).exists():
                cmd.extend(["-i", voice_file])
            else:
                cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])
            audio_idx = num_inputs_before_audio

            cmd.extend([
                "-filter_complex", vf,
                "-t", str(duration),
                "-map", "0:v",
                "-map", f"{audio_idx}:a",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                "-f", "mpegts",
                shot_path,
            ])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.error("Shot render error (%s): %s", shot_path, result.stderr[-300:])
                return False
            return Path(shot_path).exists()

        except Exception as e:
            logger.error("Shot render exception: %s", e)
            return False

    @staticmethod
    def _render_subtitle(text: str, width: int, height: int, style: dict | None = None) -> str | None:
        """用 Pillow 渲染字幕为 PNG 图片（半透明底色 + 白字）。

        style 参数:
            font_size: int (默认 36)
            font_color: str (默认 "#FFFFFF")
            bg_color: str (默认 "#000000")
            bg_opacity: int 0-255 (默认 160)
            position: str "bottom" | "top" | "center" (默认 "bottom")

        返回 PNG 文件路径，失败返回 None。
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.warning("Pillow not installed, skipping subtitle overlay")
            return None

        if not text or not text.strip():
            return None

        s = style or {}
        font_size = int(s.get("font_size", 36))
        font_color = s.get("font_color", "#FFFFFF")
        bg_color = s.get("bg_color", "#000000")
        bg_opacity = int(s.get("bg_opacity", 160))
        position = s.get("position", "bottom")

        # 解析颜色 hex → RGB
        def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
            h = hex_str.lstrip("#")
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

        fg_rgb = _hex_to_rgb(font_color)
        bg_rgb = _hex_to_rgb(bg_color)

        # 画布（透明背景）
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 字体：尝试系统中文字体，降级到默认
        font = None
        for font_path in (
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "C:\\Windows\\Fonts\\msyh.ttc",
        ):
            if Path(font_path).exists():
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except Exception:
                    continue
        if font is None:
            font = ImageFont.load_default()  # type: ignore[assignment]

        # 自动换行（每行最多 max_chars 个字符）
        max_chars = max(8, width // (font_size + 4))
        lines: list[str] = []
        line = ""
        for ch in text:
            line += ch
            if len(line) >= max_chars:
                lines.append(line)
                line = ""
        if line:
            lines.append(line)

        # 计算字幕区域位置
        line_height = font_size + 8
        bar_height = line_height * len(lines) + 24
        if position == "top":
            bar_top = 60
        elif position == "center":
            bar_top = (height - bar_height) // 2
        else:  # bottom
            bar_top = height - bar_height - 60

        # 绘制半透明底色
        draw.rectangle(
            [(0, bar_top), (width, bar_top + bar_height)],
            fill=(*bg_rgb, bg_opacity),
        )

        # 绘制文字（居中）
        for i, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            x = (width - tw) // 2
            y = bar_top + 12 + i * line_height
            draw.text((x, y), ln, fill=(*fg_rgb, 255), font=font)

        # 保存到临时文件
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".png", prefix="subtitle_")
        os.close(fd)
        img.save(path, "PNG")
        return path

    @staticmethod
    def _concat_shots(shot_files: list[str], output_path: str) -> bool:
        """拼接所有 shot 片段"""
        # 使用 concat demuxer（TS 格式可以直接拼接）
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for path in shot_files:
                f.write(f"file '{path}'\n")
            concat_list = f.name

        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.error("Concat error: %s", result.stderr[-300:])
                return False
            return Path(output_path).exists()
        finally:
            os.unlink(concat_list)

    @staticmethod
    def _apply_post_processing(
        input_path: str, output_path: str, color_grade: str = ""
    ) -> bool:
        """E4: 画面后处理 — 色调统一 + 锐化 + 暗角 + 饱和度。

        Args:
            input_path: 输入视频路径。
            output_path: 输出视频路径。
            color_grade: 色调名称（匹配 COLOR_PROFILES 键）。

        Returns:
            True 表示成功。
        """
        filters: list[str] = []

        # 色调曲线
        profile = COLOR_PROFILES.get(color_grade, "")
        if profile:
            filters.append(profile)

        # 通用后处理
        filters.extend(POST_PROCESS_FILTERS)

        if not filters:
            logger.info("No post-processing filters to apply, copying input")
            subprocess.run(["cp", input_path, output_path], check=True)
            return True

        vf = ",".join(filters)

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            output_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                logger.error("Post-processing error: %s", result.stderr[-300:])
                return False
            return Path(output_path).exists()
        except Exception as e:
            logger.error("Post-processing exception: %s", e)
            return False

    @staticmethod
    def _mix_music(
        video_path: str, music_path: str, output_path: str, shots: list[dict]
    ) -> bool:
        """混合背景音乐到视频"""
        total_duration = sum(float(s.get("duration_sec", 3.0)) for s in shots)

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", music_path,
            "-filter_complex",
            # 配音保持原音量，音乐降低到 15% 并淡入淡出
            f"[0:a]volume=1.0[voice];"
            f"[1:a]volume=0.15,"
            f"afade=t=in:st=0:d=2,"
            f"afade=t=out:st={max(0, total_duration - 3)}:d=3,"
            f"aloop=loop=-1:size=2e+09,"
            f"atrim=0:{total_duration}[music];"
            f"[voice][music]amix=inputs=2:duration=first:dropout_transition=2[audio]",
            "-map", "0:v",
            "-map", "[audio]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(total_duration),
            output_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.error("Music mix error: %s", result.stderr[-300:])
                return False
            return Path(output_path).exists()
        except Exception as e:
            logger.error("Music mix exception: %s", e)
            return False

    @staticmethod
    def _get_duration(path: str) -> float:
        """获取视频时长"""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet",
                 "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1",
                 path],
                capture_output=True, text=True, timeout=10,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    @staticmethod
    async def _run_ffmpeg_async(cmd: list[str], timeout: int = 60) -> bool:
        """异步执行 FFmpeg 命令（使用 asyncio.subprocess）。"""
        import asyncio

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode != 0:
                logger.error("Async FFmpeg error: %s", stderr.decode()[-300:])
                return False
            return True
        except TimeoutError:
            logger.error("Async FFmpeg timeout after %ds", timeout)
            proc.kill()
            return False
        except Exception as e:
            logger.error("Async FFmpeg exception: %s", e)
            return False
