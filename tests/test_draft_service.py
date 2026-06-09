import json
from types import SimpleNamespace

from novel_writer.database import Database
from novel_writer.routers.novel import draft_service


class FakeExpandGenerator:
    def expand(self, state, draft, edits, author_input=""):
        return (
            "古玉裂声",
            "叶凡发现古玉裂开，决定去黑水城寻找母亲留下的线索。"
            "黑衣人暴露了玄月宗暗号，却在说出真相前坠入深渊。",
        )

    def de_ai(self, body):
        return body, 0

    def score_quality(self, body, state):
        return {"overall": 0.82, "grade": "A", "issues": []}

    def judge_quality(self, body, state):
        return {"overall": 0.84, "grade": "A"}

    @staticmethod
    def _normalize_text_list(value, limit=8):
        from novel_writer.generator import Generator

        return Generator._normalize_text_list(value, limit=limit)

    def _extract_narrative_facts(self, meta, body):
        from novel_writer.generator import Generator

        return Generator()._extract_narrative_facts(meta, body)


class StatefulExpandGenerator(FakeExpandGenerator):
    def expand(self, state, draft, edits, author_input=""):
        state.plot.next_plot_points = ["去黑水城查玄月宗"]
        state.plot.foreshadowing.append("黑衣人临死前攥紧的铜扣")
        state.plot.resolved_foreshadowing.append({"content": "古玉裂纹", "chapter": state.total_chapters + 1})
        return super().expand(state, draft, edits, author_input=author_input)


class ExplanationExpandGenerator(FakeExpandGenerator):
    def expand(self, state, draft, edits, author_input=""):
        return "说明稿", "以下是扩写后的章节：\n\n我会加强主角主动性，并加入更多冲突。"


def test_run_expand_persists_memory_metadata(tmp_path, minimal_state, monkeypatch):
    db = Database(str(tmp_path / "draft.db"))
    db.create_novel(id="draft-book", title="草稿扩写", genre="玄幻")

    monkeypatch.setattr(draft_service, "get_db", lambda: db)
    monkeypatch.setattr(draft_service, "_load_state", lambda novel_id: minimal_state)
    monkeypatch.setattr(draft_service, "generator_for", lambda novel_id: FakeExpandGenerator())
    monkeypatch.setattr(draft_service, "_config_for", lambda novel_id: SimpleNamespace(model="fake-model"))

    draft_service.run_expand(
        "draft-book",
        chosen_id="d1",
        direction="叶凡调查古玉裂纹；黑衣人再次出现",
        preview="叶凡发现古玉裂开",
        hook="黑衣人说出玄月宗暗号",
        edits="",
    )

    chapter = db.get_novel("draft-book")["chapters"][0]
    assert chapter["ending_hook"] == "黑衣人说出玄月宗暗号"
    assert json.loads(chapter["key_events"]) == ["叶凡调查古玉裂纹", "黑衣人再次出现", "叶凡发现古玉裂开"]
    assert json.loads(chapter["narrative_facts"])
    assert minimal_state.chapters[-1].narrative_facts == json.loads(chapter["narrative_facts"])


def test_run_expand_syncs_story_state(tmp_path, minimal_state, monkeypatch):
    db = Database(str(tmp_path / "draft-state.db"))
    db.create_novel(id="draft-book", title="草稿扩写", genre="玄幻")
    db.save_foreshadowing("draft-book", 1, "古玉裂纹", due_by=2)

    monkeypatch.setattr(draft_service, "get_db", lambda: db)
    monkeypatch.setattr(draft_service, "_load_state", lambda novel_id: minimal_state)
    monkeypatch.setattr(draft_service, "generator_for", lambda novel_id: StatefulExpandGenerator())
    monkeypatch.setattr(draft_service, "_config_for", lambda novel_id: SimpleNamespace(model="fake-model"))
    monkeypatch.setattr(draft_service, "extract_story_bible", lambda *args, **kwargs: None)
    monkeypatch.setattr(draft_service, "run_consistency_check", lambda *args, **kwargs: None)

    draft_service.run_expand(
        "draft-book",
        chosen_id="d1",
        direction="叶凡调查古玉裂纹；黑衣人再次出现",
        preview="叶凡发现古玉裂开",
        hook="黑衣人说出玄月宗暗号",
        edits="",
    )

    foreshadowing = db.get_all_foreshadowing("draft-book")
    old_thread = next(thread for thread in foreshadowing if thread["description"] == "古玉裂纹")
    assert old_thread["status"] == "resolved"
    assert any(thread["description"] == "黑衣人临死前攥紧的铜扣" for thread in foreshadowing)
    novel = db.get_novel("draft-book")
    assert novel is not None
    assert [point["content"] for point in novel["plot_points"]] == ["去黑水城查玄月宗"]


def test_run_expand_rejects_explanation_without_saving_chapter(tmp_path, minimal_state, monkeypatch):
    db = Database(str(tmp_path / "draft-invalid.db"))
    db.create_novel(id="draft-book", title="草稿扩写", genre="玄幻")

    monkeypatch.setattr(draft_service, "get_db", lambda: db)
    monkeypatch.setattr(draft_service, "_load_state", lambda novel_id: minimal_state)
    monkeypatch.setattr(draft_service, "generator_for", lambda novel_id: ExplanationExpandGenerator())
    monkeypatch.setattr(draft_service, "_config_for", lambda novel_id: SimpleNamespace(model="fake-model"))

    draft_service.run_expand(
        "draft-book",
        chosen_id="d1",
        direction="叶凡调查古玉裂纹",
        preview="叶凡发现古玉裂开",
        hook="黑衣人说出玄月宗暗号",
        edits="",
    )

    novel = db.get_novel("draft-book")
    assert novel["chapters"] == []
    logs = db.get_logs()
    assert any(
        log["event"] == "expand.failed"
        and "有效章节正文" in json.loads(log["detail"])["error"]
        for log in logs
    )
