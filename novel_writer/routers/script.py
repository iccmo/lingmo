"""
剧本路由 — 视觉圣经、AI 导演分镜、Prompt 生成。

包含：视觉圣经、分镜脚本、画面 Prompt、角色参考图管理、导出。
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .deps import get_db, set_status

router = APIRouter(prefix="/api/novels", tags=["script"])

# ═══════════════ AI Film Studio: 视觉圣经 + 分镜 + Prompt ═══════════════


@router.get("/{novel_id}/visual-bible")
def get_visual_bible(novel_id: str) -> dict:
    """获取视觉圣经（角色视觉描述集合）"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    chars = db.get_visual_characters(novel_id)
    return {"novel_id": novel_id, "characters": chars, "count": len(chars)}


@router.post("/{novel_id}/visual-bible/generate")
def generate_visual_bible(novel_id: str, background: BackgroundTasks) -> dict:
    """生成视觉圣经（异步）"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")

    def _run():
        set_status(novel_id, "generating", "正在生成视觉圣经...")
        try:
            from ..stations.script.visual_bible import VisualBible
            vb = VisualBible()
            result = vb.run({"novel_id": novel_id, "db": db, "force": False})
            set_status(novel_id, "idle", f"视觉圣经完成: {result.get('generated', 0)} 个角色")
            return result
        except Exception as e:
            set_status(novel_id, "error", f"视觉圣经失败: {str(e)[:100]}")

    background.add_task(_run)
    return {"status": "started", "message": "视觉圣经生成中"}


@router.get("/{novel_id}/chapters/{chapter_num}/storyboard")
def get_storyboard(novel_id: str, chapter_num: int) -> dict:
    """获取分镜脚本"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    sb = db.get_storyboard(novel_id, chapter_num)
    if not sb:
        raise HTTPException(404, "storyboard not found")
    return sb


@router.get("/{novel_id}/chapters/{chapter_num}/shots")
def get_shots_with_images(novel_id: str, chapter_num: int) -> dict:
    """获取镜头列表（含图片路径和起始时间），用于视频预览缩略图时间轴"""
    from pathlib import Path

    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    sb = db.get_storyboard(novel_id, chapter_num)
    if not sb or not sb.get("shots"):
        raise HTTPException(404, "storyboard not found")

    shots = sb["shots"]
    image_dir = f"data/images/{novel_id}/ch{chapter_num:03d}"
    result = []
    cumulative_time = 0.0

    for shot in shots:
        shot_id = shot.get("shot_id", "")
        duration = float(shot.get("duration_sec", 3.0))
        subject = shot.get("subject", "")

        # 查找已生成的图片
        image_path = ""
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = os.path.join(image_dir, f"{shot_id}{ext}")
            if Path(candidate).exists():
                image_path = candidate
                break

        result.append({
            "shot_id": shot_id,
            "duration_sec": duration,
            "start_time": round(cumulative_time, 2),
            "subject": subject,
            "image_path": image_path,
            "shot_type": shot.get("shot_type", "medium"),
            "emotion": shot.get("emotion", ""),
        })
        cumulative_time += duration

    return {
        "shots": result,
        "total_duration": round(cumulative_time, 2),
    }


@router.post("/{novel_id}/chapters/{chapter_num}/storyboard/generate")
def generate_storyboard(novel_id: str, chapter_num: int, background: BackgroundTasks) -> dict:
    """生成分镜脚本（异步）"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    chapter = db.get_chapter(novel_id, chapter_num)
    if not chapter:
        raise HTTPException(404, "chapter not found")

    def _run():
        set_status(novel_id, "directing", f"AI导演: 第{chapter_num}章分镜...")
        try:
            from ..stations.script.ai_director import AIDirector
            director = AIDirector()
            result = director.run({
                "novel_id": novel_id,
                "chapter_num": chapter_num,
                "db": db,
                "content": chapter.get("content", ""),
            })
            if result.get("status") == "ok":
                set_status(novel_id, "idle",
                    f"分镜完成: {result.get('shots_count', 0)} 个镜头, {result.get('total_duration', 0):.0f}秒")
            else:
                set_status(novel_id, "error", f"分镜失败: {result.get('reason', 'unknown')}")
            return result
        except Exception as e:
            set_status(novel_id, "error", f"分镜失败: {str(e)[:100]}")

    background.add_task(_run)
    return {"status": "started", "message": f"第{chapter_num}章分镜生成中"}


@router.get("/{novel_id}/chapters/{chapter_num}/prompts")
def get_image_prompts(novel_id: str, chapter_num: int) -> dict:
    """获取画面 Prompt 列表"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    sb = db.get_storyboard(novel_id, chapter_num)
    if not sb:
        raise HTTPException(404, "storyboard not found — 先生成分镜")

    from ..stations.script.prompt_generator import PromptGenerator
    pg = PromptGenerator()
    # 从分镜获取 AI Director 的决策知识（E2: 知识传递）
    director_knowledge = sb.get("knowledge", []) if sb else []
    result = pg.run({
        "novel_id": novel_id, "chapter_num": chapter_num, "db": db,
        "knowledge": director_knowledge,
    })
    return result


@router.post("/{novel_id}/chapters/{chapter_num}/prompts/generate")
def generate_image_prompts(novel_id: str, chapter_num: int) -> dict:
    """生成画面 Prompt（同步，纯规则无需异步）"""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")

    from ..stations.script.prompt_generator import PromptGenerator
    pg = PromptGenerator()
    sb = db.get_storyboard(novel_id, chapter_num)
    director_knowledge = sb.get("knowledge", []) if sb else []
    result = pg.run({
        "novel_id": novel_id, "chapter_num": chapter_num, "db": db,
        "knowledge": director_knowledge,
    })
    return result



@router.post("/{novel_id}/visual-bible/character-refs/upload")
def upload_character_ref(novel_id: str, char_key: str, file: bytes) -> dict:
    """手动上传角色参考图"""

    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")

    ref_dir = f"data/character_refs/{novel_id}/{char_key}"
    os.makedirs(ref_dir, exist_ok=True)

    filename = f"ref_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.join(ref_dir, filename)
    with open(save_path, "wb") as f:
        f.write(file)

    # 更新 visual_characters.reference_images
    visual_chars = db.get_visual_characters(novel_id)
    for vc in visual_chars:
        if vc.get("char_key") == char_key:
            refs = vc.get("reference_images", [])
            refs.append(save_path)
            updated = dict(vc)
            updated["reference_images"] = refs
            db.save_visual_character(novel_id, char_key, updated)
            return {
                "status": "ok",
                "char_key": char_key,
                "path": save_path,
                "total_refs": len(refs),
            }

    return {"status": "error", "reason": f"character {char_key} not found"}



# ═══════════════ 导出功能 ═══════════════


@router.get("/{novel_id}/chapters/{chapter_num}/storyboard/export")
def export_storyboard(novel_id: str, chapter_num: int) -> dict:
    """导出分镜为 ZIP（每张 shot 一张 PNG 卡片）"""
    from fastapi.responses import StreamingResponse

    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    sb = db.get_storyboard(novel_id, chapter_num)
    if not sb:
        raise HTTPException(404, "storyboard not found")

    import io
    import zipfile

    from PIL import Image, ImageDraw, ImageFont

    shot_colors = {
        "close-up": (0x2C, 0x18, 0x10),
        "medium": (0x1A, 0x1A, 0x2E),
        "wide": (0x0D, 0x1B, 0x2A),
        "extreme-wide": (0x0A, 0x0A, 0x14),
    }
    shot_labels = {"close-up": "特写", "medium": "中景", "wide": "全景", "extreme-wide": "远景"}

    # 字体
    font = None
    font_small = None
    for fp in ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"):
        if Path(fp).exists():
            try:
                font = ImageFont.truetype(fp, 28)
                font_small = ImageFont.truetype(fp, 20)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()  # type: ignore[assignment]
        font_small = font

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for shot in sb.get("shots", []):
            shot_id = shot.get("shot_id", "unknown")
            shot_type = shot.get("shot_type", "medium")
            bg = shot_colors.get(shot_type, shot_colors["medium"])

            img = Image.new("RGB", (1080, 600), bg)
            draw = ImageDraw.Draw(img)

            # 标签
            label = shot_labels.get(shot_type, shot_type)
            draw.rectangle([(20, 20), (140, 56)], fill=(255, 255, 255, 30))
            draw.text((30, 24), f"{shot_id} {label}", fill=(255, 255, 255), font=font_small)

            # 主体描述
            subject = shot.get("subject", "")
            if subject:
                draw.text((30, 80), subject[:60], fill=(255, 255, 255), font=font)

            # 对白
            dialogue = shot.get("dialogue", "")
            if dialogue:
                draw.text((30, 140), f'"{dialogue[:50]}"', fill=(0x88, 0xCC, 0xFF), font=font_small)

            # 元信息
            meta_parts = []
            if shot.get("emotion"):
                meta_parts.append(shot["emotion"])
            if shot.get("camera_move"):
                meta_parts.append(shot["camera_move"])
            if shot.get("duration_sec"):
                meta_parts.append(f'{shot["duration_sec"]}s')
            if meta_parts:
                draw.text((30, 540), " · ".join(meta_parts), fill=(150, 150, 150), font=font_small)

            img_buf = io.BytesIO()
            img.save(img_buf, "PNG")
            zf.writestr(f"{shot_id}.png", img_buf.getvalue())

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="storyboard_ch{chapter_num:03d}.zip"'},
    )


@router.get("/{novel_id}/visual-bible/export")
def export_visual_bible(novel_id: str) -> dict:
    """导出角色卡片为 ZIP"""
    from fastapi.responses import StreamingResponse

    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "novel not found")
    chars = db.get_visual_characters(novel_id)
    if not chars:
        raise HTTPException(404, "no visual characters found")

    import io
    import zipfile

    from PIL import Image, ImageDraw, ImageFont

    font = None
    font_small = None
    for fp in ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"):
        if Path(fp).exists():
            try:
                font = ImageFont.truetype(fp, 24)
                font_small = ImageFont.truetype(fp, 18)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()  # type: ignore[assignment]
        font_small = font

    def _hex_to_rgb(h: str) -> tuple[int, int, int]:
        h = h.strip().lstrip("#")
        if len(h) >= 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        return (100, 100, 100)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for char in chars:
            name = char.get("char_key", "unknown")
            palette_str = char.get("color_palette", "#666666")
            primary_color = _hex_to_rgb(palette_str.split(",")[0])

            img = Image.new("RGB", (800, 500), primary_color)
            draw = ImageDraw.Draw(img)

            # 名称
            draw.text((30, 20), name, fill=(255, 255, 255), font=font)

            # 信息
            y = 70
            for label, key in [("外貌", "appearance"), ("服装", "costume"),
                                ("表情", "default_expression"), ("声音", "voice_character")]:
                val = char.get(key, "")
                if val:
                    draw.text((30, y), f"{label}:", fill=(200, 200, 200), font=font_small)
                    # 自动换行
                    line = ""
                    for ch_val in val:
                        line += ch_val
                        if len(line) >= 35:
                            y += 28
                            draw.text((60, y), line, fill=(255, 255, 255), font=font_small)
                            line = ""
                    if line:
                        y += 28
                        draw.text((60, y), line, fill=(255, 255, 255), font=font_small)
                    y += 36

            img_buf = io.BytesIO()
            img.save(img_buf, "PNG")
            zf.writestr(f"{name}.png", img_buf.getvalue())

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="visual_bible_{novel_id}.zip"'},
    )
