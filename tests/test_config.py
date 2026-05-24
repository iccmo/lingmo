"""Config tests"""
import os
from novel_writer.config import Config, validate

def test_config_defaults():
    c = Config()
    assert c.model == "deepseek-v4-pro"
    assert c.genre == "玄幻"
    assert c.temperature == 0.85

def test_config_validate():
    missing = validate()
    if os.getenv("OPENAI_API_KEY"):
        assert len(missing) == 0
    else:
        assert "OPENAI_API_KEY" in missing

def test_config_custom():
    c = Config(model="deepseek-chat", genre="都市", target_words_per_chapter=3000)
    assert c.model == "deepseek-chat"
    assert c.genre == "都市"
    assert c.target_words_per_chapter == 3000
