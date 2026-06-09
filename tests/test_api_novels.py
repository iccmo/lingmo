"""小说 CRUD API 集成测试。
注：需单独运行（pytest tests/test_api_novels.py），与其他测试文件共用生产 DB 时可能冲突。
"""
import uuid
import pytest
from fastapi.testclient import TestClient


def _uid(suffix: str = "") -> str:
    """Generate a unique test novel ID to avoid DB conflicts across runs."""
    return f"test-{suffix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def client():
    """TestClient — 使用 conftest.py 的全局 OpenAI mock。"""
    from novel_writer.server import app
    with TestClient(app) as c:
        yield c


class TestNovelCRUD:

    def test_create_novel(self, client):
        resp = client.post("/api/novels", json={
            "id": _uid("crud1"), "title": "测试小说", "genre": "玄幻",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "测试小说"
        assert data["genre"] == "玄幻"

    def test_create_novel_minimal(self, client):
        resp = client.post("/api/novels", json={"id": _uid("minimal"), "title": "最小"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "最小"

    def test_create_duplicate_id_rejected(self, client):
        dup_id = _uid("dup")
        client.post("/api/novels", json={"id": dup_id, "title": "重复"})
        resp = client.post("/api/novels", json={"id": dup_id, "title": "重复2"})
        assert resp.status_code == 409

    def test_list_novels(self, client):
        resp = client.get("/api/novels")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_novels_has_data(self, client):
        resp = client.get("/api/novels")
        assert len(resp.json()) > 0

    def test_get_novel(self, client):
        novel = client.post("/api/novels", json={"id": _uid("getme"), "title": "获取测试"}).json()
        resp = client.get(f"/api/novels/{novel['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "获取测试"

    def test_get_novel_404(self, client):
        resp = client.get("/api/novels/nonexistent-xyz")
        assert resp.status_code == 404

    def test_delete_novel(self, client):
        novel = client.post("/api/novels", json={"id": _uid("del"), "title": "待删除"}).json()
        resp = client.delete(f"/api/novels/{novel['id']}")
        assert resp.status_code == 200
        novels = client.get("/api/novels").json()
        ids = [n["id"] for n in novels]
        assert novel["id"] not in ids

    def test_status_endpoint(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "novels_count" in data

    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200


class TestGenerationStatus:

    def test_queue_status_idle(self, client):
        resp = client.get("/api/novels/gongmou/generate/queue-status")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("idle", "done", "running", "queued", "error")

    def test_generate_status_idle(self, client):
        novel = client.post("/api/novels", json={"id": _uid("gen-status"), "title": "生成状态"}).json()
        resp = client.get(f"/api/novels/{novel['id']}/generate/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"

    def test_foreshadowing(self, client):
        resp = client.get("/api/novels/gongmou/foreshadowing")
        assert resp.status_code == 200
        assert "total_open" in resp.json()

    def test_export_empty_novel_400(self, client):
        novel = client.post("/api/novels", json={"id": _uid("empty"), "title": "空导出"}).json()
        resp = client.get(f"/api/novels/{novel['id']}/export-epub")
        assert resp.status_code == 400

    def test_export_epub_ok(self, client):
        resp = client.get("/api/novels/gongmou/export-epub")
        assert resp.status_code == 200
