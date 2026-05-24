"""Database CRUD tests — isolated per test via tmp_path fixture"""
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
