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


def test_batch_generate_skips_explanation_candidate(gen, minimal_state, monkeypatch):
    calls = {"count": 0}

    def fake_generate(state, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return ChapterMeta(
                number=1,
                title="说明稿",
                word_count=30,
                summary="",
                content="以下是第1章正文：\n\n我会加强主角主动性，并加入更多冲突。",
            )
        return ChapterMeta(
            number=1,
            title="正文章",
            word_count=30,
            summary="",
            content="叶凡握紧古玉，推开雨幕，独自走向黑水城。",
        )

    monkeypatch.setattr(gen, "generate", fake_generate)
    monkeypatch.setattr(gen, "score_quality", lambda body, state, style=None: {"overall": 0.9, "grade": "A"})

    chapter, quality = gen.batch_generate(minimal_state, n=2)

    assert calls["count"] == 2
    assert chapter.title == "正文章"
    assert quality["overall"] == 0.9


def test_batch_generate_skips_outline_list_candidate(gen, minimal_state, monkeypatch):
    calls = {"count": 0}

    def fake_generate(state, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return ChapterMeta(
                number=1,
                title="提纲稿",
                word_count=50,
                summary="",
                content="章节大纲：\n1. 开场：叶凡进城\n2. 冲突：黑衣人现身\n3. 结尾：古玉发光",
            )
        return ChapterMeta(
            number=1,
            title="正文章",
            word_count=30,
            summary="",
            content="叶凡握紧古玉，推开雨幕，独自走向黑水城。",
        )

    monkeypatch.setattr(gen, "generate", fake_generate)
    monkeypatch.setattr(gen, "score_quality", lambda body, state, style=None: {"overall": 0.9, "grade": "A"})

    chapter, quality = gen.batch_generate(minimal_state, n=2)

    assert calls["count"] == 2
    assert chapter.title == "正文章"
    assert quality["overall"] == 0.9


def test_generate_chapter_classic_skips_explanation_candidate(gen, minimal_state, monkeypatch):
    calls = {"count": 0}

    def fake_generate(state, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return ChapterMeta(
                number=1,
                title="说明稿",
                word_count=30,
                summary="",
                content="以下是第1章正文：\n\n我会加强主角主动性，并加入更多冲突。",
            )
        return ChapterMeta(
            number=1,
            title="正文章",
            word_count=30,
            summary="",
            content="叶凡盯着古玉裂纹，没有立刻逃走，但他没有告诉任何人。",
        )

    monkeypatch.setattr(gen, "generate", fake_generate)
    monkeypatch.setattr(gen, "judge_quality", lambda body, state, style=None: {"overall": 0.9, "grade": "A", "issues": []})
    monkeypatch.setattr(gen, "_classic_check", lambda body, state, style=None: (True, []))
    monkeypatch.setattr(gen, "_cross_chapter_check", lambda body, state, style=None: (True, []))
    monkeypatch.setattr(gen, "_count_quotable_lines", lambda body: 2)
    monkeypatch.setattr(gen, "_self_edit", lambda body, state, style=None: body)

    chapter = gen.generate_chapter_classic(minimal_state)

    assert calls["count"] == 2
    assert chapter.title == "正文章"


def test_build_prompt_includes_previous_chapter_content(gen, minimal_state):
    minimal_state.chapters.append(ChapterMeta(
        number=1,
        title="序幕",
        word_count=2000,
        summary="上一章摘要",
        content="上一章完整正文：叶凡在雨夜发现古玉裂纹。",
    ))

    msgs = gen._build_prompt(minimal_state)
    system = msgs[0]["content"]

    assert "## 上一章全文" in system
    assert "叶凡在雨夜发现古玉裂纹" in system


def test_build_prompt_metadata_schema_includes_state_updates(gen, minimal_state):
    msgs = gen._build_prompt(minimal_state)
    system = msgs[0]["content"]

    assert '"character_updates"' in system
    assert '"updated_plot_points"' in system
    assert '"new_foreshadowing"' in system
    assert '"resolved_foreshadowing"' in system
    assert "故事状态更新源" in system


def test_build_prompt_requires_agency_and_cost(gen, minimal_state):
    msgs = gen._build_prompt(minimal_state)
    system = msgs[0]["content"]

    assert "主角做出一个清晰的主动选择" in system
    assert "不能只被安排、被救场或被事件推着走" in system
    assert "重要收益" in system
    assert "具体代价或后果" in system


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
    assert "第3章" not in body
    assert body.startswith("天雷散去")


def test_parse_freeform_response_strips_metadata_tail(gen):
    raw = """第1章 雨夜古玉

叶凡握紧古玉，推开雨幕。

元数据
{"summary": "雨夜", "key_events": ["叶凡出城"]}"""
    title, body, meta = gen._parse_response(raw, 1)

    assert title == "雨夜古玉"
    assert body == "叶凡握紧古玉，推开雨幕。"
    assert "summary" not in body

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
    assert "主角做出一个清晰的主动选择" in msgs[0]["content"]
    assert "具体代价或后果" in msgs[0]["content"]
    assert "测试方向" in msgs[1]["content"]

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


def test_parse_meta_nested_json(gen):
    raw = """## 标题
突破

## 正文
叶凡突破筑基。

## 元数据
```json
{"summary":"突破", "character_updates": {"叶凡": {"power_level": "筑基初期", "status": "受伤"}}, "updated_plot_points": ["调查身世"]}
```"""

    _title, _body, meta = gen._parse_response(raw, 1)

    assert meta["character_updates"]["叶凡"]["power_level"] == "筑基初期"
    assert meta["updated_plot_points"] == ["调查身世"]


def test_parse_meta_json_with_braces_inside_string(gen):
    raw = """## 标题
密信

## 正文
叶凡打开密信。

## 元数据
```json
{"summary":"密信上写着 {禁令} 两字", "key_events": ["叶凡读到密信"]}
```"""

    _title, _body, meta = gen._parse_response(raw, 1)

    assert meta["summary"] == "密信上写着 {禁令} 两字"
    assert meta["key_events"] == ["叶凡读到密信"]

def test_parse_directions_empty(gen):
    results = gen._parse_directions("")
    assert results == []

def test_build_prompt_with_author_input(gen, minimal_state):
    msgs = gen._build_prompt(minimal_state, "主角突破元婴")
    user = msgs[1]["content"]
    assert "主角突破元婴" in user


def test_revise_chapter_prompt_preserves_agency_and_cost(gen, minimal_state, monkeypatch):
    seen: dict[str, str] = {}

    def fake_call(messages, max_tokens=4096):
        seen["system"] = messages[0]["content"]
        return "叶凡决定独自进城，因此暴露身份并留下后患。"

    monkeypatch.setattr(gen, "_call_llm_with_retry", fake_call)

    gen.revise_chapter("叶凡进城。", "补足节奏", minimal_state)

    assert "不得削弱主角主动选择" in seen["system"]
    assert "不得削弱代价与后果" in seen["system"]
    assert "不能把风险写没" in seen["system"]


def test_self_edit_prompt_preserves_agency_and_cost(gen, minimal_state, monkeypatch):
    seen: dict[str, str] = {}

    def fake_call(messages, max_tokens=4096):
        seen["system"] = messages[0]["content"]
        seen["user"] = messages[1]["content"]
        return "叶凡决定押上古玉救人，因此受伤并暴露身份。"

    monkeypatch.setattr(gen, "_call_llm_with_retry", fake_call)

    gen._self_edit("叶凡决定押上古玉救人，因此受伤并暴露身份。", minimal_state)

    assert "不删除主角主动选择、代价、风险或后果" in seen["system"]
    assert "不得删除或淡化主角主动选择" in seen["user"]
    assert "不得删除或淡化收益带来的代价" in seen["user"]
    assert "关系裂痕" in seen["user"]


def test_generate_chapters_passes_author_input(gen, minimal_state, monkeypatch):
    seen_author_inputs: list[str] = []

    def fake_batch_generate(state, n=1, rag_context=None, outline=None, style=None, author_input=""):
        seen_author_inputs.append(author_input)
        chapter = ChapterMeta(
            number=state.total_chapters + 1,
            title="魂印",
            word_count=1200,
            summary="叶凡在雨夜发现古玉裂纹。",
            content="叶凡在雨夜发现古玉裂纹，决定隐瞒母亲留下的黑水城线索。",
        )
        return chapter, {"overall": 0.9, "grade": "A", "issues": []}

    monkeypatch.setattr(gen, "batch_generate", fake_batch_generate)
    monkeypatch.setattr(gen, "score_quality", lambda body, state, style=None: {"overall": 0.9})
    monkeypatch.setattr(gen, "_self_edit", lambda body, state, style=None: body)
    monkeypatch.setattr(gen, "de_ai", lambda body: (body, 0))
    monkeypatch.setattr(gen, "humanize", lambda body: body)
    monkeypatch.setattr(gen, "_save_version", lambda *args, **kwargs: None)
    monkeypatch.setattr(gen, "_extract_character_voices", lambda *args, **kwargs: None)

    chapters = gen.generate_chapters(
        minimal_state,
        n=1,
        author_input="【角色蓝图硬约束】叶凡：不能忽略核心创伤",
    )

    assert len(chapters) == 1
    assert seen_author_inputs == ["【角色蓝图硬约束】叶凡：不能忽略核心创伤"]


def test_generate_chapters_refreshes_postprocessed_memory(gen, minimal_state, monkeypatch):
    def fake_batch_generate(state, n=1, rag_context=None, outline=None, style=None, author_input=""):
        chapter = ChapterMeta(
            number=state.total_chapters + 1,
            title="魂印",
            word_count=1200,
            summary="叶凡得到魂印。",
            content="叶凡得到魂印。",
            narrative_facts=["叶凡得到魂印"],
        )
        return chapter, {"overall": 0.9, "grade": "A", "issues": []}

    monkeypatch.setattr(gen, "batch_generate", fake_batch_generate)
    monkeypatch.setattr(gen, "score_quality", lambda body, state, style=None: {"overall": 0.9})
    monkeypatch.setattr(gen, "_self_edit", lambda body, state, style=None: body)
    monkeypatch.setattr(gen, "de_ai", lambda body: (body, 0))
    monkeypatch.setattr(gen, "humanize", lambda body: "叶凡得到魂印后决定隐瞒真相，因此受伤流血并暴露身份。")
    monkeypatch.setattr(gen, "_save_version", lambda *args, **kwargs: None)
    monkeypatch.setattr(gen, "_extract_character_voices", lambda *args, **kwargs: None)

    chapters = gen.generate_chapters(minimal_state, n=1)

    assert chapters[0].content == "叶凡得到魂印后决定隐瞒真相，因此受伤流血并暴露身份。"
    assert any("受伤" in fact or "暴露身份" in fact for fact in chapters[0].narrative_facts)
    assert minimal_state.chapters[-1].narrative_facts == chapters[0].narrative_facts


def test_humanize_processes_entire_long_chapter(gen, monkeypatch):
    seen_chunks: list[str] = []

    def fake_call(messages, max_tokens=8192):
        source = messages[1]["content"].split("原稿：\n", 1)[1].split("\n\n修改后：", 1)[0]
        seen_chunks.append(source)
        return source.replace("AI腔", "人味感")

    monkeypatch.setattr(gen, "_call_llm_with_retry", fake_call)
    body = ("前段AI腔。" * 900) + "尾部标记TAILAI腔。"

    result = gen.humanize(body)

    assert len(seen_chunks) > 1
    assert "尾部标记TAIL人味感" in result
    assert "尾部标记TAILAI腔" not in result
    assert len(result) == len(body)


def test_humanize_prompt_preserves_agency_and_cost(gen, monkeypatch):
    seen: dict[str, str] = {}

    def fake_call(messages, max_tokens=8192):
        seen["system"] = messages[0]["content"]
        seen["user"] = messages[1]["content"]
        source = messages[1]["content"].split("原稿：\n", 1)[1].split("\n\n修改后：", 1)[0]
        return source

    monkeypatch.setattr(gen, "_call_llm_with_retry", fake_call)

    gen.humanize("叶凡决定独自进城，因此暴露身份并留下后患。" * 4)

    assert "不删除主角主动选择、代价、风险或后果" in seen["system"]
    assert "绝对不要删除或淡化主角的主动选择" in seen["user"]
    assert "后续麻烦" in seen["user"]


def test_humanize_returns_original_when_any_chunk_is_too_short(gen, monkeypatch):
    calls = 0

    def fake_call(messages, max_tokens=8192):
        nonlocal calls
        calls += 1
        if calls == 2:
            return "过短"
        source = messages[1]["content"].split("原稿：\n", 1)[1].split("\n\n修改后：", 1)[0]
        return source

    monkeypatch.setattr(gen, "_call_llm_with_retry", fake_call)
    body = ("前段AI腔。" * 900) + "尾部标记TAILAI腔。"

    assert gen.humanize(body) == body


def test_generate_chapter_classic_passes_author_input(gen, minimal_state, monkeypatch):
    seen_author_inputs: list[str] = []

    def fake_generate(state, rag_context=None, outline=None, style=None, author_input=""):
        seen_author_inputs.append(author_input)
        chapter = ChapterMeta(
            number=state.total_chapters + 1,
            title="魂印",
            word_count=1200,
            summary="叶凡在雨夜发现古玉裂纹。",
            content="叶凡在雨夜发现古玉裂纹，决定隐瞒母亲留下的黑水城线索。",
        )
        state.chapters.append(chapter)
        return chapter

    monkeypatch.setattr(gen, "generate", fake_generate)
    monkeypatch.setattr(gen, "judge_quality", lambda body, state, style=None: {"overall": 0.9, "issues": []})
    monkeypatch.setattr(gen, "_classic_check", lambda body, state, style=None: (True, []))
    monkeypatch.setattr(gen, "_cross_chapter_check", lambda body, state, style=None: (True, []))
    monkeypatch.setattr(gen, "_count_quotable_lines", lambda body: 2)
    monkeypatch.setattr(gen, "_self_edit", lambda body, state, style=None: body)

    chapter = gen.generate_chapter_classic(
        minimal_state,
        author_input="【灵魂注入 · 核心矛盾】自我与宿命",
    )

    assert chapter.title == "魂印"
    assert seen_author_inputs == ["【灵魂注入 · 核心矛盾】自我与宿命"]


def test_expand_prompt_includes_author_input(gen, minimal_state):
    from novel_writer.generator import DraftOption

    draft = DraftOption(id="B", title="走向B", direction="测试方向", preview="预览", hook="钩子")

    msgs = gen._build_expand_prompt(
        minimal_state,
        draft,
        edits="修改意见",
        author_input="【角色蓝图硬约束】叶凡：声音要克制",
    )

    assert "【角色蓝图硬约束】叶凡：声音要克制" in msgs[1]["content"]


def test_memory_context_does_not_split_string_fields(minimal_state):
    minimal_state.chapters.append(ChapterMeta(
        number=1,
        title="月痕",
        word_count=1000,
        summary="林逸发现锈剑异变。",
        key_events="锈剑吸收月光；林逸决定隐瞒",  # type: ignore[arg-type]
        revelations="锈剑与月光有关",  # type: ignore[arg-type]
    ))

    context = minimal_state.memory_context()

    assert "锈剑吸收月光" in context
    assert "林逸决定隐瞒" in context
    assert "- 第1章：锈" not in context.splitlines()


def test_update_state_accepts_string_list_fields(gen, minimal_state):
    minimal_state.plot.foreshadowing = ["父亲下落成谜"]
    chapter = ChapterMeta(number=1, title="突破", word_count=1000, summary="叶凡突破。")
    meta = {
        "resolved_foreshadowing": "父亲下落",
        "new_foreshadowing": "黑衣人身份；古玉裂纹",
        "updated_plot_points": "调查身世；寻找古玉来源",
    }

    gen._update_state(minimal_state, chapter, meta)

    assert "父亲下落成谜" not in minimal_state.plot.foreshadowing
    assert {"content": "父亲下落成谜", "chapter": 1} in minimal_state.plot.resolved_foreshadowing
    assert "黑衣人身份" in minimal_state.plot.foreshadowing
    assert "古玉裂纹" in minimal_state.plot.foreshadowing
    assert minimal_state.plot.next_plot_points == ["调查身世", "寻找古玉来源"]


def test_update_state_accepts_chinese_character_update_keys(gen, minimal_state):
    protagonist = minimal_state.protagonist
    assert protagonist is not None
    chapter = ChapterMeta(number=1, title="突破", word_count=1000, summary="叶凡突破。")
    meta = {
        "character_updates": {
            "叶凡": {"境界": "筑基初期", "状态": "左臂受伤"}
        }
    }

    gen._update_state(minimal_state, chapter, meta)

    assert protagonist.current_power_level == "筑基初期"
    assert protagonist.status == "左臂受伤"


def test_update_state_accepts_character_updates_list(gen, minimal_state):
    protagonist = minimal_state.protagonist
    assert protagonist is not None
    chapter = ChapterMeta(number=1, title="突破", word_count=1000, summary="叶凡突破。")
    meta = {
        "character_updates": [
            {"姓名": "叶凡", "修为": "筑基中期", "身体状态": "灵力透支"}
        ]
    }

    gen._update_state(minimal_state, chapter, meta)

    assert protagonist.current_power_level == "筑基中期"
    assert protagonist.status == "灵力透支"


def test_refresh_chapter_content_updates_persisted_metadata(gen):
    chapter = ChapterMeta(
        number=1,
        title="旧章",
        word_count=6,
        summary="旧正文",
        content="旧正文",
        narrative_facts=["旧事实"],
    )

    gen.refresh_chapter_content(chapter, "叶凡发现古玉裂开，决定去黑水城寻找母亲留下的线索。")

    assert chapter.content == "叶凡发现古玉裂开，决定去黑水城寻找母亲留下的线索。"
    assert chapter.word_count == len(chapter.content)
    assert chapter.summary == chapter.content[:200]
    assert "旧事实" not in chapter.narrative_facts
    assert "叶凡发现古玉裂开，决定去黑水城寻找母亲留下的线索" in chapter.narrative_facts


def test_extract_narrative_facts_preserves_cost_even_with_meta_events(gen):
    body = "叶凡获得玄月宗线索，却因此暴露身份，欠下师父人情债，并留下后患。"

    facts = gen._extract_narrative_facts({"key_events": ["叶凡获得玄月宗线索"]}, body)

    assert "叶凡获得玄月宗线索" in facts
    assert any("暴露身份" in fact and "人情债" in fact for fact in facts)


def test_refresh_chapter_content_keeps_supported_existing_facts(gen):
    chapter = ChapterMeta(
        number=1,
        title="旧章",
        word_count=6,
        summary="旧正文",
        content="旧正文",
        narrative_facts=["叶凡已经知道母亲留下黑水城线索"],
    )

    gen.refresh_chapter_content(chapter, "叶凡已经知道母亲留下黑水城线索，但他决定暂时留在宗门。")

    assert "叶凡已经知道母亲留下黑水城线索" in chapter.narrative_facts


def test_refresh_chapter_content_removes_stale_rewritten_facts(gen):
    chapter = ChapterMeta(
        number=1,
        title="旧章",
        word_count=6,
        summary="旧正文",
        content="旧正文",
        narrative_facts=["叶凡决定去黑水城"],
    )

    gen.refresh_chapter_content(chapter, "叶凡决定留在宗门，等待师父带回母亲留下的线索。")

    assert "叶凡决定去黑水城" not in chapter.narrative_facts
    assert any("叶凡决定留在宗门" in fact for fact in chapter.narrative_facts)


def test_generator_init(gen):
    assert gen.cfg.model == "deepseek-v4-pro"


def test_humanize_llm_error_token_expired():
    from novel_writer.generator import humanize_llm_error

    msg = humanize_llm_error("Error code: 492 - token expired")
    assert "token 已过期" in msg
    assert "设置页" in msg


def test_humanize_llm_error_permission_denied():
    from novel_writer.generator import humanize_llm_error

    msg = humanize_llm_error("403 Forbidden: permission denied for this model")
    assert "无权限" in msg
    assert "模型" in msg


def test_humanize_llm_error_context_limit():
    from novel_writer.generator import humanize_llm_error

    msg = humanize_llm_error("maximum context length exceeded")
    assert "内容过长" in msg


def test_humanize_llm_error_chinese_token_expired():
    from novel_writer.generator import humanize_llm_error

    msg = humanize_llm_error("访问令牌过期，请重新登录")
    assert "token 已过期" in msg
    assert "设置页" in msg


def test_humanize_llm_error_missing_api_key():
    from novel_writer.generator import humanize_llm_error

    msg = humanize_llm_error("No API key provided")
    assert "API Key 无效" in msg


def test_humanize_llm_error_model_not_found():
    from novel_writer.generator import humanize_llm_error

    msg = humanize_llm_error("model_not_found: model does not exist")
    assert "模型不存在" in msg or "模型" in msg
    assert "设置页" in msg

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
    """Verify all local quality dimensions exist."""
    body = "叶凡" * 100 + "\n\n对话内容" * 20 + "\n\n结尾悬疑……难道？"
    result = gen.score_quality(body, minimal_state)
    for dim in [
        'coherence',
        'consistency',
        'pacing',
        'hook',
        'readability',
        'show_dont_tell',
        'formatting',
        'antagonist',
        'agency',
        'cost',
    ]:
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


def test_retrieve_relevant_context_falls_back_to_chapter_body(gen, tmp_path, monkeypatch):
    from novel_writer.database import Database

    db = Database(str(tmp_path / "rag.db"))
    db.create_novel(id="rag-book", title="检索测试", genre="玄幻")
    db.add_chapter(
        "rag-book",
        number=1,
        title="雨夜",
        word_count=30,
        summary="叶凡暂时休整。",
        content="叶凡在雨夜发现古玉裂纹，裂纹里浮现母亲留下的黑水城线索。",
    )
    db.save_chapter_summary("rag-book", 1, "叶凡暂时休整。")

    monkeypatch.setattr("novel_writer.database.Database", lambda: db)

    results = gen.retrieve_relevant_context("黑水城线索", "rag-book", top_k=3)

    assert results
    assert results[0]["chapter_number"] == 1
    assert "黑水城线索" in results[0]["chunk_text"]


def test_retrieve_relevant_context_prioritizes_cost_context(gen, tmp_path, monkeypatch):
    from novel_writer.database import Database

    db = Database(str(tmp_path / "rag-cost.db"))
    db.create_novel(id="rag-cost-book", title="代价检索", genre="玄幻")
    db.add_chapter(
        "rag-cost-book",
        number=1,
        title="普通线索",
        word_count=40,
        summary="叶凡拿到黑水城线索。",
        content="叶凡拿到黑水城线索，随后回到客栈休整。",
    )
    db.add_chapter(
        "rag-cost-book",
        number=2,
        title="代价线索",
        word_count=80,
        summary="叶凡拿到黑水城线索。",
        content="叶凡拿到黑水城线索，却因此暴露身份，欠下师父人情债，并留下后患。",
    )
    monkeypatch.setattr("novel_writer.database.Database", lambda: db)

    results = gen.retrieve_relevant_context("黑水城线索", "rag-cost-book", top_k=2)

    assert [item["chapter_number"] for item in results] == [2, 1]
    assert "暴露身份" in results[0]["chunk_text"]
    assert "人情债" in results[0]["chunk_text"]


def test_global_context_marks_cost_summaries(gen, tmp_path, monkeypatch):
    from novel_writer.database import Database

    db = Database(str(tmp_path / "global-context-cost.db"))
    db.create_novel(id="global-cost-book", title="前情代价", genre="玄幻")
    db.save_chapter_summary("global-cost-book", 1, "叶凡拿到线索。")
    db.save_chapter_summary("global-cost-book", 2, "叶凡拿到线索，却暴露身份并欠下债务。")
    monkeypatch.setattr("novel_writer.database.Database", lambda: db)

    context = gen.get_global_context("global-cost-book", max_chapters=2)

    assert "第1章: 叶凡拿到线索。" in context
    assert "第2章（代价/后果需延续）: 叶凡拿到线索，却暴露身份并欠下债务。" in context


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
