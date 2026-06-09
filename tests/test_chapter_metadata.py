import json

from novel_writer.database import Database
from novel_writer.routers.novel import chapter_metadata
from novel_writer.routers.novel.chapter_metadata import update_chapter_content


def test_update_chapter_content_refreshes_continuity_metadata(tmp_path):
    db = Database(str(tmp_path / "metadata.db"))
    db.create_novel(id="meta-book", title="元数据同步")
    db.add_chapter(
        "meta-book",
        number=1,
        title="旧章",
        word_count=2,
        summary="旧",
        content="旧",
        narrative_facts=json.dumps(["旧事实"], ensure_ascii=False),
    )

    content = "叶凡发现古玉裂开，决定去黑水城寻找母亲留下的线索。"
    update_chapter_content(db, "meta-book", 1, content)

    chapter = db.get_chapter("meta-book", 1)
    assert chapter["content"] == content
    assert chapter["word_count"] == len(content)
    assert chapter["summary"] == content
    facts = json.loads(chapter["narrative_facts"])
    assert "旧事实" not in facts
    assert "叶凡发现古玉裂开，决定去黑水城寻找母亲留下的线索" in facts


def test_update_chapter_content_keeps_supported_continuity_metadata(tmp_path):
    db = Database(str(tmp_path / "metadata-supported.db"))
    db.create_novel(id="meta-supported", title="元数据同步")
    db.add_chapter(
        "meta-supported",
        number=1,
        title="旧章",
        word_count=2,
        summary="旧",
        content="旧",
        narrative_facts=json.dumps(["叶凡已经知道母亲留下黑水城线索"], ensure_ascii=False),
    )

    content = "叶凡已经知道母亲留下黑水城线索，但他决定暂时留在宗门等待师父。"
    update_chapter_content(db, "meta-supported", 1, content)

    chapter = db.get_chapter("meta-supported", 1)
    facts = json.loads(chapter["narrative_facts"])
    assert "叶凡已经知道母亲留下黑水城线索" in facts


def test_update_chapter_content_resets_stale_quality_when_body_changes(tmp_path):
    db = Database(str(tmp_path / "metadata-quality.db"))
    db.create_novel(id="meta-quality", title="质量同步")
    db.add_chapter(
        "meta-quality",
        number=1,
        title="旧章",
        word_count=3,
        summary="旧正文",
        content="旧正文",
        quality_score=0.92,
    )

    update_chapter_content(db, "meta-quality", 1, "新正文")

    chapter = db.get_chapter("meta-quality", 1)
    assert chapter["content"] == "新正文"
    assert chapter["quality_score"] == 0


def test_update_chapter_content_refreshes_chapter_summary_cache(tmp_path):
    db = Database(str(tmp_path / "metadata-summary-cache.db"))
    db.create_novel(id="meta-summary-cache", title="摘要缓存")
    db.add_chapter("meta-summary-cache", number=1, title="旧章", word_count=3, summary="旧正文", content="旧正文")
    db.save_chapter_summary("meta-summary-cache", 1, "旧缓存摘要")

    content = "叶凡决定押上古玉救人，因此受伤流血并暴露身份。"
    update_chapter_content(db, "meta-summary-cache", 1, content)

    summaries = db.get_chapter_summaries("meta-summary-cache", [1])
    assert summaries[0]["summary_text"] == content


def test_update_chapter_content_keeps_explicit_quality_score(tmp_path):
    db = Database(str(tmp_path / "metadata-explicit-quality.db"))
    db.create_novel(id="meta-explicit-quality", title="显式质量")
    db.add_chapter(
        "meta-explicit-quality",
        number=1,
        title="旧章",
        word_count=3,
        summary="旧正文",
        content="旧正文",
        quality_score=0.92,
    )

    update_chapter_content(db, "meta-explicit-quality", 1, "新正文", quality_score=0.81)

    chapter = db.get_chapter("meta-explicit-quality", 1)
    assert chapter["content"] == "新正文"
    assert chapter["quality_score"] == 0.81


def test_update_chapter_content_can_refresh_story_bible(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "meta-bible.db"))
    db.create_novel(id="meta-book", title="元数据同步")
    db.add_chapter("meta-book", number=1, title="裂纹", word_count=1, summary="旧", content="旧")
    calls = []

    monkeypatch.setattr(
        chapter_metadata,
        "extract_story_bible",
        lambda *args: calls.append(("extract", *args)),
    )
    monkeypatch.setattr(
        chapter_metadata,
        "run_consistency_check",
        lambda *args: calls.append(("check", *args)),
    )

    content = "叶凡发现古玉裂开。"
    update_chapter_content(db, "meta-book", 1, content, refresh_story_bible=True)

    assert ("extract", "meta-book", 1, content, "裂纹") in calls
    assert ("check", "meta-book", 1) in calls
