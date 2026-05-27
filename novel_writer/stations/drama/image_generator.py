"""
工位：画面生成器 (ImageGenerator)
将 Prompt Generator 产出的 prompt 转化为实际图片。

输入：novel_id, chapter_num, db, output_dir, provider, quality_config
输出：每个镜头的图片文件路径 + 质量报告

支持多级降级策略：
  1. ComfyUI + IP-Adapter（需要 ComfyUI 服务）
  2. Stability AI API（需要 API key）
  3. DALL·E 3 API（需要 OpenAI key）
  4. FFmpeg 生成渐变占位图（兜底，无需外部依赖）

质量保障（E4）：
  - shot_type 参数自动优化（close-up 更高 steps/cfg）
  - 文件完整性 + 尺寸 + 可选人脸/CLIP 检查
  - 选择性重试（最多 max_retries 次，换 seed）
"""

from __future__ import annotations

import logging
import os
import random
from typing import Any
import subprocess
from pathlib import Path

from ..base import BaseStation
from .quality_checker import QualityChecker, QualityConfig

logger = logging.getLogger(__name__)

# shot_type → ComfyUI 参数优化（A: 源头强化）
SHOT_OPTIMIZE: dict[str, dict] = {
    "close-up": {
        "steps": 30,
        "cfg": 8.0,
        "prompt_prefix": "detailed face, sharp eyes, skin texture, ",
    },
    "medium": {
        "steps": 25,
        "cfg": 7.0,
        "prompt_prefix": "balanced composition, waist-up portrait, ",
    },
    "wide": {
        "steps": 25,
        "cfg": 6.5,
        "prompt_prefix": "full body shot, environmental context, ",
    },
    "extreme-wide": {
        "steps": 25,
        "cfg": 6.0,
        "prompt_prefix": "establishing shot, vast landscape, cinematic wide angle, ",
    },
}


class ImageGenerator(BaseStation):
    """画面生成器 — 将 prompt 转化为 AI 绘图"""

    name = "image_generator"
    required_every_chapter = False

    # 竖屏漫剧分辨率
    WIDTH = 1080
    HEIGHT = 1920

    # shot_type → 渐变色方案（占位模式）
    GRADIENT_THEMES: dict[str, tuple[str, str]] = {
        "close-up": ("0x2c1810", "0x1a0e08"),
        "medium": ("0x1a1a2e", "0x16213e"),
        "wide": ("0x0d1b2a", "0x1b2838"),
        "extreme-wide": ("0x0a0a14", "0x0d1117"),
    }

    # 情绪 → 色调叠加
    EMOTION_TINTS: dict[str, str] = {
        "紧张": "0x330000@0.2",
        "恐惧": "0x000011@0.3",
        "悲伤": "0x000033@0.2",
        "愤怒": "0x440000@0.25",
        "平静": "0x002211@0.15",
        "孤独": "0x000022@0.25",
        "希望": "0x332200@0.15",
        "悬疑": "0x000011@0.25",
        "压抑": "0x110011@0.2",
        "温暖": "0x331100@0.15",
    }

    def run(self, ctx: dict) -> dict:
        """
        ctx: {
            novel_id: str,
            chapter_num: int,
            db: Database,
            output_dir: str,
            provider: str,
            api_key: str,
            dalle3_api_key: str,
            comfyui_config: dict | None,
            character_refs: dict | None,
            quality_config: dict | None,  # E4: 质量检查配置
        }
        """
        novel_id: str = ctx["novel_id"]
        chapter_num: int = ctx["chapter_num"]
        db = ctx["db"]
        output_dir: str = ctx.get("output_dir", f"data/images/{novel_id}/ch{chapter_num:03d}")
        provider: str = ctx.get("provider", "placeholder")
        api_key: str = ctx.get("api_key", "")
        dalle3_api_key: str = ctx.get("dalle3_api_key", "")
        comfyui_config: dict | None = ctx.get("comfyui_config")
        character_refs: dict[str, list[str]] = ctx.get("character_refs", {})

        # E4: 质量检查器
        qc_config = QualityConfig.from_dict(ctx.get("quality_config"))
        checker = QualityChecker(qc_config)

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 1. 获取分镜
        sb_data = db.get_storyboard(novel_id, chapter_num)
        if not sb_data or not sb_data.get("shots"):
            return {"status": "error", "reason": "no storyboard found"}

        # 2. 获取 prompt（如果已生成）
        from ..script.prompt_generator import PromptGenerator
        pg = PromptGenerator()
        prompt_result = pg.run({"novel_id": novel_id, "chapter_num": chapter_num, "db": db})

        prompt_map: dict[str, dict] = {}
        if prompt_result.get("status") == "ok":
            for p in prompt_result.get("prompts", []):
                prompt_map[p["shot_id"]] = p

        # 3. 质量报告统计
        qr: dict[str, Any] = {
            "total": len(sb_data["shots"]),
            "passed_first_try": 0,
            "passed_after_retry": 0,
            "best_effort": 0,
            "skipped_existing": 0,
            "checks_used": checker.check_result_summary if qc_config.enabled else [],
            "clip_threshold": qc_config.clip_threshold if qc_config.check_clip else None,
        }

        # 4. 为每个 shot 生成图片（带质量检查 + 重试）
        images: list[dict] = []
        for shot in sb_data["shots"]:
            shot_id = shot.get("shot_id", "")
            shot_type = shot.get("shot_type", "medium")
            emotion = shot.get("emotion", "")
            subject = shot.get("subject", "")

            output_path = os.path.join(output_dir, f"{shot_id}.png")

            # 检查是否已有图片
            if Path(output_path).exists():
                images.append({
                    "shot_id": shot_id,
                    "image_path": output_path,
                    "source": "existing",
                })
                qr["skipped_existing"] += 1
                continue

            # 获取 prompt
            prompt_data = prompt_map.get(shot_id, {})
            prompt_text = prompt_data.get("prompt", subject)
            negative = prompt_data.get("negative_prompt", "")

            # A: 源头强化 — 按 shot_type 优化参数
            opt = SHOT_OPTIMIZE.get(shot_type, {})
            optimized_prompt = opt.get("prompt_prefix", "") + prompt_text

            # B: 质量检查 + 选择性重试
            max_attempts = 1 + qc_config.max_retries
            candidates: list[str] = []
            attempt_results: list[str] = []

            for attempt in range(max_attempts):
                # 每次重试换不同 seed
                seed = random.randint(1, 2**32 - 1) if attempt > 0 else None

                # 临时路径（重试时用不同文件名）
                if attempt == 0:
                    gen_path = output_path
                else:
                    gen_path = os.path.join(
                        output_dir, f"{shot_id}_retry{attempt}.png",
                    )

                # 生成图片
                success = self._generate_shot(
                    provider=provider,
                    prompt_text=optimized_prompt,
                    negative=negative,
                    output_path=gen_path,
                    subject=subject,
                    shot_type=shot_type,
                    emotion=emotion,
                    character_refs=character_refs,
                    comfyui_config=comfyui_config,
                    api_key=api_key,
                    dalle3_api_key=dalle3_api_key,
                    opt_params=opt,
                    seed=seed,
                )

                if not success or not Path(gen_path).exists():
                    attempt_results.append(f"attempt{attempt}: generation failed")
                    continue

                candidates.append(gen_path)

                # 质量检查
                check = checker.check(gen_path, prompt=prompt_text, shot_type=shot_type)
                if check.passed:
                    # 通过！如果不是第一次尝试，重命名为最终文件
                    if attempt > 0 and gen_path != output_path:
                        Path(gen_path).rename(output_path)
                    if attempt == 0:
                        qr["passed_first_try"] += 1
                    else:
                        qr["passed_after_retry"] += 1
                    images.append({
                        "shot_id": shot_id,
                        "image_path": output_path,
                        "source": provider,
                        "prompt": prompt_text[:100],
                        "attempts": attempt + 1,
                        "clip_score": check.clip_score if qc_config.check_clip else None,
                    })
                    break
                else:
                    attempt_results.append(
                        f"attempt{attempt}: {check.failure_reason}",
                    )
            else:
                # 所有尝试都失败，选最好的
                best = checker.best_of(candidates, prompt=prompt_text)
                if best and best != output_path:
                    Path(best).rename(output_path)
                # 清理重试文件
                for c in candidates:
                    if c != output_path and Path(c).exists():
                        Path(c).unlink(missing_ok=True)

                qr["best_effort"] += 1
                images.append({
                    "shot_id": shot_id,
                    "image_path": output_path if Path(output_path).exists() else "",
                    "source": f"{provider}(best_effort)",
                    "prompt": prompt_text[:100],
                    "attempts": max_attempts,
                    "quality_note": "; ".join(attempt_results),
                })

            # 清理残留的重试文件（成功时）
            for c in candidates:
                if c != output_path and Path(c).exists():
                    Path(c).unlink(missing_ok=True)

        # 计算平均尝试次数
        attempts_list = [i.get("attempts", 1) for i in images if i.get("image_path")]
        qr["avg_attempts"] = round(
            sum(attempts_list) / len(attempts_list), 2,
        ) if attempts_list else 0

        return {
            "status": "ok",
            "images": images,
            "count": len([i for i in images if i.get("image_path")]),
            "total": len(images),
            "output_dir": output_dir,
            "provider": provider,
            "quality_report": qr,
        }

    def _generate_shot(
        self,
        provider: str,
        prompt_text: str,
        negative: str,
        output_path: str,
        subject: str,
        shot_type: str,
        emotion: str,
        character_refs: dict[str, list[str]],
        comfyui_config: dict | None,
        api_key: str,
        dalle3_api_key: str,
        opt_params: dict,
        seed: int | None = None,
    ) -> bool:
        """生成单张图片（路由到具体 provider）。"""
        if provider == "comfyui" and comfyui_config:
            ref_images = self._match_character_refs(subject, character_refs)
            return self._generate_comfyui(
                prompt_text, negative, output_path,
                ref_images, comfyui_config,
                override_steps=opt_params.get("steps"),
                override_cfg=opt_params.get("cfg"),
                seed=seed,
            )
        elif provider == "stability" and api_key:
            return self._generate_stability(prompt_text, negative, output_path, api_key)
        elif provider == "dalle3" and dalle3_api_key:
            return self._generate_dalle3(prompt_text, negative, output_path, dalle3_api_key)
        else:
            return self._generate_placeholder(shot_type, emotion, output_path)

    @staticmethod
    def _generate_stability(prompt: str, negative: str, output_path: str, api_key: str) -> bool:
        """调用 Stability AI API 生成图片"""
        import urllib.request

        url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"
        boundary = "----FormBoundary7MA4YWxkTrZu0gW"

        # multipart/form-data 构建
        body_parts: list[bytes] = []

        for field_name, value in [
            ("prompt", prompt),
            ("negative_prompt", negative),
            ("output_format", "png"),
            ("aspect_ratio", "9:16"),
        ]:
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"\r\n'
                f"\r\n"
                f"{value}\r\n".encode()
            )

        body_parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(body_parts)

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "image/*",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(output_path, "wb") as f:
                    f.write(resp.read())
                return True
        except Exception as e:
            logger.error("Stability API error: %s", e)
            return False

    @staticmethod
    def _generate_dalle3(prompt: str, negative: str, output_path: str, api_key: str) -> bool:
        """调用 OpenAI DALL·E 3 API 生成图片"""
        import base64
        import json
        import urllib.request

        # DALL·E 3 不支持独立 negative prompt，拼接到 prompt 尾部
        full_prompt = prompt
        if negative:
            full_prompt += f". Avoid: {negative}"

        url = "https://api.openai.com/v1/images/generations"
        payload = {
            "model": "dall-e-3",
            "prompt": full_prompt[:4000],  # DALL·E 3 prompt 限制
            "size": "1024x1792",  # 9:16 竖屏
            "quality": "standard",
            "n": 1,
            "response_format": "b64_json",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                b64_data = data["data"][0]["b64_json"]
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                return True
        except Exception as e:
            logger.error("DALL·E 3 API error: %s", e)
            return False

    def _generate_comfyui(
        self,
        prompt_text: str,
        negative: str,
        output_path: str,
        reference_images: list[str],
        config: dict,
        override_steps: int | None = None,
        override_cfg: float | None = None,
        seed: int | None = None,
    ) -> bool:
        """使用 ComfyUI IP-Adapter 生成带角色一致性的图片。

        Args:
            prompt_text: 正向提示词。
            negative: 负向提示词。
            output_path: 输出图片路径。
            reference_images: 角色参考图本地路径列表。
            config: ComfyUI 配置（来自 film_settings）。
            override_steps: 覆盖 steps 参数（shot_type 优化）。
            override_cfg: 覆盖 cfg 参数（shot_type 优化）。
            seed: 随机种子（重试时换种子）。

        Returns:
            成功返回 True。
        """
        from .comfyui_client import ComfyUIClient, ComfyUIError

        comfyui_url = config.get("url", "http://127.0.0.1:8188")
        # 解析 host:port
        host = "127.0.0.1"
        port = 8188
        try:
            from urllib.parse import urlparse
            parsed = urlparse(comfyui_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 8188
        except Exception:
            pass

        client = ComfyUIClient(host=host, port=port)

        try:
            # 选择工作流模式
            if reference_images:
                return self._generate_comfyui_ipadapter(
                    client, prompt_text, negative, output_path,
                    reference_images, config,
                    override_steps=override_steps,
                    override_cfg=override_cfg,
                    seed=seed,
                )
            else:
                return self._generate_comfyui_txt2img(
                    client, prompt_text, negative, output_path, config,
                    override_steps=override_steps,
                    override_cfg=override_cfg,
                    seed=seed,
                )
        except ComfyUIError as e:
            logger.error("ComfyUI generation error: %s", e)
            return False
        except Exception as e:
            logger.error("ComfyUI unexpected error: %s", e)
            return False

    def _generate_comfyui_ipadapter(
        self,
        client: object,
        prompt_text: str,
        negative: str,
        output_path: str,
        reference_images: list[str],
        config: dict,
        override_steps: int | None = None,
        override_cfg: float | None = None,
        seed: int | None = None,
    ) -> bool:
        """使用 IP-Adapter FaceID 生成图片（带参考图）。"""
        from .comfyui_client import ComfyUIClient
        from .comfyui_workflows import build_ipadapter_faceid_workflow

        assert isinstance(client, ComfyUIClient)

        # 上传参考图到 ComfyUI
        ref_image_name = ""
        for ref_path in reference_images[:1]:  # 取第一张参考图
            try:
                result = client.upload_image(ref_path)
                ref_image_name = result.get("name", "")
                break
            except Exception as e:
                logger.warning("Failed to upload ref image %s: %s", ref_path, e)

        if not ref_image_name:
            logger.warning("No reference image uploaded, falling back to txt2img")
            return self._generate_comfyui_txt2img(
                client, prompt_text, negative, output_path, config,
            )

        # 构建 workflow（shot_type 优化覆盖全局配置）
        steps = override_steps or int(config.get("steps", 25))
        cfg = override_cfg or float(config.get("cfg", 7.0))
        effective_seed = seed if seed is not None else random.randint(1, 2**32 - 1)

        workflow = build_ipadapter_faceid_workflow(
            prompt=prompt_text,
            negative=negative,
            ref_image_name=ref_image_name,
            checkpoint=config.get("checkpoint", "sd_xl_base_1.0.safetensors"),
            ipadapter_model=config.get(
                "ipadapter_model", "ip-adapter-faceid-plusv2_sd15.bin",
            ),
            clip_vision_model=config.get(
                "clip_vision_model", "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
            ),
            insightface_model=config.get("insightface_model", "buffalo_l"),
            lora_strength=float(config.get("lora_strength", 0.8)),
            width=self.WIDTH // 2,
            height=self.HEIGHT // 2,
            steps=steps,
            cfg=cfg,
            seed=effective_seed,
        )

        return client.generate_image(workflow, output_path, timeout=300)

    def _generate_comfyui_txt2img(
        self,
        client: object,
        prompt_text: str,
        negative: str,
        output_path: str,
        config: dict,
        override_steps: int | None = None,
        override_cfg: float | None = None,
        seed: int | None = None,
    ) -> bool:
        """使用纯文生图 workflow（无参考图）。"""
        from .comfyui_client import ComfyUIClient
        from .comfyui_workflows import build_txt2img_workflow

        assert isinstance(client, ComfyUIClient)

        steps = override_steps or int(config.get("steps", 25))
        cfg = override_cfg or float(config.get("cfg", 7.0))
        effective_seed = seed if seed is not None else random.randint(1, 2**32 - 1)

        workflow = build_txt2img_workflow(
            prompt=prompt_text,
            negative=negative,
            checkpoint=config.get("checkpoint", "sd_xl_base_1.0.safetensors"),
            width=self.WIDTH // 2,
            height=self.HEIGHT // 2,
            steps=steps,
            cfg=cfg,
            seed=effective_seed,
        )

        return client.generate_image(workflow, output_path, timeout=300)

    @staticmethod
    def _match_character_refs(
        subject: str,
        character_refs: dict[str, list[str]],
    ) -> list[str]:
        """根据 shot 的 subject 匹配角色参考图。

        遍历 character_refs 的 key，如果 key 出现在 subject 中，
        则返回该角色的参考图路径列表。

        Args:
            subject: shot 的主体描述（如 "李明站在窗前"）。
            character_refs: {char_key: [path, ...]} 映射。

        Returns:
            匹配到的参考图路径列表，无匹配返回空列表。
        """
        for char_key, refs in character_refs.items():
            if char_key in subject and refs:
                return refs
        return []

    def _generate_placeholder(self, shot_type: str, emotion: str, output_path: str) -> bool:
        """用 FFmpeg 生成渐变占位图"""
        colors = self.GRADIENT_THEMES.get(shot_type, ("0x1a1a2e", "0x16213e"))
        c1, c2 = colors

        # 基础渐变
        gradient_filter = (
            f"gradients=c0={c1}:c1={c2}:"
            f"x0=0:y0=0:x1=0:y1={self.HEIGHT}:"
            f"duration=1:s={self.WIDTH}x{self.HEIGHT}:type=linear"
        )

        # 情绪色调叠加
        tint = self.EMOTION_TINTS.get(emotion, "")
        vf_parts: list[str] = []

        if tint:
            # 用 color overlay 实现色调
            color_val, alpha = tint.split("@")
            vf_parts.append(
                f"color=c={color_val}:s={self.WIDTH}x{self.HEIGHT}:d=1[overlay];"
                f"[0:v][overlay]overlay=0:0:format=auto,format=rgb24"
            )

        if not vf_parts:
            vf_parts.append("format=rgb24")

        vf = ",".join(vf_parts)

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", gradient_filter,
            "-vf", vf,
            "-frames:v", "1",
            "-update", "1",
            output_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                # 降级：纯色图
                return self._generate_solid(shot_type, output_path)
            return Path(output_path).exists()
        except Exception:
            return self._generate_solid(shot_type, output_path)

    @staticmethod
    def _generate_solid(shot_type: str, output_path: str) -> bool:
        """最终降级：纯色占位图"""
        colors = {
            "close-up": "0x2c1810",
            "medium": "0x1a1a2e",
            "wide": "0x0d1b2a",
            "extreme-wide": "0x0a0a14",
        }
        color = colors.get(shot_type, "0x1a1a2e")

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c={color}:s=1080x1920:d=1",
            "-frames:v", "1",
            "-update", "1",
            output_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0 and Path(output_path).exists()
        except Exception:
            return False
