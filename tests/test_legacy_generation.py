from types import SimpleNamespace

from novel_writer.story_state import ChapterMeta
from novel_writer.routers.novel import _legacy


def test_generation_retry_context_preserves_hard_constraints():
    base = "【硬约束】\n叶凡必须保留父亲失踪创伤\n\n【角色蓝图硬约束】\n台词:我自己选，也自己扛。"
    repair = "请改进以下问题：节奏拖沓。保持其他部分不变。"

    merged = _legacy._with_generation_context(base, repair)

    assert "叶凡必须保留父亲失踪创伤" in merged
    assert "我自己选，也自己扛。" in merged
    assert "【本次修复要求】" in merged
    assert "节奏拖沓" in merged


def test_generation_retry_context_handles_empty_base():
    repair = "请改进以下问题：缺少钩子。"

    assert _legacy._with_generation_context("", repair) == repair


def test_pattern_disruption_prompt_preserves_agency_and_cost():
    prompt = _legacy._build_pattern_disruption_prompt(
        "叶凡主动押上古玉赢下擂台，却因此暴露身份并和师姐生出裂痕。"
    )

    assert "不得删除或淡化主角主动选择" in prompt
    assert "押注" in prompt
    assert "不得删除或淡化收益带来的代价" in prompt
    assert "身份暴露" in prompt
    assert "关系裂痕" in prompt
    assert "无代价开挂" in prompt


def test_final_save_quality_error_blocks_below_threshold():
    assert _legacy._final_save_quality_error({"overall": 0.82}, 0.8) == ""

    error = _legacy._final_save_quality_error({"overall": 0.62}, 0.8)

    assert "最终保存稿质量 0.62 低于门槛 0.80" in error
    assert "已拒绝落库" in error


def test_recovery_direction_keeps_core_quality_contract(minimal_state):
    prompt = _legacy._build_recovery_direction(minimal_state)

    assert "清晰主动选择" in prompt
    assert "拒绝、承担、冒险、反击或押注" in prompt
    assert "重要收益必须绑定具体代价或后果" in prompt
    assert "身份暴露" in prompt
    assert "关系裂痕" in prompt


def test_single_generation_persists_chapter_summary(monkeypatch):
    from novel_writer.routers.novel import generation_service

    summary_calls: list[tuple[str, int, str]] = []

    class FakeDb:
        def __init__(self):
            self.saved: list[dict] = []

        def get_novel(self, novel_id):
            return {
                "id": novel_id,
                "title": "记忆长篇",
                "author": "AI",
                "synopsis": "叶凡追查母亲留下的黑水城线索。",
                "genre": "玄幻",
                "main_arc": "追查身世",
                "current_arc": "黑水城",
                "arc_chapter_start": 1,
                "chapters": [],
                "characters": [],
                "plot_points": [],
            }

        def get_next_chapter_number(self, _novel_id):
            return 1

        def get_provider(self, _provider_id):
            return {"api_key": "sk-test", "base_url": "https://example.test", "models": ["fake-model"]}

        def list_providers(self):
            return []

        def get_style_profile(self, _novel_id):
            return None

        def get_all_foreshadowing(self, _novel_id):
            return []

        def get_unsaid(self, _novel_id):
            return []

        def add_chapter(self, **kwargs):
            self.saved.append(kwargs)
            return 1

        def log(self, *_args, **_kwargs):
            pass

        def get_chapter_traces(self, _novel_id):
            return []

        def save_style_profile(self, *_args, **_kwargs):
            pass

        class _Conn:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def execute(self, *_args, **_kwargs):
                return self

            def fetchall(self):
                return []

        def conn(self):
            return self._Conn()

    class FakeGenerator:
        def __init__(self, cfg):
            self.cfg = cfg
            self.model_switched = {}

        def _strip_thinking(self, text):
            return text

        def retrieve_relevant_context(self, **_kwargs):
            return []

        def get_global_context(self, *_args, **_kwargs):
            return ""

        def inject_lessons(self, *_args, **_kwargs):
            return ""

        def batch_generate(self, state, **_kwargs):
            chapter = ChapterMeta(
                number=state.total_chapters + 1,
                title="黑水城",
                word_count=180,
                summary="叶凡确认黑水城线索仍然有效。",
                content="叶凡确认黑水城线索仍然有效，决定把古玉裂纹的秘密继续隐瞒。" * 8,
                narrative_facts=["叶凡已经知道母亲留下黑水城线索"],
            )
            return chapter, {"overall": 0.9, "grade": "A", "issues": []}

        def get_dynamic_threshold(self, *_args, **_kwargs):
            return 0.5

        def score_quality(self, *_args, **_kwargs):
            return {"overall": 0.9, "grade": "A", "issues": []}

        def _call_llm_with_retry(self, messages, **_kwargs):
            content = messages[0]["content"]
            if "正文：" in content:
                return content.split("正文：", 1)[1].split("直接返回", 1)[0].strip()
            return "黑水城线索会推动叶凡追查母亲旧案"

        def de_ai(self, body):
            return body, 0

        def judge_quality(self, *_args, **_kwargs):
            return {"overall": 0.9, "grade": "A", "issues": [], "judge_detail": {}}

        def check_constraints(self, *_args, **_kwargs):
            return {"violations": []}

        def refresh_chapter_content(self, chapter, content):
            chapter.content = content
            chapter.word_count = len(content)
            chapter.summary = content[:200]
            return chapter

        def compute_quality_trend(self, *_args, **_kwargs):
            return None

        def _extract_character_voices(self, *_args, **_kwargs):
            pass

        def audit_foreshadowing(self, *_args, **_kwargs):
            return {}

    class FakeBrain:
        def __init__(self, _db):
            self.constraint_builder = SimpleNamespace(run=lambda *_args, **_kwargs: {})
            self.deslop_filter = SimpleNamespace(run=lambda *_args, **_kwargs: {"score": 50, "max_score": 50, "grade": "A"})
            self.consistency_checker = SimpleNamespace(run=lambda *_args, **_kwargs: {"error_count": 0, "confidence": 100})

    class FakeCompressor:
        def compress(self, *_args, **_kwargs):
            return {"text": "", "char_count": 0}

    fake_db = FakeDb()
    monkeypatch.setattr(_legacy, "db", fake_db)
    monkeypatch.setattr(_legacy, "_set_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(_legacy, "_gen_status", {"memory-single": {}})
    monkeypatch.setattr(_legacy, "BrainAgent", FakeBrain)
    monkeypatch.setattr(_legacy, "ConstraintCompressor", lambda: FakeCompressor())
    monkeypatch.setattr(_legacy, "extract_story_bible", lambda *args, **kwargs: None)
    monkeypatch.setattr(_legacy, "run_consistency_check", lambda *args, **kwargs: None)
    monkeypatch.setattr(_legacy, "_sync_resolved_foreshadowing", lambda *args, **kwargs: None)
    monkeypatch.setattr(_legacy, "_sync_new_foreshadowing", lambda *args, **kwargs: None)
    monkeypatch.setattr(_legacy, "_sync_next_plot_points", lambda *args, **kwargs: None)
    monkeypatch.setattr("novel_writer.generator.Generator", FakeGenerator)
    monkeypatch.setattr(
        generation_service,
        "_generate_single_chapter_summary",
        lambda novel_id, gen, chapter_num, content: summary_calls.append((novel_id, chapter_num, content)),
    )

    _legacy._run_generation("memory-single")

    assert fake_db.saved
    assert summary_calls
    assert summary_calls[0][0] == "memory-single"
    assert summary_calls[0][1] == 1
    assert "黑水城线索" in summary_calls[0][2]
