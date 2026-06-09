from novel_writer.routers.novel import orchestration_service
from novel_writer.story_state import ChapterMeta


class FakePipelineDb:
    def __init__(self):
        self.logs = []

    def get_style_profile(self, novel_id):
        return None

    def get_novel(self, novel_id):
        return {
            "chapters": [
                {"number": 1, "title": "第一章", "summary": "一", "word_count": 1000, "quality_score": 0.9},
                {"number": 2, "title": "第二章", "summary": "二", "word_count": 1000, "quality_score": 0.6},
                {"number": 3, "title": "第三章", "summary": "三", "word_count": 1000, "quality_score": 0.9},
                {"number": 4, "title": "第四章", "summary": "四", "word_count": 1000, "quality_score": 0.9},
                {"number": 5, "title": "第五章", "summary": "五", "word_count": 1000, "quality_score": 0.9},
            ]
        }

    def log(self, novel_id, event, detail):
        self.logs.append((event, detail))


class FakePipelineGenerator:
    def generate_chapters(self, state, n, style=None, author_input=""):
        return []

    def revise_opening(self, state, target_chapters=3, style=None):
        return [
            ChapterMeta(number=1, title="第一章", word_count=10, summary="回修", content="回修正文"),
        ]

    def generate_chapter_classic(self, state, style=None, author_input=""):
        return ChapterMeta(number=99, title="弱章新稿", word_count=10, summary="重写", content="弱章重写正文")


class BadRewriteGenerator(FakePipelineGenerator):
    def revise_opening(self, state, target_chapters=3, style=None):
        return [
            ChapterMeta(number=1, title="第一章", word_count=0, summary="", content=""),
        ]

    def generate_chapter_classic(self, state, style=None, author_input=""):
        return ChapterMeta(number=99, title="弱章新稿", word_count=10, summary="重写", content="弱章重写正文")


def test_run_pipeline_refreshes_story_bible_after_rewrites(minimal_state, monkeypatch):
    db = FakePipelineDb()
    calls = []
    minimal_state.chapters = [
        ChapterMeta(number=i, title=f"第{i}章", word_count=1000, summary=str(i), content=f"正文{i}")
        for i in range(1, 6)
    ]

    monkeypatch.setattr(orchestration_service, "get_db", lambda: db)
    monkeypatch.setattr(orchestration_service, "_generator_for", lambda novel_id: FakePipelineGenerator())
    monkeypatch.setattr(orchestration_service, "_load_state", lambda novel_id: minimal_state)
    monkeypatch.setattr(orchestration_service, "build_creation_brief", lambda db, novel_id: "创作硬约束")
    monkeypatch.setattr(orchestration_service, "_set_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        orchestration_service,
        "update_chapter_content",
        lambda db, novel_id, chapter_num, content, **kwargs: calls.append((chapter_num, content, kwargs)),
    )

    orchestration_service.run_pipeline("book")

    assert (1, "回修正文", {"refresh_story_bible": True}) in calls
    assert (2, "弱章重写正文", {"refresh_story_bible": True}) in calls


def test_run_pipeline_rejects_bad_rewrite_without_overwriting(minimal_state, monkeypatch):
    db = FakePipelineDb()
    calls = []
    minimal_state.chapters = [
        ChapterMeta(
            number=i,
            title=f"第{i}章",
            word_count=120,
            summary=str(i),
            content="叶凡握紧古玉，决定独自进城。他知道这一步会暴露身份，却仍然推开雨幕。城门后有人低声叫出他的名字。",
        )
        for i in range(1, 6)
    ]

    monkeypatch.setattr(orchestration_service, "get_db", lambda: db)
    monkeypatch.setattr(orchestration_service, "_generator_for", lambda novel_id: BadRewriteGenerator())
    monkeypatch.setattr(orchestration_service, "_load_state", lambda novel_id: minimal_state)
    monkeypatch.setattr(orchestration_service, "build_creation_brief", lambda db, novel_id: "创作硬约束")
    monkeypatch.setattr(orchestration_service, "_set_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        orchestration_service,
        "update_chapter_content",
        lambda db, novel_id, chapter_num, content, **kwargs: calls.append((chapter_num, content, kwargs)),
    )

    orchestration_service.run_pipeline("book")

    assert not any(call[0] == 1 for call in calls)
    assert any(event == "pipeline.rewrite_rejected" and detail["chapter"] == 1 for event, detail in db.logs)
