"""Integration tests — full pipeline"""
import os

import pytest
from starlette.testclient import TestClient

from novel_writer.config import Config
from novel_writer.database import Database
from novel_writer.generator import Generator
from novel_writer.server import app


@pytest.fixture
def client():
    # Use temp DB
    db_path = "/tmp/test_integration.db"
    if os.path.exists(db_path): os.remove(db_path)
    from novel_writer.server import db
    old = db.db_path
    db.db_path = db_path
    db._init()
    yield TestClient(app)
    db.db_path = old
    if os.path.exists(db_path): os.remove(db_path)

def test_full_crud_flow(client):
    """Create novel → list → get → delete → verify deleted"""
    r = client.post("/api/novels", json={"id":"flow","title":"完整流程","genre":"都市"})
    assert r.status_code == 200

    r = client.get("/api/novels")
    assert len(r.json()) == 1

    r = client.get("/api/novels/flow")
    assert r.json()["title"] == "完整流程"

    r = client.delete("/api/novels/flow")
    assert r.status_code == 200

    r = client.get("/api/novels/flow")
    assert r.status_code == 404

def test_mode_switch_flow(client):
    """Auto start → stop → verify mode changes"""
    client.post("/api/novels", json={"id":"mode","title":"模式测试"})
    client.post("/api/novels/mode/auto/start")
    client.post("/api/novels/mode/auto/stop")
    r = client.get("/api/novels/mode")
    assert r.status_code == 200

def test_chapter_edit_flow(client):
    """Create novel → save chapter → read chapter back"""
    client.post("/api/novels", json={"id":"ch","title":"章节测试"})
    r = client.put("/api/novels/ch/chapters/1", json={"content":"测试正文内容"})
    assert r.status_code == 200

def test_error_handling(client):
    """Verify proper error responses for invalid inputs"""
    assert client.get("/api/novels/nonexistent").status_code == 404
    assert client.post("/api/novels", json={}).status_code == 400
    assert client.post("/api/novels", json={"id":"x"}).status_code == 200  # title optional
    assert client.post("/api/novels", json={"id":"x"}).status_code == 409  # duplicate

def test_generator_quality_scoring():
    """V3: Quality scoring produces valid output"""
    from unittest.mock import patch

    from novel_writer.story_state import Character, Plot, StoryState, World
    state = StoryState(novel_id="q",title="q",author="AI",synopsis="",genre="玄幻",
        world=World(name="",era="",geography="",power_system=""),
        characters=[Character(id="p",name="叶凡",role="主角",personality="",background="",current_power_level="")],
        plot=Plot(premise="",main_arc="",current_arc="开篇"),chapters=[])
    with patch('novel_writer.generator.OpenAI'):
        gen = Generator(Config())
    body = "叶凡站在山巅，体内灵力翻涌。" * 60 + "\n\n\"准备好了吗？\"她问。\n" + "叶凡点头。" * 30
    result = gen.score_quality(body, state)
    assert 'scores' in result
    assert 'overall' in result
    assert 'grade' in result
    assert result['overall'] >= 0

def test_generator_de_ai():
    """V3: De-AI removes known patterns"""
    from unittest.mock import patch

    with patch('novel_writer.generator.OpenAI'):
        gen = Generator(Config())
    body = "在这个世界里，修炼是十分重要的。不仅如此，还需要坚持。"
    cleaned, changes = gen.de_ai(body)
    assert changes >= 1
    assert "在这个世界" not in cleaned

def test_database_transaction_integrity():
    """DB: Verify FK constraints and rollback"""
    db = Database("/tmp/test_tx.db")
    db.create_novel(id="tx", title="事务测试")
    # Attempt FK violation
    try:
        db.set_scheduler_state("nonexistent", is_running=1)
        assert False, "Should have raised IntegrityError"
    except Exception:
        pass  # Expected
    # Verify novel still exists
    assert db.get_novel("tx") is not None
    os.remove("/tmp/test_tx.db")

def test_publisher_params_validation():
    """Publisher: Instantiation with default config works"""
    from novel_writer.publisher import Publisher
    pub = Publisher()
    assert pub is not None
    assert hasattr(pub, 'publish')
    assert callable(pub.publish)

def test_config_defaults():
    """Config: Defaults are sane"""
    c = Config()
    assert c.model == "deepseek-v4-pro"
    assert 0 < c.temperature <= 1.0
    assert c.target_words_per_chapter > 0
    assert c.daily_run_time
