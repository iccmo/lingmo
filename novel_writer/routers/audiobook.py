"""听书路由 — TTS 语音合成、音频播放。"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audiobook"])

@router.get("/api/writer-voices")
def list_writer_voices() -> list:
    """List available writer voices."""
    from ..generator import WRITER_VOICES
    return [{"key": k, "name": v.name, "description": v.description} for k, v in WRITER_VOICES.items()]



@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/tts")
async def chapter_tts(novel_id: str, chapter_num: int, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%", pitch: str = "+0Hz") -> dict:
    """Stream chapter audio — cached MP3 (pre-generated in background)."""
    novel = get_db().get_novel(novel_id)
    if not novel: raise HTTPException(404)
    ch = get_db().get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404)
    content = ch.get("content", "") or ch.get("summary", "")
    if not content: raise HTTPException(400, "No content")

    text = content.replace("#", "").replace("*", "").replace("_", "").replace(">", "").replace("[", "").replace("]", "")
    text = text[:5000]

    import hashlib
    content_hash = hashlib.md5(text.encode()).hexdigest()[:12]
    rate_safe = rate.replace("+", "p").replace("-", "m").replace("%", "")
    cache_name = f"{novel_id}_ch{chapter_num}_{voice}_{rate_safe}_{content_hash}.mp3"
    cache_dir = Path(__file__).parent.parent.parent / "data" / "tts_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_name


    # Cache hit — instant
    if cache_path.exists():
        return FileResponse(str(cache_path), media_type="audio/mpeg",
                          headers={"Content-Disposition": f"inline; filename=ch{chapter_num}.mp3"})

    # Cache miss — generate on-the-fly
    try:
        await _generate_tts_async(text, voice, rate, str(cache_path))
        return FileResponse(str(cache_path), media_type="audio/mpeg",
                          headers={"Content-Disposition": f"inline; filename=ch{chapter_num}.mp3"})
    except Exception as e:
        raise HTTPException(500, f"TTS failed: {str(e)[:100]}")


# ═══════════════ Full-text Search ═══════════════

@router.get("/api/search")
def search_chapters(q: str = "", novel_id: str = "", limit: int = 20) -> dict:
    """Full-text search across all chapters or within a novel."""
    if not q or len(q) < 2:
        return {"results": [], "total": 0}

    with get_db().conn() as conn:
        if novel_id:
            rows = conn.execute("""
                SELECT c.novel_id, n.title as novel_title, c.number, c.title,
                       substr(c.content, max(0, instr(c.content, ?) - 40), 120) as snippet,
                       c.word_count
                FROM chapters c JOIN novels n ON n.id = c.novel_id
                WHERE c.novel_id = ? AND c.content LIKE ? AND c.word_count > 0
                ORDER BY c.number LIMIT ?
            """, (q, novel_id, '%' + q + '%', limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT c.novel_id, n.title as novel_title, c.number, c.title,
                       substr(c.content, max(0, instr(c.content, ?) - 40), 120) as snippet,
                       c.word_count
                FROM chapters c JOIN novels n ON n.id = c.novel_id
                WHERE c.content LIKE ? AND c.word_count > 0
                ORDER BY c.novel_id, c.number LIMIT ?
            """, (q, '%' + q + '%', limit)).fetchall()

        results = [{
            "novel_id": r["novel_id"], "novel_title": r["novel_title"],
            "chapter": r["number"], "title": r["title"],
            "snippet": r["snippet"], "word_count": r["word_count"],
        } for r in rows]

        count_row = conn.execute("SELECT COUNT(*) as cnt FROM chapters WHERE content LIKE ? AND word_count > 0",
            ('%' + q + '%',)).fetchone()
        return {"results": results, "total": count_row["cnt"] if count_row else 0}


# ═══════════════ App Settings Persistence ═══════════════

@router.post("/api/audio/sync")
def audio_sync(data: dict) -> dict:
    """Sync audio data from frontend localStorage to server DB."""
    try:
        if 'progress' in data and data['progress']:
            for p in data['progress']:
                get_db().save_audio_progress(p['novelId'], p['chapterNum'], p.get('position', 0))
        if 'bookmarks' in data and data['bookmarks']:
            get_db().save_audio_bookmarks(data['bookmarks'])
        if 'settings' in data and data['settings']:
            for k, v in data['settings'].items():
                get_db().save_audio_setting(k, str(v))
        if 'playlist' in data and data['playlist']:
            get_db().save_audio_playlist(data['playlist'])
        if 'stats' in data and data['stats']:
            get_db().save_audio_stats(data['stats'])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/audio/data")
def audio_load() -> dict:
    """Load all audio data from server DB."""
    try:
        db = get_db()
        bookmarks = db.load_audio_bookmarks()
        settings = db.load_audio_settings()
        playlist = db.load_audio_playlist()
        stats = db.load_audio_stats()
        progress = db.get_all_audio_progress()
        # Convert to frontend-friendly format
        return {
            "bookmarks": [{  "id": b['id'], "novelId": b['novel_id'], "novelTitle": b['novel_title'],
                "chapterNum": b['chapter_num'], "chapterTitle": b['chapter_title'],
                "position": b['position'], "note": b['note'], "tag": b['tag'],
                "createdAt": b.get('created_at', '')
            } for b in bookmarks],
            "progress": [{"novelId": p['novel_id'], "chapterNum": p['chapter_num'], "position": p['position_sec']} for p in progress],
            "settings": settings,
            "playlist": [{"novelId": p['novel_id'], "novelTitle": p['novel_title'], "chapterNum": p['chapter_num'], "chapterTitle": p['chapter_title']} for p in playlist],
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


async def _generate_tts_async(text: str, voice: str, rate: str, output_path: str):
    """Generate TTS audio: edge_tts → ffmpeg → MP3 file."""
    import os
    import subprocess
    import tempfile

    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    tmp_raw = tempfile.NamedTemporaryFile(delete=False, suffix=".adts")
    raw_path = tmp_raw.name
    tmp_raw.close()
    await communicate.save(raw_path)

    result = subprocess.run([
        "ffmpeg", "-y", "-i", raw_path,
        "-acodec", "libmp3lame", "-ar", "44100", "-ac", "2", "-ab", "128k",
        output_path,
    ], capture_output=True, timeout=30)
    os.unlink(raw_path)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:200]}")


@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/tts-dramatic")
async def chapter_tts_dramatic(novel_id: str, chapter_num: int, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%") -> dict:
    """Dramatic reading: single voice with pitch/rate variation per character."""
    novel = get_db().get_novel(novel_id)
    if not novel: raise HTTPException(404)
    ch = get_db().get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404)
    content = ch.get("content", "") or ch.get("summary", "")
    if not content: raise HTTPException(400, "No content")

    text = content.replace("#", "").replace("*", "").replace("_", "").replace(">", "").replace("[", "").replace("]", "")
    text = text[:5000]

    import hashlib
    content_hash = hashlib.md5(text.encode()).hexdigest()[:12]
    rate_safe = rate.replace("+", "p").replace("-", "m").replace("%", "")
    cache_name = f"{novel_id}_ch{chapter_num}_{voice}_{rate_safe}_dramatic_{content_hash}.mp3"
    cache_dir = Path(__file__).parent.parent.parent / "data" / "tts_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_name

    if cache_path.exists():
        return FileResponse(str(cache_path), media_type="audio/mpeg",
                          headers={"Content-Disposition": f"inline; filename=ch{chapter_num}_dramatic.mp3"})

    try:
        import os
        import re
        import subprocess
        import tempfile

        import edge_tts

        # Parse text into segments
        segments: list[tuple[str, str, str]] = []  # (text, pitch, rate)
        parts = re.split(r'(「[^」]*」)', text)

        for part in parts:
            if not part.strip():
                continue
            if part.startswith('「') and part.endswith('」'):
                # Dialogue — detect speaker type from nearby cues
                dialogue = part[1:-1]
                pitch, spd = _detect_voice_modulation(part, text)
                segments.append((dialogue, pitch, spd))
            else:
                # Narration
                segments.append((part, "+0Hz", rate))

        # Generate per-segment TTS
        seg_files: list[str] = []
        for i, (seg_text, seg_pitch, seg_rate) in enumerate(segments):
            if not seg_text.strip():
                continue
            communicate = edge_tts.Communicate(seg_text.strip(), voice, rate=seg_rate, pitch=seg_pitch)
            tmp_raw = tempfile.NamedTemporaryFile(delete=False, suffix=".adts")
            raw_path = tmp_raw.name
            tmp_raw.close()
            await communicate.save(raw_path)

            tmp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            mp3_path = tmp_mp3.name
            tmp_mp3.close()

            result = subprocess.run([
                "ffmpeg", "-y", "-i", raw_path,
                "-acodec", "libmp3lame", "-ar", "44100", "-ac", "2", "-ab", "128k",
                mp3_path,
            ], capture_output=True, timeout=30)
            os.unlink(raw_path)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg seg {i} failed: {result.stderr.decode()[:200]}")
            seg_files.append(mp3_path)

        # Concatenate all segments
        concat_list = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w")
        for sf in seg_files:
            concat_list.write(f"file '{sf}'\n")
        concat_list.close()

        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list.name,
            "-acodec", "copy", str(cache_path),
        ], capture_output=True, timeout=30)
        os.unlink(concat_list.name)

        # Cleanup segment files
        for sf in seg_files:
            try: os.unlink(sf)
            except: pass

        return FileResponse(str(cache_path), media_type="audio/mpeg",
                          headers={"Content-Disposition": f"inline; filename=ch{chapter_num}_dramatic.mp3"})
    except ImportError:
        raise HTTPException(500, "edge-tts not installed")
    except Exception as e:
        raise HTTPException(500, f"Dramatic TTS failed: {str(e)[:100]}")


def _detect_voice_modulation(dialogue: str, full_text: str) -> tuple[str, str]:
    """Detect speaker type from dialogue cues and return (pitch, rate)."""
    # Look for speaker cue in nearby text (before or after dialogue)
    combined = full_text

    # Male indicators
    if re.search(r'(他|男|父|兄|叔|爷|弟|君|公子|先生)(说|道|问|喊|吼|叫|怒|喝|冷笑|叹)', combined):
        return ("-5Hz", "-5%")
    # Female indicators
    if re.search(r'(她|女|母|姐|妹|姨|婆|娘|妃|小姐|姑娘|夫人)(说|道|问|喊|吼|叫|怒|喝|冷笑|叹)', combined):
        return ("+5Hz", "+3%")
    # Angry/shouting
    if re.search(r'(吼|怒|喝|斥|骂|叫|厉声|沉声|冷声)', combined):
        return ("-3Hz", "+10%")
    # Gentle/soft
    if re.search(r'(笑|轻|柔|叹|缓|慢|细|低声|悄声|温声|柔声)', combined):
        return ("+3Hz", "-5%")
    # Young/child
    if re.search(r'(小|童|孩|幼|少)(说|道|问|喊|叫)', combined):
        return ("+10Hz", "+10%")
    # Old/elder
    if re.search(r'(老|翁|媪|叟)(说|道|问)', combined):
        return ("-8Hz", "-8%")

    # Default: alternate based on dialogue position
    return ("+3Hz", "+3%") if hash(dialogue[:10]) % 2 == 0 else ("-3Hz", "-3%")


def _pregen_tts_background(novel_id: str, chapter_num: int):
    """Background task: pre-generate TTS for all voices at default speed."""
    try:
        novel = get_db().get_novel(novel_id)
        if not novel: return
        ch = get_db().get_chapter(novel_id, chapter_num)
        if not ch: return
        content = ch.get("content", "") or ch.get("summary", "")
        if not content: return

        text = content.replace("#", "").replace("*", "").replace("_", "").replace(">", "").replace("[", "").replace("]", "")
        text = text[:5000]

        import hashlib
        content_hash = hashlib.md5(text.encode()).hexdigest()[:12]
        cache_dir = Path(__file__).parent.parent.parent / "data" / "tts_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Pre-generate with default voice at 1x speed
        voice = "zh-CN-XiaoxiaoNeural"
        rate = "+0%"
        rate_safe = rate.replace("+", "p").replace("-", "m").replace("%", "")
        cache_name = f"{novel_id}_ch{chapter_num}_{voice}_{rate_safe}_{content_hash}.mp3"
        cache_path = cache_dir / cache_name

        if not cache_path.exists():
            print(f"[TTS-PREGEN] Generating {novel_id} ch{chapter_num}...")
            import asyncio
            asyncio.run(_generate_tts_async(text, voice, rate, str(cache_path)))
            print(f"[TTS-PREGEN] Done: {cache_path.name}")
    except Exception as e:
        print(f"[TTS-PREGEN] Failed: {e}")

@router.get("/api/novels/{novel_id}/voice-profile")
def get_voice_profile(novel_id: str) -> dict:
    """Get voice profile samples for a novel."""
    db = get_db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    return {"samples": db.get_voice_samples(novel_id)}


# ═══════════════ Cost Ledger API (§50) ═══════════════
