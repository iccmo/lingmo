from novel_writer.database import Database
from novel_writer.routers import deps
from novel_writer.routers.novel.generation_service import (
    _build_batch_targets,
    _batch_generate_with_retries,
    _retarget_generated_chapter,
    _sync_new_foreshadowing,
    _sync_next_plot_points,
    _sync_resolved_foreshadowing,
    get_queue_status,
    start_batch_job,
)
from novel_writer.routers.novel.revision_service import _load_state
from novel_writer.state import GenerationState
from novel_writer.story_state import ChapterMeta

LONG_BATCH_BODY = "叶凡握紧古玉，主动踏入雨夜，救下同伴后左臂受伤，身份也在黑水城前暴露。" * 60
ORPHAN_QUOTE_BATCH_BODY = ("「叶凡主动踏进黑水城，左臂的伤口还在流血，身份暴露后的追兵就压在身后。\n」\n" * 55)


class RetryGenerator:
    def __init__(self):
        self.seen_arcs = []
        self.author_inputs = []
        self.calls = 0

    def batch_generate(self, state, n, rag_context=None, outline=None, style=None, author_input=""):
        self.calls += 1
        self.seen_arcs.append(state.plot.current_arc)
        self.author_inputs.append(author_input)
        state.plot.current_arc = f"candidate-{self.calls}"
        chapter = ChapterMeta(
            number=state.total_chapters + 1,
            title=f"候选{self.calls}",
            word_count=20,
            summary=f"候选{self.calls}摘要",
            content=f"候选{self.calls}正文",
        )
        return chapter, {"overall": 0.4 if self.calls == 1 else 0.9, "grade": "B"}

    def score_quality(self, body, state, style=None):
        return {"overall": 0.9, "grade": "A"}


class EmptyGenerator:
    def batch_generate(self, state, n, rag_context=None, outline=None, style=None, author_input=""):
        state.plot.current_arc = "empty-candidate"
        return ChapterMeta(number=1, title="空", word_count=0, summary="", content=""), {"overall": 0.9}

    def score_quality(self, body, state, style=None):
        return {"overall": 0.9}


class ExplanationThenGoodGenerator:
    def __init__(self):
        self.calls = 0
        self.seen_arcs = []

    def batch_generate(self, state, n, rag_context=None, outline=None, style=None, author_input=""):
        self.calls += 1
        self.seen_arcs.append(state.plot.current_arc)
        state.plot.current_arc = f"candidate-{self.calls}"
        if self.calls == 1:
            state.plot.foreshadowing.append("坏候选伏笔")
            state.plot.next_plot_points = ["坏候选剧情目标"]
            content = "以下是第1章正文：\n\n我会加强主角主动性，并加入更多冲突。"
            return ChapterMeta(number=1, title="说明", word_count=len(content), summary="", content=content), {
                "overall": 0.95,
                "grade": "A",
            }
        state.plot.foreshadowing.append("好候选伏笔")
        state.plot.next_plot_points = ["好候选剧情目标"]
        return ChapterMeta(number=1, title="正文章", word_count=20, summary="", content="叶凡握紧古玉，推开雨幕，独自走向黑水城。"), {
            "overall": 0.9,
            "grade": "A",
        }

    def score_quality(self, body, state, style=None):
        return {"overall": 0.9, "grade": "A"}


class NoopThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass


class BatchGenerator:
    def __init__(self, *_args, **_kwargs):
        self._last_usage = {}

    def retrieve_relevant_context(self, **_kwargs):
        return []

    def batch_generate(self, state, n, rag_context=None, outline=None, style=None, author_input=""):
        chapter_num = state.total_chapters + 1
        return ChapterMeta(
            number=chapter_num,
            title=f"第{chapter_num}章",
            word_count=1200,
            summary=f"第{chapter_num}章摘要",
            content=LONG_BATCH_BODY,
        ), {"overall": 0.9, "grade": "A"}

    def _self_edit(self, body, state, style=None):
        return body

    def de_ai(self, body):
        return body, 0

    def judge_quality(self, body, state, style=None):
        return {"overall": 0.9, "grade": "A"}

    def refresh_chapter_content(self, chapter, body):
        chapter.content = body
        chapter.word_count = len(body)

    def _extract_character_voices(self, body, state):
        return None


class LowFinalQualityBatchGenerator(BatchGenerator):
    def judge_quality(self, body, state, style=None):
        return {"overall": 0.72, "grade": "C"}


class FinalDeAiFixesOrphanQuotesGenerator(BatchGenerator):
    def __init__(self, *_args, **_kwargs):
        super().__init__(*_args, **_kwargs)
        self.de_ai_calls = 0

    def batch_generate(self, state, n, rag_context=None, outline=None, style=None, author_input=""):
        return ChapterMeta(
            number=1,
            title="孤儿引号",
            word_count=len(ORPHAN_QUOTE_BATCH_BODY),
            summary="孤儿引号",
            content=ORPHAN_QUOTE_BATCH_BODY,
        ), {"overall": 0.92, "grade": "A"}

    def de_ai(self, body):
        self.de_ai_calls += 1
        if self.de_ai_calls == 1:
            return body.replace("追兵", "追兵"), 10
        return body.replace("\n」", "」"), 121


class UnfixedOrphanQuotesGenerator(FinalDeAiFixesOrphanQuotesGenerator):
    def de_ai(self, body):
        self.de_ai_calls += 1
        return body, 0


def test_batch_retry_restores_state_before_next_candidate(minimal_state):
    gen = RetryGenerator()

    chapter, quality, body, retries = _batch_generate_with_retries(
        gen,
        minimal_state,
        q_threshold=0.8,
        rag_context=[],
        outline=[],
        style=None,
    )

    assert gen.seen_arcs == ["开篇", "开篇"]
    assert retries == 1
    assert chapter.title == "候选2"
    assert body == "候选2正文"
    assert quality["overall"] == 0.9
    assert minimal_state.plot.current_arc == "candidate-2"


def test_batch_empty_candidate_restores_slot_state(minimal_state):
    _batch_generate_with_retries(
        EmptyGenerator(),
        minimal_state,
        q_threshold=0.8,
        rag_context=[],
        outline=[],
        style=None,
    )

    assert minimal_state.plot.current_arc == "开篇"


def test_batch_retries_high_score_explanation_candidate(minimal_state):
    gen = ExplanationThenGoodGenerator()

    chapter, quality, body, retries = _batch_generate_with_retries(
        gen,
        minimal_state,
        q_threshold=0.8,
        rag_context=[],
        outline=[],
        style=None,
    )

    assert retries == 1
    assert gen.seen_arcs == ["开篇", "开篇"]
    assert chapter.title == "正文章"
    assert body == "叶凡握紧古玉，推开雨幕，独自走向黑水城。"
    assert quality["overall"] == 0.9
    assert minimal_state.plot.current_arc == "candidate-2"
    assert "坏候选伏笔" not in minimal_state.plot.foreshadowing
    assert "好候选伏笔" in minimal_state.plot.foreshadowing
    assert minimal_state.plot.next_plot_points == ["好候选剧情目标"]


def test_batch_generate_with_retries_passes_author_input(minimal_state):
    gen = RetryGenerator()

    _batch_generate_with_retries(
        gen,
        minimal_state,
        q_threshold=0.8,
        rag_context=[],
        outline=[],
        style=None,
        author_input="【角色蓝图硬约束】叶凡",
    )

    assert gen.author_inputs == ["【角色蓝图硬约束】叶凡", "【角色蓝图硬约束】叶凡"]


def test_retarget_generated_chapter_updates_resolved_foreshadowing(minimal_state):
    minimal_state.plot.resolved_foreshadowing.append({"content": "铜镜背面藏着婚书", "chapter": 2})
    chapter = ChapterMeta(number=2, title="错位章", word_count=1000, summary="摘要", content="正文")

    source_chapter_num = _retarget_generated_chapter(minimal_state, chapter, 5)

    assert source_chapter_num == 2
    assert chapter.number == 5
    assert minimal_state.plot.resolved_foreshadowing == [{"content": "铜镜背面藏着婚书", "chapter": 5}]


def test_start_batch_job_appends_after_latest_generated_chapter(tmp_path, monkeypatch):
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-next-number.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        monkeypatch.setattr(service_module.threading, "Thread", NoopThread)
        db.create_novel(id="book", title="批量章号")
        db.add_chapter("book", number=1, title="第一章", word_count=1000, content="正文")
        db.add_chapter("book", number=2, title="第二章大纲", word_count=0, summary="计划")
        db.add_chapter("book", number=3, title="第三章", word_count=1000, content="正文")

        result = start_batch_job("book", count=2, quality_threshold=0.8)

        assert result["next_chapter"] == 4
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_queue_job_marks_error_when_batch_generates_no_chapters(monkeypatch):
    from novel_writer.routers.novel import generation_service as service_module

    job = {
        "job_id": "job-empty",
        "novel_id": "book",
        "status": "queued",
        "progress": {"current": 0, "total": 2},
        "count": 2,
        "quality_threshold": 0.8,
        "last_error": None,
    }
    monkeypatch.setattr(
        service_module,
        "run_batch_generation",
        lambda *_args, **_kwargs: {
            "requested": 2,
            "generated": 0,
            "failed": 2,
            "failed_slots": [1, 2],
            "message": "批量生成失败：0/2章产出有效内容",
        },
    )
    monkeypatch.setattr(service_module.threading, "Thread", NoopThread)

    service_module._run_queue_job(job)

    assert job["status"] == "error"
    assert job["progress"] == {"current": 2, "total": 2}
    assert job["last_error"] == "批量生成失败：0/2章产出有效内容"


def test_queue_status_exposes_recent_done_job_for_polling(tmp_path):
    db = Database(str(tmp_path / "queue-status-done.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        deps.get_gen_state()._job_queue["done-job"] = {
            "job_id": "done-job",
            "novel_id": "book",
            "status": "done",
            "progress": {"current": 2, "total": 2},
            "last_error": None,
        }

        status = get_queue_status("book")

        assert status == {
            "job_id": "done-job",
            "status": "done",
            "progress": {"current": 2, "total": 2},
            "last_error": None,
        }
        assert get_queue_status("book", active_only=True) is None
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_queue_status_exposes_recent_error_job_for_polling(tmp_path):
    db = Database(str(tmp_path / "queue-status-error.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        deps.get_gen_state()._job_queue["error-job"] = {
            "job_id": "error-job",
            "novel_id": "book",
            "status": "error",
            "progress": {"current": 0, "total": 2},
            "last_error": "生成失败",
        }

        status = get_queue_status("book")

        assert status["status"] == "error"
        assert status["last_error"] == "生成失败"
        assert get_queue_status("book", active_only=True) is None
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_generates_requested_count_without_outline(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-no-outline.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="无大纲批量")
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["fake"]})
        monkeypatch.setattr(generator_module, "Generator", BatchGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "extract_story_bible", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "run_consistency_check", lambda *_args, **_kwargs: None)

        service_module.run_batch_generation("book", count=2, quality_threshold=0.8)

        novel = db.get_novel("book")
        generated = [chapter for chapter in novel["chapters"] if chapter["word_count"] > 0]
        assert [chapter["number"] for chapter in generated] == [1, 2]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_reports_error_when_all_slots_are_empty(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-empty-all.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="空批量")
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["fake"]})
        monkeypatch.setattr(generator_module, "Generator", BatchGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)

        def empty_retry(*_args, **_kwargs):
            return ChapterMeta(number=1, title="空章", word_count=0, summary="", content=""), {"overall": 0.9}, "", 3

        monkeypatch.setattr(service_module, "_batch_generate_with_retries", empty_retry)

        result = service_module.run_batch_generation("book", count=2, quality_threshold=0.8)

        novel = db.get_novel("book")
        status = deps.get_gen_state().get_status("book")
        generated = [chapter for chapter in novel["chapters"] if chapter["word_count"] > 0]
        assert generated == []
        assert result["generated"] == 0
        assert result["failed"] == 2
        assert status["status"] == "error"
        assert "0/2章" in status["message"]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_rejects_explanation_as_invalid_chapter(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-invalid-output.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="说明文字拒绝")
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["fake"]})
        monkeypatch.setattr(generator_module, "Generator", BatchGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)

        def explanation_retry(*_args, **_kwargs):
            content = "以下是第1章正文：\n\n我会增强主角主动性，并加入更多冲突。"
            chapter = ChapterMeta(number=1, title="说明", word_count=len(content), summary="", content=content)
            return chapter, {"overall": 0.9, "grade": "A"}, content, 0

        monkeypatch.setattr(service_module, "_batch_generate_with_retries", explanation_retry)

        result = service_module.run_batch_generation("book", count=1, quality_threshold=0.8)

        novel = db.get_novel("book")
        status = deps.get_gen_state().get_status("book")
        generated = [chapter for chapter in novel["chapters"] if chapter["word_count"] > 0]
        assert generated == []
        assert result["generated"] == 0
        assert result["failed"] == 1
        assert status["status"] == "error"
        assert "有效正文" in status["message"]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_rejects_flash_short_final_text(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-flash-short.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    short_body = "叶凡主动救人并付出代价。" * 80
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="Flash短章拒绝")
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["flash"]})
        monkeypatch.setattr(generator_module, "Generator", BatchGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)

        def short_retry(*_args, **_kwargs):
            chapter = ChapterMeta(number=1, title="短章", word_count=len(short_body), summary="短章", content=short_body)
            return chapter, {"overall": 0.92, "grade": "A"}, short_body, 0

        monkeypatch.setattr(service_module, "_batch_generate_with_retries", short_retry)

        result = service_module.run_batch_generation("book", count=1, quality_threshold=0.8)

        novel = db.get_novel("book")
        status = deps.get_gen_state().get_status("book")
        generated = [chapter for chapter in novel["chapters"] if chapter["word_count"] > 0]
        assert generated == []
        assert result["generated"] == 0
        assert result["failed"] == 1
        assert status["status"] == "error"
        assert "字数不足1000字" in status["message"]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_rejects_final_quality_below_threshold(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-low-final-quality.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="最终分拒绝")
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["flash"]})
        monkeypatch.setattr(generator_module, "Generator", LowFinalQualityBatchGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)

        result = service_module.run_batch_generation("book", count=1, quality_threshold=0.8)

        novel = db.get_novel("book")
        status = deps.get_gen_state().get_status("book")
        generated = [chapter for chapter in novel["chapters"] if chapter["word_count"] > 0]
        assert generated == []
        assert result["generated"] == 0
        assert result["failed"] == 1
        assert status["status"] == "error"
        assert "质量分 0.72 低于门槛 0.80" in status["message"]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_saves_final_de_ai_text(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-final-de-ai.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="最终去AI落库")
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["flash"]})
        monkeypatch.setattr(generator_module, "Generator", FinalDeAiFixesOrphanQuotesGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "extract_story_bible", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "run_consistency_check", lambda *_args, **_kwargs: None)

        result = service_module.run_batch_generation("book", count=1, quality_threshold=0.8)

        chapter = db.get_chapter("book", 1)
        assert result["generated"] == 1
        assert chapter is not None
        assert "\n」" not in chapter["content"]
        assert chapter["content"].count("」") == ORPHAN_QUOTE_BATCH_BODY.count("」")

    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_rejects_remaining_orphan_quotes(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-orphan-reject.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="孤儿引号拒绝")
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["flash"]})
        monkeypatch.setattr(generator_module, "Generator", UnfixedOrphanQuotesGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)

        result = service_module.run_batch_generation("book", count=1, quality_threshold=0.8)

        status = deps.get_gen_state().get_status("book")
        assert db.get_chapter("book", 1) is None
        assert result["generated"] == 0
        assert result["failed"] == 1
        assert status["status"] == "error"
        assert "孤儿引号" in status["message"]

    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_reports_partial_count_when_empty_slots_are_skipped(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-empty-partial.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    calls = {"count": 0}
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="部分空批量")
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["fake"]})
        monkeypatch.setattr(generator_module, "Generator", BatchGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "extract_story_bible", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "run_consistency_check", lambda *_args, **_kwargs: None)

        def sometimes_empty(*_args, **_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return ChapterMeta(number=1, title="空章", word_count=0, summary="", content=""), {"overall": 0.9}, "", 3
            chapter = ChapterMeta(number=2, title="第二章", word_count=len(LONG_BATCH_BODY), summary="摘要", content=LONG_BATCH_BODY)
            return chapter, {"overall": 0.9, "grade": "A"}, chapter.content, 0

        monkeypatch.setattr(service_module, "_batch_generate_with_retries", sometimes_empty)

        result = service_module.run_batch_generation("book", count=2, quality_threshold=0.8)

        novel = db.get_novel("book")
        status = deps.get_gen_state().get_status("book")
        generated = [chapter for chapter in novel["chapters"] if chapter["word_count"] > 0]
        assert [chapter["number"] for chapter in generated] == [2]
        assert result["generated"] == 1
        assert result["failed"] == 1
        assert result["failed_slots"] == [1]
        assert status["status"] == "complete"
        assert "1/2章" in status["message"]
        assert "第1章内容为空" in status["message"]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_skips_stale_outline_gaps(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-skip-stale-outline.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="跳过旧大纲空洞")
        db.add_chapter("book", number=1, title="第一章", word_count=1000, content="正文")
        db.add_chapter("book", number=2, title="第二章大纲", word_count=0, summary="旧计划")
        db.add_chapter("book", number=3, title="第三章", word_count=1000, content="正文")
        minimal_state.chapters = [
            ChapterMeta(number=1, title="第一章", word_count=1000, summary="一", content="正文"),
            ChapterMeta(number=3, title="第三章", word_count=1000, summary="三", content="正文"),
        ]
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["fake"]})
        monkeypatch.setattr(generator_module, "Generator", BatchGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "extract_story_bible", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "run_consistency_check", lambda *_args, **_kwargs: None)

        service_module.run_batch_generation("book", count=2, quality_threshold=0.8)

        novel = db.get_novel("book")
        generated = [chapter for chapter in novel["chapters"] if chapter["word_count"] > 0]
        placeholders = [chapter for chapter in novel["chapters"] if chapter["word_count"] == 0]
        assert [chapter["number"] for chapter in generated] == [1, 3, 4, 5]
        assert [chapter["number"] for chapter in placeholders] == [2]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_syncs_story_bible_with_target_chapter_number(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-target-story-bible.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    story_bible_calls = []
    consistency_calls = []
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="目标章号同步")
        db.add_chapter("book", number=1, title="第一章", word_count=1000, content="正文")
        db.add_chapter("book", number=2, title="第二章大纲", word_count=0, summary="旧计划")
        db.add_chapter("book", number=3, title="第三章", word_count=1000, content="正文")
        minimal_state.chapters = [
            ChapterMeta(number=1, title="第一章", word_count=1000, summary="一", content="正文"),
            ChapterMeta(number=3, title="第三章", word_count=1000, summary="三", content="正文"),
        ]
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["fake"]})
        monkeypatch.setattr(generator_module, "Generator", BatchGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(
            service_module,
            "extract_story_bible",
            lambda novel_id, chapter_num, content, title: story_bible_calls.append((chapter_num, title)),
        )
        monkeypatch.setattr(
            service_module,
            "run_consistency_check",
            lambda novel_id, chapter_num: consistency_calls.append(chapter_num),
        )

        service_module.run_batch_generation("book", count=1, quality_threshold=0.8)

        assert story_bible_calls == [(4, "第4章")]
        assert consistency_calls == [4]
        assert minimal_state.chapters[-1].number == 4
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_run_batch_generation_does_not_jump_to_far_future_outline(tmp_path, monkeypatch, minimal_state):
    from novel_writer import generator as generator_module
    from novel_writer.routers.novel import generation_service as service_module

    db = Database(str(tmp_path / "batch-future-outline.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="不跳远期大纲")
        db.add_chapter("book", number=1, title="第一章", word_count=1000, content="正文")
        db.add_chapter("book", number=10, title="第十章大纲", word_count=0, summary="远期计划")
        minimal_state.chapters = [
            ChapterMeta(number=1, title="第一章", word_count=1000, summary="一", content="正文"),
        ]
        monkeypatch.setattr(service_module, "_get_provider", lambda _novel_id: {"api_key": "", "base_url": "", "models": ["fake"]})
        monkeypatch.setattr(generator_module, "Generator", BatchGenerator)
        monkeypatch.setattr(service_module, "_load_state", lambda _novel_id: minimal_state)
        monkeypatch.setattr(service_module, "_style_for", lambda _novel_id: None)
        monkeypatch.setattr(service_module, "_ensure_smart_context", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "extract_story_bible", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(service_module, "run_consistency_check", lambda *_args, **_kwargs: None)

        service_module.run_batch_generation("book", count=2, quality_threshold=0.8)

        novel = db.get_novel("book")
        generated = [chapter for chapter in novel["chapters"] if chapter["word_count"] > 0]
        placeholders = [chapter for chapter in novel["chapters"] if chapter["word_count"] == 0]
        assert [chapter["number"] for chapter in generated] == [1, 2, 3]
        assert [chapter["number"] for chapter in placeholders] == [10]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_build_batch_targets_keeps_generation_slots_contiguous(tmp_path):
    db = Database(str(tmp_path / "batch-targets-contiguous.db"))
    db.create_novel(id="book", title="连续槽位")
    db.add_chapter("book", number=1, title="第一章", word_count=1000, content="正文")
    db.add_chapter("book", number=10, title="第十章大纲", word_count=0, summary="远期计划")

    targets = _build_batch_targets(db, "book", count=3)

    assert [target["number"] for target in targets] == [2, 3, 4]
    assert all(target["summary"] != "远期计划" for target in targets)


def test_generate_summary_prompt_preserves_agency_and_cost():
    from novel_writer.routers.novel.generation_service import _generate_summary_with_llm

    seen: dict[str, str] = {}

    class FakeGenerator:
        def _call_llm_with_retry(self, messages, max_tokens=128):
            seen["system"] = messages[0]["content"]
            seen["user"] = messages[1]["content"]
            return "叶凡主动进城拿到线索，却暴露身份并欠下债务。"

    summary = _generate_summary_with_llm(
        FakeGenerator(),
        "book",
        1,
        "叶凡决定独自进城，拿到玄月宗线索，却暴露身份并欠下人情债。",
    )

    assert "主角主动选择" in seen["system"]
    assert "代价/后果" in seen["system"]
    assert "暴露风险" in seen["system"]
    assert summary == "叶凡主动进城拿到线索，却暴露身份并欠下债务。"


def test_load_state_includes_active_and_overdue_foreshadowing(tmp_path):
    db = Database(str(tmp_path / "load-foreshadowing.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="伏笔加载")
        db.save_foreshadowing("book", 1, "青铜铃会在月圆夜响起", due_by=3)
        db.save_foreshadowing("book", 2, "镜中人知道真相", due_by=5)
        thread = db.get_active_foreshadowing("book")[0]
        db.resolve_foreshadowing(thread["id"], 3, "青铜铃已经响起")
        overdue = db.get_active_foreshadowing("book")[0]
        with db.conn() as conn:
            conn.execute("UPDATE foreshadowing_tracker SET status='overdue' WHERE id=?", (overdue["id"],))

        state = _load_state("book")

        assert state is not None
        assert state.plot is not None
        assert "镜中人知道真相" in state.plot.foreshadowing
        assert "青铜铃会在月圆夜响起" not in state.plot.foreshadowing

    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_load_state_includes_unresolved_plot_points(tmp_path):
    db = Database(str(tmp_path / "load-plot-points.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="剧情点加载")
        with db.conn() as conn:
            conn.execute(
                "INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
                ("book", "plot", "调查铜镜来源", 0, 1),
            )
            conn.execute(
                "INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
                ("book", "plot", "已完成的旧目标", 1, 2),
            )
            conn.execute(
                "INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
                ("book", "foreshadowing", "这不是剧情目标", 0, 3),
            )

        state = _load_state("book")

        assert state is not None
        assert state.plot is not None
        assert state.plot.next_plot_points == ["调查铜镜来源"]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_legacy_load_state_includes_continuity_context(tmp_path):
    from novel_writer.routers.novel import _legacy

    db = Database(str(tmp_path / "legacy-load-state.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="旧入口状态")
        db.save_foreshadowing("book", 1, "青铜铃会在月圆夜响起", due_by=3)
        with db.conn() as conn:
            conn.execute(
                "INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
                ("book", "plot", "调查铜镜来源", 0, 1),
            )

        state = _legacy._load_state("book")

        assert state is not None
        assert state.plot is not None
        assert state.plot.foreshadowing == ["青铜铃会在月圆夜响起"]
        assert state.plot.next_plot_points == ["调查铜镜来源"]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_sync_resolved_foreshadowing_updates_database(tmp_path, minimal_state):
    db = Database(str(tmp_path / "sync-foreshadowing.db"))
    db.create_novel(id="book", title="伏笔同步")
    db.save_foreshadowing("book", 1, "父亲下落成谜", due_by=4)
    minimal_state.plot.resolved_foreshadowing.append({"content": "父亲下落成谜", "chapter": 3})

    _sync_resolved_foreshadowing(db, "book", minimal_state, 3)

    threads = db.get_all_foreshadowing("book")
    assert threads[0]["status"] == "resolved"
    assert threads[0]["resolved_chapter"] == 3


def test_sync_resolved_foreshadowing_uses_fuzzy_match(tmp_path, minimal_state):
    db = Database(str(tmp_path / "sync-fuzzy-foreshadowing.db"))
    db.create_novel(id="book", title="伏笔模糊同步")
    db.save_foreshadowing("book", 1, "青铜铃会在月圆夜响起", due_by=4)
    minimal_state.plot.resolved_foreshadowing.append({"content": "青铜铃响起", "chapter": 3})

    _sync_resolved_foreshadowing(db, "book", minimal_state, 3)

    threads = db.get_all_foreshadowing("book")
    assert threads[0]["status"] == "resolved"
    assert threads[0]["resolved_chapter"] == 3


def test_sync_resolved_foreshadowing_ignores_unrelated_match(tmp_path, minimal_state):
    db = Database(str(tmp_path / "sync-unrelated-foreshadowing.db"))
    db.create_novel(id="book", title="伏笔防误回收")
    db.save_foreshadowing("book", 1, "青铜铃会在月圆夜响起", due_by=4)
    minimal_state.plot.resolved_foreshadowing.append({"content": "父亲已经回家", "chapter": 3})

    _sync_resolved_foreshadowing(db, "book", minimal_state, 3)

    threads = db.get_all_foreshadowing("book")
    assert threads[0]["status"] == "active"
    assert threads[0]["resolved_chapter"] is None


def test_sync_resolved_foreshadowing_accepts_generated_source_chapter(tmp_path, minimal_state):
    db = Database(str(tmp_path / "sync-source-chapter.db"))
    db.create_novel(id="book", title="伏笔目标章号")
    db.save_foreshadowing("book", 1, "铜镜背面藏着婚书", due_by=5)
    minimal_state.plot.resolved_foreshadowing.append({"content": "铜镜背面藏着婚书", "chapter": 3})

    _sync_resolved_foreshadowing(db, "book", minimal_state, 5, source_chapter_num=3)

    threads = db.get_all_foreshadowing("book")
    assert threads[0]["status"] == "resolved"
    assert threads[0]["resolved_chapter"] == 5


def test_sync_new_foreshadowing_persists_generated_threads(tmp_path, minimal_state):
    db = Database(str(tmp_path / "sync-new-foreshadowing.db"))
    db.create_novel(id="book", title="新伏笔同步")
    minimal_state.plot.foreshadowing = ["铜镜背面藏着婚书", "雨夜黑衣人认得叶凡"]

    _sync_new_foreshadowing(db, "book", minimal_state, 3)

    threads = db.get_all_foreshadowing("book")
    assert [thread["description"] for thread in threads] == ["铜镜背面藏着婚书", "雨夜黑衣人认得叶凡"]
    assert {thread["created_chapter"] for thread in threads} == {3}


def test_sync_new_foreshadowing_deduplicates_existing_threads(tmp_path, minimal_state):
    db = Database(str(tmp_path / "sync-new-foreshadowing-dedupe.db"))
    db.create_novel(id="book", title="新伏笔去重")
    db.save_foreshadowing("book", 1, "铜镜背面藏着婚书", due_by=5)
    minimal_state.plot.foreshadowing = ["铜镜背面藏着婚书", "铜镜里藏着婚书", "雨夜黑衣人认得叶凡"]

    _sync_new_foreshadowing(db, "book", minimal_state, 3)

    threads = db.get_all_foreshadowing("book")
    descriptions = [thread["description"] for thread in threads]
    assert descriptions.count("铜镜背面藏着婚书") == 1
    assert "铜镜里藏着婚书" not in descriptions
    assert "雨夜黑衣人认得叶凡" in descriptions


def test_sync_next_plot_points_persists_generated_targets(tmp_path, minimal_state):
    db = Database(str(tmp_path / "sync-next-plot.db"))
    db.create_novel(id="book", title="剧情目标同步")
    minimal_state.plot.next_plot_points = ["调查铜镜来源", "寻找失踪证人"]

    _sync_next_plot_points(db, "book", minimal_state)

    novel = db.get_novel("book")
    assert novel is not None
    assert [point["content"] for point in novel["plot_points"]] == ["调查铜镜来源", "寻找失踪证人"]


def test_sync_next_plot_points_deduplicates_existing_targets(tmp_path, minimal_state):
    db = Database(str(tmp_path / "sync-next-plot-dedupe.db"))
    db.create_novel(id="book", title="剧情目标去重")
    with db.conn() as conn:
        conn.execute(
            "INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
            ("book", "plot", "调查铜镜来源", 0, 1),
        )
    minimal_state.plot.next_plot_points = ["调查铜镜来源", "寻找失踪证人"]

    _sync_next_plot_points(db, "book", minimal_state)

    novel = db.get_novel("book")
    assert novel is not None
    assert [point["content"] for point in novel["plot_points"]].count("调查铜镜来源") == 1
    assert "寻找失踪证人" in [point["content"] for point in novel["plot_points"]]


def test_sync_next_plot_points_archives_replaced_targets(tmp_path, minimal_state):
    db = Database(str(tmp_path / "sync-next-plot-archive.db"))
    db.create_novel(id="book", title="剧情目标归档")
    with db.conn() as conn:
        conn.execute(
            "INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
            ("book", "plot", "调查铜镜来源", 0, 1),
        )
        conn.execute(
            "INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
            ("book", "plot", "寻找旧证人", 0, 2),
        )
    minimal_state.plot.next_plot_points = ["调查铜镜来源", "寻找失踪证人"]

    _sync_next_plot_points(db, "book", minimal_state)

    novel = db.get_novel("book")
    assert novel is not None
    active = [point["content"] for point in novel["plot_points"] if not point["is_resolved"]]
    resolved = [point["content"] for point in novel["plot_points"] if point["is_resolved"]]
    assert active == ["调查铜镜来源", "寻找失踪证人"]
    assert resolved == ["寻找旧证人"]
