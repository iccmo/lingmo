from novel_writer.routers.novel import story_bible_service
from novel_writer.database import Database


class FakeBibleDB:
    def __init__(self):
        self.calls = []

    def clear_story_bible_chapter(self, novel_id, chapter_num):
        self.calls.append(("clear", novel_id, chapter_num))

    def save_character_state(self, novel_id, chapter_num, char_name, **kwargs):
        self.calls.append(("character", novel_id, chapter_num, char_name, kwargs))

    def save_foreshadowing(self, novel_id, chapter_num, description, **kwargs):
        self.calls.append(("foreshadowing", novel_id, chapter_num, description, kwargs))

    def save_location_history(self, novel_id, chapter_num, location_name, **kwargs):
        self.calls.append(("location", novel_id, chapter_num, location_name, kwargs))

    def save_timeline_event(self, novel_id, chapter_num, **kwargs):
        self.calls.append(("timeline", novel_id, chapter_num, kwargs))

    def save_world_state(self, novel_id, chapter_num, rule_name, **kwargs):
        self.calls.append(("world", novel_id, chapter_num, rule_name, kwargs))

    def save_cost_entry(self, novel_id, chapter_num, **kwargs):
        self.calls.append(("cost", novel_id, chapter_num, kwargs))


class FakeBibleGenerator:
    def _call_llm_with_retry(self, messages, max_tokens=2048):
        return """{
          "characters": [{"name": "叶凡", "emotion": "震惊", "physical_state": "受伤"}],
          "foreshadowing": [{"description": "古玉裂纹", "hint_text": "裂纹发光", "due_by_chapter": 5}],
          "locations": [{"name": "黑水城", "event": "抵达"}],
          "timeline": {"event_summary": "叶凡抵达黑水城"},
          "world_rules": [{"rule": "古玉可传讯", "description": "裂纹浮现线索"}],
          "costs": [{"character": "叶凡", "gain": "母亲线索", "loss": "左臂受伤"}]
        }"""


class DirtyBibleGenerator:
    def _call_llm_with_retry(self, messages, max_tokens=2048):
        return """{
          "characters": [
            {"name": " 叶凡 ", "knowledge": ["古玉裂开", "古玉裂开"], "relationships": [{"target": "母亲", "change": "留下线索"}]},
            {"name": "叶凡", "emotion": "重复角色"},
            {"name": ""}
          ],
          "foreshadowing": [
            {"description": " 古玉裂纹 ", "hint_text": "裂纹发光", "due_by_chapter": "第五章"},
            {"description": "古玉裂纹", "due_by_chapter": "第七章"},
            {"description": ""}
          ],
          "locations": [{"name": "黑水城"}, {"name": "黑水城"}, {"name": ""}],
          "timeline": {"event_summary": "叶凡抵达黑水城"},
          "world_rules": [{"rule": "古玉可传讯"}, {"rule": "古玉可传讯"}],
          "costs": [{"character": "叶凡", "gain": "母亲线索", "loss": ""}]
        }"""


class BlankLossBibleGenerator:
    def _call_llm_with_retry(self, messages, max_tokens=2048):
        return """{
          "characters": [{"name": "叶凡"}],
          "costs": [{"character": "叶凡", "gain": "母亲线索", "loss": ""}]
        }"""


class NoCostBibleGenerator:
    def _call_llm_with_retry(self, messages, max_tokens=2048):
        return """{
          "characters": [{"name": "叶凡"}],
          "costs": []
        }"""


def test_extract_story_bible_clears_existing_chapter_rows(monkeypatch):
    db = FakeBibleDB()
    monkeypatch.setattr(story_bible_service, "get_db", lambda: db)
    monkeypatch.setattr(story_bible_service, "_generator_for", lambda novel_id: FakeBibleGenerator())

    story_bible_service.extract_story_bible("book", 3, "正文", "裂纹")

    assert db.calls[0] == ("clear", "book", 3)
    assert any(call[0] == "character" for call in db.calls)
    assert any(call[0] == "foreshadowing" for call in db.calls)


def test_parse_story_bible_json_handles_nested_and_braces_in_strings():
    raw = """模型说明：
```json
{
  "characters": [
    {"name": "叶凡", "relationships": [{"target": "母亲", "change": "读到密信 {禁令}"}]}
  ],
  "timeline": {"event_summary": "叶凡发现古玉裂纹"},
}
```
"""

    parsed = story_bible_service._parse_story_bible_json(raw)

    assert parsed["characters"][0]["relationships"][0]["change"] == "读到密信 {禁令}"
    assert parsed["timeline"]["event_summary"] == "叶凡发现古玉裂纹"


def test_extract_story_bible_normalizes_dirty_fields(monkeypatch):
    db = FakeBibleDB()
    monkeypatch.setattr(story_bible_service, "get_db", lambda: db)
    monkeypatch.setattr(story_bible_service, "_generator_for", lambda novel_id: DirtyBibleGenerator())

    story_bible_service.extract_story_bible("book", 5, "正文", "裂纹")

    characters = [call for call in db.calls if call[0] == "character"]
    foreshadowing = [call for call in db.calls if call[0] == "foreshadowing"]
    locations = [call for call in db.calls if call[0] == "location"]
    rules = [call for call in db.calls if call[0] == "world"]

    assert len(characters) == 1
    assert characters[0][3] == "叶凡"
    assert characters[0][4]["knowledge"] == '["古玉裂开"]'
    assert len(foreshadowing) == 1
    assert foreshadowing[0][3] == "古玉裂纹"
    assert foreshadowing[0][4]["due_by"] == 5
    assert len(locations) == 1
    assert len(rules) == 1


def test_extract_story_bible_fills_blank_cost_loss_from_content(monkeypatch):
    db = FakeBibleDB()
    monkeypatch.setattr(story_bible_service, "get_db", lambda: db)
    monkeypatch.setattr(story_bible_service, "_generator_for", lambda novel_id: BlankLossBibleGenerator())

    story_bible_service.extract_story_bible(
        "book",
        6,
        "叶凡拿到母亲线索，却因此左臂受伤流血，还在众人面前暴露身份。",
        "代价",
    )

    costs = [call for call in db.calls if call[0] == "cost"]
    assert len(costs) == 1
    assert "受伤" in costs[0][3]["loss"]
    assert costs[0][3]["loss_type"] == "health"


def test_extract_story_bible_adds_cost_when_llm_omits_costs(monkeypatch):
    db = FakeBibleDB()
    monkeypatch.setattr(story_bible_service, "get_db", lambda: db)
    monkeypatch.setattr(story_bible_service, "_generator_for", lambda novel_id: NoCostBibleGenerator())

    story_bible_service.extract_story_bible(
        "book",
        7,
        "叶凡救下同伴，却欠下城主一笔人情债，后患还没结束。",
        "人情债",
    )

    costs = [call for call in db.calls if call[0] == "cost"]
    assert len(costs) == 1
    assert costs[0][3]["character_name"] == "叶凡"
    assert "人情债" in costs[0][3]["loss"]
    assert costs[0][3]["loss_type"] == "freedom"


def test_consistency_check_uses_latest_prior_character_state(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "consistency.db"))
    db.create_novel(id="book", title="一致性")
    db.save_character_state("book", 1, "叶凡", physical_state="左臂受伤")
    db.save_character_state("book", 3, "叶凡", physical_state="健康")
    monkeypatch.setattr(story_bible_service, "get_db", lambda: db)

    story_bible_service.run_consistency_check("book", 3)

    log = db.get_consistency_log("book")
    assert len(log) == 1
    assert log[0]["check_type"] == "character"
    assert "第1章状态" in log[0]["description"]


def test_consistency_check_flags_same_character_location_jump(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "location-jump.db"))
    db.create_novel(id="book", title="地点跳转")
    db.save_character_state("book", 1, "叶凡", location="青云山")
    db.save_character_state("book", 3, "叶凡", location="天都城")
    monkeypatch.setattr(story_bible_service, "get_db", lambda: db)

    story_bible_service.run_consistency_check("book", 3)

    log = db.get_consistency_log("book")
    assert len(log) == 1
    assert log[0]["check_type"] == "timeline"
    assert "青云山" in log[0]["description"]
    assert "天都城" in log[0]["description"]


def test_consistency_check_is_idempotent_for_same_chapter(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "idempotent-check.db"))
    db.create_novel(id="book", title="重复检查")
    db.save_character_state("book", 1, "叶凡", physical_state="重伤")
    db.save_character_state("book", 2, "叶凡", physical_state="健康")
    monkeypatch.setattr(story_bible_service, "get_db", lambda: db)

    story_bible_service.run_consistency_check("book", 2)
    story_bible_service.run_consistency_check("book", 2)

    log = db.get_consistency_log("book")
    assert len(log) == 1
    assert log[0]["check_type"] == "character"


def test_consistency_check_ignores_global_location_history_without_character_move(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "global-location.db"))
    db.create_novel(id="book", title="全局地点")
    db.save_location_history("book", 1, "青云山")
    db.save_location_history("book", 2, "天都城")
    monkeypatch.setattr(story_bible_service, "get_db", lambda: db)

    story_bible_service.run_consistency_check("book", 2)

    assert db.get_consistency_log("book") == []
