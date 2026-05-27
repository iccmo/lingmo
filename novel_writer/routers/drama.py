"""
短剧路由 — 画面生成、配音配乐、视频合成。

包含：影视制作配置、一键制片、ComfyUI 管理、角色参考图生成。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .deps import get_db, set_status

router = APIRouter(prefix="/api/novels", tags=["drama"])

# ═══════════════ Film Studio Settings ═══════════════


@router.get("/film-settings")
def get_film_settings() -> dict:
    """获取影视制作配置"""
    db = get_db()
    settings = db.load_film_settings()
    return {
        "image_provider": settings.get("image_provider", "placeholder"),
        "image_api_key": _mask_key(settings.get("image_api_key", "")),
        "dalle3_api_key": _mask_key(settings.get("dalle3_api_key", "")),
        "music_provider": settings.get("music_provider", "ambient"),
        "suno_api_key": _mask_key(settings.get("suno_api_key", "")),
        "subtitle_font_size": settings.get("subtitle_font_size", "36"),
        "subtitle_font_color": settings.get("subtitle_font_color", "#FFFFFF"),
        "subtitle_bg_color": settings.get("subtitle_bg_color", "#000000"),
        "subtitle_bg_opacity": settings.get("subtitle_bg_opacity", "160"),
        "subtitle_position": settings.get("subtitle_position", "bottom"),
        "comfyui_url": settings.get("comfyui_url", "http://127.0.0.1:8188"),
        "comfyui_checkpoint": settings.get("comfyui_checkpoint", "sd_xl_base_1.0.safetensors"),
        "comfyui_ipadapter_model": settings.get("comfyui_ipadapter_model", "ip-adapter-faceid-plusv2_sd15.bin"),
        "comfyui_lora_strength": settings.get("comfyui_lora_strength", "0.8"),
        "comfyui_steps": settings.get("comfyui_steps", "25"),
        "comfyui_cfg": settings.get("comfyui_cfg", "7.0"),
        # E4: 图片质量检查配置
        "quality_enabled": settings.get("quality_enabled", "true"),
        "quality_max_retries": settings.get("quality_max_retries", "2"),
        "quality_check_face": settings.get("quality_check_face", "false"),
        "quality_check_clip": settings.get("quality_check_clip", "false"),
        "quality_clip_threshold": settings.get("quality_clip_threshold", "0.20"),
    }


@router.put("/film-settings")
def update_film_settings(body: dict) -> dict:
    """更新影视制作配置"""
    db = get_db()
    if "image_provider" in body:
        db.save_film_setting("image_provider", str(body["image_provider"]))
    if "image_api_key" in body and body["image_api_key"]:
        db.save_film_setting("image_api_key", str(body["image_api_key"]))
    if "dalle3_api_key" in body and body["dalle3_api_key"]:
        db.save_film_setting("dalle3_api_key", str(body["dalle3_api_key"]))
    if "music_provider" in body:
        db.save_film_setting("music_provider", str(body["music_provider"]))
    if "suno_api_key" in body and body["suno_api_key"]:
        db.save_film_setting("suno_api_key", str(body["suno_api_key"]))
    # 字幕样式字段
    for key in ("subtitle_font_size", "subtitle_font_color", "subtitle_bg_color",
                "subtitle_bg_opacity", "subtitle_position"):
        if key in body:
            db.save_film_setting(key, str(body[key]))
    # ComfyUI 配置字段
    for key in ("comfyui_url", "comfyui_checkpoint", "comfyui_ipadapter_model",
                "comfyui_lora_strength", "comfyui_steps", "comfyui_cfg"):
        if key in body:
            db.save_film_setting(key, str(body[key]))
    # E4: 图片质量检查配置
    for key in ("quality_enabled", "quality_max_retries",
                "quality_check_face", "quality_check_clip", "quality_clip_threshold"):
        if key in body:
            db.save_film_setting(key, str(body[key]))
    return {"status": "ok"}


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return key[:4] + "***" + key[-4:]


def _get_image_config() -> tuple[str, str, str]:
    """读取当前 image provider 配置 → (provider, stability_key, dalle3_key)"""
    db = get_db()
    settings = db.load_film_settings()
    return (
        settings.get("image_provider", "placeholder"),
        settings.get("image_api_key", ""),
        settings.get("dalle3_api_key", ""),
    )


def _get_comfyui_config() -> dict:
    """读取 ComfyUI 配置"""
    db = get_db()
    settings = db.load_film_settings()
    return {
        "url": settings.get("comfyui_url", "http://127.0.0.1:8188"),
        "checkpoint": settings.get("comfyui_checkpoint", "sd_xl_base_1.0.safetensors"),
        "ipadapter_model": settings.get(
            "comfyui_ipadapter_model", "ip-adapter-faceid-plusv2_sd15.bin",
        ),
        "lora_strength": settings.get("comfyui_lora_strength", "0.8"),
        "steps": settings.get("comfyui_steps", "25"),
        "cfg": settings.get("comfyui_cfg", "7.0"),
    }


def _load_character_refs(novel_id: str) -> dict[str, list[str]]:
    """加载角色参考图映射 → {char_key: [path, ...]}"""
    db = get_db()
    visual_chars = db.get_visual_characters(novel_id)
    refs: dict[str, list[str]] = {}
    for vc in visual_chars:
        char_key = vc.get("char_key", "")
        images = vc.get("reference_images", [])
        if char_key and images:
            refs[char_key] = images
    return refs


def _get_quality_config() -> dict:
    """读取图片质量检查配置（E4）"""
    db = get_db()
    settings = db.load_film_settings()
    return {
        "enabled": settings.get("quality_enabled", "true") == "true",
        "max_retries": int(settings.get("quality_max_retries", "2")),
        "check_file": True,
        "check_dimensions": True,
        "check_face": settings.get("quality_check_face", "false") == "true",
        "check_clip": settings.get("quality_check_clip", "false") == "true",
        "clip_threshold": float(settings.get("quality_clip_threshold", "0.20")),
    }


def _get_subtitle_style() -> dict:
    """读取字幕样式配置"""
    db = get_db()
    settings = db.load_film_settings()
    return {
        "font_size": int(settings.get("subtitle_font_size", "36")),
        "font_color": settings.get("subtitle_font_color", "#FFFFFF"),
        "bg_color": settings.get("subtitle_bg_color", "#000000"),
        "bg_opacity": int(settings.get("subtitle_bg_opacity", "160")),
        "position": settings.get("subtitle_position", "bottom"),
    }



# ═══════════════ AI Film Studio: 多媒体管线（配音 + 配乐 + 合成）═══════════════


@router.post("/{novel_id}/chapters/{chapter_num}/voice/generate")
def generate_voice(novel_id: str, chapter_num: int, background: BackgroundTasks) -> dict:
    """生成配音（异步）"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    chapter = db.get_chapter(novel_id, chapter_num)
    if not chapter:
        raise HTTPException(404, "chapter not found")

    def _run():
        set_status(novel_id, "voice", f"正在生成第{chapter_num}章配音...")
        try:
            from ..stations.drama.voice_engine import VoiceEngine
            ve = VoiceEngine()
            result = ve.run({
                "novel_id": novel_id,
                "chapter_num": chapter_num,
                "db": db,
            })
            count = result.get("count", 0)
            dur = result.get("total_duration", 0)
            set_status(novel_id, "idle", f"配音完成: {count} 条, {dur:.1f}秒")
            return result
        except Exception as e:
            set_status(novel_id, "error", f"配音失败: {str(e)[:100]}")

    background.add_task(_run)
    return {"status": "started", "message": f"第{chapter_num}章配音生成中"}


@router.post("/{novel_id}/chapters/{chapter_num}/music/generate")
def generate_music(novel_id: str, chapter_num: int, background: BackgroundTasks) -> dict:
    """生成配乐（异步）"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    chapter = db.get_chapter(novel_id, chapter_num)
    if not chapter:
        raise HTTPException(404, "chapter not found")

    def _run():
        set_status(novel_id, "music", f"正在生成第{chapter_num}章配乐...")
        try:
            from ..stations.drama.music_engine import MusicEngine
            me = MusicEngine()
            settings = db.load_film_settings()
            result = me.run({
                "novel_id": novel_id,
                "chapter_num": chapter_num,
                "db": db,
                "provider": settings.get("music_provider", "ambient"),
                "api_key": settings.get("suno_api_key", ""),
            })
            mood = result.get("mood", "")
            set_status(novel_id, "idle", f"配乐完成: {mood}")
            return result
        except Exception as e:
            set_status(novel_id, "error", f"配乐失败: {str(e)[:100]}")

    background.add_task(_run)
    return {"status": "started", "message": f"第{chapter_num}章配乐生成中"}


@router.post("/{novel_id}/chapters/{chapter_num}/produce")
def produce_chapter(novel_id: str, chapter_num: int, background: BackgroundTasks) -> dict:
    """一键制片：配音 + 配乐 + 合成视频（异步）"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    chapter = db.get_chapter(novel_id, chapter_num)
    if not chapter:
        raise HTTPException(404, "chapter not found")
    sb = db.get_storyboard(novel_id, chapter_num)
    if not sb:
        raise HTTPException(404, "storyboard not found — 先生成分镜")

    def _run():
        set_status(novel_id, "producing", f"制片中: 第{chapter_num}章...")
        try:
            image_dir = f"data/images/{novel_id}/ch{chapter_num:03d}"
            voice_dir = f"data/voice/{novel_id}/ch{chapter_num:03d}"
            music_dir = f"data/music/{novel_id}"
            output_dir = f"data/video/{novel_id}"

            # 知识链：从分镜获取 AI Director 的决策知识（E2）
            accumulated_knowledge: list[dict] = []
            if sb:
                # 读取已存储的分镜知识（如果有）
                director_knowledge = sb.get("knowledge", [])
                if director_knowledge:
                    accumulated_knowledge.extend(director_knowledge)

            # Step 1: 画面生成（接收知识链）
            from ..stations.drama.image_generator import ImageGenerator
            set_status(novel_id, "producing", "步骤1/4: 生成画面...")
            img_provider, stability_key, dalle3_key = _get_image_config()
            comfyui_config = _get_comfyui_config() if img_provider == "comfyui" else None
            character_refs = _load_character_refs(novel_id) if img_provider == "comfyui" else {}
            ig = ImageGenerator()
            image_result = ig.run({
                "novel_id": novel_id, "chapter_num": chapter_num,
                "db": db, "output_dir": image_dir,
                "provider": img_provider, "api_key": stability_key,
                "dalle3_api_key": dalle3_key,
                "comfyui_config": comfyui_config,
                "character_refs": character_refs,
                "knowledge": accumulated_knowledge,
                "quality_config": _get_quality_config(),
            })
            # 收集画面生成的知识
            accumulated_knowledge.extend(image_result.get("knowledge", []))
            if image_result.get("status") != "ok":
                set_status(novel_id, "error",
                           f"画面生成失败: {image_result.get('reason', 'unknown')}")
                return {"images": image_result}

            # Step 2: 配音（接收知识链）
            from ..stations.drama.voice_engine import VoiceEngine
            set_status(novel_id, "producing", "步骤2/4: 生成配音...")
            ve = VoiceEngine()
            voice_result = ve.run({
                "novel_id": novel_id, "chapter_num": chapter_num,
                "db": db, "output_dir": voice_dir,
                "knowledge": accumulated_knowledge,
            })
            accumulated_knowledge.extend(voice_result.get("knowledge", []))
            if voice_result.get("status") != "ok":
                set_status(novel_id, "error",
                           f"配音失败: {voice_result.get('reason', 'unknown')}")
                return {"images": image_result, "voice": voice_result}

            # Step 3: 配乐（接收知识链）
            from ..stations.drama.music_engine import MusicEngine
            set_status(novel_id, "producing", "步骤3/4: 生成配乐...")
            me = MusicEngine()
            film_settings = db.load_film_settings()
            music_result = me.run({
                "novel_id": novel_id, "chapter_num": chapter_num,
                "db": db, "output_dir": music_dir,
                "provider": film_settings.get("music_provider", "ambient"),
                "api_key": film_settings.get("suno_api_key", ""),
                "knowledge": accumulated_knowledge,
            })
            accumulated_knowledge.extend(music_result.get("knowledge", []))
            if music_result.get("status") != "ok":
                set_status(novel_id, "error",
                           f"配乐失败: {music_result.get('reason', 'unknown')}")
                return {"images": image_result, "voice": voice_result, "music": music_result}
            music_path = music_result.get("music_path", "")

            # Step 4: 合成（接收完整知识链）
            from ..stations.drama.compositor import Compositor
            set_status(novel_id, "producing", "步骤4/4: 合成视频...")
            comp = Compositor()
            video_result = comp.run({
                "novel_id": novel_id, "chapter_num": chapter_num,
                "db": db,
                "image_dir": image_dir,
                "voice_dir": voice_dir,
                "music_path": music_path,
                "output_dir": output_dir,
                "subtitle_style": _get_subtitle_style(),
                "knowledge": accumulated_knowledge,
            })

            # 验证视频文件确实存在且可读
            video_path = video_result.get("video_path", "")
            if (video_result.get("status") == "ok"
                    and video_path
                    and Path(video_path).exists()
                    and Path(video_path).stat().st_size > 1000):
                dur = video_result.get("duration_sec", 0)
                size = video_result.get("file_size_mb", 0)
                skipped = len(video_result.get("skipped_shots", []))
                msg = f"制片完成: {dur:.0f}秒, {size}MB"
                if skipped:
                    msg += f" (跳过{skipped}个镜头)"
                set_status(novel_id, "idle", msg)
            else:
                reason = video_result.get("reason", "视频文件未生成")
                set_status(novel_id, "error", f"合成失败: {reason}")

            return {
                "images": image_result,
                "voice": voice_result,
                "music": music_result,
                "video": video_result,
            }
        except Exception as e:
            set_status(novel_id, "error", f"制片失败: {str(e)[:100]}")

    background.add_task(_run)
    return {"status": "started", "message": f"第{chapter_num}章一键制片中"}



# ═══════════════ ComfyUI + 角色参考图 ═══════════════


@router.get("/comfyui/test")
def test_comfyui_connection() -> dict:
    """测试 ComfyUI 连接"""
    config = _get_comfyui_config()
    from urllib.parse import urlparse
    parsed = urlparse(config.get("url", "http://127.0.0.1:8188"))
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8188

    from ..stations.drama.comfyui_client import ComfyUIClient
    client = ComfyUIClient(host=host, port=port)

    if client.health_check():
        stats = client.get_system_stats()
        return {
            "status": "ok",
            "connected": True,
            "url": config.get("url"),
            "system": stats.get("system", {}),
            "devices": stats.get("devices", []),
        }
    return {
        "status": "error",
        "connected": False,
        "url": config.get("url"),
        "reason": "ComfyUI 不可用，请检查是否已启动",
    }


@router.post("/{novel_id}/visual-bible/character-refs/generate")
def generate_character_refs(novel_id: str, background: BackgroundTasks) -> dict:
    """为角色生成参考图（异步，需要 ComfyUI）"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")

    def _run():
        set_status(novel_id, "generating", "正在生成角色参考图...")
        try:
            from ..stations.script.visual_bible import VisualBible
            vb = VisualBible()
            config = _get_comfyui_config()
            result = vb.generate_character_refs(
                novel_id=novel_id, db=db, comfyui_config=config, count_per_char=1,
            )
            count = result.get("count", 0)
            if result.get("status") == "ok":
                set_status(novel_id, "idle", f"角色参考图完成: {count} 张")
            else:
                set_status(novel_id, "error",
                           f"参考图失败: {result.get('reason', 'unknown')}")
            return result
        except Exception as e:
            set_status(novel_id, "error", f"参考图失败: {str(e)[:100]}")

    background.add_task(_run)
    return {"status": "started", "message": "角色参考图生成中"}


# ═══════════════ 批量制片 ═══════════════


@router.post("/{novel_id}/produce/batch")
def batch_produce(
    novel_id: str,
    start_chapter: int = 1,
    end_chapter: int = 1,
    background: BackgroundTasks = None,  # type: ignore[assignment]  # FastAPI injects
) -> dict:
    """批量制片：连续生成多章视频（异步）"""
    db = get_db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "novel not found")

    chapters = novel.get("chapters", [])
    max_ch = max((c.get("number", 0) for c in chapters), default=0)
    if start_chapter < 1 or end_chapter < start_chapter or end_chapter > max_ch:
        raise HTTPException(400, f"invalid range: {start_chapter}-{end_chapter} (max {max_ch})")

    total = end_chapter - start_chapter + 1

    def _run():
        set_status(novel_id, "batch_producing", f"批量制片: {total} 章...")
        img_provider, stability_key, dalle3_key = _get_image_config()
        comfyui_config = _get_comfyui_config() if img_provider == "comfyui" else None
        character_refs = _load_character_refs(novel_id) if img_provider == "comfyui" else {}
        subtitle_style = _get_subtitle_style()
        film_settings = db.load_film_settings()
        music_provider = film_settings.get("music_provider", "ambient")
        suno_key = film_settings.get("suno_api_key", "")
        quality_config = _get_quality_config()
        completed = 0
        failed = 0
        errors: list[str] = []

        for ch_num in range(start_chapter, end_chapter + 1):
            try:
                set_status(
                    novel_id, "batch_producing",
                    f"制片进度: {completed + 1}/{total} (第{ch_num}章)",
                    progress=completed,
                )

                image_dir = f"data/images/{novel_id}/ch{ch_num:03d}"
                voice_dir = f"data/voice/{novel_id}/ch{ch_num:03d}"
                music_dir = f"data/music/{novel_id}"
                output_dir = f"data/video/{novel_id}"

                # 知识链：每章独立积累（E2）
                ch_knowledge: list[dict] = []

                # Step 1: 画面
                from ..stations.drama.image_generator import ImageGenerator
                img_result = ImageGenerator().run({
                    "novel_id": novel_id, "chapter_num": ch_num,
                    "db": db, "output_dir": image_dir,
                    "provider": img_provider, "api_key": stability_key,
                    "dalle3_api_key": dalle3_key,
                    "comfyui_config": comfyui_config,
                    "character_refs": character_refs,
                    "knowledge": ch_knowledge,
                    "quality_config": quality_config,
                })
                ch_knowledge.extend(img_result.get("knowledge", []))
                if img_result.get("status") != "ok":
                    raise RuntimeError(f"画面失败: {img_result.get('reason', 'unknown')}")

                # Step 2: 配音
                from ..stations.drama.voice_engine import VoiceEngine
                voice_result = VoiceEngine().run({
                    "novel_id": novel_id, "chapter_num": ch_num,
                    "db": db, "output_dir": voice_dir,
                    "knowledge": ch_knowledge,
                })
                ch_knowledge.extend(voice_result.get("knowledge", []))
                if voice_result.get("status") != "ok":
                    raise RuntimeError(f"配音失败: {voice_result.get('reason', 'unknown')}")

                # Step 3: 配乐
                from ..stations.drama.music_engine import MusicEngine
                music_result = MusicEngine().run({
                    "novel_id": novel_id, "chapter_num": ch_num,
                    "db": db, "output_dir": music_dir,
                    "provider": music_provider, "api_key": suno_key,
                    "knowledge": ch_knowledge,
                })
                ch_knowledge.extend(music_result.get("knowledge", []))
                music_path = music_result.get("music_path", "")

                # Step 4: 合成
                from ..stations.drama.compositor import Compositor
                video_result = Compositor().run({
                    "novel_id": novel_id, "chapter_num": ch_num,
                    "db": db,
                    "image_dir": image_dir,
                    "voice_dir": voice_dir,
                    "music_path": music_path,
                    "output_dir": output_dir,
                    "subtitle_style": subtitle_style,
                    "knowledge": ch_knowledge,
                })

                video_path = video_result.get("video_path", "")
                if (video_result.get("status") == "ok"
                        and video_path
                        and Path(video_path).exists()
                        and Path(video_path).stat().st_size > 1000):
                    completed += 1
                else:
                    failed += 1
                    errors.append(f"第{ch_num}章: {video_result.get('reason', '合成失败')}")

            except Exception as e:
                failed += 1
                errors.append(f"第{ch_num}章: {str(e)[:80]}")

        detail = ""
        if errors:
            detail = " | " + "; ".join(errors[:3])
        set_status(
            novel_id, "idle",
            f"批量制片完成: {completed} 成功, {failed} 失败 (共{total}章){detail}",
        )

    if background is not None:
        background.add_task(_run)
    return {
        "status": "started",
        "message": f"批量制片: 第{start_chapter}-{end_chapter}章 ({total}章)",
        "total": total,
    }
