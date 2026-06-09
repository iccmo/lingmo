"""Narrative and reader-state diagnostic endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from novel_writer.routers.deps import get_db
from novel_writer.routers.novel.request_validation import text_field

from . import _legacy

router = APIRouter(tags=["agent-diagnostics"])


def _db():
    return get_db()


def _novel_or_404(novel_id: str) -> dict:
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    return novel


def _generated_chapters(novel: dict) -> list[dict]:
    """Return only chapters with real body text; outline placeholders distort diagnostics."""
    return [
        chapter
        for chapter in novel.get("chapters", [])
        if (chapter.get("word_count", 0) or 0) > 0 and (chapter.get("content", "") or "").strip()
    ]


@router.get("/api/novels/{novel_id}/pre-understanding")
def pre_understanding(novel_id: str) -> dict:
    """Simulate novice, veteran, and critic pre-understanding."""
    novel = _novel_or_404(novel_id)
    db = _db()
    genre = novel.get("genre", "") or ""
    text_parts = []
    for chapter in _generated_chapters(novel):
        full = db.get_chapter(novel_id, chapter["number"])
        if full and full.get("content"):
            text_parts.append(full["content"])
    all_text = " ".join(text_parts) or novel.get("synopsis", "") or ""

    tropes = _legacy.GENRE_TROPES.get(genre, _legacy.GENRE_TROPES_DEFAULT)
    novice_hits = sum(1 for trope in tropes if trope in all_text)
    novice_score = min(100, round(novice_hits / max(1, len(tropes)) * 100))

    veteran_hits = 0
    for trope in tropes:
        for match in re.finditer(re.escape(trope), all_text):
            after = all_text[match.end() : match.end() + 60]
            if any(signal in after for signal in _legacy.SUBVERSION_SIGNALS):
                veteran_hits += 1
                break
    veteran_score = min(100, round(veteran_hits / max(1, len(tropes)) * 100))

    critic_raw = 0
    for signals in _legacy.NARRATIVE_SIGNALS.values():
        for signal in signals:
            critic_raw += all_text.count(signal)
    critic_score = min(100, critic_raw * 3)

    if veteran_score > novice_score:
        suggested = f"资深读者感知到{veteran_score}%的反套路——建议继续强化反套路叙事，当前套路符合度仅{novice_score}%"
    elif critic_score > 50:
        suggested = f"叙事技巧密度较高({critic_score}%)——适合文学向读者，但可能牺牲可读性，建议适度简化"
    elif novice_score > 70:
        suggested = f"套路符合度高({novice_score}%)——新手读者友好，建议加入{veteran_hits}个反套路点提升老读者体验"
    else:
        suggested = "建议明确体裁定位，增加核心套路元素以匹配读者预期"

    return {
        "novice_score": novice_score,
        "veteran_score": veteran_score,
        "critic_score": critic_score,
        "suggested_adjustment": suggested,
        "genre": genre,
    }


@router.get("/api/novels/{novel_id}/psych-time")
def psych_time(novel_id: str, chapter: int) -> dict:
    """Estimate reading time versus story time for a chapter."""
    ch = _db().get_chapter(novel_id, chapter)
    if not ch:
        raise HTTPException(404)
    content = ch.get("content", "") or ""
    story_minutes = sum(content.count(marker) * minutes for marker, minutes in _legacy.TIME_MARKERS.items())
    chars = len(content.replace(" ", "").replace("\n", ""))
    reading_seconds = round(chars / 400 * 60)
    time_stretch_ratio = round(story_minutes / (reading_seconds / 60), 2) if reading_seconds > 0 else 0.0
    if time_stretch_ratio > 10:
        assessment = "高度压缩——故事时间远大于阅读时间（跳跃式叙事）"
    elif time_stretch_ratio > 1:
        assessment = "适度拉伸——故事时间与阅读时间接近，场景描写较充分"
    elif time_stretch_ratio > 0.1:
        assessment = "实时叙事——阅读时间接近故事时间，接近'实时'体验"
    else:
        assessment = "时间膨胀——大量描写/内心活动，阅读时间远超故事时间"
    return {
        "story_minutes": round(story_minutes, 1),
        "reading_seconds": reading_seconds,
        "time_stretch_ratio": time_stretch_ratio,
        "assessment": assessment,
        "chapter": chapter,
    }


@router.get("/api/novels/{novel_id}/attention-curve")
def attention_curve(novel_id: str, chapter: int) -> dict:
    """Model reader attention across a chapter in 200-char windows."""
    ch = _db().get_chapter(novel_id, chapter)
    if not ch:
        raise HTTPException(404)
    content = ch.get("content", "") or ""
    if not content:
        return {"curve": [], "min_attention": 0, "recovery_points": 0, "chapter": chapter}

    attention = 100.0
    curve = []
    recovery_points = 0
    min_attention = 100.0
    for index in range(0, len(content), 200):
        window = content[index : index + 200]
        if any(hook in window for hook in _legacy.ATTENTION_HOOKS):
            attention = 90.0
            recovery_points += 1
        else:
            attention = max(10.0, attention - 15.0)
        curve.append({"char_position": index, "attention_level": round(attention, 1)})
        min_attention = min(min_attention, attention)
    return {
        "curve": curve,
        "min_attention": round(min_attention, 1),
        "recovery_points": recovery_points,
        "chapter": chapter,
        "total_windows": len(curve),
    }


@router.get("/api/novels/{novel_id}/expectation-check")
def expectation_check(novel_id: str) -> dict:
    """Check genre contract compliance in the first three chapters."""
    novel = _novel_or_404(novel_id)
    db = _db()
    genre = novel.get("genre", "") or ""
    expected = _legacy.GENRE_CONTRACT.get(genre, _legacy.GENRE_CONTRACT_DEFAULT)
    text_parts = []
    for chapter in _generated_chapters(novel)[:3]:
        full = db.get_chapter(novel_id, chapter["number"])
        if full and full.get("content"):
            text_parts.append(full["content"])
    all_text = " ".join(text_parts) or novel.get("synopsis", "") or ""
    found = [element for element in expected if element in all_text]
    missing = [element for element in expected if element not in all_text]
    fulfillment_pct = round(len(found) / max(1, len(expected)) * 100)
    return {
        "genre": genre,
        "expected_elements": expected,
        "found_elements": found,
        "missing_elements": missing,
        "fulfillment_pct": fulfillment_pct,
        "contract_status": "fulfilled" if fulfillment_pct >= 80 else "partial" if fulfillment_pct >= 50 else "breached",
    }


@router.post("/api/text/touch-analysis")
def touch_analysis(data: dict) -> dict:
    """Analyze what sensory memory channels a text opens."""
    text = data.get("text", "")
    if not text:
        raise HTTPException(400, "text is required")
    channels = [
        {"name": "温暖", "strength": min(100, sum(text.count(signal) for signal in _legacy.WARMTH_SIGNALS) * 15)},
        {"name": "关怀", "strength": min(100, sum(text.count(signal) for signal in _legacy.CARE_SIGNALS) * 10)},
        {"name": "疼痛", "strength": min(100, sum(text.count(signal) for signal in _legacy.PAIN_SIGNALS) * 10)},
    ]
    dominant = max(channels, key=lambda channel: channel["strength"])
    if dominant["strength"] < 20:
        assessment = "文字距离较远，感官通道未充分打开——建议增加触觉细节"
    elif dominant["name"] == "疼痛":
        assessment = "疼痛通道主导——文字有强烈的身体感，读者易被卷入"
    elif dominant["name"] == "温暖":
        assessment = "温暖通道主导——营造安全/治愈氛围"
    else:
        assessment = "关怀通道主导——角色间的互动感强烈"
    return {"channels": channels, "dominant_channel": dominant["name"], "assessment": assessment}


@router.post("/api/text/negative-space")
def negative_space(data: dict) -> dict:
    """Estimate what the reader fills in: unsaid or implied content."""
    text = data.get("text", "")
    if not text:
        raise HTTPException(400, "text is required")
    sentences = [sentence.strip() for sentence in re.split(r"[。！？；\n]", text) if sentence.strip()]
    if not sentences:
        return {
            "gap_count": 0,
            "gap_density": 0,
            "optimal_zone": "under",
            "breakdown": {"action_gaps": 0, "emotional_gaps": 0, "info_gaps": 0},
            "total_sentences": 0,
        }
    action_pattern = re.compile(r"[打走跑跳拿放推拉开关杀砍刺射拔穿脱吃喝说喊叫哭笑坐站躺跪爬飞落升降进出]")
    emotion_words = [
        "喜", "怒", "哀", "乐", "悲", "恐", "惊", "忧", "愁", "恨",
        "高兴", "难过", "愤怒", "害怕", "紧张", "兴奋", "失望", "感动",
        "幸福", "痛苦", "焦虑", "恐惧", "开心", "伤心",
    ]
    action_gaps = sum(1 for sentence in sentences if len(action_pattern.findall(sentence)) >= 3)
    emotional_gaps = sum(
        1
        for sentence in sentences
        if action_pattern.search(sentence) and not any(word in sentence for word in emotion_words)
    )
    question_count = sum(1 for sentence in sentences if sentence.endswith("？"))
    answer_count = sum(text.count(signal) for signal in ["因为", "所以", "于是", "原来", "其实", "结果"])
    info_gaps = max(0, question_count - answer_count)
    total_gaps = action_gaps + emotional_gaps + info_gaps
    gap_density = round(total_gaps / len(sentences), 2)
    return {
        "gap_count": total_gaps,
        "gap_density": gap_density,
        "optimal_zone": "under" if gap_density < 0.1 else "over" if gap_density > 0.5 else "optimal",
        "breakdown": {"action_gaps": action_gaps, "emotional_gaps": emotional_gaps, "info_gaps": info_gaps},
        "total_sentences": len(sentences),
    }


@router.get("/api/novels/{novel_id}/neg-space-health")
def neg_space_health(novel_id: str) -> dict:
    """Check if later chapters consume negative space created earlier."""
    novel = _novel_or_404(novel_id)
    db = _db()
    chapters = _generated_chapters(novel)
    if len(chapters) < 2:
        return {"intact_spaces": 0, "consumed_spaces": 0, "health": "healthy", "total_chapters": len(chapters), "note": "章节不足，无法判断"}

    mystery_signals = ["？", "神秘", "未知", "秘密", "谜", "不为人知", "隐藏", "到底", "究竟", "为何", "为什么", "是谁", "什么东西", "怎么回事"]
    reveal_signals = ["原来", "真相", "其实", "揭秘", "答案", "原因是", "真相是", "竟然是"]
    early_text = " ".join(
        full.get("content", "")
        for chapter in chapters[:3]
        for full in [db.get_chapter(novel_id, chapter["number"])]
        if full and full.get("content")
    )
    later_text = " ".join(
        full.get("content", "")
        for chapter in chapters[3:]
        for full in [db.get_chapter(novel_id, chapter["number"])]
        if full and full.get("content")
    )
    mystery_count = sum(1 for signal in mystery_signals if signal in early_text)
    reveal_count = sum(1 for signal in reveal_signals if signal in later_text)
    intact_spaces = max(0, mystery_count - reveal_count)
    consumed_spaces = min(mystery_count, reveal_count)
    return {
        "intact_spaces": intact_spaces,
        "consumed_spaces": consumed_spaces,
        "health": "depleting" if mystery_count > 0 and consumed_spaces >= mystery_count * 0.7 else "healthy",
        "total_chapters": len(chapters),
    }


@router.get("/api/novels/{novel_id}/wound-arc")
def get_wound_arc(novel_id: str) -> dict:
    """Track the narrative wound arc across chapters."""
    _novel_or_404(novel_id)
    db = _db()
    timeline = db.get_timeline(novel_id)
    costs = db.get_cost_ledger(novel_id)
    losses = [entry for entry in costs if entry.get("loss")]
    wound_score = len(losses) / max(1, len(timeline)) if timeline else 0

    char_losses: dict[str, int] = {}
    for entry in costs:
        if entry.get("loss") and entry.get("character_name"):
            char_losses[entry["character_name"]] = char_losses.get(entry["character_name"], 0) + 1
    primary = max(char_losses, key=lambda key: char_losses[key]) if char_losses else "未知"

    return {
        "primary_carrier": primary,
        "wound_score": round(wound_score, 2),
        "total_losses": len(losses),
        "arc_stage": "深化" if wound_score > 0.3 else "建立" if wound_score > 0 else "未启动",
        "suggestion": "伤口足够深，可以开始愈合弧线" if wound_score > 0.3 else "需要更多代价来建立伤口深度",
    }


@router.get("/api/novels/{novel_id}/energy-form")
def get_energy_form(novel_id: str) -> dict:
    """Track energy transformation across chapters."""
    _novel_or_404(novel_id)
    db = _db()
    timeline = db.get_timeline(novel_id)
    costs = db.get_cost_ledger(novel_id)
    chars = db.get_character_state(novel_id)
    if not timeline:
        return {"current": "潜在", "history": [], "suggestion": "故事尚未开始"}

    recent_losses = [entry for entry in costs if entry.get("loss")][-3:]
    recent_emotions = [char.get("emotion", "") for char in chars[-5:] if char.get("emotion")]
    if any("愤怒" in emotion or "恨" in emotion for emotion in recent_emotions):
        current = "动能"
    elif len(recent_losses) >= 2:
        current = "势能"
    elif any("悲伤" in emotion or "悔" in emotion for emotion in recent_emotions):
        current = "热"
    elif len(costs) > len(timeline) * 0.5:
        current = "爆炸"
    else:
        current = "潜在"

    return {
        "current": current,
        "chapter_count": len(timeline),
        "loss_density": round(len(recent_losses) / max(1, len(timeline)), 2),
        "suggestion": (
            "能量积累充足，适合释放（高潮章节）"
            if current == "势能"
            else "能量正在释放，注意释放后的余波处理"
            if current == "爆炸"
            else "能量平稳，适合推进或铺垫"
        ),
    }


@router.get("/api/novels/{novel_id}/self-check")
def system_self_check(novel_id: str) -> dict:
    """Run data-driven self-checks and return a unified confidence report."""
    _novel_or_404(novel_id)
    db = _db()
    results = {}
    confidence = 100

    chars = db.get_character_state(novel_id)
    results["bible"] = {"status": "ok" if chars else "empty", "chars": len(chars)}
    if not chars:
        confidence -= 25

    foreshadowing = db.get_active_foreshadowing(novel_id)
    overdue = [item for item in foreshadowing if item.get("status") == "overdue"]
    results["foreshadowing"] = {"active": len(foreshadowing), "overdue": len(overdue)}
    if overdue:
        confidence -= len(overdue) * 10

    issues = db.get_consistency_log(novel_id)
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    unfixed = [issue for issue in issues if not issue.get("was_fixed")]
    results["consistency"] = {"total": len(issues), "errors": len(errors), "unfixed": len(unfixed)}
    confidence -= len(errors) * 15 - len([issue for issue in issues if issue.get("was_fixed")]) * 10

    costs = db.get_cost_ledger(novel_id)
    gains = len([entry for entry in costs if entry.get("gain")])
    losses = len([entry for entry in costs if entry.get("loss")])
    balance = gains - losses
    results["costs"] = {"gains": gains, "losses": losses, "balance": balance}
    if abs(balance) > 3:
        confidence -= 10

    voice = db.get_voice_samples(novel_id)
    results["voice"] = {"samples": len(voice)}
    if not voice:
        confidence -= 5
    results["unsaid"] = {"entries": len(db.get_unsaid(novel_id))}

    confidence = max(0, min(100, confidence))
    return {
        "results": results,
        "confidence": confidence,
        "grade": "S" if confidence >= 90 else "A" if confidence >= 75 else "B" if confidence >= 60 else "C" if confidence >= 40 else "D",
        "ready_for_next": confidence >= 60,
    }


@router.get("/api/novels/{novel_id}/reader-state")
def get_reader_state(novel_id: str) -> dict:
    novel = _novel_or_404(novel_id)
    db = _db()
    known = [
        {"name": char["char_name"], "emotion": char.get("emotion", "")}
        for char in db.get_character_state(novel_id)[-5:]
    ]
    active_fs = db.get_active_foreshadowing(novel_id)
    expecting = [{"desc": item["description"][:60], "due": item.get("due_by_chapter")} for item in active_fs[:3]]
    costs = db.get_cost_ledger(novel_id)
    gains = len([entry for entry in costs if entry.get("gain")])
    losses = len([entry for entry in costs if entry.get("loss")])
    return {
        "current_chapter": novel.get("total_chapters", 0),
        "known_characters": known,
        "expecting": expecting,
        "cost_balance": {"gains": gains, "losses": losses},
        "reader_mood": "engaged" if len(expecting) >= 2 else "drifting",
        "suggestion": "读者期待值高" if len(expecting) >= 2 else "可推进主线",
    }


@router.get("/api/novels/{novel_id}/narrative-distance")
def get_narrative_distance(novel_id: str) -> dict:
    """Measure immersion versus observation distance in recent chapters."""
    novel = _novel_or_404(novel_id)
    total = novel.get("total_chapters", 0)
    if total == 0:
        return {"distance_0_pct": 0, "distance_1_pct": 0, "distance_2_pct": 0, "assessment": "无章节数据"}

    db = _db()
    texts = []
    for number in range(max(1, total - 2), total + 1):
        chapter = db.get_chapter(novel_id, number)
        if chapter:
            texts.append(chapter.get("content", ""))
    all_text = " ".join(texts)
    if len(all_text) < 50:
        return {"distance_0_pct": 0, "distance_1_pct": 0, "distance_2_pct": 0, "assessment": "内容不足"}

    first_person = len(re.findall(r"我|我的|我们", all_text))
    sensory = len(re.findall(r"疼|痛|冷|热|凉|暖|触|摸|碰|气味|味道|听见|闻到", all_text))
    interior = len(re.findall(r"想|觉得|知道|明白|心里|暗自|心底|记得|忘了", all_text))
    immersion = first_person + sensory + interior

    third_person = len(re.findall(r"他|她|他们|她们|它", all_text))
    visual = len(re.findall(r"看|见|望|看见|望去|凝望|远望|眺|盯|瞪", all_text))
    measurement = len(re.findall(r"米|公里|步|分钟|小时|秒|丈|尺|寸", all_text))
    observation = third_person + visual + measurement

    total_signals = immersion + observation
    if total_signals == 0:
        return {"distance_0_pct": 0, "distance_1_pct": 0, "distance_2_pct": 0, "assessment": "无法判定"}

    d0 = round(immersion / total_signals * 100, 1)
    d2 = round(observation / total_signals * 100, 1)
    d1 = round(100 - d0 - d2, 1)
    if d0 > 55:
        assessment = "近距离主导：读者高度沉浸于角色感知"
    elif d2 > 55:
        assessment = "远距离主导：叙述者保持旁观距离"
    else:
        assessment = "中距离：沉浸与观察交替"
    return {"distance_0_pct": d0, "distance_1_pct": max(0, d1), "distance_2_pct": d2, "assessment": assessment}


@router.get("/api/novels/{novel_id}/info-gradient")
def get_info_gradient(novel_id: str, chapter: int = 0) -> dict:
    """Analyze dialogue for information asymmetry between characters."""
    novel = _novel_or_404(novel_id)
    total = novel.get("total_chapters", 0)
    if total == 0:
        return {"gradient_level": 1, "hot_spots": [], "assessment": "无章节数据"}

    target = chapter if chapter > 0 else total
    ch = _db().get_chapter(novel_id, target)
    if not ch:
        raise HTTPException(404, f"Chapter {target} not found")
    content = ch.get("content", "")
    if len(content) < 50:
        return {"gradient_level": 1, "hot_spots": [], "assessment": "内容不足"}

    dialogues = re.compile(r'[「『"](.+?)[」』"]').findall(content)
    negation_markers = r"没说|没有说|不说|沉默|其实|真正|不是你想的那样|不是那样的|不是这样"
    subtext_markers = r"弦外之音|言外之意|话中有话|暗示|言下之意|暗指|别有深意|意味深长"
    hot_spots = []
    gradient_score = 0
    for dialogue in dialogues:
        if len(dialogue) < 5:
            continue
        count = len(re.findall(negation_markers, dialogue)) + len(re.findall(subtext_markers, dialogue))
        if count > 0:
            hot_spots.append(dialogue[:80] + ("..." if len(dialogue) > 80 else ""))
            gradient_score += count

    if len(dialogues) == 0:
        gradient_level = 1
    elif gradient_score >= 6:
        gradient_level = 5
    elif gradient_score >= 4:
        gradient_level = 4
    elif gradient_score >= 2:
        gradient_level = 3
    elif gradient_score >= 1:
        gradient_level = 2
    else:
        gradient_level = 1
    level_labels = {1: "信息透明", 2: "轻微不对称", 3: "明显不对称", 4: "高度不对称", 5: "信息极致失衡"}
    return {
        "gradient_level": gradient_level,
        "hot_spots": hot_spots[:10],
        "dialogue_count": len(dialogues),
        "assessment": f"{len(hot_spots)}处信息不对称，梯度等级{gradient_level}：{level_labels[gradient_level]}",
    }


@router.get("/api/novels/{novel_id}/pov-shifts")
def get_pov_shifts(novel_id: str) -> dict:
    """Detect dominant POV character and shifts between chapters."""
    novel = _novel_or_404(novel_id)
    total = novel.get("total_chapters", 0)
    if total == 0:
        return {"shifts": [], "consistency": "consistent", "assessment": "无章节数据"}
    if total < 2:
        return {"shifts": [], "consistency": "consistent", "assessment": "仅一章，无法判断切换"}

    db = _db()
    known_names = [char.get("char_name", "") for char in db.get_character_state(novel_id) if char.get("char_name")]
    pov_per_chapter = []
    for number in range(1, total + 1):
        chapter = db.get_chapter(novel_id, number)
        if not chapter:
            continue
        content = chapter.get("content", "")
        if len(content) < 20:
            continue
        name_counts = {name: content.count(name) for name in known_names if content.count(name) > 0}
        first_person = content.count("我") - content.count("我们") // 2
        if name_counts:
            dominant = max(name_counts, key=lambda key: name_counts[key])
            dominant_count = name_counts[dominant]
        elif first_person > 3:
            dominant = "我(第一人称)"
            dominant_count = first_person
        else:
            dominant = "未知"
            dominant_count = 0
        pov_per_chapter.append({"chapter": number, "dominant_char": dominant, "mentions": dominant_count, "all_mentions": name_counts})

    shifts = []
    for index in range(1, len(pov_per_chapter)):
        previous = pov_per_chapter[index - 1]
        current = pov_per_chapter[index]
        if previous["dominant_char"] != current["dominant_char"] and previous["dominant_char"] != "未知":
            shifts.append({
                "from_chapter": previous["chapter"],
                "from_char": previous["dominant_char"],
                "to_chapter": current["chapter"],
                "to_char": current["dominant_char"],
            })
    shift_ratio = len(shifts) / max(1, len(pov_per_chapter) - 1)
    consistency = "consistent" if shift_ratio == 0 else "mostly_consistent" if shift_ratio < 0.3 else "shifting" if shift_ratio < 0.6 else "highly_shifting"
    return {"shifts": shifts, "pov_per_chapter": pov_per_chapter, "consistency": consistency, "assessment": f"共{len(shifts)}次POV切换，{total}章"}


@router.get("/api/novels/{novel_id}/narrative-voice")
def get_narrative_voice(novel_id: str) -> dict:
    """Determine narrative person and tense hint."""
    novel = _novel_or_404(novel_id)
    total = novel.get("total_chapters", 0)
    if total == 0:
        return {"person": "unknown", "tense_hint": "unknown", "consistency": "unknown", "assessment": "无章节数据"}

    db = _db()
    texts = []
    for number in range(1, min(4, total + 1)):
        chapter = db.get_chapter(novel_id, number)
        if chapter:
            texts.append(chapter.get("content", ""))
    all_text = " ".join(texts)
    if len(all_text) < 50:
        return {"person": "unknown", "tense_hint": "unknown", "consistency": "unknown", "assessment": "内容不足"}

    first_count = len(re.findall(r"我[^们]|我的", all_text))
    third_count = len(re.findall(r"他[^们]|她[^们]|他的|她的", all_text))
    total_person = first_count + third_count
    if total_person == 0:
        person = "unknown"
    elif first_count > third_count * 2:
        person = "first"
    elif third_count > first_count * 2:
        person = "third"
    else:
        person = "mixed"

    past_markers = len(re.findall(r"了|过|曾经|那时|当年|从前|已经|已", all_text))
    present_markers = len(re.findall(r"正在|现在|此刻|着|在(?!了)", all_text))
    tense_hint = "past" if past_markers > present_markers * 3 else "present" if present_markers > past_markers * 3 else "mixed"

    if total >= 5:
        late_texts = []
        for number in [total // 2, total]:
            chapter = db.get_chapter(novel_id, number)
            if chapter:
                late_texts.append(chapter.get("content", ""))
        late_text = " ".join(late_texts)
        late_first = len(re.findall(r"我[^们]|我的", late_text))
        late_third = len(re.findall(r"他[^们]|她[^们]|他的|她的", late_text))
        consistency = "shifting" if (person == "first" and late_third > late_first * 2) or (person == "third" and late_first > late_third * 2) else "consistent"
    else:
        consistency = "consistent"

    person_labels = {"first": "第一人称", "third": "第三人称", "mixed": "混合人称", "unknown": "未确定"}
    ratio = round(first_count / max(1, total_person) * 100, 1)
    return {
        "person": person,
        "tense_hint": tense_hint,
        "first_pct": ratio,
        "third_pct": round(100 - ratio, 1),
        "consistency": consistency,
        "assessment": f"{person_labels[person]}主导，{consistency}",
    }


@router.post("/api/novels/{novel_id}/anti-narrative")
def get_anti_narrative(novel_id: str, data: dict) -> dict:
    """Generate the anti-narrative: what happens when conventions are inverted."""
    _novel_or_404(novel_id)
    chapter_num = data.get("chapter_num", 0)
    scene_description = text_field(data, "scene_description")
    expected_next = data.get("expected_next", [])
    if not scene_description:
        raise HTTPException(400, "scene_description is required")
    if not isinstance(expected_next, list) or len(expected_next) == 0:
        raise HTTPException(400, "expected_next must be a non-empty list")

    invert_map = {
        "成功": "失败",
        "失败": "成功",
        "赢": "输",
        "输": "赢",
        "活着": "死亡",
        "死": "复活",
        "相遇": "错过",
        "错过": "相遇",
        "拯救": "毁灭",
        "毁灭": "拯救",
        "得到": "失去",
        "失去": "得到",
        "和解": "决裂",
        "决裂": "和解",
        "留下": "离开",
        "离开": "留下",
        "前进": "后退",
        "后退": "前进",
        "开放": "封闭",
        "封闭": "开放",
        "战斗": "谈判",
        "谈判": "放弃",
        "揭露": "隐藏",
        "隐藏": "揭露",
        "坦白": "撒谎",
        "撒谎": "坦白",
        "爱": "恨",
        "恨": "理解",
    }
    anti_events = []
    outcome_pairs = []
    for event in expected_next:
        if not isinstance(event, str) or not event.strip():
            continue
        text = event.strip()
        anti_text = text
        for positive in invert_map:
            if positive in text:
                anti_text = text.replace(positive, f"__ANTI_{positive}__")
                break
        for positive, negative in invert_map.items():
            anti_text = anti_text.replace(f"__ANTI_{positive}__", negative)
        if anti_text == text:
            anti_text = f"不是{text}，而是相反的情况"
        anti_events.append(anti_text)
        outcome_pairs.append({"expected": text, "anti": anti_text})

    if not anti_events:
        raise HTTPException(400, "expected_next must include at least one text event")

    if len(anti_events) >= 3:
        suggestion = "试完全反写：反写高潮、反写结尾、反写情感 —— 全部逆行"
    elif len(anti_events) >= 2:
        suggestion = "选一个反事件放大为核心反转"
    else:
        suggestion = f"试试'{anti_events[0]}'这个方向"
    return {
        "scene": scene_description[:120],
        "chapter_num": chapter_num,
        "expected": expected_next,
        "anti": anti_events,
        "pairs": outcome_pairs,
        "suggestion": suggestion,
    }


@router.get("/api/novels/{novel_id}/reverse-reading")
def reverse_reading(novel_id: str) -> dict:
    """Scan earliest chapters for sentences that gain new meaning given later reveals."""
    novel = _novel_or_404(novel_id)
    patterns = re.compile(r"不知道|没说|没问|沉默|看起来|似乎|好像|也许|大概|其实|未必|不敢|不敢说")
    sentences = []
    for chapter in _generated_chapters(novel)[:3]:
        content = chapter.get("content", "")
        for match in re.finditer(r"[^。！？\n]{6,}[。！？]", content):
            sentence = match.group().strip()
            if patterns.search(sentence):
                sentences.append({
                    "chapter": chapter["number"],
                    "text": sentence[:100],
                    "potential_new_meaning": "读者已知后续，这句话可能另有深意",
                })
    return {"sentences": sentences[:10], "count": len(sentences)}


@router.get("/api/novels/{novel_id}/scream-moments")
def scream_moments(novel_id: str) -> dict:
    """Find hidden connections: repeated unique phrases appearing in chapters far apart."""
    novel = _novel_or_404(novel_id)
    phrase_map: dict[str, list[int]] = {}
    for chapter in _generated_chapters(novel):
        for word in set(re.findall(r"[一-鿿]{3,}", chapter.get("content", ""))):
            phrase_map.setdefault(word, []).append(chapter["number"])

    connections = []
    for phrase, chapter_numbers in phrase_map.items():
        if len(chapter_numbers) < 2:
            continue
        sorted_numbers = sorted(set(chapter_numbers))
        for i, first in enumerate(sorted_numbers):
            for second in sorted_numbers[i + 1:]:
                gap = second - first
                if gap > 5:
                    connections.append({"phrase": phrase, "ch1": first, "ch2": second, "gap": gap})
    connections.sort(key=lambda item: item["gap"], reverse=True)
    strongest = (
        f"'{connections[0]['phrase']}' 在第{connections[0]['ch1']}章和第{connections[0]['ch2']}章之间相隔{connections[0]['gap']}章出现"
        if connections
        else "暂无跨章节呼应"
    )
    return {"connections": connections[:15], "strongest": strongest}


@router.get("/api/novels/{novel_id}/ending-candidates")
def ending_candidates(novel_id: str) -> dict:
    """Scan for dormant images across all chapters."""
    novel = _novel_or_404(novel_id)
    phrase_chapters: dict[str, list[int]] = {}
    for chapter in _generated_chapters(novel):
        for phrase in set(re.findall(r"[一-鿿]{2,4}", chapter.get("content", ""))):
            phrase_chapters.setdefault(phrase, []).append(chapter["number"])
    dormant = [
        {
            "image": phrase,
            "first_appearance_chapter": chapters[0],
            "last_appearance_chapter": chapters[-1],
        }
        for phrase, chapters in phrase_chapters.items()
        if 1 <= len(chapters) <= 2 and len(phrase) >= 3
    ]
    dormant.sort(key=lambda item: item["first_appearance_chapter"])
    recommendation = (
        f"建议在终章回收意象：'{dormant[0]['image']}'（首现第{dormant[0]['first_appearance_chapter']}章）"
        if dormant
        else "暂无休眠意象，可继续铺垫"
    )
    return {"dormant": dormant[:20], "recommendation": recommendation}


@router.get("/api/novels/{novel_id}/midpoint-health")
def midpoint_health(novel_id: str) -> dict:
    """Check if the story's midpoint has enough hangout time versus plot density."""
    novel = _novel_or_404(novel_id)
    chapters = _generated_chapters(novel)
    total = len(chapters)
    if total == 0:
        return {"midpoint_chapter": 0, "plot_density": 0, "hangout_score": 0, "assessment": "暂无章节"}
    middle = max(1, total // 2)
    plot_keywords = ["杀", "死", "逃", "追", "战", "打", "破", "碎", "险", "危", "急", "决", "变", "转"]
    hangout_keywords = ["说", "笑", "吃", "喝", "走", "看", "坐", "聊", "问", "答", "想", "等", "陪", "一起"]
    start, end = max(0, middle - 2), min(total, middle + 3)
    plot_count = 0
    hangout_count = 0
    for chapter in chapters[start:end]:
        content = chapter.get("content", "")[:500]
        plot_count += sum(1 for keyword in plot_keywords if keyword in content)
        hangout_count += sum(1 for keyword in hangout_keywords if keyword in content)
    window = max(1, end - start)
    plot_density = round(plot_count / window, 1)
    hangout_score = round(hangout_count / window, 1)
    if 3 < plot_density < 8:
        assessment = "剧情密度适中，节奏良好"
    elif plot_density >= 8:
        assessment = "事件过密，缺少喘息空间——建议在中点前后插入相处场景"
    else:
        assessment = "相处时间充足，读者对角色投入足够"
    return {
        "midpoint_chapter": middle,
        "plot_density": plot_density,
        "hangout_score": hangout_score,
        "assessment": assessment,
    }


@router.get("/api/novels/{novel_id}/rituals")
def rituals(novel_id: str) -> dict:
    """Track repeated gestures and phrases across chapters."""
    novel = _novel_or_404(novel_id)
    chapters = _generated_chapters(novel)
    phrase_chapters: dict[str, list[int]] = {}
    for chapter in chapters:
        for phrase in set(re.findall(r"[一-鿿]{2,4}", chapter.get("content", ""))):
            phrase_chapters.setdefault(phrase, []).append(chapter["number"])
    result = []
    for phrase, chapter_numbers in phrase_chapters.items():
        if len(chapter_numbers) >= 3:
            sorted_numbers = sorted(set(chapter_numbers))
            first = sorted_numbers[0]
            last = sorted_numbers[-1]
            if last - first > len(chapters) * 0.5:
                progression = "growing"
            elif first < len(chapters) * 0.3 and last < len(chapters) * 0.3:
                progression = "fading"
            else:
                progression = "stable"
            result.append({"phrase": phrase, "chapters": sorted_numbers, "meaning_progression": progression})
    result.sort(key=lambda item: len(item["chapters"]), reverse=True)
    return {"rituals": result[:15]}


@router.get("/api/novels/{novel_id}/time-spiral")
def time_spiral(novel_id: str) -> dict:
    """Compare early and late chapter states for retrospective meaning."""
    novel = _novel_or_404(novel_id)
    chapters = _generated_chapters(novel)
    if len(chapters) < 6:
        return {"early_state": "故事太短", "late_state": "暂无", "meaning_shift": "需要更多章节才能分析"}
    early_chars = set()
    late_chars = set()
    for chapter in chapters[:3]:
        early_chars.update(re.findall(r"(他|她|它|我|你)[一-鿿]{2,6}", chapter.get("content", "")[:500])[:5])
    for chapter in chapters[-3:]:
        late_chars.update(re.findall(r"(他|她|它|我|你)[一-鿿]{2,6}", chapter.get("content", "")[:500])[:5])
    early_state = f"前3章角色状态：{', '.join(list(early_chars)[:3]) or '未知'}"
    late_state = f"后3章角色状态：{', '.join(list(late_chars)[:3]) or '未知'}"
    meaning_shift = (
        "回头再看开头，那些看似寻常的细节——一句话、一个眼神、一次犹豫——都在后来的故事里获得了全新的重量。读者此时才明白，那不是闲笔，是伏笔。"
        if early_chars != late_chars
        else "开篇与结尾状态一致，首尾形成闭环"
    )
    return {"early_state": early_state, "late_state": late_state, "meaning_shift": meaning_shift}


_protected_drafts: dict[str, set[int]] = {}


@router.post("/api/novels/{novel_id}/draft-protect")
def draft_protect(novel_id: str, body: dict) -> dict:
    """Mark a chapter as first-draft protected."""
    _novel_or_404(novel_id)
    chapter_num = body.get("chapter_num")
    if chapter_num is None:
        raise HTTPException(400, "chapter_num is required")
    key = f"{novel_id}"
    _protected_drafts.setdefault(key, set())
    is_first_draft = body.get("is_first_draft", False)
    if is_first_draft:
        _protected_drafts[key].add(chapter_num)
    else:
        _protected_drafts[key].discard(chapter_num)
    return {
        "protected": is_first_draft,
        "note": "First draft protected. No analysis will run." if is_first_draft else "Protection removed.",
    }


@router.get("/api/novels/{novel_id}/abandonment-candidates")
def abandonment_candidates(novel_id: str) -> dict:
    """Identify chapters that may be candidates for deletion or restructuring."""
    novel = _novel_or_404(novel_id)
    db = _db()
    chapters = _generated_chapters(novel)
    candidates = []
    for index, chapter in enumerate(chapters):
        word_count = chapter.get("word_count", 0) or 0
        content = chapter.get("content", "")
        char_states = db.get_character_state(novel_id, chapter["number"])
        reasons = []
        if 0 < word_count < 500:
            reasons.append(f"字数极低({word_count}字)")
        if not char_states and word_count > 0:
            reasons.append("未提取到角色状态")
        if 0 < index < len(chapters) - 1:
            prev_content = chapters[index - 1].get("content", "")[:200]
            overlap = len(set(prev_content) & set(content[:200]))
            if overlap > 80:
                reasons.append("与前一章内容高度重复")
        if reasons:
            suggestion = "merge" if "重复" in reasons[0] else "delete" if word_count < 300 else "move"
            candidates.append({"chapter": chapter["number"], "reason": "；".join(reasons), "suggestion": suggestion})
    return {
        "candidates": candidates,
        "assessment": f"发现{len(candidates)}个可优化章节" if candidates else "所有章节状态良好",
    }


@router.get("/api/novels/{novel_id}/boundary-check")
def boundary_check(novel_id: str) -> dict:
    """Return rules for when the system should stay silent."""
    _novel_or_404(novel_id)
    return {
        "rules": [
            "never give final answer",
            "never rush human choice",
            "never pretend to feel",
            "never exploit vulnerability",
            "never replace the moment of not-looking-away",
        ],
        "active": True,
    }
