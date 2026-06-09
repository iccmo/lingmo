"""ORM model/schema alignment tests."""

from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from novel_writer.db_models import Base, Chapter, Novel, create_db_engine
from novel_writer.services.novel_service import NovelService


def test_orm_core_tables_include_schema_fields(tmp_path):
    engine = create_db_engine(str(tmp_path / "orm.db"))
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    chapter_columns = {column["name"] for column in inspector.get_columns("chapters")}
    assert {
        "narrative_facts",
        "prompt_version",
        "edit_ratio",
    }.issubset(chapter_columns)

    cost_columns = {column["name"] for column in inspector.get_columns("cost_logs")}
    assert {"total_tokens", "purpose"}.issubset(cost_columns)

    trace_columns = {column["name"] for column in inspector.get_columns("chapter_traces")}
    assert {
        "novel_id",
        "chapter_num",
        "steps_json",
        "final_quality",
        "total_duration_ms",
        "total_cost",
    }.issubset(trace_columns)

    trace_uniques = inspector.get_unique_constraints("chapter_traces")
    assert any(
        set(unique["column_names"]) == {"novel_id", "chapter_num"}
        for unique in trace_uniques
    )


def test_novel_service_ignores_outline_placeholders_for_latest_chapter(tmp_path):
    engine = create_db_engine(str(tmp_path / "service.db"))
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        novel = Novel(id="svc-outline", title="服务层统计")
        novel.chapters.extend([
            Chapter(novel_id="svc-outline", number=1, title="第一章", word_count=1000, content="正文"),
            Chapter(novel_id="svc-outline", number=2, title="第二章大纲", word_count=0, summary="计划"),
        ])
        session.add(novel)
        session.commit()

        summary = NovelService(session).list_novels()[0]

        assert summary.total_chapters == 1
        assert summary.latest_chapter == {"number": 1, "title": "第一章", "generated_at": None}
    finally:
        session.close()


def test_novel_service_stats_count_only_generated_chapters(tmp_path):
    engine = create_db_engine(str(tmp_path / "service-stats.db"))
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        novel = Novel(id="svc-stats", title="服务层状态")
        novel.chapters.extend([
            Chapter(novel_id="svc-stats", number=1, title="第一章", word_count=1000, content="正文"),
            Chapter(novel_id="svc-stats", number=2, title="第二章大纲", word_count=0, summary="计划"),
        ])
        session.add(novel)
        session.commit()

        stats = NovelService(session).get_stats()

        assert stats["total_chapters"] == 1
        assert stats["total_words"] == 1000
    finally:
        session.close()
