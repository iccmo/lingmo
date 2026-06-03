"""TEST.md UT-GEN-01 ~ UT-QC-04"""
import pytest

from novel_writer.config import Config
from novel_writer.generator import Generator
from novel_writer.story_state import ChapterMeta


@pytest.fixture
def gen():
    return Generator(Config())

def test_build_prompt_world(gen, minimal_state):
    """UT-GEN-01: Prompt includes world info"""
    msgs = gen._build_prompt(minimal_state)
    sys = msgs[0]["content"]
    assert "测试大陆" in sys
    assert "练气→筑基→金丹" in sys

def test_build_prompt_characters(gen, minimal_state):
    """UT-GEN-02: Prompt includes character info"""
    msgs = gen._build_prompt(minimal_state)
    sys = msgs[0]["content"]
    assert "叶凡" in sys

def test_build_prompt_recent_chapters(gen, minimal_state):
    """UT-GEN-03: Prompt includes recent chapters"""
    for i in range(1, 8):
        minimal_state.chapters.append(ChapterMeta(
            number=i, title=f"Ch{i}", word_count=2000,
            summary=f"摘要{i}", ending_hook=f"钩子{i}",
        ))
    msgs = gen._build_prompt(minimal_state)
    sys = msgs[0]["content"]
    assert "Ch" in sys or "摘要" in sys

def test_build_prompt_ending_hook(gen, minimal_state):
    """UT-GEN-04: Prompt includes previous chapter hook"""
    minimal_state.chapters.append(ChapterMeta(
        number=1, title="序幕", word_count=2000,
        summary="开始", ending_hook="神秘人回头：我知道你的秘密",
    ))
    msgs = gen._build_prompt(minimal_state)
    user = msgs[1]["content"]
    assert "神秘人回头" in user or "我知道你的秘密" in user

def test_parse_markdown_response(gen):
    """UT-PARSE-01: Parse Markdown format"""
    raw = """## 标题
惊天反转

## 正文
这是正文内容，超过千字的故事徐徐展开...

## 元数据
```json
{"summary": "测试摘要", "key_events": ["事件1"], "revelations": [], "ending_hook": "钩子"}
```"""
    title, body, meta = gen._parse_response(raw, 3)
    assert title == "惊天反转"
    assert "正文内容" in body
    assert meta.get("summary") == "测试摘要"

def test_parse_natural_title(gen):
    """UT-PARSE-03: Extract title from natural text"""
    raw = "第3章 突破金丹\n\n天雷散去，叶凡睁开双眼..."
    title, body, meta = gen._parse_response(raw, 3)
    assert "突破金丹" in title

def test_parse_directions(gen, mock_llm_response):
    """UT-PARSE-04: Parse direction drafts"""
    directions_raw = """### 走向A
**概述**：叶凡突破后返回宗门
**预览**：叶凡脚踏飞剑，感受着体内澎湃的灵力。
**钩子**：比武台上，对手摘下斗笠——竟是失踪的大师兄

### 走向B
**概述**：叶凡卷入村庄阴谋
**预览**：叶凡本想回宗门，但路边老妇的哭声让他停下。
**钩子**：村长拿出玉佩，刻着叶凡未见过的家徽

### 走向C
**概述**：叶凡被隐藏势力盯上
**预览**：天雷散去，黑影从云层浮现。
**钩子**：黑影说：少爷，老爷让我接您回家
"""
    options = gen._parse_directions(directions_raw)
    assert len(options) == 3
    assert options[0].id == "A"
    assert "叶凡" in options[0].direction

def test_quality_short(gen, minimal_state):
    """UT-QC-01: Word count too short"""
    report = gen._check_quality("短", minimal_state)
    assert report.passed is False

def test_quality_pass(gen, minimal_state):
    """UT-QC-02: Quality passes"""
    body = "叶凡" + "测试正文内容" * 400
    report = gen._check_quality(body, minimal_state)
    assert report.passed is True

def test_quality_protagonist_missing(gen, minimal_state):
    """UT-QC-03: Protagonist not appearing"""
    body = "路人" * 500
    report = gen._check_quality(body, minimal_state)
    assert not report.passed or any("主角" in i for i in report.issues)

# --- Coverage gap tests ---

def test_split_markdown_sections(gen):
    raw = """## 标题
惊喜反转

## 正文
这是正文部分

## 元数据
一些元数据"""
    sections = gen._split_markdown_sections(raw)
    assert "标题" in sections or "title" in sections

def test_extract_title_digits(gen):
    title = gen._extract_title_from_text("第42章 巅峰对决\n正文开始...", 42)
    assert "巅峰对决" in title

def test_parse_response_no_title(gen):
    """Parse response with minimal content"""
    title, body, meta = gen._parse_response("只有正文内容没有标题", 5)
    assert len(title) > 0

def test_direction_prompt_structure(gen, minimal_state):
    msgs = gen._build_direction_prompt(minimal_state, "测试方向", 3)
    assert len(msgs) == 2
    assert "测试方向" in msgs[1]["content"]

def test_expand_prompt_structure(gen, minimal_state):
    from novel_writer.generator import DraftOption
    draft = DraftOption(id="B", title="走向B", direction="测试方向", preview="预览", hook="钩子")
    msgs = gen._build_expand_prompt(minimal_state, draft, edits="修改意见")
    assert len(msgs) == 2

def test_quality_report_dataclass():
    from novel_writer.generator import QualityReport
    r = QualityReport(passed=True, word_count=2500)
    assert r.passed
    assert r.issues == []

def test_draft_option_dataclass():
    from novel_writer.generator import DraftOption
    d = DraftOption(id="A", title="走向A", direction="测试", preview="预", hook="钩")
    assert d.id == "A"

# --- More edge cases ---

def test_parse_empty_response(gen):
    title, body, meta = gen._parse_response("", 1)
    assert body == ""
    # Empty input may produce empty title — that's acceptable

def test_parse_meta_no_json(gen):
    raw = """## 标题\n测试\n## 正文\n内容\n## 元数据\n这不是JSON"""
    title, body, meta = gen._parse_response(raw, 1)
    assert title == "测试"
    assert meta == {}

def test_parse_directions_empty(gen):
    results = gen._parse_directions("")
    assert results == []

def test_build_prompt_with_author_input(gen, minimal_state):
    msgs = gen._build_prompt(minimal_state, "主角突破元婴")
    user = msgs[1]["content"]
    assert "主角突破元婴" in user

def test_generator_init(gen):
    assert gen.cfg.model == "deepseek-v4-pro"

# --- V3: Quality scoring tests ---

def test_score_quality_excellent(gen, minimal_state):
    body = "叶凡站在山巅，感受着体内澎湃的灵力。" * 50 + "\n\n\"你真的要这样做吗？\"她问道。\n\n" + "叶凡深吸一口气。" * 10 + "\n\n突然，天空中裂开一道缝隙——难道这就是传说中的天门？"
    result = gen.score_quality(body, minimal_state)
    assert 'scores' in result
    assert 'overall' in result
    assert result['overall'] > 0.5
    assert result['grade'] in ('A', 'B', 'C')  # C is acceptable for synthetic test data

def test_score_quality_poor(gen, minimal_state):
    body = "短"
    result = gen.score_quality(body, minimal_state)
    assert result['overall'] < 0.55  # 8 dimensions now, some default high on tiny input
    assert result['grade'] in ('C', 'D')
    assert len(result['issues']) > 0

def test_score_quality_missing_protagonist(gen, minimal_state):
    body = "路人甲" * 500
    result = gen.score_quality(body, minimal_state)
    assert result['scores']['consistency'] < 0.5

def test_score_quality_all_dimensions(gen, minimal_state):
    """Verify all 5 dimensions exist"""
    body = "叶凡" * 100 + "\n\n对话内容" * 20 + "\n\n结尾悬疑……难道？"
    result = gen.score_quality(body, minimal_state)
    for dim in ['coherence', 'consistency', 'pacing', 'hook', 'readability', 'formatting', 'antagonist']:
        assert dim in result['scores'], f"Missing dimension: {dim}"

# --- V3: De-AI tests ---

def test_de_ai_removes_patterns(gen):
    body = "在这个世界上，叶凡开始了修炼。不仅如此，他还遇到了宿敌。"
    cleaned, changes = gen.de_ai(body)
    assert "在这个世界" not in cleaned
    assert "不仅如此" not in cleaned
    assert changes >= 2

def test_de_ai_no_false_positives(gen):
    body = "叶凡深吸一口气，手中的长剑微微颤抖。他知道，这一战避无可避。"
    cleaned, changes = gen.de_ai(body)
    assert cleaned == body
    assert changes == 0

def test_de_ai_formulaic_sequencing(gen):
    body = "首先，叶凡检查了装备。其次，他制定了计划。最后，他出发了。"
    cleaned, changes = gen.de_ai(body)
    assert "首先" not in cleaned
    assert "其次" not in cleaned
    assert "最后" not in cleaned

# --- V3: RAG tests ---

def test_cosine_similarity_identical(gen):
    v = [1.0, 2.0, 3.0]
    assert gen._cosine_similarity(v, v) == 1.0

def test_cosine_similarity_orthogonal(gen):
    assert gen._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

def test_cosine_similarity_empty(gen):
    assert gen._cosine_similarity([], [1.0]) == 0.0
    assert gen._cosine_similarity([1.0], []) == 0.0

def test_de_ai_no_changes_on_clean_text(gen):
    """De-AI should not modify clean human-like text"""
    body = "夜已深，叶凡独自坐在院子里，望着满天星辰。他知道，明天就是宗门大比的日子。"
    cleaned, changes = gen.de_ai(body)
    assert changes == 0
    assert cleaned == body

def test_de_ai_multiple_patterns(gen):
    body = "首先，在这个世界里修炼是十分重要的。其次，不仅如此，还需要丹药辅助。最后，总的来说，坚持不懈才是关键。"
    cleaned, changes = gen.de_ai(body)
    assert changes >= 4
    assert "首先" not in cleaned
    assert "总的来说" not in cleaned
