"""
工位：配乐引擎 (MusicEngine)
根据分镜脚本的情绪基调生成背景音乐。

输入：novel_id, chapter_num, db, output_dir
输出：背景音乐文件路径 + 时长

核心逻辑（两层策略）：
  1. 从 storyboards 获取 overall_mood, music_theme
  2. 用 FFmpeg 合成氛围音（本地兜底，无 API 依赖）
  3. 预留 Suno API 接口（高质量选项）
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from ..base import BaseStation

logger = logging.getLogger(__name__)


class MusicEngine(BaseStation):
    """配乐引擎 — 用 FFmpeg 生成氛围背景音乐"""

    name = "music_engine"
    required_every_chapter = False

    # 情绪 → 音乐参数（频率、波形、BPM、调性）
    EMOTION_MUSIC: dict[str, dict] = {
        "紧张":    {"base_freq": 110, "harmonic_freq": 165, "volume": 0.08, "lp_cutoff": 400},
        "恐惧":    {"base_freq": 98,  "harmonic_freq": 147, "volume": 0.06, "lp_cutoff": 300},
        "悲伤":    {"base_freq": 130, "harmonic_freq": 196, "volume": 0.07, "lp_cutoff": 500},
        "愤怒":    {"base_freq": 110, "harmonic_freq": 220, "volume": 0.10, "lp_cutoff": 600},
        "平静":    {"base_freq": 196, "harmonic_freq": 293, "volume": 0.05, "lp_cutoff": 800},
        "孤独":    {"base_freq": 130, "harmonic_freq": 196, "volume": 0.05, "lp_cutoff": 350},
        "希望":    {"base_freq": 164, "harmonic_freq": 247, "volume": 0.07, "lp_cutoff": 700},
        "震惊":    {"base_freq": 110, "harmonic_freq": 165, "volume": 0.09, "lp_cutoff": 500},
        "压抑":    {"base_freq": 98,  "harmonic_freq": 147, "volume": 0.06, "lp_cutoff": 300},
        "温暖":    {"base_freq": 196, "harmonic_freq": 261, "volume": 0.06, "lp_cutoff": 600},
        "悬疑":    {"base_freq": 110, "harmonic_freq": 155, "volume": 0.07, "lp_cutoff": 350},
        "爆发":    {"base_freq": 130, "harmonic_freq": 261, "volume": 0.10, "lp_cutoff": 800},
    }

    # 默认参数（无法匹配情绪时使用）
    DEFAULT_MUSIC = {"base_freq": 130, "harmonic_freq": 196, "volume": 0.06, "lp_cutoff": 400}

    def run(self, ctx: dict) -> dict:
        """
        ctx: {
            novel_id: str,
            chapter_num: int,
            db: Database,
            output_dir: str,       # 输出目录
            duration_sec: float,   # 目标时长（默认从 storyboard 获取）
            provider: str,         # "ambient" | "suno"（默认 ambient）
            api_key: str,          # Suno API key（provider=suno 时需要）
        }
        """
        novel_id: str = ctx["novel_id"]
        chapter_num: int = ctx["chapter_num"]
        db = ctx["db"]
        output_dir: str = ctx.get("output_dir", f"data/music/{novel_id}")
        provider: str = ctx.get("provider", "ambient")
        api_key: str = ctx.get("api_key", "")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 1. 获取分镜数据
        sb_data = db.get_storyboard(novel_id, chapter_num)
        if not sb_data:
            return {"status": "error", "reason": "no storyboard found"}

        overall_mood = sb_data.get("overall_mood", "")
        music_theme = sb_data.get("music_theme", "")
        duration = ctx.get("duration_sec", sb_data.get("total_duration_sec", 60.0))

        output_path = os.path.join(output_dir, f"ch{chapter_num:03d}_music.mp3")

        # 2. 尝试 Suno API（高质量），失败则降级到 FFmpeg ambient
        source = "ambient"
        if provider == "suno" and api_key:
            prompt = f"{overall_mood} {music_theme}".strip()
            success = self._generate_suno(prompt, duration, output_path, api_key)
            if success:
                source = "suno"
            else:
                logger.warning("Suno failed, falling back to FFmpeg ambient")

        if source == "ambient":
            # 匹配情绪参数 → FFmpeg 合成
            params = self._match_mood(overall_mood)
            success = self._generate_ambient(duration, params, output_path)
            if not success:
                return {"status": "error", "reason": "ffmpeg generation failed"}
        else:
            params = {}

        logger.info("Music generated: mood=%s, duration=%.1fs, source=%s → %s",
                     overall_mood, duration, source, output_path)

        return {
            "status": "ok",
            "music_path": output_path,
            "duration_sec": duration,
            "mood": overall_mood,
            "music_theme": music_theme,
            "source": source,
            "params": params,
        }

    def _match_mood(self, mood: str) -> dict:
        """模糊匹配情绪到音乐参数"""
        if not mood:
            return self.DEFAULT_MUSIC
        for key, params in self.EMOTION_MUSIC.items():
            if key in mood:
                return params
        return self.DEFAULT_MUSIC

    @staticmethod
    def _generate_suno(prompt: str, duration: float, output_path: str, api_key: str) -> bool:
        """调用 Suno API 生成配乐（带轮询机制）。

        Suno API 使用异步生成模式：
        1. POST /api/generate → 返回 clip ID
        2. GET /api/feed/{id} → 轮询直到音频就绪
        3. 下载音频到本地

        支持两种端点（自动尝试）：
        - 官方 Suno API: https://studio-api.suno.ai
        - 第三方 wrapper: https://api.sunoapi.org
        """

        # 尝试的 API 端点列表
        endpoints = [
            {
                "generate": "https://studio-api.suno.ai/api/generate",
                "feed": "https://studio-api.suno.ai/api/feed/{clip_id}",
            },
            {
                "generate": "https://api.sunoapi.org/v1/generate",
                "feed": "https://api.sunoapi.org/v1/feed/{clip_id}",
            },
        ]

        payload = {
            "prompt": prompt[:200],
            "make_instrumental": True,
            "wait_audio": True,  # 尝试同步模式
        }

        for ep in endpoints:
            success = _try_suno_endpoint(ep, payload, api_key, duration, output_path)
            if success:
                return True

        logger.error("All Suno API endpoints failed")
        return False

    @staticmethod
    def _generate_ambient(duration: float, params: dict, output_path: str) -> bool:
        """用 FFmpeg 合成氛围音"""
        base_freq = params["base_freq"]
        harmonic_freq = params["harmonic_freq"]
        volume = params["volume"]
        lp_cutoff = params["lp_cutoff"]

        # FFmpeg 滤镜链：
        #   1. 基频正弦波（低音 drone）
        #   2. 泛音正弦波（和声）
        #   3. 粉红噪声（增加质感）
        #   4. 低通滤波 + 混响效果
        filter_complex = (
            f"[0:a]volume={volume},lowpass=f={lp_cutoff}[base];"
            f"[1:a]volume={volume * 0.5},lowpass=f={lp_cutoff}[harm];"
            f"[2:a]volume=0.015,lowpass=f={lp_cutoff * 0.8}[noise];"
            f"[base][harm]amix=inputs=2:duration=longest[mix1];"
            f"[mix1][noise]amix=inputs=2:duration=longest,"
            f"aecho=0.6:0.3:500:0.3,"
            f"afade=t=in:st=0:d=3,"
            f"afade=t=out:st={max(0, duration - 3)}:d=3"
            f"[out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"sine=frequency={base_freq}:duration={duration}",
            "-f", "lavfi", "-i", f"sine=frequency={harmonic_freq}:duration={duration}",
            "-f", "lavfi", "-i", f"anoisesrc=d={duration}:c=pink:a=1",
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", str(duration),
            "-c:a", "libmp3lame", "-q:a", "4",
            output_path,
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                logger.error("FFmpeg music error: %s", result.stderr[:300])
                return False
            return Path(output_path).exists()
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg music timeout")
            return False
        except Exception as e:
            logger.error("FFmpeg music exception: %s", e)
            return False


def _try_suno_endpoint(
    endpoint: dict[str, str],
    payload: dict,
    api_key: str,
    duration: float,
    output_path: str,
) -> bool:
    """尝试通过指定 Suno API 端点生成配乐（含轮询）。

    Args:
        endpoint: {"generate": url, "feed": url_template_with_{clip_id}}
        payload: 请求体
        api_key: API key
        duration: 目标时长
        output_path: 输出路径

    Returns:
        True if audio downloaded successfully
    """
    import json
    import time
    import urllib.request

    generate_url = endpoint["generate"]
    feed_template = endpoint["feed"]

    # 1. 发起生成请求
    req = urllib.request.Request(
        generate_url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        logger.debug("Suno generate request failed (%s): %s", generate_url, e)
        return False

    # 检查是否直接返回了音频 URL（同步模式）
    audio_url = _extract_audio_url(data)
    if audio_url:
        return _download_audio(audio_url, output_path)

    # 2. 提取 clip_id，开始轮询
    clip_id = _extract_clip_id(data)
    if not clip_id:
        logger.debug("Suno: no clip_id in response from %s: %s", generate_url, str(data)[:200])
        return False

    logger.info("Suno: polling clip %s", clip_id)
    feed_url = feed_template.replace("{clip_id}", clip_id)

    # 轮询（最多等待 5 分钟）
    max_polls = 60
    poll_interval = 5  # 秒

    for attempt in range(max_polls):
        time.sleep(poll_interval)
        try:
            req = urllib.request.Request(
                feed_url,
                headers={"Authorization": f"Bearer {api_key}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                feed_data = json.loads(resp.read())

            audio_url = _extract_audio_url(feed_data)
            if audio_url:
                return _download_audio(audio_url, output_path)

            # 检查是否失败
            status = feed_data.get("status", "") if isinstance(feed_data, dict) else ""
            if status in ("failed", "error"):
                logger.error("Suno generation failed: %s", feed_data)
                return False

        except Exception as e:
            logger.debug("Suno poll attempt %d failed: %s", attempt + 1, e)

    logger.error("Suno polling timeout after %d attempts", max_polls)
    return False


def _extract_audio_url(data: dict | list | None) -> str:
    """从 Suno API 响应中提取音频 URL"""
    if not data:
        return ""
    if isinstance(data, dict):
        # 直接 audio_url 字段
        if data.get("audio_url"):
            return data["audio_url"]
        # clips 数组
        clips = data.get("clips", [])
        if clips and isinstance(clips, list):
            return clips[0].get("audio_url", "")
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict):
            return first.get("audio_url", "")
    return ""


def _extract_clip_id(data: dict | list | None) -> str:
    """从 Suno API 响应中提取 clip ID"""
    if not data:
        return ""
    if isinstance(data, dict):
        if data.get("clip_id"):
            return data["clip_id"]
        if data.get("id"):
            return data["id"]
        clips = data.get("clips", [])
        if clips and isinstance(clips, list) and len(clips) > 0:
            return clips[0].get("clip_id", clips[0].get("id", ""))
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict):
            return str(first.get("clip_id", first.get("id", "")))
    return ""


def _download_audio(audio_url: str, output_path: str) -> bool:
    """下载音频文件"""
    import urllib.request

    try:
        urllib.request.urlretrieve(audio_url, output_path)
        return Path(output_path).exists()
    except Exception as e:
        logger.error("Audio download failed: %s", e)
        return False
