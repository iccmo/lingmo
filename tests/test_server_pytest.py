"""FastAPI endpoint tests — isolated per test via tmp_path fixture"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """Each test gets its own TestClient with an isolated temp database."""
    db_path = str(tmp_path / "test.db")

    from novel_writer.server import app, db
    old_path = db.db_path
    db.db_path = db_path
    db._init()
    tc = TestClient(app)
    yield tc
    # Restore original path
    db.db_path = old_path


# --- Status & Health ---

def test_status_endpoint(client):
    """GET /api/status returns 200 with expected keys."""
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "novels_count" in data
    assert "total_chapters" in data
    assert "total_words" in data
    assert "server_time" in data
    assert data["novels_count"] == 0
    assert data["total_chapters"] == 0
    assert data["total_words"] == 0


def test_health_endpoint(client):
    """GET /api/health returns a valid status."""
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "healthy", "degraded")
    assert "issues" in data


# --- Novel CRUD ---

def test_list_novels(client):
    """GET /api/novels returns a list (empty or populated)."""
    # Initially empty
    r = client.get("/api/novels")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) == 0

    # Create some novels
    client.post("/api/novels", json={"id": "api-n1", "title": "第一本"})
    client.post("/api/novels", json={"id": "api-n2", "title": "第二本"})

    r2 = client.get("/api/novels")
    assert r2.status_code == 200
    novels = r2.json()
    assert len(novels) == 2
    titles = {n["title"] for n in novels}
    assert titles == {"第一本", "第二本"}


def test_create_and_get_novel(client):
    """POST /api/novels creates, GET /api/novels/{id} retrieves."""
    r = client.post("/api/novels", json={
        "id": "api-get-test",
        "title": "获取测试",
        "genre": "都市",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "获取测试"
    assert data["genre"] == "都市"

    r2 = client.get("/api/novels/api-get-test")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["title"] == "获取测试"
    assert data2["genre"] == "都市"


# --- Settings Persistence ---

def test_settings_sync(client):
    """POST /api/settings/sync saves settings, GET /api/settings loads them."""
    # Sync settings
    r = client.post("/api/settings/sync", json={
        "theme": "dark",
        "fontSize": "16",
        "autoSave": "true",
    })
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    # Load settings back
    r2 = client.get("/api/settings")
    assert r2.status_code == 200
    settings = r2.json()
    assert settings["theme"] == "dark"
    assert settings["fontSize"] == "16"
    assert settings["autoSave"] == "true"

    # Sync again to update values
    client.post("/api/settings/sync", json={
        "theme": "light",
        "language": "zh-CN",
    })
    r3 = client.get("/api/settings")
    assert r3.status_code == 200
    settings2 = r3.json()
    assert settings2["theme"] == "light"
    assert settings2["language"] == "zh-CN"
    # Old settings should still be there
    assert settings2["fontSize"] == "16"
    assert settings2["autoSave"] == "true"


# --- Search ---

def test_search(client):
    """GET /api/search?q=test returns results (searches chapter content).

    Uses db.add_chapter() directly because the PUT /chapters/{n} endpoint
    only updates existing chapters and doesn't set word_count (required by
    the search query's WHERE word_count > 0 filter).
    """
    from novel_writer.server import db as srv_db

    # Create a novel
    client.post("/api/novels", json={
        "id": "search-test",
        "title": "搜索测试",
    })

    # Add a chapter with searchable content via DB (word_count must be > 0)
    srv_db.add_chapter(
        novel_id="search-test",
        number=1,
        title="第一章",
        word_count=500,
        content="主角叶凡在测试中突破境界，灵力翻涌如潮。",
    )

    # Search for content
    r = client.get("/api/search", params={"q": "叶凡"})
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "total" in data
    assert isinstance(data["results"], list)
    # Should find at least one result
    assert len(data["results"]) >= 1
    assert data["total"] >= 1

    # Search for non-existent text
    r2 = client.get("/api/search", params={"q": "不存在的文本xyz"})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["total"] == 0
    assert len(data2["results"]) == 0

    # Search with too-short query returns empty
    r3 = client.get("/api/search", params={"q": "叶"})
    assert r3.status_code == 200
    data3 = r3.json()
    assert data3["total"] == 0


def test_search_with_novel_id(client):
    """GET /api/search filters by novel_id."""
    from novel_writer.server import db as srv_db

    client.post("/api/novels", json={"id": "n-a", "title": "Novel A"})
    client.post("/api/novels", json={"id": "n-b", "title": "Novel B"})

    srv_db.add_chapter(novel_id="n-a", number=1, title="Ch1",
                       word_count=300, content="修仙世界")
    srv_db.add_chapter(novel_id="n-b", number=1, title="Ch1",
                       word_count=300, content="都市生活")

    # Search within novel A only
    r = client.get("/api/search", params={"q": "修仙", "novel_id": "n-a"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    for result in data["results"]:
        assert result["novel_id"] == "n-a"

    # Search within novel B should not find "修仙" in results
    r2 = client.get("/api/search", params={"q": "修仙", "novel_id": "n-b"})
    assert r2.status_code == 200
    data2 = r2.json()
    assert len(data2["results"]) == 0
    # Note: total counts across all novels (unfiltered), so it may be >= 1


# --- Audio Data ---

def test_audio_data(client):
    """GET /api/audio/data returns bookmarks/playlist/settings structure."""
    # Seed some audio data first
    client.post("/api/audio/sync", json={
        "bookmarks": [{
            "id": "bm1",
            "novelId": "test-novel",
            "novelTitle": "Test Novel",
            "chapterNum": 3,
            "chapterTitle": "Chapter 3",
            "position": 150.0,
            "note": "Interesting",
            "tag": "climax",
            "createdAt": "2026-05-25T10:00:00",
        }],
        "settings": {
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "1.0",
        },
        "playlist": [{
            "novelId": "test-novel",
            "novelTitle": "Test Novel",
            "chapterNum": 3,
            "chapterTitle": "Chapter 3",
        }],
        "stats": {
            "total_listened": "3600",
            "sessions": "12",
        },
    })

    # Load audio data
    r = client.get("/api/audio/data")
    assert r.status_code == 200
    data = r.json()

    # Verify all expected sections exist
    assert "bookmarks" in data
    assert "settings" in data
    assert "playlist" in data
    assert "progress" in data
    assert "stats" in data

    # Verify bookmarks
    assert len(data["bookmarks"]) >= 1
    bm = data["bookmarks"][0]
    assert bm["id"] == "bm1"
    assert bm["novelId"] == "test-novel"
    assert bm["chapterNum"] == 3
    assert bm["note"] == "Interesting"
    assert bm["tag"] == "climax"

    # Verify settings
    assert data["settings"]["voice"] == "zh-CN-XiaoxiaoNeural"
    assert data["settings"]["rate"] == "1.0"

    # Verify playlist
    assert len(data["playlist"]) >= 1
    pl = data["playlist"][0]
    assert pl["novelId"] == "test-novel"
    assert pl["chapterNum"] == 3

    # Verify stats
    assert data["stats"]["total_listened"] == "3600"
    assert data["stats"]["sessions"] == "12"


def test_audio_sync_updates(client):
    """POST /api/audio/sync updates audio data incrementally.

    Note: audio_progress has a FK to novels(id), so we create novels first.
    """
    # Create novels so progress FK constraint is satisfied
    client.post("/api/novels", json={"id": "n1", "title": "Novel One"})

    # Initial sync
    r0 = client.post("/api/audio/sync", json={
        "settings": {"voice": "voice-a", "rate": "1.0"},
        "progress": [{"novelId": "n1", "chapterNum": 5, "position": 300.0}],
    })
    assert r0.status_code == 200

    r1 = client.get("/api/audio/data")
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["settings"]["voice"] == "voice-a"
    assert len(data1["progress"]) >= 1

    # Update settings and add bookmarks
    client.post("/api/audio/sync", json={
        "settings": {"voice": "voice-b"},
        "bookmarks": [{
            "id": "bm-new",
            "novelId": "n1",
            "novelTitle": "Novel One",
            "chapterNum": 5,
            "chapterTitle": "Ch5",
            "position": 300.0,
            "note": "Resume point",
            "tag": "",
            "createdAt": "2026-05-25T12:00:00",
        }],
    })

    r2 = client.get("/api/audio/data")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["settings"]["voice"] == "voice-b"
    # Old setting should still be there
    assert data2["settings"]["rate"] == "1.0"
    assert len(data2["bookmarks"]) >= 1


def test_audio_sync_progress(client):
    """POST /api/audio/sync with progress saves and retrieves correctly.

    Note: audio_progress has PRIMARY KEY(novel_id), so each novel_id
    can have only one progress entry. Use different novel IDs.
    Also has FK to novels(id), so create novels first.
    """
    client.post("/api/novels", json={"id": "n-prog-1", "title": "Progress Novel 1"})
    client.post("/api/novels", json={"id": "n-prog-2", "title": "Progress Novel 2"})
    client.post("/api/novels", json={"id": "n-prog-3", "title": "Progress Novel 3"})

    r0 = client.post("/api/audio/sync", json={
        "progress": [
            {"novelId": "n-prog-1", "chapterNum": 1, "position": 45.5},
            {"novelId": "n-prog-2", "chapterNum": 2, "position": 120.0},
            {"novelId": "n-prog-3", "chapterNum": 3, "position": 250.0},
        ],
    })
    assert r0.status_code == 200

    r = client.get("/api/audio/data")
    assert r.status_code == 200
    progress_items = r.json()["progress"]
    assert len(progress_items) >= 2
    positions = {(p["novelId"], p["chapterNum"], p["position"]) for p in progress_items}
    assert ("n-prog-1", 1, 45.5) in positions
    assert ("n-prog-2", 2, 120.0) in positions
    assert ("n-prog-3", 3, 250.0) in positions
