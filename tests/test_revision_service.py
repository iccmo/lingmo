from novel_writer.database import Database
from novel_writer.routers import deps
from novel_writer.routers.novel import chapter_metadata, revision_service
from novel_writer.state import GenerationState


def _install_test_deps(db: Database):
    old_db = deps._db
    old_gen_state = deps._gen_state
    deps.init_deps(db, GenerationState())
    return old_db, old_gen_state


def _restore_test_deps(old_db, old_gen_state):
    deps._db = old_db
    deps._gen_state = old_gen_state


def _seed_chapter(db: Database, novel_id: str, content: str):
    db.create_novel(id=novel_id, title="修订保护")
    db.add_chapter(
        novel_id,
        number=1,
        title="第一章",
        content=content,
        word_count=len(content),
    )


def test_run_revise_chapter_accepts_body_like_revision(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "revision-ok.db"))
    old_db, old_gen_state = _install_test_deps(db)
    original = "叶凡握紧古玉，决定独自进城。他知道这一步会暴露身份，却仍然推开雨幕。城门后有人低声叫出他的名字。"
    revised = "叶凡握紧裂开的古玉，决定独自进城。他知道这一步会暴露身份，也会欠下师父的人情，却仍然推开雨幕。城门后有人低声叫出他的名字。"
    _seed_chapter(db, "book", original)

    class FakeGenerator:
        def revise_chapter(self, *_args, **_kwargs):
            return revised

    monkeypatch.setattr(revision_service, "_generator_for", lambda *_args: FakeGenerator())
    monkeypatch.setattr(revision_service, "_load_state", lambda *_args: object())
    monkeypatch.setattr(
        revision_service,
        "update_chapter_content",
        lambda db_arg, novel_id, chapter_num, content, **_kwargs:
            chapter_metadata.update_chapter_content(db_arg, novel_id, chapter_num, content),
    )

    try:
        revision_service.run_revise_chapter("book", 1, "补足代价")

        chapter = db.get_chapter("book", 1)
        assert chapter["content"] == revised
        assert deps.get_gen_state().get_status("book")["status"] == "complete"
    finally:
        _restore_test_deps(old_db, old_gen_state)


def test_run_revise_chapter_rejects_explanation_output_without_overwriting(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "revision-bad.db"))
    old_db, old_gen_state = _install_test_deps(db)
    original = "叶凡握紧古玉，决定独自进城。他知道这一步会暴露身份，却仍然推开雨幕。城门后有人低声叫出他的名字。"
    _seed_chapter(db, "book", original)

    class FakeGenerator:
        def revise_chapter(self, *_args, **_kwargs):
            return "以下是修改后的章节：\n\n我加强了主角主动性，并增加了胜利代价。"

    monkeypatch.setattr(revision_service, "_generator_for", lambda *_args: FakeGenerator())
    monkeypatch.setattr(revision_service, "_load_state", lambda *_args: object())

    try:
        revision_service.run_revise_chapter("book", 1, "补足代价")

        chapter = db.get_chapter("book", 1)
        status = deps.get_gen_state().get_status("book")
        assert chapter["content"] == original
        assert status["status"] == "error"
        assert "说明文字" in status["message"]
    finally:
        _restore_test_deps(old_db, old_gen_state)


def test_run_humanize_rejects_bad_output_without_overwriting(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "humanize-bad.db"))
    old_db, old_gen_state = _install_test_deps(db)
    original = "叶凡握紧古玉，决定独自进城。他知道这一步会暴露身份，却仍然推开雨幕。城门后有人低声叫出他的名字。"
    _seed_chapter(db, "book", original)

    class FakeGenerator:
        def humanize(self, *_args, **_kwargs):
            return "以下是去AI味后的说明：我删掉了套话，并调整了节奏。"

    monkeypatch.setattr(revision_service, "_generator_for", lambda *_args: FakeGenerator())

    try:
        revision_service.run_humanize("book", 1)

        chapter = db.get_chapter("book", 1)
        status = deps.get_gen_state().get_status("book")
        assert chapter["content"] == original
        assert status["status"] == "error"
        assert "说明文字" in status["message"]
    finally:
        _restore_test_deps(old_db, old_gen_state)


def test_run_polish_skips_bad_output_without_overwriting(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "polish-bad.db"))
    old_db, old_gen_state = _install_test_deps(db)
    original = "叶凡握紧古玉，决定独自进城。他知道这一步会暴露身份，却仍然推开雨幕。城门后有人低声叫出他的名字。"
    _seed_chapter(db, "book", original)

    class FakeGenerator:
        def _call_llm_with_retry(self, *_args, **_kwargs):
            return "修改说明：本章节奏已经调整，角色主动性也更明显。"

    monkeypatch.setattr(revision_service, "_generator_for", lambda *_args: FakeGenerator())

    try:
        revision_service.run_polish("book")

        chapter = db.get_chapter("book", 1)
        status = deps.get_gen_state().get_status("book")
        assert chapter["content"] == original
        assert status["status"] == "complete"
        assert db.get_chapter_versions("book", 1) == []
    finally:
        _restore_test_deps(old_db, old_gen_state)


def test_run_polish_prompt_preserves_agency_and_cost(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "polish-prompt.db"))
    old_db, old_gen_state = _install_test_deps(db)
    original = "叶凡握紧古玉，决定独自进城。他知道这一步会暴露身份，却仍然推开雨幕。城门后有人低声叫出他的名字。"
    _seed_chapter(db, "book", original)
    seen: dict[str, str] = {}

    class FakeGenerator:
        def _call_llm_with_retry(self, messages, **_kwargs):
            seen["system"] = messages[0]["content"]
            seen["user"] = messages[1]["content"]
            return original

    monkeypatch.setattr(revision_service, "_generator_for", lambda *_args: FakeGenerator())
    monkeypatch.setattr(
        revision_service,
        "update_chapter_content",
        lambda db_arg, novel_id, chapter_num, content, **_kwargs:
            chapter_metadata.update_chapter_content(db_arg, novel_id, chapter_num, content),
    )

    try:
        revision_service.run_polish("book")

        assert "不删除主角主动选择、代价、风险或后果" in seen["system"]
        assert "不得删除或淡化主角主动选择" in seen["user"]
        assert "后续麻烦" in seen["user"]
    finally:
        _restore_test_deps(old_db, old_gen_state)
