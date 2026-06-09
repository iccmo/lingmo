from novel_writer.routers.novel import agent_pipeline_service


class FakeCreativeDb:
    def get_character_state(self, novel_id):
        return []

    def get_active_foreshadowing(self, novel_id):
        return []

    def get_unsaid(self, novel_id):
        return []

    def get_cost_ledger(self, novel_id):
        return []

    def get_soul_fingerprint(self, novel_id):
        return {
            "polarity": "freedom-fate",
            "answer": "自由选择本身会揭露命运",
            "position": 7,
        }

    def get_character_blueprints(self, novel_id):
        return [
            {
                "id": "hero",
                "name": "叶凡",
                "role": "主角",
                "coreWound": "父亲失踪",
                "voiceSample": "我自己选，也自己扛。",
            }
        ]


class CapturingGenerator:
    def __init__(self):
        self.prompts: list[str] = []

    def _call_llm_with_retry(self, messages, max_tokens=512):
        self.prompts.append(messages[0]["content"])
        return "生成结果"


def test_editor_in_chief_brief_includes_creation_brief(monkeypatch):
    fake_gen = CapturingGenerator()
    monkeypatch.setattr(agent_pipeline_service, "get_db", lambda: FakeCreativeDb())
    monkeypatch.setattr(agent_pipeline_service, "_generator_for", lambda novel_id: fake_gen)

    result = agent_pipeline_service.editor_in_chief_brief("book", 3)

    assert result == "生成结果"
    prompt = fake_gen.prompts[0]
    assert "【创作硬约束】" in prompt
    assert "自由vs命运" in prompt
    assert "自由选择本身会揭露命运" in prompt
    assert "叶凡（主角）" in prompt
    assert "父亲失踪" in prompt
    assert "我自己选，也自己扛。" in prompt


def test_architect_outline_includes_creation_brief(monkeypatch):
    fake_gen = CapturingGenerator()
    monkeypatch.setattr(agent_pipeline_service, "get_db", lambda: FakeCreativeDb())
    monkeypatch.setattr(agent_pipeline_service, "_generator_for", lambda novel_id: fake_gen)

    result = agent_pipeline_service.architect_outline("book", 3, "总编要求本章支付代价")

    assert result == "生成结果"
    prompt = fake_gen.prompts[0]
    assert "【创作硬约束】" in prompt
    assert "自由vs命运" in prompt
    assert "叶凡（主角）" in prompt
    assert "总编要求本章支付代价" in prompt
