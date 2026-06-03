import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ═══ Module-level OpenAI mock — must be active BEFORE any test module imports Generator ═══
_openai_patcher = patch('openai.OpenAI')
_openai_patcher.start()

import pytest

from novel_writer.config import Config
from novel_writer.story_state import Character, Plot, StateManager, StoryState, World


@pytest.fixture(autouse=True)
def _disable_proxy():
    """Disable HTTP proxies during tests to avoid SOCKS tunnel errors."""
    for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
        os.environ.pop(key, None)


@pytest.fixture
def gen():
    """Generator with mocked OpenAI client (no real API call needed)."""
    with patch('openai.OpenAI'):
        from novel_writer.generator import Generator
        return Generator(Config())

@pytest.fixture
def tmp_data_dir(tmp_path):
    return str(tmp_path / "data")

@pytest.fixture
def state_manager(tmp_data_dir):
    return StateManager(tmp_data_dir)

@pytest.fixture
def minimal_state():
    return StoryState(
        novel_id="test-book",
        title="测试之书",
        author="AI",
        synopsis="测试用",
        genre="玄幻",
        world=World(
            name="测试大陆", era="上古", geography="一片大陆",
            power_system="练气→筑基→金丹",
        ),
        characters=[
            Character(
                id="protagonist", name="叶凡", role="主角",
                personality="坚韧不拔", background="普通少年",
                current_power_level="练气三层",
            )
        ],
        plot=Plot(
            premise="测试", main_arc="测试主线",
            current_arc="开篇", next_plot_points=["入门"],
        ),
        chapters=[],
    )

@pytest.fixture
def mock_llm_response():
    return """## 标题
突破筑基

## 正文
天雷滚滚，叶凡盘膝坐在山巅。体内灵力翻涌如潮，三年苦修只为这一刻。
（此处省略2000字正文内容）
他睁开双眼，眸中精光一闪——筑基已成！

## 元数据
```json
{
  "summary": "叶凡在雷劫中突破筑基，遭遇宿敌伏击",
  "key_events": ["叶凡突破", "宿敌出现"],
  "revelations": ["宿敌与叶凡同出一门"],
  "ending_hook": "宿敌临死前说：你以为你是孤儿？",
  "character_updates": {"叶凡": {"power_level": "筑基初期"}},
  "updated_plot_points": ["调查身世"],
  "new_foreshadowing": ["父亲下落"],
  "resolved_foreshadowing": []
}
```
"""
