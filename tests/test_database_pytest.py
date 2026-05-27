"""Database CRUD tests — isolated per test via tmp_path fixture"""
import json
import pytest

from novel_writer.database import Database


@pytest.fixture
def db(tmp_path):
    """Each test gets its own isolated SQLite database."""
    db_path = str(tmp_path / "test.db")
    return Database(db_path)


# --- Novel CRUD ---

def test_create_and_get_novel(db):
    """Create a novel and verify all fields are stored correctly."""
    novel = db.create_novel(
        id="test-book",
        title="测试之书",
        author="AI",
        synopsis="测试用简介",
        genre="玄幻",
        world_name="测试大陆",
        world_era="上古",
        world_geo="一片大陆",
        power_system="练气→筑基→金丹",
        main_arc="测试主线",
        current_arc="开篇",
    )
    assert novel is not None
    assert novel["title"] == "测试之书"
    assert novel["author"] == "AI"
    assert novel["synopsis"] == "测试用简介"
    assert novel["genre"] == "玄幻"
    assert novel["world_name"] == "测试大陆"
    assert novel["world_era"] == "上古"
    assert novel["world_geo"] == "一片大陆"
    assert novel["power_system"] == "练气→筑基→金丹"
    assert novel["main_arc"] == "测试主线"
    assert novel["current_arc"] == "开篇"
    assert novel["total_chapters"] == 0
    assert novel["total_words"] == 0

    # Verify get_novel returns the same data
    retrieved = db.get_novel("test-book")
    assert retrieved is not None
    assert retrieved["title"] == "测试之书"
    assert retrieved["genre"] == "玄幻"


def test_list_novels(db):
    """Create 2 novels, list them, verify count and contents."""
    db.create_novel(id="n1", title="第一本", genre="玄幻")
    db.create_novel(id="n2", title="第二本", genre="都市")

    novels = db.list_novels()
    assert len(novels) == 2
    titles = {n["title"] for n in novels}
    assert titles == {"第一本", "第二本"}


def test_soft_delete_novel(db):
    """Create a novel, soft-delete it, verify it disappears from list."""
    db.create_novel(id="del-test", title="待删除")

    # Verify it exists
    assert db.get_novel("del-test") is not None
    assert len(db.list_novels()) == 1

    # Soft delete
    db.soft_delete_novel("del-test")

    # Verify it's gone from active list
    assert db.get_novel("del-test") is None
    assert len(db.list_novels()) == 0


# --- Chapter CRUD ---

def test_add_and_get_chapter(db):
    """Add a chapter and retrieve it with all fields intact."""
    db.create_novel(id="ch-test", title="章节测试")

    cid = db.add_chapter(
        novel_id="ch-test",
        number=1,
        title="第一章",
        word_count=2500,
        summary="测试摘要",
        content="正文内容",
        ending_hook="悬念钩子",
        quality_score=0.85,
        model_used="gpt-4o",
        cost=0.05,
    )
    assert cid is not None

    # Get chapter by novel_id + number
    chapter = db.get_chapter("ch-test", 1)
    assert chapter is not None
    assert chapter["title"] == "第一章"
    assert chapter["number"] == 1
    assert chapter["word_count"] == 2500
    assert chapter["summary"] == "测试摘要"
    assert chapter["content"] == "正文内容"
    assert chapter["ending_hook"] == "悬念钩子"
    assert chapter["model_used"] == "gpt-4o"

    # Verify novel stats are updated
    novel = db.get_novel("ch-test")
    assert novel["total_chapters"] == 1
    assert novel["total_words"] == 2500
    assert novel["latest_chapter"]["title"] == "第一章"


# --- Audio Data ---

def test_save_audio_bookmarks(db):
    """Save audio bookmarks and load them back."""
    bookmarks = [
        {
            "id": "bm1",
            "novelId": "test-book",
            "novelTitle": "测试之书",
            "chapterNum": 5,
            "chapterTitle": "第五章",
            "position": 120.5,
            "note": "精彩段落",
            "tag": "高潮",
            "createdAt": "2026-05-25T10:00:00",
        },
        {
            "id": "bm2",
            "novelId": "test-book",
            "novelTitle": "测试之书",
            "chapterNum": 10,
            "chapterTitle": "第十章",
            "position": 340.0,
            "note": "转折点",
            "tag": "重要",
            "createdAt": "2026-05-25T11:00:00",
        },
    ]
    db.save_audio_bookmarks(bookmarks)

    loaded = db.load_audio_bookmarks()
    assert len(loaded) == 2
    assert loaded[0]["id"] == "bm2"  # Most recent first (DESC)
    assert loaded[0]["novel_id"] == "test-book"
    assert loaded[0]["chapter_num"] == 10
    assert loaded[0]["note"] == "转折点"
    assert loaded[0]["tag"] == "重要"

    assert loaded[1]["id"] == "bm1"
    assert loaded[1]["chapter_title"] == "第五章"
    assert loaded[1]["position"] == 120.5

    # Verify overwrite: saving again replaces all bookmarks
    new_bookmarks = [{
        "id": "bm3",
        "novelId": "other-book",
        "novelTitle": "另一本",
        "chapterNum": 1,
        "chapterTitle": "第一章",
        "position": 50.0,
        "note": "",
        "tag": "",
        "createdAt": "2026-05-25T12:00:00",
    }]
    db.save_audio_bookmarks(new_bookmarks)
    loaded2 = db.load_audio_bookmarks()
    assert len(loaded2) == 1
    assert loaded2[0]["id"] == "bm3"


def test_save_audio_settings(db):
    """Save audio settings and load them back as a dict."""
    db.save_audio_setting("voice", "zh-CN-XiaoxiaoNeural")
    db.save_audio_setting("rate", "1.2")
    db.save_audio_setting("volume", "0.8")

    settings = db.load_audio_settings()
    assert settings["voice"] == "zh-CN-XiaoxiaoNeural"
    assert settings["rate"] == "1.2"
    assert settings["volume"] == "0.8"

    # Overwrite an existing key
    db.save_audio_setting("voice", "zh-CN-YunxiNeural")
    db.save_audio_setting("auto_play", "true")

    settings2 = db.load_audio_settings()
    assert settings2["voice"] == "zh-CN-YunxiNeural"
    assert settings2["rate"] == "1.2"
    assert settings2["auto_play"] == "true"
    assert len(settings2) == 4

    # Empty settings
    db2 = Database(str(db.db_path))
    empty_settings = db2.load_audio_settings()
    # Should be empty for a fresh DB, but this one shares the same file
    # so it should still have the 4 settings
    assert len(empty_settings) == 4


# ═══════════════ Story Bible ═══════════════


def test_save_character_state(db):
    db.create_novel(id="s1", title="状态测试")
    db.save_character_state("s1", chapter_num=1, char_name="叶凡",
                            emotion="愤怒", physical_state="受伤", knowledge='["知道秘密"]',
                            goal="复仇", location="山洞", relationships='[{"target":"小红","relation":"恋人"}]',
                            notes="测试备注")
    states = db.get_character_state("s1", chapter_num=1)
    assert len(states) == 1
    assert states[0]["char_name"] == "叶凡"
    assert states[0]["emotion"] == "愤怒"
    assert states[0]["physical_state"] == "受伤"
    assert states[0]["location"] == "山洞"


def test_get_character_state_latest(db):
    db.create_novel(id="s2", title="最新状态")
    db.save_character_state("s2", 1, "叶凡", emotion="平静")
    db.save_character_state("s2", 2, "叶凡", emotion="愤怒")
    db.save_character_state("s2", 3, "叶凡", emotion="悲伤")
    # No chapter_num → latest per character
    states = db.get_character_state("s2")
    assert len(states) == 1
    assert states[0]["emotion"] == "悲伤"


def test_get_all_character_states(db):
    db.create_novel(id="s3", title="全部状态")
    db.save_character_state("s3", 1, "叶凡", emotion="平静")
    db.save_character_state("s3", 2, "叶凡", emotion="愤怒")
    db.save_character_state("s3", 3, "叶凡", emotion="悲伤")
    all_states = db.get_all_character_states("s3", char_name="叶凡")
    assert len(all_states) == 3
    assert all_states[0]["emotion"] == "平静"
    assert all_states[2]["emotion"] == "悲伤"


def test_get_all_character_states_no_name(db):
    db.create_novel(id="s3b", title="全部状态2")
    db.save_character_state("s3b", 1, "叶凡", emotion="平静")
    db.save_character_state("s3b", 1, "小红", emotion="开心")
    all_states = db.get_all_character_states("s3b")
    assert len(all_states) == 2


def test_get_all_character_states_with_limit(db):
    db.create_novel(id="s3c", title="带限制")
    db.save_character_state("s3c", 1, "叶凡", emotion="平静")
    db.save_character_state("s3c", 2, "叶凡", emotion="愤怒")
    db.save_character_state("s3c", 3, "叶凡", emotion="悲伤")
    limited = db.get_all_character_states("s3c", char_name="叶凡", up_to_chapter=2)
    assert len(limited) == 2


def test_save_foreshadowing(db):
    db.create_novel(id="f1", title="伏笔测试")
    db.save_foreshadowing("f1", chapter_num=1, description="山洞中的神秘符文",
                          hint_text="叶凡注意到墙壁上的符号", due_by=5)
    active = db.get_active_foreshadowing("f1")
    assert len(active) == 1
    assert active[0]["description"] == "山洞中的神秘符文"
    assert active[0]["status"] == "active"


def test_resolve_foreshadowing(db):
    db.create_novel(id="f2", title="伏笔收束")
    db.save_foreshadowing("f2", 1, description="神秘符文", due_by=5)
    active = db.get_active_foreshadowing("f2")
    fs_id = active[0]["id"]
    db.resolve_foreshadowing(fs_id, resolved_chapter=4, resolved_text="符文是开启秘境的钥匙")
    # Should no longer be active
    assert len(db.get_active_foreshadowing("f2")) == 0
    # Should appear in all
    all_fs = db.get_all_foreshadowing("f2")
    assert len(all_fs) == 1
    assert all_fs[0]["status"] == "resolved"


def test_save_location_history(db):
    db.create_novel(id="l1", title="地点测试")
    db.save_location_history("l1", 1, "青云山", event="到达", state_change="晴天")
    db.save_location_history("l1", 2, "青云山", event="离开")
    history = db.get_location_history("l1", location_name="青云山")
    assert len(history) == 2
    assert history[0]["event"] == "到达"


def test_get_location_history_all(db):
    db.create_novel(id="l2", title="全部地点")
    db.save_location_history("l2", 1, "青云山")
    db.save_location_history("l2", 2, "天都城")
    history = db.get_location_history("l2")
    assert len(history) == 2


def test_save_timeline_event(db):
    db.create_novel(id="t1", title="时间线测试")
    db.save_timeline_event("t1", 1, absolute_time="上古历3000年", relative_time="第1天",
                           event_summary="叶凡觉醒")
    db.save_timeline_event("t1", 2, absolute_time="上古历3001年", relative_time="第365天",
                           event_summary="叶凡突破")
    timeline = db.get_timeline("t1")
    assert len(timeline) == 2
    assert timeline[0]["event_summary"] == "叶凡觉醒"
    assert timeline[1]["event_summary"] == "叶凡突破"


def test_save_world_state(db):
    db.create_novel(id="w1", title="世界状态")
    db.save_world_state("w1", 1, rule_name="灵气复苏", rule_description="天地灵气恢复", is_broken=False)
    db.save_world_state("w1", 2, rule_name="灵气复苏", rule_description="天地灵气恢复", is_broken=True)
    states = db.get_world_state("w1")
    assert len(states) == 2
    assert states[0]["is_broken"] == 0
    assert states[1]["is_broken"] == 1


def test_log_consistency_issue(db):
    db.create_novel(id="c1", title="一致性测试")
    db.log_consistency_issue("c1", 1, check_type="character", severity="error",
                             description="叶凡在第1章已死但第2章出现", fix_suggestion="修改第2章")
    db.log_consistency_issue("c1", 2, check_type="world", severity="warning",
                             description="灵气等级不一致")
    log = db.get_consistency_log("c1")
    assert len(log) == 2
    # Ordered by chapter_num DESC
    assert log[0]["check_type"] == "world"
    assert log[1]["check_type"] == "character"


def test_mark_consistency_fixed(db):
    db.create_novel(id="c2", title="修复标记")
    db.log_consistency_issue("c2", 1, "character", "error", "问题描述")
    log = db.get_consistency_log("c2")
    issue_id = log[0]["id"]
    db.mark_consistency_fixed(issue_id)
    log2 = db.get_consistency_log("c2")
    assert log2[0]["was_fixed"] == 1


def test_save_unsaid(db):
    db.create_novel(id="u1", title="冰山测试")
    db.save_unsaid("u1", "叶凡其实是魔族后裔")
    db.save_unsaid("u1", "小红暗中保护叶凡")
    unsaid = db.get_unsaid("u1")
    assert len(unsaid) == 2
    assert unsaid[0]["entry"] == "小红暗中保护叶凡"  # DESC order


def test_delete_unsaid(db):
    db.create_novel(id="u2", title="删除冰山")
    db.save_unsaid("u2", "秘密A")
    db.save_unsaid("u2", "秘密B")
    unsaid = db.get_unsaid("u2")
    db.delete_unsaid(unsaid[1]["id"])  # delete the older one
    remaining = db.get_unsaid("u2")
    assert len(remaining) == 1
    assert remaining[0]["entry"] == "秘密B"


def test_save_voice_sample(db):
    db.create_novel(id="v1", title="声音测试")
    db.save_voice_sample("v1", 1, before_text="叶凡站在山巅。", after_text="叶凡站在山巅，体内灵力翻涌。")
    db.save_voice_sample("v1", 2, before_text="战斗开始。", after_text="战斗在黎明前打响。")
    samples = db.get_voice_samples("v1")
    assert len(samples) == 2
    assert samples[0]["before_text"] == "战斗开始。"  # DESC order


def test_save_cost_entry(db):
    db.create_novel(id="cost1", title="代价测试")
    db.save_cost_entry("cost1", 1, "叶凡", gain="获得灵丹", loss="失去记忆",
                       gain_type="item", loss_type="info", is_immediate=True)
    db.save_cost_entry("cost1", 1, "小红", gain="信任", loss="自由",
                       gain_type="relation", loss_type="freedom", is_immediate=False)
    ledger = db.get_cost_ledger("cost1")
    assert len(ledger) == 2
    assert ledger[0]["character_name"] == "叶凡"
    assert ledger[0]["gain"] == "获得灵丹"
    assert ledger[1]["is_immediate"] == 0


def test_get_character_location(db):
    db.create_novel(id="loc1", title="位置查询")
    db.save_character_state("loc1", 1, "叶凡", location="青云山")
    db.save_character_state("loc1", 2, "叶凡", location="天都城")
    location = db.get_character_location("loc1", "叶凡")
    assert location == "天都城"


def test_get_character_location_none(db):
    assert db.get_character_location("nonexistent", "叶凡") is None


def test_get_relationship_changes(db):
    db.create_novel(id="rel1", title="关系变化")
    db.save_character_state("rel1", 1, "叶凡",
                            relationships='[{"target":"小红","relation":"朋友","change":"变亲近"}]')
    db.save_character_state("rel1", 2, "叶凡",
                            relationships='[{"target":"师傅","relation":"师徒","change":"建立"}]')
    db.save_character_state("rel1", 3, "叶凡", relationships='[]')  # empty, should be skipped
    changes = db.get_relationship_changes("rel1")
    assert len(changes) == 2
    assert changes[0]["target"] == "小红"
    assert changes[1]["relation"] == "师徒"


def test_get_knowledge_state(db):
    db.create_novel(id="k1", title="知识状态")
    db.save_character_state("k1", 1, "叶凡", knowledge='["知道灵气复苏", "认识小红"]')
    db.save_character_state("k1", 2, "叶凡", knowledge='["知道魔族秘密"]')
    knowledge = db.get_knowledge_state("k1", "叶凡")
    assert len(knowledge) == 3
    assert "知道灵气复苏" in knowledge
    assert "知道魔族秘密" in knowledge


def test_get_knowledge_state_empty(db):
    db.create_novel(id="k2", title="空知识")
    db.save_character_state("k2", 1, "叶凡", knowledge='[]')
    knowledge = db.get_knowledge_state("k2", "叶凡")
    assert knowledge == []


# ═══════════════ Chapter Summaries ═══════════════


def test_save_chapter_summary(db):
    db.create_novel(id="sum1", title="摘要测试")
    db.save_chapter_summary("sum1", 1, "叶凡在山巅觉醒灵力。")
    db.save_chapter_summary("sum1", 2, "叶凡下山遇到小红。")
    summaries = db.get_chapter_summaries("sum1")
    assert len(summaries) == 2
    assert summaries[0]["summary_text"] == "叶凡在山巅觉醒灵力。"


def test_get_chapter_summaries_filtered(db):
    db.create_novel(id="sum2", title="过滤摘要")
    db.save_chapter_summary("sum2", 1, "第一章摘要")
    db.save_chapter_summary("sum2", 2, "第二章摘要")
    db.save_chapter_summary("sum2", 3, "第三章摘要")
    filtered = db.get_chapter_summaries("sum2", chapter_nums=[1, 3])
    assert len(filtered) == 2
    assert filtered[0]["chapter_num"] == 1
    assert filtered[1]["chapter_num"] == 3


def test_has_chapter_summaries(db):
    db.create_novel(id="sum3", title="存在性检查")
    assert not db.has_chapter_summaries("sum3", up_to_chapter=3)
    db.save_chapter_summary("sum3", 1, "摘要1")
    db.save_chapter_summary("sum3", 2, "摘要2")
    db.save_chapter_summary("sum3", 3, "摘要3")
    assert db.has_chapter_summaries("sum3", up_to_chapter=3)
    assert not db.has_chapter_summaries("sum3", up_to_chapter=4)


# ═══════════════ Providers ═══════════════


def test_save_provider(db):
    db.save_provider("openai", name="OpenAI", base_url="https://api.openai.com",
                     api_key="sk-test1234", models='["gpt-4o"]')
    provider = db.get_provider("openai")
    assert provider is not None
    assert provider["name"] == "OpenAI"
    assert provider["models"] == ["gpt-4o"]


def test_save_provider_update(db):
    db.save_provider("openai", name="OpenAI", base_url="https://api.openai.com",
                     api_key="sk-old", models='["gpt-4"]')
    db.save_provider("openai", api_key="sk-new", models='["gpt-4o"]')
    provider = db.get_provider("openai")
    assert provider["api_key"] == "sk-new"


def test_get_provider_nonexistent(db):
    assert db.get_provider("nonexistent") is None


def test_list_providers(db):
    # Schema seeds default providers, so count includes those
    initial_count = len(db.list_providers())
    db.save_provider("p1", name="Provider1", base_url="https://p1.com",
                     api_key="sk-1234abcd", models='["m1"]')
    db.save_provider("p2", name="Provider2", base_url="https://p2.com",
                     api_key="sk-5678efgh", models='["m2"]')
    providers = db.list_providers()
    assert len(providers) == initial_count + 2
    # API key should be masked (only shows last 4 chars)
    p1 = [p for p in providers if p["id"] == "p1"][0]
    assert p1["api_key"].endswith("abcd")


# ═══════════════ Audio Progress & Playlist ═══════════════


def test_save_audio_progress(db):
    db.create_novel(id="novel-a", title="音频进度")
    db.save_audio_progress("novel-a", chapter_num=5, position_sec=120.5)
    progress = db.get_audio_progress("novel-a")
    assert progress is not None
    assert progress["chapter_num"] == 5
    assert progress["position_sec"] == 120.5


def test_save_audio_progress_upsert(db):
    db.create_novel(id="novel-a", title="音频进度")
    db.save_audio_progress("novel-a", 3, 50.0)
    db.save_audio_progress("novel-a", 5, 200.0)  # same novel_id → upsert
    progress = db.get_audio_progress("novel-a")
    assert progress["chapter_num"] == 5
    assert progress["position_sec"] == 200.0


def test_get_audio_progress_nonexistent(db):
    assert db.get_audio_progress("nonexistent") is None


def test_get_all_audio_progress(db):
    db.create_novel(id="n1", title="小说1")
    db.create_novel(id="n2", title="小说2")
    db.save_audio_progress("n1", 1, 10.0)
    db.save_audio_progress("n2", 3, 30.0)
    all_progress = db.get_all_audio_progress()
    assert len(all_progress) == 2


def test_save_audio_playlist(db):
    items = [
        {"novelId": "n1", "novelTitle": "小说A", "chapterNum": 1, "chapterTitle": "第一章"},
        {"novelId": "n1", "novelTitle": "小说A", "chapterNum": 2, "chapterTitle": "第二章"},
    ]
    db.save_audio_playlist(items)
    playlist = db.load_audio_playlist()
    assert len(playlist) == 2
    assert playlist[0]["novel_id"] == "n1"
    assert playlist[0]["sort_order"] == 0
    assert playlist[1]["sort_order"] == 1


def test_save_audio_playlist_overwrite(db):
    db.save_audio_playlist([{"novelId": "n1", "novelTitle": "A", "chapterNum": 1, "chapterTitle": "ch1"}])
    db.save_audio_playlist([{"novelId": "n2", "novelTitle": "B", "chapterNum": 1, "chapterTitle": "ch1"}])
    playlist = db.load_audio_playlist()
    assert len(playlist) == 1
    assert playlist[0]["novel_id"] == "n2"


def test_save_audio_stats(db):
    db.save_audio_stats({"total_listening_time": "3600", "chapters_completed": "10"})
    stats = db.load_audio_stats()
    assert stats["total_listening_time"] == "3600"
    assert stats["chapters_completed"] == "10"


def test_save_audio_stats_overwrite(db):
    db.save_audio_stats({"key1": "val1"})
    db.save_audio_stats({"key1": "val2", "key2": "val3"})
    stats = db.load_audio_stats()
    assert stats["key1"] == "val2"
    assert stats["key2"] == "val3"


# ═══════════════ Film Studio ═══════════════


def test_save_film_setting(db):
    db.save_film_setting("comfyui_url", "http://localhost:8188")
    db.save_film_setting("default_fps", "24")
    settings = db.load_film_settings()
    assert settings["comfyui_url"] == "http://localhost:8188"
    assert settings["default_fps"] == "24"


def test_save_visual_character(db):
    db.create_novel(id="vc1", title="视觉角色")
    data = {
        "appearance": "黑发少年，剑眉星目",
        "default_expression": "冷峻",
        "signature_pose": "单手持剑",
        "color_palette": "#1a1a2e,#16213e",
        "costume": "黑色劲装",
        "injury_marks": "",
        "voice_character": "低沉",
        "reference_images": ["ref1.png", "ref2.png"],
    }
    db.save_visual_character("vc1", "hero", data)
    chars = db.get_visual_characters("vc1")
    assert len(chars) == 1
    assert chars[0]["char_key"] == "hero"
    assert chars[0]["appearance"] == "黑发少年，剑眉星目"
    assert chars[0]["reference_images"] == ["ref1.png", "ref2.png"]


def test_save_visual_character_upsert(db):
    db.create_novel(id="vc2", title="视觉角色更新")
    db.save_visual_character("vc2", "hero", {"appearance": "旧外貌"})
    db.save_visual_character("vc2", "hero", {"appearance": "新外貌"})
    chars = db.get_visual_characters("vc2")
    assert len(chars) == 1
    assert chars[0]["appearance"] == "新外貌"


def test_save_storyboard(db):
    db.create_novel(id="sb1", title="分镜测试")
    data = {
        "title": "第一幕",
        "total_duration_sec": 30.0,
        "overall_mood": "紧张",
        "pacing": "快",
        "color_grade": "冷色调",
        "music_theme": "战斗",
        "shots": [
            {"shot_id": "s001", "subject": "叶凡特写", "duration_sec": 3.0},
            {"shot_id": "s002", "subject": "全景战斗", "duration_sec": 5.0},
        ],
    }
    db.save_storyboard("sb1", 1, data)
    sb = db.get_storyboard("sb1", 1)
    assert sb is not None
    assert sb["title"] == "第一幕"
    assert sb["total_duration_sec"] == 30.0
    assert len(sb["shots"]) == 2
    assert sb["shots"][0]["shot_id"] == "s001"


def test_get_storyboard_nonexistent(db):
    db.create_novel(id="sb2", title="空分镜")
    assert db.get_storyboard("sb2", 1) is None


def test_list_storyboards(db):
    db.create_novel(id="sb3", title="分镜列表")
    db.save_storyboard("sb3", 1, {"title": "第一幕", "shots": []})
    db.save_storyboard("sb3", 2, {"title": "第二幕", "shots": [{"shot_id": "s001"}]})
    sbs = db.list_storyboards("sb3")
    assert len(sbs) == 2
    assert sbs[0]["title"] == "第一幕"
    assert len(sbs[1]["shots"]) == 1


def test_save_character_voice(db):
    db.create_novel(id="cv1", title="角色声音")
    db.save_character_voice("cv1", "hero", {
        "voice_id": "zh-CN-YunxiNeural",
        "speed": 1.1,
        "pitch": "-2Hz",
        "emotion_default": "calm",
    })
    voices = db.get_character_voices("cv1")
    assert len(voices) == 1
    assert voices[0]["char_key"] == "hero"
    assert voices[0]["voice_id"] == "zh-CN-YunxiNeural"
    assert voices[0]["speed"] == 1.1


def test_save_character_voice_upsert(db):
    db.create_novel(id="cv2", title="声音更新")
    db.save_character_voice("cv2", "hero", {"voice_id": "voice-a", "speed": 1.0})
    db.save_character_voice("cv2", "hero", {"voice_id": "voice-b", "speed": 1.2})
    voices = db.get_character_voices("cv2")
    assert len(voices) == 1
    assert voices[0]["voice_id"] == "voice-b"


# ═══════════════ Cost Logs & Summary ═══════════════


def test_log_cost(db):
    db.create_novel(id="cl1", title="费用日志")
    db.log_cost("cl1", chapter_number=1, model="gpt-4o",
                prompt_tokens=1000, completion_tokens=500, total_tokens=1500,
                cost=0.015, purpose="generate")
    summary = db.get_cost_summary("cl1")
    assert summary["total_cost"] == 0.015
    assert len(summary["by_model"]) == 1
    assert summary["by_model"][0]["model"] == "gpt-4o"


def test_get_cost_summary_all(db):
    db.create_novel(id="cl2a", title="费用A")
    db.create_novel(id="cl2b", title="费用B")
    db.log_cost("cl2a", 1, "gpt-4o", 1000, 500, 1500, 0.01, "generate")
    db.log_cost("cl2b", 1, "deepseek", 2000, 1000, 3000, 0.005, "generate")
    summary = db.get_cost_summary()  # all novels
    assert summary["total_cost"] == 0.015
    assert len(summary["by_model"]) == 2
    assert len(summary["by_novel"]) == 2


# ═══════════════ Chapter Versions ═══════════════


def test_save_chapter_version(db):
    db.create_novel(id="ver1", title="版本测试")
    db.add_chapter("ver1", number=1, title="第一章", word_count=1000, content="初稿内容")
    db.save_chapter_version("ver1", 1, "修改后的内容", reason="修正错别字")
    versions = db.get_chapter_versions("ver1", 1)
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["reason"] == "修正错别字"


def test_get_chapter_version_content(db):
    db.create_novel(id="ver2", title="版本内容")
    db.add_chapter("ver2", number=1, title="第一章", word_count=100, content="原文")
    db.save_chapter_version("ver2", 1, "版本内容ABC")
    versions = db.get_chapter_versions("ver2", 1)
    content = db.get_chapter_version_content(versions[0]["id"])
    assert content == "版本内容ABC"


def test_get_chapter_version_content_nonexistent(db):
    assert db.get_chapter_version_content(9999) is None


def test_save_chapter_version_nonexistent_chapter(db):
    db.create_novel(id="ver3", title="不存在的章节")
    # Should be a no-op
    db.save_chapter_version("ver3", 99, "内容", reason="test")
    versions = db.get_chapter_versions("ver3", 99)
    assert len(versions) == 0


def test_get_chapter_versions_nonexistent_chapter(db):
    db.create_novel(id="ver4", title="空版本")
    versions = db.get_chapter_versions("ver4", 1)
    assert versions == []
