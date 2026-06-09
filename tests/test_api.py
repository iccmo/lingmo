"""API endpoint tests"""
import json
import os
import tempfile

import pytest
from starlette.testclient import TestClient


def test_sse_status_key_changes_when_stream_content_updates_at_same_progress():
    from novel_writer.routers.novel.generation import _sse_status_key

    first = {
        "status": "generating",
        "message": "正在生成候选版本",
        "progress": 20,
        "stream_content": "第一段",
        "stream_version": 1,
    }
    second = {
        **first,
        "stream_content": "第一段第二句",
        "stream_version": 2,
    }

    assert _sse_status_key(first) != _sse_status_key(second)


@pytest.mark.asyncio
async def test_generate_stream_sse_emits_same_progress_stream_updates():
    from novel_writer.routers.deps import get_gen_state
    from novel_writer.routers.novel.generation import generate_stream_sse

    novel_id = "api-sse-live"
    state = get_gen_state()
    state.set_status(novel_id, "generating", "正在生成候选版本", 20)
    state.update_stream_content(novel_id, "第一段")

    response = await generate_stream_sse(novel_id)
    events = response.body_iterator
    first = await anext(events)

    state.update_stream_content(novel_id, "第一段第二句")
    second = await anext(events)

    state.set_status(novel_id, "complete", "完成", 100)
    third = await anext(events)
    state.pop_status(novel_id)

    first_status = json.loads(first.removeprefix("data: ").strip())
    second_status = json.loads(second.removeprefix("data: ").strip())
    third_status = json.loads(third.removeprefix("data: ").strip())
    assert first_status["stream_content"] == "第一段"
    assert second_status["stream_content"] == "第一段第二句"
    assert third_status["status"] == "complete"


@pytest.mark.asyncio
async def test_generate_stream_sse_does_not_duplicate_terminal_event():
    from novel_writer.routers.deps import get_gen_state
    from novel_writer.routers.novel.generation import generate_stream_sse

    novel_id = "api-sse-terminal"
    state = get_gen_state()
    state.set_status(novel_id, "complete", "完成", 100, 0.9, extra={"grade": "A"})

    response = await generate_stream_sse(novel_id)
    events = response.body_iterator
    first = await anext(events)
    state.pop_status(novel_id)

    first_status = json.loads(first.removeprefix("data: ").strip())
    assert first_status["status"] == "complete"
    with pytest.raises(StopAsyncIteration):
        await anext(events)


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["done", "failed", "finished"])
async def test_generate_stream_sse_stops_on_terminal_status_aliases(terminal_status):
    from novel_writer.routers.deps import get_gen_state
    from novel_writer.routers.novel.generation import generate_stream_sse

    novel_id = f"api-sse-terminal-{terminal_status}"
    state = get_gen_state()
    state.set_status(novel_id, terminal_status, "终止", 100)

    response = await generate_stream_sse(novel_id)
    events = response.body_iterator
    first = await anext(events)
    state.pop_status(novel_id)

    first_status = json.loads(first.removeprefix("data: ").strip())
    assert first_status["status"] == terminal_status
    with pytest.raises(StopAsyncIteration):
        await anext(events)


@pytest.fixture
def client(monkeypatch):
    """Each test gets its own temp database"""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    # Override the Database path
    from novel_writer.server import app, db
    old_path = db.db_path
    db.db_path = db_path
    db._init()
    tc = TestClient(app)
    yield tc
    db.db_path = old_path
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

def test_list_novels_empty(client):
    assert client.get("/api/novels").status_code == 200

def test_create_novel(client):
    r = client.post("/api/novels", json={"id": "api-create", "title": "API测试"})
    assert r.status_code == 200
    assert r.json()["title"] == "API测试"
    assert r.json()["total_chapters"] == 0
    assert r.json()["latest_chapter"] is None

def test_create_duplicate(client):
    client.post("/api/novels", json={"id": "dup", "title": "重复"})
    assert client.post("/api/novels", json={"id": "dup", "title": "重复2"}).status_code == 409

def test_create_missing_id(client):
    assert client.post("/api/novels", json={"title": "无ID"}).status_code == 400


def test_create_missing_title_defaults_to_id(client):
    response = client.post("/api/novels", json={"id": "missing-title"})

    assert response.status_code == 200
    assert response.json()["title"] == "missing-title"


def test_create_blank_title_is_rejected(client):
    response = client.post("/api/novels", json={"id": "blank-title", "title": "  "})

    assert response.status_code == 400
    assert "title" in response.json()["detail"]


def test_create_rejects_invalid_total_chapters(client):
    response = client.post(
        "/api/novels",
        json={"id": "bad-total", "title": "坏章节数", "total_chapters": "很多"},
    )

    assert response.status_code == 400
    assert "total_chapters" in response.json()["detail"]


def test_create_rejects_total_chapters_above_limit(client):
    response = client.post(
        "/api/novels",
        json={"id": "too-many-chapters", "title": "太多章节", "total_chapters": 2001},
    )

    assert response.status_code == 400
    assert "total_chapters" in response.json()["detail"]


def test_get_novel(client):
    client.post("/api/novels", json={"id": "api-get", "title": "获取"})
    assert client.get("/api/novels/api-get").json()["title"] == "获取"

def test_get_nonexistent(client):
    assert client.get("/api/novels/nope").status_code == 404

def test_delete_novel(client):
    client.post("/api/novels", json={"id": "api-del", "title": "删除"})
    assert client.delete("/api/novels/api-del").status_code == 200
    assert client.get("/api/novels/del-me").status_code == 404

def test_status(client):
    assert "novels_count" in client.get("/api/status").json()

def test_health(client):
    status = client.get("/api/health").json()["status"]
    assert status in ("ok", "healthy", "degraded")

def test_auto_start_stop(client):
    client.post("/api/novels", json={"id": "api-auto", "title": "自动"})
    assert client.post("/api/novels/api-auto/auto/start").status_code == 200
    assert client.post("/api/novels/api-auto/auto/stop").status_code == 200

def test_save_chapter(client):
    client.post("/api/novels", json={"id": "api-ch", "title": "章节"})
    content = "叶凡发现古玉裂开，决定去黑水城寻找母亲留下的线索。"
    assert client.put("/api/novels/api-ch/chapters/1", json={"content": content}).status_code == 200
    chapter = client.get("/api/novels/api-ch/chapters/1").json()
    assert chapter["content"] == content
    assert chapter["word_count"] == len(content)
    assert chapter["summary"] == content
    assert "叶凡发现古玉裂开，决定去黑水城寻找母亲留下的线索" in chapter["narrative_facts"]


def test_reverse_polish_processes_entire_long_chapter(client, monkeypatch):
    from novel_writer.routers.novel import quality

    calls: list[str] = []

    class FakeGenerator:
        def _call_llm_with_retry(self, messages, max_tokens=4096):
            source = messages[0]["content"].split("原文：\n", 1)[1]
            calls.append(source)
            return source.replace("突然", "").replace("说道", "说").strip()

    monkeypatch.setattr(quality, "_generator_for", lambda novel_id, prefer_pro=False: FakeGenerator())
    client.post("/api/novels", json={"id": "api-polish-long", "title": "长章润色"})
    content = "\n\n".join(
        [
            "前段突然他说道。石阶上有旧雨痕。" * 240,
            "尾部标记TAIL突然她说道。灯在门后晃了一下。" * 240,
        ]
    )
    client.put("/api/novels/api-polish-long/chapters/1", json={"content": content})

    response = client.post("/api/novels/api-polish-long/chapters/1/polish-reverse")

    assert response.status_code == 200
    data = response.json()
    assert data["chunks"] > 1
    assert len(calls) == data["chunks"]
    assert "尾部标记TAIL" in data["polished"]
    assert "突然" not in data["polished"]
    assert "说道" not in data["polished"]
    assert data["original_length"] == len(content)


def test_reverse_polish_uses_request_content_before_saved_chapter(client, monkeypatch):
    from novel_writer.routers.novel import quality

    class FakeGenerator:
        def _call_llm_with_retry(self, messages, max_tokens=4096):
            source = messages[0]["content"].split("原文：\n", 1)[1]
            return source.replace("突然", "").replace("说道", "说").strip()

    monkeypatch.setattr(quality, "_generator_for", lambda novel_id, prefer_pro=False: FakeGenerator())
    client.post("/api/novels", json={"id": "api-polish-unsaved", "title": "未保存润色"})
    client.put("/api/novels/api-polish-unsaved/chapters/1", json={"content": "数据库旧正文突然他说道。"})
    current_content = "编辑器未保存TAIL突然她说道。"

    response = client.post(
        "/api/novels/api-polish-unsaved/chapters/1/polish-reverse",
        json={"content": current_content},
    )

    assert response.status_code == 200
    data = response.json()
    assert "编辑器未保存TAIL" in data["polished"]
    assert "数据库旧正文" not in data["polished"]
    assert data["original_length"] == len(current_content)


def test_reverse_polish_prompt_preserves_agency_and_cost():
    from novel_writer.routers.novel.quality import _build_reverse_polish_prompt

    prompt = _build_reverse_polish_prompt("叶凡决定独自进城，因此暴露身份并留下后患。", 1, 1)

    assert "绝对不要删除或淡化主角主动选择" in prompt
    assert "代价" in prompt
    assert "后续麻烦" in prompt


def test_import_chapters_rejects_missing_text_without_server_error(client):
    client.post("/api/novels", json={"id": "api-import-empty", "title": "导入空文本"})

    response = client.post("/api/novels/api-import-empty/import-chapters", json={"text": None})

    assert response.status_code == 400
    assert response.json()["detail"] == "text required"


def test_import_chapters_accepts_numeric_text_without_server_error(client):
    client.post("/api/novels", json={"id": "api-import-numeric", "title": "导入数字"})

    response = client.post("/api/novels/api-import-numeric/import-chapters", json={"text": 0})

    assert response.status_code == 200
    assert response.json()["imported"] == 0


def test_import_chapters_extracts_narrative_facts(client):
    from novel_writer.routers.deps import get_db

    novel_id = "api-import-facts"
    client.post("/api/novels", json={"id": novel_id, "title": "导入事实"})
    text = "第一章\n叶凡得到魂印后决定隐瞒真相，因此受伤流血并暴露身份。\n---\n第二章\n师姐因此误会叶凡，两人的关系出现裂痕。"

    response = client.post(f"/api/novels/{novel_id}/import-chapters", json={"text": text})

    assert response.status_code == 200
    assert response.json()["imported"] == 2
    first = get_db().get_chapter(novel_id, 1)
    facts = json.loads(first["narrative_facts"])
    assert any("受伤" in fact or "暴露身份" in fact for fact in facts)


def test_import_novel_file_extracts_narrative_facts(client):
    from novel_writer.routers.deps import get_db

    text = "第1章\n叶凡得到魂印后决定隐瞒真相，因此受伤流血并暴露身份。"
    response = client.post(
        "/api/novels/import",
        data={"title": "文件导入事实", "genre": "玄幻"},
        files={"file": ("facts.txt", text.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    novel_id = response.json()["novel_id"]
    chapter = get_db().get_chapter(novel_id, 1)
    facts = json.loads(chapter["narrative_facts"])
    assert any("受伤" in fact or "暴露身份" in fact for fact in facts)


def test_search_accepts_non_string_query_without_server_error(client):
    response = client.post("/api/novels/search", json={"q": 123})

    assert response.status_code == 200
    assert "results" in response.json()


def test_story_world_character_accepts_numeric_key_without_server_error(client):
    client.post("/api/novels", json={"id": "api-char-num", "title": "数字角色"})

    response = client.post(
        "/api/novels/api-char-num/characters",
        json={"char_key": 123, "name": "数字人"},
    )

    assert response.status_code == 200


def test_story_world_faction_accepts_numeric_name_without_server_error(client):
    client.post("/api/novels", json={"id": "api-faction-num", "title": "数字势力"})

    response = client.post(
        "/api/novels/api-faction-num/factions",
        json={"name": 123, "description": "数字势力"},
    )

    assert response.status_code == 200


def test_ab_test_accepts_non_string_synopsis_without_server_error(client, monkeypatch):
    from novel_writer.routers.novel import revision

    monkeypatch.setattr(revision, "run_ab_test", lambda *args: None)

    response = client.post("/api/ab-test", json={"synopsis": 123, "voices": ["简洁"]})

    assert response.status_code == 200


def test_revise_accepts_numeric_critique_without_server_error(client, monkeypatch):
    from novel_writer.routers.deps import get_db, get_gen_state
    from novel_writer.routers.novel import revision

    novel_id = "api-revise-numeric"
    client.post("/api/novels", json={"id": novel_id, "title": "数字修订"})
    get_db().add_chapter(novel_id, number=1, title="第一章", content="旧正文", word_count=3)
    monkeypatch.setattr(revision, "run_revise_chapter", lambda *args: None)

    response = client.post(f"/api/novels/{novel_id}/chapters/1/revise", json={"critique": 123})

    assert response.status_code == 200
    status = get_gen_state().get_status(novel_id)
    assert status["status"] == "revising"
    assert "第1章" in status["message"]
    get_gen_state().pop_status(novel_id)


def test_autonomous_novel_accepts_numeric_synopsis_without_server_error(client, monkeypatch):
    from novel_writer.routers.novel import orchestration

    monkeypatch.setattr(orchestration._legacy, "_run_autonomous", lambda *args: None)

    response = client.post(
        "/api/autonomous-novel",
        json={"id": "api-auto-numeric", "synopsis": 123, "chapters": 1},
    )

    assert response.status_code == 200
    assert response.json()["novel_id"] == "api-auto-numeric"


def test_constraint_collapse_accepts_numeric_scene_without_server_error(client):
    client.post("/api/novels", json={"id": "api-constraint-num", "title": "数字约束"})

    response = client.post(
        "/api/novels/api-constraint-num/constraint-collapse",
        json={"scene_description": 123, "choices": ["向前走", "留下"]},
    )

    assert response.status_code == 200


def test_anti_narrative_accepts_numeric_scene_without_server_error(client):
    client.post("/api/novels", json={"id": "api-anti-num", "title": "数字反叙事"})

    response = client.post(
        "/api/novels/api-anti-num/anti-narrative",
        json={"scene_description": 123, "expected_next": ["主角成功"]},
    )

    assert response.status_code == 200
    assert response.json()["scene"] == "123"


def test_anti_narrative_rejects_empty_text_events_without_server_error(client):
    client.post("/api/novels", json={"id": "api-anti-empty-events", "title": "空反叙事"})

    response = client.post(
        "/api/novels/api-anti-empty-events/anti-narrative",
        json={"scene_description": "现场", "expected_next": [None, 123, "  "]},
    )

    assert response.status_code == 400
    assert "expected_next" in response.json()["detail"]


def test_add_foreshadowing_accepts_numeric_description_without_server_error(client):
    client.post("/api/novels", json={"id": "api-fs-num", "title": "数字伏笔"})

    response = client.post(
        "/api/novels/api-fs-num/foreshadowing",
        json={"description": 123, "chapter": 1},
    )

    assert response.status_code == 200


def test_add_foreshadowing_rejects_invalid_chapter_without_server_error(client):
    client.post("/api/novels", json={"id": "api-fs-bad-ch", "title": "坏伏笔章节"})

    response = client.post(
        "/api/novels/api-fs-bad-ch/foreshadowing",
        json={"description": "玉佩裂开", "chapter": "第一章"},
    )

    assert response.status_code == 400
    assert "chapter" in response.json()["detail"]


def test_add_foreshadowing_rejects_invalid_due_by_without_server_error(client):
    client.post("/api/novels", json={"id": "api-fs-bad-due", "title": "坏伏笔期限"})

    response = client.post(
        "/api/novels/api-fs-bad-due/foreshadowing",
        json={"description": "玉佩裂开", "chapter": 1, "due_by": "三"},
    )

    assert response.status_code == 400
    assert "due_by" in response.json()["detail"]


def test_resolve_foreshadowing_rejects_invalid_chapter_without_server_error(client):
    from novel_writer.routers.deps import get_db

    novel_id = "api-fs-resolve-bad"
    client.post("/api/novels", json={"id": novel_id, "title": "坏伏笔回收"})
    get_db().save_foreshadowing(novel_id, 1, "玉佩裂开", due_by=3)
    fs_id = get_db().get_active_foreshadowing(novel_id)[0]["id"]

    response = client.post(
        f"/api/novels/{novel_id}/foreshadowing/{fs_id}/resolve",
        json={"chapter_num": "第三章", "text": "已回收"},
    )

    assert response.status_code == 400
    assert "chapter_num" in response.json()["detail"]


def test_v2_soul_fingerprint_rejects_invalid_position_without_server_error(client):
    client.post("/api/novels", json={"id": "api-soul-bad-position", "title": "坏灵魂位置"})

    response = client.post(
        "/api/v2/novels/api-soul-bad-position/soul-fingerprint",
        json={"polarity": "自由", "position": "中间", "answer": "不被命运驯服"},
    )

    assert response.status_code == 400
    assert "position" in response.json()["detail"]


def test_v2_soul_fingerprint_rejects_out_of_range_position(client):
    client.post("/api/novels", json={"id": "api-soul-range", "title": "灵魂范围"})

    response = client.post(
        "/api/v2/novels/api-soul-range/soul-fingerprint",
        json={"polarity": "自由", "position": 11, "answer": "不被命运驯服"},
    )

    assert response.status_code == 400
    assert "position" in response.json()["detail"]


def test_v2_soul_fingerprint_rejects_blank_answer(client):
    client.post("/api/novels", json={"id": "api-soul-blank-answer", "title": "空灵魂回答"})

    response = client.post(
        "/api/v2/novels/api-soul-blank-answer/soul-fingerprint",
        json={"polarity": "自由", "position": 5, "answer": "  "},
    )

    assert response.status_code == 400
    assert "answer" in response.json()["detail"]


def test_v2_character_blueprints_normalizes_and_persists_valid_items(client):
    client.post("/api/novels", json={"id": "api-char-blueprint-ok", "title": "角色蓝图"})

    response = client.post(
        "/api/v2/novels/api-char-blueprint-ok/character-blueprints",
        json={
            "characters": [
                {
                    "id": " hero ",
                    "name": " 叶凡 ",
                    "role": "主角",
                    "entrance": 123,
                    "unknown": "ignored",
                }
            ]
        },
    )

    assert response.status_code == 200
    characters = response.json()["characters"]
    assert characters[0]["id"] == "hero"
    assert characters[0]["name"] == "叶凡"
    assert characters[0]["entrance"] == "123"
    assert "unknown" not in characters[0]
    stored = client.get("/api/v2/novels/api-char-blueprint-ok/character-blueprints").json()["characters"]
    assert stored == characters


def test_v2_character_blueprints_rejects_non_list_payload(client):
    client.post("/api/novels", json={"id": "api-char-blueprint-bad-list", "title": "坏蓝图列表"})

    response = client.post(
        "/api/v2/novels/api-char-blueprint-bad-list/character-blueprints",
        json={"characters": {"id": "hero", "name": "叶凡"}},
    )

    assert response.status_code == 400
    assert "characters" in response.json()["detail"]


def test_v2_character_blueprints_rejects_missing_required_fields(client):
    client.post("/api/novels", json={"id": "api-char-blueprint-missing", "title": "缺蓝图字段"})

    response = client.post(
        "/api/v2/novels/api-char-blueprint-missing/character-blueprints",
        json={"characters": [{"id": "hero", "name": " "}]},
    )

    assert response.status_code == 400
    assert "name" in response.json()["detail"]


def test_v2_character_blueprints_rejects_duplicate_ids(client):
    client.post("/api/novels", json={"id": "api-char-blueprint-dupe", "title": "重复蓝图"})

    response = client.post(
        "/api/v2/novels/api-char-blueprint-dupe/character-blueprints",
        json={"characters": [{"id": "hero", "name": "甲"}, {"id": " hero ", "name": "乙"}]},
    )

    assert response.status_code == 400
    assert "duplicate" in response.json()["detail"]


def test_v2_delete_character_blueprint_returns_404_for_missing_item(client):
    client.post("/api/novels", json={"id": "api-char-blueprint-delete-missing", "title": "删缺蓝图"})
    client.post(
        "/api/v2/novels/api-char-blueprint-delete-missing/character-blueprints",
        json={"characters": [{"id": "hero", "name": "叶凡"}]},
    )

    response = client.delete(
        "/api/v2/novels/api-char-blueprint-delete-missing/character-blueprints/missing"
    )

    assert response.status_code == 404
    assert "Character blueprint" in response.json()["detail"]


def test_save_chapter_creates_missing_chapter_for_existing_novel(client):
    novel_id = "api-ch-create-missing"
    content = "第一章从零开始。"
    client.post("/api/novels", json={"id": novel_id, "title": "缺章保存", "total_chapters": 0})

    response = client.put(f"/api/novels/{novel_id}/chapters/1", json={"content": content})

    assert response.status_code == 200
    chapter = client.get(f"/api/novels/{novel_id}/chapters/1").json()
    assert chapter["number"] == 1
    assert chapter["title"] == "第1章"
    assert chapter["content"] == content
    assert chapter["word_count"] == len(content)


def test_save_chapter_resets_stale_quality_when_content_changes(client):
    from novel_writer.routers.deps import get_db

    novel_id = "api-ch-quality-reset"
    client.post("/api/novels", json={"id": novel_id, "title": "质量重置"})
    db = get_db()
    db.add_chapter(
        novel_id,
        number=1,
        title="第一章",
        content="旧正文",
        word_count=3,
        quality_score=0.91,
    )

    response = client.put(f"/api/novels/{novel_id}/chapters/1", json={"content": "新正文"})

    assert response.status_code == 200
    chapter = client.get(f"/api/novels/{novel_id}/chapters/1").json()
    assert chapter["content"] == "新正文"
    assert chapter["quality_score"] == 0


def test_save_chapter_preserves_quality_when_content_is_unchanged(client):
    from novel_writer.routers.deps import get_db

    novel_id = "api-ch-quality-preserve"
    content = "正文未变"
    client.post("/api/novels", json={"id": novel_id, "title": "质量保留"})
    db = get_db()
    db.add_chapter(
        novel_id,
        number=1,
        title="第一章",
        content=content,
        word_count=len(content),
        quality_score=0.88,
    )

    response = client.put(f"/api/novels/{novel_id}/chapters/1", json={"content": content})

    assert response.status_code == 200
    chapter = client.get(f"/api/novels/{novel_id}/chapters/1").json()
    assert chapter["quality_score"] == 0.88


def test_save_chapter_rejects_empty_content(client):
    client.post("/api/novels", json={"id": "api-ch-empty-reject", "title": "空正文拒绝"})

    response = client.put("/api/novels/api-ch-empty-reject/chapters/1", json={"content": "   "})

    assert response.status_code == 400
    assert "content" in response.json()["detail"]
    chapter = client.get("/api/novels/api-ch-empty-reject/chapters/1").json()
    assert chapter["content"] == ""
    assert chapter["word_count"] == 0


def test_save_chapter_rejects_explanation_overwrite(client):
    from novel_writer.routers.deps import get_db

    novel_id = "api-ch-explain-reject"
    original = "叶凡握紧古玉，决定独自进城。他知道这一步会暴露身份，却仍然推开雨幕。城门后有人低声叫出他的名字。"
    client.post("/api/novels", json={"id": novel_id, "title": "说明覆盖拒绝"})
    get_db().add_chapter(
        novel_id,
        number=1,
        title="第一章",
        content=original,
        word_count=len(original),
    )

    response = client.put(
        f"/api/novels/{novel_id}/chapters/1",
        json={"content": "以下是修改后的章节：\n\n我增强了节奏，并加入更多细节。"},
    )

    assert response.status_code == 400
    chapter = client.get(f"/api/novels/{novel_id}/chapters/1").json()
    assert chapter["content"] == original


def test_save_chapter_rejects_report_or_outline_overwrite(client):
    from novel_writer.routers.deps import get_db

    novel_id = "api-ch-report-reject"
    original = "叶凡握紧古玉，决定独自进城。他知道这一步会暴露身份，却仍然推开雨幕。城门后有人低声叫出他的名字。"
    client.post("/api/novels", json={"id": novel_id, "title": "报告覆盖拒绝"})
    get_db().add_chapter(
        novel_id,
        number=1,
        title="第一章",
        content=original,
        word_count=len(original),
    )
    report = """分析报告：
1. 问题：主角主动性不足
2. 建议：增加代价
3. 计划：重写开头冲突"""

    response = client.put(f"/api/novels/{novel_id}/chapters/1", json={"content": report})

    assert response.status_code == 400
    chapter = client.get(f"/api/novels/{novel_id}/chapters/1").json()
    assert chapter["content"] == original


def test_fix_formatting_rejects_bad_output_without_overwriting(client, monkeypatch):
    from novel_writer.generator import Generator
    from novel_writer.routers.deps import get_db

    novel_id = "api-formatting-bad-output"
    original = "叶凡握紧古玉，决定独自进城。他知道这一步会暴露身份，却仍然推开雨幕。城门后有人低声叫出他的名字。"
    client.post("/api/novels", json={"id": novel_id, "title": "格式坏输出拒绝"})
    get_db().add_chapter(
        novel_id,
        number=1,
        title="第一章",
        content=original,
        word_count=len(original),
    )
    monkeypatch.setattr(Generator, "fix_formatting", lambda self, body: ("", 1))

    response = client.post(f"/api/novels/{novel_id}/chapters/1/fix-formatting")

    assert response.status_code == 400
    assert "formatting result rejected" in response.json()["detail"]
    chapter = client.get(f"/api/novels/{novel_id}/chapters/1").json()
    assert chapter["content"] == original


def test_quality_report_includes_agency_and_cost_diagnostics(client, monkeypatch):
    from novel_writer.routers.deps import get_db
    from novel_writer.routers.novel import quality as quality_router

    novel_id = "api-quality-dimensions"
    client.post("/api/novels", json={"id": novel_id, "title": "质量维度报告"})
    db = get_db()
    db.add_chapter(
        novel_id,
        number=1,
        title="被推着走",
        content="叶凡只能接受安排。他只好获得神丹，突破成功，赢下胜利。",
        word_count=30,
        quality_score=0.82,
    )
    db.add_chapter(
        novel_id,
        number=2,
        title="有选择",
        content="叶凡决定主动拒绝退让，亲自站出来反击。他获得线索，却受伤流血，欠下债务。",
        word_count=35,
        quality_score=0.9,
    )
    db.add_chapter(
        novel_id,
        number=3,
        title="无代价收益",
        content="叶凡得到法宝，成功救下同伴，夺回玉佩，众人欢呼。",
        word_count=25,
        quality_score=0.78,
    )
    db.save_cost_entry(novel_id, 3, "叶凡", gain="法宝", loss="")

    class NoopGenerator:
        def _call_llm_with_retry(self, *_args, **_kwargs):
            return ""

    monkeypatch.setattr(quality_router, "_generator_for", lambda *_args, **_kwargs: NoopGenerator())

    response = client.get(f"/api/novels/{novel_id}/report")

    assert response.status_code == 200
    diagnostics = response.json()["dimension_diagnostics"]
    weak = diagnostics["weak_dimensions"]
    assert any(item["number"] == 1 and "主角主动性不足" in item["issues"] for item in weak)
    assert any(item["number"] == 3 and "胜利缺少代价" in item["issues"] for item in weak)
    assert "补主角主动选择：每章至少一个拒绝、押注、反击或承担后果的决定" in response.json()["revision_focus"]
    assert "补胜利代价：获得线索/突破/救人后必须留下伤口、债务、暴露风险或关系裂痕" in response.json()["revision_focus"]


def test_save_chapter_refreshes_story_bible(client, monkeypatch):
    from novel_writer.routers.novel import chapter_metadata

    client.post("/api/novels", json={"id": "api-ch-bible", "title": "章节"})
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
    assert client.put("/api/novels/api-ch-bible/chapters/1", json={"content": content}).status_code == 200

    assert ("extract", "api-ch-bible", 1, content, "第1章") in calls
    assert ("check", "api-ch-bible", 1) in calls

def test_publish_no_chapters(client):
    client.post("/api/novels", json={"id": "api-pub", "title": "发布", "total_chapters": 0})
    assert client.post("/api/novels/api-pub/publish").status_code == 400

def test_generate_endpoint(client):
    client.post("/api/novels", json={"id": "api-gen", "title": "生成"})
    assert client.post("/api/novels/api-gen/generate").status_code == 200


def test_generate_accepts_non_string_direction_without_server_error(client, monkeypatch):
    from novel_writer.routers.novel import generation

    captured = []
    monkeypatch.setattr(
        generation._legacy,
        "_run_generation",
        lambda novel_id: captured.append(novel_id),
    )
    client.post("/api/novels", json={"id": "api-gen-num-dir", "title": "数字方向"})

    response = client.post("/api/novels/api-gen-num-dir/generate", json={"direction": 123})

    assert response.status_code == 200
    assert generation._legacy._gen_directions["api-gen-num-dir"] == "123"


def test_generate_rejects_quality_threshold_below_floor(client):
    client.post("/api/novels", json={"id": "api-gen-low-q", "title": "低门槛"})

    response = client.post("/api/novels/api-gen-low-q/generate", json={"quality_threshold": 0.1})

    assert response.status_code == 422
    assert "quality_threshold" in response.json()["detail"]


def test_generate_rejects_non_finite_quality_threshold(client):
    client.post("/api/novels", json={"id": "api-gen-nan-q", "title": "非数门槛"})

    response = client.post("/api/novels/api-gen-nan-q/generate", json={"quality_threshold": "nan"})

    assert response.status_code == 422
    assert "quality_threshold" in response.json()["detail"]


def test_generate_batch_rejects_invalid_count(client):
    client.post("/api/novels", json={"id": "api-gen-bad-count", "title": "坏章数"})

    response = client.post("/api/novels/api-gen-bad-count/generate-batch", json={"count": "很多"})

    assert response.status_code == 422
    assert "count" in response.json()["detail"]


def test_generate_batch_rejects_out_of_range_quality_threshold(client):
    client.post("/api/novels", json={"id": "api-gen-bad-q", "title": "坏门槛"})

    response = client.post(
        "/api/novels/api-gen-bad-q/generate-batch",
        json={"count": 2, "quality_threshold": 1.5},
    )

    assert response.status_code == 422
    assert "quality_threshold" in response.json()["detail"]


def test_generate_batch_rejects_non_finite_quality_threshold(client):
    client.post("/api/novels", json={"id": "api-gen-inf-q", "title": "无限门槛"})

    response = client.post(
        "/api/novels/api-gen-inf-q/generate-batch",
        json={"count": 2, "quality_threshold": "inf"},
    )

    assert response.status_code == 422
    assert "quality_threshold" in response.json()["detail"]


def test_longrun_batch_generate_rejects_invalid_chapters(client):
    client.post("/api/novels", json={"id": "api-longrun-bad-chapters", "title": "长跑坏章数"})

    response = client.post(
        "/api/novels/api-longrun-bad-chapters/batch-generate",
        json={"chapters": "很多"},
    )

    assert response.status_code == 400
    assert "chapters" in response.json()["detail"]


def test_longrun_batch_generate_rejects_chapters_above_limit(client):
    client.post("/api/novels", json={"id": "api-longrun-too-many", "title": "长跑太多"})

    response = client.post(
        "/api/novels/api-longrun-too-many/batch-generate",
        json={"chapters": 21},
    )

    assert response.status_code == 400
    assert "chapters" in response.json()["detail"]


def test_longrun_batch_generate_rejects_non_finite_quality_threshold(client):
    client.post("/api/novels", json={"id": "api-longrun-nan", "title": "长跑非数"})

    response = client.post(
        "/api/novels/api-longrun-nan/batch-generate",
        json={"chapters": 2, "quality_threshold": "nan"},
    )

    assert response.status_code == 400
    assert "quality_threshold" in response.json()["detail"]


def test_generate_rejects_active_batch_job(client):
    from novel_writer.routers.deps import get_gen_state

    novel_id = "api-gen-batch-active"
    client.post("/api/novels", json={"id": novel_id, "title": "批量占用"})
    state = get_gen_state()
    state._job_queue["active-batch"] = {
        "job_id": "active-batch",
        "novel_id": novel_id,
        "status": "queued",
        "progress": {"current": 0, "total": 2},
        "last_error": None,
    }
    try:
        resp = client.post(f"/api/novels/{novel_id}/generate")

        assert resp.status_code == 409
        assert "已有任务进行中" in resp.json()["detail"]
    finally:
        state._job_queue.pop("active-batch", None)


def test_generate_batch_rejects_active_single_generation(client):
    from novel_writer.routers.deps import get_gen_state

    novel_id = "api-gen-single-active"
    client.post("/api/novels", json={"id": novel_id, "title": "单章占用"})
    state = get_gen_state()
    state.set_status(novel_id, "generating", "正在生成", 20)
    try:
        resp = client.post(f"/api/novels/{novel_id}/generate-batch", json={"count": 2})

        assert resp.status_code == 409
        assert "已有生成任务进行中" in resp.json()["detail"]
    finally:
        state.pop_status(novel_id)


def test_generate_rejects_active_revision_status(client):
    from novel_writer.routers.deps import get_gen_state

    novel_id = "api-gen-polishing-active"
    client.post("/api/novels", json={"id": novel_id, "title": "打磨占用"})
    state = get_gen_state()
    state.set_status(novel_id, "polishing", "终极打磨中", 70)
    try:
        resp = client.post(f"/api/novels/{novel_id}/generate")

        assert resp.status_code == 409
        assert "已有生成任务进行中" in resp.json()["detail"]
    finally:
        state.pop_status(novel_id)


def test_auto_once_rejects_active_single_generation(client):
    from novel_writer.routers.deps import get_gen_state

    novel_id = "api-auto-once-active"
    client.post("/api/novels", json={"id": novel_id, "title": "自动单次占用"})
    state = get_gen_state()
    state.set_status(novel_id, "generating", "正在生成", 20)
    try:
        resp = client.post(f"/api/novels/{novel_id}/auto/once")

        assert resp.status_code == 409
        assert "已有生成任务进行中" in resp.json()["detail"]
    finally:
        state.pop_status(novel_id)


def test_auto_once_rejects_active_batch_job(client):
    from novel_writer.routers.deps import get_gen_state

    novel_id = "api-auto-once-batch-active"
    client.post("/api/novels", json={"id": novel_id, "title": "自动批量占用"})
    state = get_gen_state()
    state._job_queue["auto-once-active-batch"] = {
        "job_id": "auto-once-active-batch",
        "novel_id": novel_id,
        "status": "running",
        "progress": {"current": 1, "total": 3},
        "last_error": None,
    }
    try:
        resp = client.post(f"/api/novels/{novel_id}/auto/once")

        assert resp.status_code == 409
        assert "已有任务进行中" in resp.json()["detail"]
    finally:
        state._job_queue.pop("auto-once-active-batch", None)


def test_generate_classic_rejects_active_generation(client):
    from novel_writer.routers.deps import get_gen_state

    novel_id = "api-classic-active"
    client.post("/api/novels", json={"id": novel_id, "title": "经典占用"})
    state = get_gen_state()
    state.set_status(novel_id, "generating", "正在生成", 20)
    try:
        resp = client.post(f"/api/novels/{novel_id}/generate-classic")

        assert resp.status_code == 409
        assert "已有生成任务进行中" in resp.json()["detail"]
    finally:
        state.pop_status(novel_id)


def test_revise_chapter_rejects_active_generation(client):
    from novel_writer.routers.deps import get_db, get_gen_state

    novel_id = "api-revise-active"
    client.post("/api/novels", json={"id": novel_id, "title": "修订占用"})
    get_db().add_chapter(novel_id, number=1, title="第一章", content="旧正文", word_count=3)
    state = get_gen_state()
    state.set_status(novel_id, "generating", "正在生成", 20)
    try:
        resp = client.post(f"/api/novels/{novel_id}/chapters/1/revise", json={"critique": "加强冲突"})

        assert resp.status_code == 409
        assert "已有生成任务进行中" in resp.json()["detail"]
    finally:
        state.pop_status(novel_id)


def test_pipeline_rejects_active_generation(client):
    from novel_writer.routers.deps import get_gen_state

    novel_id = "api-pipeline-active"
    client.post("/api/novels", json={"id": novel_id, "title": "管线占用"})
    state = get_gen_state()
    state.set_status(novel_id, "generating", "正在生成", 20)
    try:
        resp = client.post(f"/api/novels/{novel_id}/pipeline")

        assert resp.status_code == 409
        assert "已有生成任务进行中" in resp.json()["detail"]
    finally:
        state.pop_status(novel_id)


def test_world_bible_rejects_active_batch_job(client):
    from novel_writer.routers.deps import get_gen_state

    novel_id = "api-world-bible-batch-active"
    client.post("/api/novels", json={"id": novel_id, "title": "世界观批量占用"})
    state = get_gen_state()
    state._job_queue["world-bible-active-batch"] = {
        "job_id": "world-bible-active-batch",
        "novel_id": novel_id,
        "status": "running",
        "progress": {"current": 1, "total": 3},
        "last_error": None,
    }
    try:
        resp = client.post(f"/api/novels/{novel_id}/world-bible")

        assert resp.status_code == 409
        assert "已有任务进行中" in resp.json()["detail"]
    finally:
        state._job_queue.pop("world-bible-active-batch", None)


def test_autonomous_novel_rejects_active_existing_novel(client):
    from novel_writer.routers.deps import get_gen_state

    novel_id = "api-autonomous-active"
    client.post("/api/novels", json={"id": novel_id, "title": "全自动占用"})
    state = get_gen_state()
    state.set_status(novel_id, "generating", "正在生成", 20)
    try:
        resp = client.post(
            "/api/autonomous-novel",
            json={"id": novel_id, "synopsis": "已有书继续生成", "chapters": 3},
        )

        assert resp.status_code == 409
        assert "已有生成任务进行中" in resp.json()["detail"]
    finally:
        state.pop_status(novel_id)


def test_agent_pipeline_rejects_active_generation_before_planning(client, monkeypatch):
    from novel_writer.routers.deps import get_gen_state
    from novel_writer.routers.novel import agent_pipeline

    novel_id = "api-agent-pipeline-active"
    client.post("/api/novels", json={"id": novel_id, "title": "Agent占用"})
    state = get_gen_state()
    state.set_status(novel_id, "generating", "正在生成", 20)
    called = {"brief": False}

    def fake_brief(*args):
        called["brief"] = True
        return "不应执行"

    monkeypatch.setattr(agent_pipeline, "editor_in_chief_brief", fake_brief)
    try:
        resp = client.post(f"/api/novels/{novel_id}/agent-pipeline")

        assert resp.status_code == 409
        assert "已有生成任务进行中" in resp.json()["detail"]
        assert called["brief"] is False
    finally:
        state.pop_status(novel_id)


def test_logs(client):
    assert client.get("/api/logs").status_code == 200

# --- Edge case tests ---

def test_create_invalid_id_special_chars(client):
    r = client.post("/api/novels", json={"id": "my novel!", "title": "x"})
    assert r.status_code == 400


def test_create_non_string_id_is_coerced_to_string(client):
    response = client.post("/api/novels", json={"id": 123, "title": "数字ID"})

    assert response.status_code == 200
    assert response.json()["id"] == "123"


def test_create_invalid_id_too_long(client):
    r = client.post("/api/novels", json={"id": "a" * 51, "title": "x"})
    assert r.status_code == 400

def test_create_novel_minimal(client):
    r = client.post("/api/novels", json={"id": "api-min", "title": "最小"})
    assert r.status_code == 200

def test_save_chapter_nonexistent_novel(client):
    r = client.put("/api/novels/fake-novel/chapters/1", json={"content": "x"})
    assert r.status_code == 404

def test_publish_nonexistent_novel(client):
    r = client.post("/api/novels/fake-novel/publish")
    assert r.status_code == 404

def test_auto_on_nonexistent(client):
    r = client.post("/api/novels/fake-novel/auto/start")
    assert r.status_code == 404

def test_get_chapter_nonexistent(client):
    r = client.get("/api/novels/fake-novel/chapters/999")
    assert r.status_code == 404

def test_delete_chapter_clears_story_bible_rows(client):
    from novel_writer.server import db

    client.post("/api/novels", json={"id": "api-del-ch", "title": "删章"})
    db.add_chapter("api-del-ch", number=1, title="第一章", word_count=10, content="正文")
    db.save_character_state("api-del-ch", 1, "叶凡", emotion="震惊")
    db.save_foreshadowing("api-del-ch", 1, "古玉裂纹", due_by=3)
    db.save_foreshadowing("api-del-ch", 0, "前文伏笔", due_by=2)
    prior_thread = db.get_active_foreshadowing("api-del-ch")[0]
    db.resolve_foreshadowing(prior_thread["id"], 1, "本章回收")
    db.save_location_history("api-del-ch", 1, "黑水城")
    db.save_timeline_event("api-del-ch", 1, event_summary="抵达黑水城")
    db.save_world_state("api-del-ch", 1, "古玉可传讯")
    db.save_cost_entry("api-del-ch", 1, "叶凡", gain="线索", loss="")
    db.log_consistency_issue("api-del-ch", 1, "character", "warning", "旧问题")
    db.save_chapter_summary("api-del-ch", 1, "第一章摘要")
    db.save_chapter_trace({
        "novel_id": "api-del-ch",
        "chapter_num": 1,
        "steps": [{"name": "draft"}],
        "final_quality": 0.8,
        "total_duration_ms": 10,
        "total_cost": 0.01,
    })
    db.log_cost("api-del-ch", 1, "deepseek-test", 10, 20, 30, 0.01)

    assert client.delete("/api/novels/api-del-ch/chapters/1").status_code == 200

    assert db.get_chapter("api-del-ch", 1) is None
    assert db.get_character_state("api-del-ch", 1) == []
    foreshadowing = db.get_active_foreshadowing("api-del-ch")
    assert len(foreshadowing) == 1
    assert foreshadowing[0]["description"] == "前文伏笔"
    assert foreshadowing[0]["resolved_chapter"] is None
    assert db.get_location_history("api-del-ch") == []
    assert db.get_timeline("api-del-ch") == []
    assert db.get_world_state("api-del-ch") == []
    assert db.get_cost_ledger("api-del-ch") == []
    assert db.get_consistency_log("api-del-ch") == []
    assert db.get_chapter_summaries("api-del-ch") == []
    assert db.get_chapter_traces("api-del-ch") == []
    assert db.get_cost_summary("api-del-ch")["total_calls"] == 0


def test_reorder_chapters_moves_chapter_scoped_artifacts(client):
    from novel_writer.server import db

    client.post("/api/novels", json={"id": "api-reorder-artifacts", "title": "重排账本"})
    db.add_chapter("api-reorder-artifacts", number=1, title="第一章", word_count=10, content="正文一")
    db.add_chapter("api-reorder-artifacts", number=2, title="第二章", word_count=10, content="正文二")
    db.save_chapter_summary("api-reorder-artifacts", 1, "第一章摘要")
    db.save_chapter_trace({
        "novel_id": "api-reorder-artifacts",
        "chapter_num": 1,
        "steps": [{"name": "draft"}],
        "final_quality": 0.8,
        "total_duration_ms": 10,
        "total_cost": 0.01,
    })
    db.log_cost("api-reorder-artifacts", 1, "deepseek-test", 10, 20, 30, 0.01)
    db.save_character_state("api-reorder-artifacts", 1, "叶凡", emotion="震惊")
    db.save_foreshadowing("api-reorder-artifacts", 1, "古玉裂纹", due_by=2)
    thread = db.get_active_foreshadowing("api-reorder-artifacts")[0]
    db.resolve_foreshadowing(thread["id"], 2, "古玉裂纹回收")

    response = client.post(
        "/api/novels/api-reorder-artifacts/chapters/reorder",
        json={"order": {"1": 2, "2": 1}},
    )

    assert response.status_code == 200
    assert db.get_chapter("api-reorder-artifacts", 2)["title"] == "第一章"
    assert db.get_chapter_summaries("api-reorder-artifacts", [2])[0]["summary_text"] == "第一章摘要"
    assert db.get_chapter_traces("api-reorder-artifacts")[0]["chapter_num"] == 2
    assert db.get_cost_summary("api-reorder-artifacts")["by_model"][0]["calls"] == 1
    assert db.get_character_state("api-reorder-artifacts", 2)[0]["char_name"] == "叶凡"
    foreshadowing = db.get_all_foreshadowing("api-reorder-artifacts")[0]
    assert foreshadowing["created_chapter"] == 2
    assert foreshadowing["due_by_chapter"] == 1
    assert foreshadowing["resolved_chapter"] == 1


def test_reorder_chapters_rejects_invalid_mapping_without_server_error(client):
    from novel_writer.server import db

    client.post("/api/novels", json={"id": "api-reorder-invalid", "title": "坏重排"})
    db.add_chapter("api-reorder-invalid", number=1, title="第一章", word_count=10, content="正文一")
    db.add_chapter("api-reorder-invalid", number=2, title="第二章", word_count=10, content="正文二")
    db.add_chapter("api-reorder-invalid", number=3, title="第三章", word_count=10, content="正文三")

    not_object = client.post(
        "/api/novels/api-reorder-invalid/chapters/reorder",
        json={"order": ["bad"]},
    )
    bad_number = client.post(
        "/api/novels/api-reorder-invalid/chapters/reorder",
        json={"order": {"one": 2}},
    )
    duplicate_target = client.post(
        "/api/novels/api-reorder-invalid/chapters/reorder",
        json={"order": {"1": 2, "3": 2}},
    )
    occupied_target = client.post(
        "/api/novels/api-reorder-invalid/chapters/reorder",
        json={"order": {"1": 2}},
    )

    assert not_object.status_code == 400
    assert bad_number.status_code == 400
    assert duplicate_target.status_code == 400
    assert occupied_target.status_code == 400
    assert db.get_chapter("api-reorder-invalid", 1)["title"] == "第一章"
    assert db.get_chapter("api-reorder-invalid", 2)["title"] == "第二章"
    assert db.get_chapter("api-reorder-invalid", 3)["title"] == "第三章"


def test_outline_next_number_uses_next_generated_chapter_not_far_future_outline(client):
    from novel_writer.server import db

    client.post("/api/novels", json={"id": "api-outline-next", "title": "大纲续写"})
    db.add_chapter("api-outline-next", number=1, title="第一章", word_count=1000, content="正文")
    db.add_chapter("api-outline-next", number=10, title="第十章大纲", word_count=0, summary="远期计划")

    response = client.get("/api/novels/api-outline-next/outline")

    assert response.status_code == 200
    payload = response.json()
    assert payload["next_number"] == 2
    assert 10 in {item["number"] for item in payload["outline"]}


def test_expectation_check_uses_first_generated_chapters_not_outline_placeholders(client):
    from novel_writer.server import db

    novel_id = "api-diagnostic-outline-contract"
    client.post("/api/novels", json={"id": novel_id, "title": "诊断大纲", "genre": "玄幻"})
    db.add_chapter(
        novel_id,
        number=1,
        title="第一章",
        word_count=20,
        content="主角开始修炼，获得功法。",
    )
    db.add_chapter(novel_id, number=2, title="第二章大纲", word_count=0, summary="占位：丹药、法宝")
    db.add_chapter(novel_id, number=3, title="第三章大纲", word_count=0, summary="占位：战斗、突破")
    db.add_chapter(
        novel_id,
        number=4,
        title="第四章",
        word_count=20,
        content="他吞下丹药，借法宝突破，在战斗里觉醒金手指。",
    )

    response = client.get(f"/api/novels/{novel_id}/expectation-check")

    assert response.status_code == 200
    data = response.json()
    assert data["fulfillment_pct"] == 100
    assert data["missing_elements"] == []


def test_negative_space_health_counts_generated_chapters_not_outline_placeholders(client):
    from novel_writer.server import db

    novel_id = "api-diagnostic-outline-negative-space"
    client.post("/api/novels", json={"id": novel_id, "title": "负空间大纲"})
    db.add_chapter(novel_id, number=1, title="第一章", word_count=20, content="古盒里有一个谜。")
    db.add_chapter(novel_id, number=2, title="第二章大纲", word_count=0, summary="占位")
    db.add_chapter(novel_id, number=3, title="第三章", word_count=20, content="众人继续寻找线索。")
    db.add_chapter(novel_id, number=4, title="第四章大纲", word_count=0, summary="占位")
    db.add_chapter(novel_id, number=5, title="第五章", word_count=20, content="主角仍不知道答案，只能继续追查。")
    db.add_chapter(novel_id, number=6, title="第六章", word_count=20, content="答案就在师父手里。")

    response = client.get(f"/api/novels/{novel_id}/neg-space-health")

    assert response.status_code == 200
    data = response.json()
    assert data["total_chapters"] == 4
    assert data["consumed_spaces"] == 1


def test_create_with_unicode_title(client):
    r = client.post("/api/novels", json={"id": "api-uni", "title": "修仙从炼丹开始✨"})
    assert r.status_code == 200
    assert "炼丹" in r.json()["title"]

def test_draft_endpoint(client):
    client.post("/api/novels", json={"id": "api-draft", "title": "草稿"})
    r = client.post("/api/novels/api-draft/draft", json={"input": "主角突破"})
    assert r.status_code == 200
    assert r.json().get("status") == "drafting"

def test_auto_once(client):
    client.post("/api/novels", json={"id": "api-once", "title": "手动触发"})
    r = client.post("/api/novels/api-once/auto/once")
    assert r.status_code == 200
