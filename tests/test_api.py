"""API endpoint tests"""
import os
import tempfile

import pytest
from starlette.testclient import TestClient


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

def test_create_duplicate(client):
    client.post("/api/novels", json={"id": "dup", "title": "重复"})
    assert client.post("/api/novels", json={"id": "dup", "title": "重复2"}).status_code == 409

def test_create_missing_id(client):
    assert client.post("/api/novels", json={"title": "无ID"}).status_code == 400

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
    assert client.put("/api/novels/api-ch/chapters/1", json={"content": "测试"}).status_code == 200

def test_publish_no_chapters(client):
    client.post("/api/novels", json={"id": "api-pub", "title": "发布"})
    assert client.post("/api/novels/api-pub/publish").status_code == 400

def test_generate_endpoint(client):
    client.post("/api/novels", json={"id": "api-gen", "title": "生成"})
    assert client.post("/api/novels/api-gen/generate").status_code == 200

def test_logs(client):
    assert client.get("/api/logs").status_code == 200

# --- Edge case tests ---

def test_create_invalid_id_special_chars(client):
    r = client.post("/api/novels", json={"id": "my novel!", "title": "x"})
    assert r.status_code == 400

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
