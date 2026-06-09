"""Pipeline integration tests: generate, score_quality, de_ai, batch_generate, scheduler."""
from unittest.mock import MagicMock, patch

import pytest

from novel_writer.config import Config
from novel_writer.generator import Generator
from novel_writer.story_state import ChapterMeta
from tests.fixtures.sample_state import (
    build_sample_state,
    high_quality_body,
    low_quality_body,
    sample_outline,
    sample_rag_context,
)

# ═══════════════════ Helpers ═══════════════════

def _mock_chat_completion(content: str) -> MagicMock:
    """Build a mock OpenAI ChatCompletion with given content."""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _mock_embedding_response(dim: int = 1536) -> MagicMock:
    """Build a mock embedding response."""
    emb = MagicMock()
    emb.embedding = [0.1] * dim
    data = MagicMock()
    data.data = [emb]
    return data


@pytest.fixture
def gen():
    return Generator(Config())


# ═══════════════════ 1. generate() single call ═══════════════════

def test_generate_returns_chapter_meta(gen):
    """generate() returns ChapterMeta with title, content, word_count."""
    state = build_sample_state(0)  # no existing chapters
    mock_body = "第1章 觉醒\n\n天雷滚滚，叶凡睁开双眼。他感受着体内澎湃的灵力...（省略2000字）"

    with patch.object(gen, '_call_llm_with_retry', return_value=mock_body):
        chapter = gen.generate(state)

    assert isinstance(chapter, ChapterMeta)
    assert chapter.number == 1
    assert chapter.word_count == len("天雷滚滚，叶凡睁开双眼。他感受着体内澎湃的灵力...（省略2000字）")
    assert chapter.content == "天雷滚滚，叶凡睁开双眼。他感受着体内澎湃的灵力...（省略2000字）"
    assert len(chapter.title) > 0


def test_generate_parses_markdown_format(gen):
    """generate() correctly parses Markdown-formatted LLM response."""
    state = build_sample_state(0)
    raw = """## 标题
锈剑觉醒

## 正文
林逸站在演武场上，手中锈剑微微颤抖。他深吸一口气——
剑出！一道剑气划破长空，将对面林浩轰下擂台。
全场哗然。

## 元数据
```json
{"summary": "林逸比武获胜", "key_events": ["锈剑觉醒"], "ending_hook": "远处，林啸天眼中闪过寒光"}
```"""

    with patch.object(gen, '_call_llm_with_retry', return_value=raw):
        chapter = gen.generate(state)

    assert "锈剑觉醒" in chapter.title
    assert chapter.word_count > 50  # mock text is short
    assert "林逸" in chapter.content
    assert "林啸天眼中闪过寒光" in chapter.ending_hook


# ═══════════════════ 2. _build_prompt outline injection ═══════════════════

def test_build_prompt_injects_outline(gen):
    """Outline items appear in system prompt under ## 章节大纲."""
    state = build_sample_state(1)
    outline = sample_outline()

    msgs = gen._build_prompt(state, outline=outline)
    system = msgs[0]["content"]

    assert "## 章节大纲" in system
    assert "第六章：剑意对决" in system
    assert "柳青烟正式收林逸为徒" in system


def test_build_prompt_no_outline(gen):
    """Without outline, no ## 章节大纲 header."""
    state = build_sample_state(1)
    msgs = gen._build_prompt(state)
    system = msgs[0]["content"]
    assert "## 章节大纲" not in system


# ═══════════════════ 3. _build_prompt RAG injection ═══════════════════

def test_build_prompt_injects_rag(gen):
    """RAG context appears in system prompt under ## 相关历史剧情."""
    state = build_sample_state(3)
    rag = sample_rag_context()

    msgs = gen._build_prompt(state, rag_context=rag)
    system = msgs[0]["content"]

    assert "## 相关历史剧情" in system
    assert "后山禁地" in system  # from chunk_text


def test_build_prompt_no_rag(gen):
    """Without RAG, no ## 相关历史剧情 header."""
    state = build_sample_state(1)
    msgs = gen._build_prompt(state)
    system = msgs[0]["content"]
    assert "## 相关历史剧情" not in system


def test_build_prompt_injects_long_term_memory(gen):
    """Narrative facts from earlier chapters become hard continuity constraints."""
    state = build_sample_state(1)
    state.chapters[0].narrative_facts = ["林逸已经知道锈剑会吸收月光", "柳青烟欠林逸一次人情"]

    msgs = gen._build_prompt(state)
    system = msgs[0]["content"]

    assert "## 长期事实账本" in system
    assert "锈剑会吸收月光" in system
    assert "不能遗忘" in system


def test_generate_extracts_narrative_facts_from_metadata(gen):
    """generate() stores continuity facts for the next chapter without another LLM call."""
    state = build_sample_state(0)
    raw = """## 标题
月下锈剑

## 正文
林逸发现锈剑会吸收月光。他决定隐瞒这件事。

## 元数据
```json
{"summary": "林逸发现锈剑异变", "key_events": ["锈剑吸收月光"], "revelations": ["锈剑与月光有关"], "narrative_facts": ["林逸已经知道锈剑会吸收月光"], "ending_hook": "剑身浮出一个陌生名字"}
```"""

    with patch.object(gen, '_call_llm_with_retry', return_value=raw):
        chapter = gen.generate(state)

    assert "林逸已经知道锈剑会吸收月光" in chapter.narrative_facts


def test_generate_normalizes_string_metadata_lists(gen):
    """LLMs sometimes return semicolon-delimited strings instead of arrays."""
    state = build_sample_state(0)
    raw = """## 标题
月痕

## 正文
林逸发现锈剑会吸收月光。

## 元数据
```json
{"summary": "林逸发现锈剑异变", "key_events": "锈剑吸收月光；林逸决定隐瞒", "revelations": "锈剑与月光有关", "ending_hook": "剑身浮出一个陌生名字"}
```"""

    with patch.object(gen, '_call_llm_with_retry', return_value=raw):
        chapter = gen.generate(state)

    assert chapter.key_events == ["锈剑吸收月光", "林逸决定隐瞒"]
    assert chapter.revelations == ["锈剑与月光有关"]
    assert "锈剑吸收月光" in chapter.narrative_facts


# ═══════════════════ 4. score_quality 五维评分 ═══════════════════

def test_score_quality_high(gen):
    """High-quality text scores >= 0.5 and passes."""
    state = build_sample_state(3)
    body = high_quality_body()

    result = gen.score_quality(body, state)

    assert 'overall' in result
    assert 'scores' in result
    assert 'grade' in result
    assert 'issues' in result
    assert len(result['scores']) == 10
    assert result['overall'] >= 0.5, f"Expected >= 0.5, got {result['overall']}"
    assert result['passed'] is True


def test_score_quality_low(gen):
    """Low-quality text scores < 0.5 and has issues."""
    state = build_sample_state(3)
    body = low_quality_body()

    result = gen.score_quality(body, state)

    assert result['overall'] < 0.5, f"Expected < 0.5, got {result['overall']}"
    assert result['passed'] is False
    assert len(result['issues']) > 0


def test_score_quality_consistency_checks_protagonist(gen):
    """Protagonist absence lowers consistency score."""
    state = build_sample_state(3)
    # Text that does NOT mention the protagonist "林逸"
    body = "在一片古老的森林中，妖兽横行。一位无名旅人艰难地穿越着密林。阳光透过树叶洒下斑驳的光影。"

    result = gen.score_quality(body, state)
    assert result['scores']['consistency'] < 0.5  # protagonist not found
    assert any("林逸" in issue for issue in result['issues'])


def test_score_quality_rewards_agency_and_cost(gen):
    state = build_sample_state(3)
    body = """
林逸站在演武场中央，林浩逼他交出锈剑。

"交出来，你还能活。"

林逸握紧锈剑，选择守住演武场。他知道这会暴露剑骨，也知道林家长老会因此追杀他。

他主动踏前一步，宁可押上前途，也不再逃。

剑光落下，林浩败退。可林逸的掌心裂开，鲜血顺着剑柄流下。突破带来反噬，也让他欠下剑尘一个无法偿还的债。

远处，林啸天冷冷抬眼。

这意味着，从今夜开始，他再也不能回头。
"""

    result = gen.score_quality(body, state)

    assert result["scores"]["agency"] >= 0.7
    assert result["scores"]["cost"] >= 0.7


def test_score_quality_penalizes_gain_without_choice_or_cost(gen):
    state = build_sample_state(3)
    body = """
林逸来到山洞。

一道光落下来，他获得了上古传承，成功突破，赢得所有人的称赞。

系统奖励了法宝和丹药。

众人都很高兴。

第二天，他继续前进。
"""

    result = gen.score_quality(body, state)

    assert result["scores"]["agency"] < 0.5
    assert result["scores"]["cost"] < 0.5
    assert any("主动选择" in issue for issue in result["issues"])
    assert any("缺少代价" in issue for issue in result["issues"])


# ═══════════════════ 5. de_ai post-processing ═══════════════════

def test_de_ai_removes_patterns(gen):
    """de_ai removes AI cliché phrases and reports changes."""
    body = "在这个世界里，修炼者需要不断突破。随着时间之推移，他越来越强。不仅如此，他还掌握了剑意。总的来说，这是一个强者的故事。"

    cleaned, changes = gen.de_ai(body)

    assert changes > 0
    assert "在这个世界里" not in cleaned
    assert "随着时间推移" not in cleaned
    assert "不仅如此" not in cleaned
    assert len(cleaned) < len(body) or cleaned != body  # something changed


def test_de_ai_clean_text_unchanged(gen):
    """de_ai should not substantially alter clean narrative text."""
    body = high_quality_body()

    cleaned, changes = gen.de_ai(body)

    # Clean text may have minor pattern matches but should not be destroyed
    assert len(cleaned) >= len(body) * 0.9  # at most 10% removed


# ═══════════════════ 6. batch_generate best-of-k ═══════════════════

def test_batch_generate_picks_best(gen):
    """batch_generate returns the chapter with highest quality score."""
    state = build_sample_state(0)

    # Create two chapters with different quality
    ch1 = ChapterMeta(number=1, title="Version A", word_count=2500,
                      summary="A", content="A" * 2500)
    ch2 = ChapterMeta(number=1, title="Version B", word_count=2600,
                      summary="B", content="B" * 2600)

    # Quality scores: B > A
    q1 = {'overall': 0.55, 'scores': {}, 'grade': 'C', 'passed': True, 'issues': [], 'word_count': 2500}
    q2 = {'overall': 0.82, 'scores': {}, 'grade': 'A', 'passed': True, 'issues': [], 'word_count': 2600}

    with patch.object(gen, 'generate', side_effect=[ch1, ch2]):
        with patch.object(gen, 'score_quality', side_effect=[q1, q2]):
            best_ch, best_q = gen.batch_generate(state, n=2)

    assert best_ch.title == "Version B"
    assert best_q['overall'] == 0.82
    assert best_q['grade'] == 'A'


def test_batch_generate_commits_only_best_candidate_state(gen):
    """Rejected candidates must not mutate plot/character state for later chapters."""
    state = build_sample_state(0)
    state.plot.next_plot_points = ["原始目标"]
    low_quality_raw = """## 标题
低分候选

## 正文
林逸误入歧路。

## 元数据
```json
{"summary":"低分候选","updated_plot_points":["错误目标"],"key_events":["误入歧路"]}
```"""
    high_quality_raw = """## 标题
高分候选

## 正文
林逸握紧锈剑，选择守住演武场。

## 元数据
```json
{"summary":"高分候选","updated_plot_points":["守住演武场"],"key_events":["守住演武场"]}
```"""
    q1 = {'overall': 0.45, 'scores': {}, 'grade': 'D', 'passed': False, 'issues': [], 'word_count': 20}
    q2 = {'overall': 0.88, 'scores': {}, 'grade': 'A', 'passed': True, 'issues': [], 'word_count': 20}

    with patch.object(gen, '_call_llm_with_retry', side_effect=[low_quality_raw, high_quality_raw]):
        with patch.object(gen, 'score_quality', side_effect=[q1, q2]):
            best_ch, best_q = gen.batch_generate(state, n=2)

    assert best_ch.title == "高分候选"
    assert best_q["overall"] == 0.88
    assert state.plot.next_plot_points == ["守住演武场"]


def test_batch_generate_varying_temperature(gen):
    """batch_generate uses different temperatures for diversity."""
    state = build_sample_state(0)
    original_temp = gen.cfg.temperature

    ch = ChapterMeta(number=1, title="Test", word_count=2500,
                     summary="ok", content="ok" * 2500)
    q = {'overall': 0.7, 'scores': {}, 'grade': 'B', 'passed': True, 'issues': [], 'word_count': 2500}

    temps_used = []
    original_generate = gen.generate

    def track_temp(*args, **kwargs):
        temps_used.append(gen.cfg.temperature)
        return ch

    with patch.object(gen, 'generate', side_effect=track_temp):
        with patch.object(gen, 'score_quality', return_value=q):
            gen.batch_generate(state, n=2)

    # Temperature should have been modified and then restored
    assert gen.cfg.temperature == original_temp
    assert len(temps_used) == 2
    # Two temperatures should differ (one around base-0.05, one around base+0.05)
    assert temps_used[0] != temps_used[1]


# ═══════════════════ 7. scheduler.run_once pipeline ═══════════════════

@patch('novel_writer.scheduler.Database')
def test_scheduler_run_once_full_pipeline(_mock_db_cls):
    """scheduler.run_once calls generate, score_quality, de_ai, store_chapter_embedding."""
    from novel_writer.config import Config as Cfg
    from novel_writer.scheduler import Scheduler

    sched = Scheduler(Cfg())
    _mock_db_cls.return_value = sched.db

    ch = ChapterMeta(number=1, title="Test", word_count=2600,
                     summary="summary", content="body" * 600,
                     key_events=[], revelations=[], ending_hook="hook?")
    quality = {'overall': 0.72, 'scores': {}, 'grade': 'B', 'passed': True, 'issues': [], 'word_count': 2600}

    with patch.object(sched.db, 'get_novel', return_value={
        'id': 'test', 'title': 'test', 'author': 'AI', 'genre': '玄幻',
        'synopsis': '', 'world_name': '', 'world_era': '', 'world_geo': '',
        'power_system': '', 'main_arc': '', 'current_arc': '开篇',
        'arc_chapter_start': 1, 'characters': [], 'chapters': [],
    }):
        with patch.object(sched.db, 'get_provider', return_value={'api_key': 'sk-test', 'base_url': '', 'models': ['gpt-4o']}):
            with patch.object(sched.db, 'add_chapter', return_value=1) as mock_add:
                with patch.object(sched.db, 'log'):
                    with patch.object(sched.db, 'record_scheduler_run'):
                        with patch.object(sched.db, 'conn'):
                            with patch('novel_writer.generator.Generator') as MockGen:
                                mock_gen = MockGen.return_value
                                mock_gen.batch_generate.return_value = (ch, quality)
                                mock_gen.score_quality.return_value = quality
                                mock_gen.de_ai.return_value = ("de_ai_body", 5)
                                mock_gen.retrieve_relevant_context.return_value = []
                                mock_gen.store_chapter_embedding.return_value = None

                                result = sched.run_once('test')

    assert 'success' in result
    mock_gen.batch_generate.assert_called_once()
    mock_gen.de_ai.assert_called_once()
    mock_gen.store_chapter_embedding.assert_called_once()
    mock_add.assert_called_once()
    # Verify content is de-AI'd
    call_kwargs = mock_add.call_args[1]
    assert call_kwargs['content'] == 'de_ai_body'
    assert call_kwargs['quality_score'] == 0.72
    assert mock_gen.store_chapter_embedding.call_args.args[2] == 'de_ai_body'
    mock_gen.score_quality.assert_called_once()
    assert mock_gen.score_quality.call_args.args[0] == 'de_ai_body'


@patch('novel_writer.scheduler.Database')
def test_scheduler_run_once_retry_on_low_quality(_mock_db_cls):
    """scheduler.run_once retries batch_generate when quality < 0.5."""
    from novel_writer.config import Config as Cfg
    from novel_writer.scheduler import Scheduler

    sched = Scheduler(Cfg())
    _mock_db_cls.return_value = sched.db

    ch_low = ChapterMeta(number=1, title="Low", word_count=1200,
                         summary="bad", content="x" * 500)
    ch_good = ChapterMeta(number=1, title="Good", word_count=2600,
                          summary="good", content="body" * 650)
    q_low = {'overall': 0.30, 'scores': {}, 'grade': 'D', 'passed': False,
             'issues': ['字数不足'], 'word_count': 1200}
    q_good = {'overall': 0.75, 'scores': {}, 'grade': 'B', 'passed': True,
              'issues': [], 'word_count': 2600}

    with patch.object(sched.db, 'get_novel', return_value={
        'id': 'test', 'title': 'test', 'author': 'AI', 'genre': '玄幻',
        'synopsis': '', 'world_name': '', 'world_era': '', 'world_geo': '',
        'power_system': '', 'main_arc': '', 'current_arc': '开篇',
        'arc_chapter_start': 1, 'characters': [], 'chapters': [],
    }):
        with patch.object(sched.db, 'get_provider', return_value={'api_key': 'sk-test', 'base_url': '', 'models': ['gpt-4o']}):
            with patch.object(sched.db, 'add_chapter', return_value=1):
                with patch.object(sched.db, 'log'):
                    with patch.object(sched.db, 'record_scheduler_run'):
                        with patch.object(sched.db, 'conn'):
                            with patch('novel_writer.generator.Generator') as MockGen:
                                mock_gen = MockGen.return_value
                                # First call low quality, retry returns good
                                mock_gen.batch_generate.side_effect = [(ch_low, q_low), (ch_good, q_good)]
                                mock_gen.de_ai.return_value = ("body", 0)
                                mock_gen.retrieve_relevant_context.return_value = []
                                mock_gen.store_chapter_embedding.return_value = None

                                result = sched.run_once('test')

    assert 'success' in result
    # batch_generate called twice: initial + 1 retry
    assert mock_gen.batch_generate.call_count == 2


@patch('novel_writer.scheduler.Database')
def test_scheduler_run_once_rejects_explanation_without_saving(_mock_db_cls):
    """scheduler.run_once should not persist non-prose model output."""
    from novel_writer.config import Config as Cfg
    from novel_writer.scheduler import Scheduler

    sched = Scheduler(Cfg())
    _mock_db_cls.return_value = sched.db

    body = "以下是本章正文：\n\n我会加强主角主动性，并加入更多冲突。"
    ch = ChapterMeta(number=1, title="Bad", word_count=len(body), summary="", content=body)
    quality = {'overall': 0.72, 'scores': {}, 'grade': 'B', 'passed': True, 'issues': [], 'word_count': len(body)}

    with patch.object(sched.db, 'get_novel', return_value={
        'id': 'test', 'title': 'test', 'author': 'AI', 'genre': '玄幻',
        'synopsis': '', 'world_name': '', 'world_era': '', 'world_geo': '',
        'power_system': '', 'main_arc': '', 'current_arc': '开篇',
        'arc_chapter_start': 1, 'characters': [], 'chapters': [],
    }):
        with patch.object(sched.db, 'get_provider', return_value={'api_key': 'sk-test', 'base_url': '', 'models': ['gpt-4o']}):
            with patch.object(sched.db, 'add_chapter', return_value=1) as mock_add:
                with patch.object(sched.db, 'log'):
                    with patch.object(sched.db, 'record_scheduler_run') as mock_record:
                        with patch.object(sched.db, 'conn'):
                            with patch('novel_writer.generator.Generator') as MockGen:
                                mock_gen = MockGen.return_value
                                mock_gen.batch_generate.return_value = (ch, quality)
                                mock_gen.score_quality.return_value = quality
                                mock_gen.de_ai.return_value = (body, 0)
                                mock_gen.retrieve_relevant_context.return_value = []
                                mock_gen.store_chapter_embedding.return_value = None

                                result = sched.run_once('test')

    assert result.startswith("failed:")
    mock_add.assert_not_called()
    mock_record.assert_called_once_with('test', 'failed')


@patch('novel_writer.scheduler.Database')
def test_scheduler_run_once_loads_story_state_continuity(_mock_db_cls):
    """scheduler.run_once should inject persisted foreshadowing and plot targets."""
    from novel_writer.config import Config as Cfg
    from novel_writer.scheduler import Scheduler

    sched = Scheduler(Cfg())
    _mock_db_cls.return_value = sched.db

    ch = ChapterMeta(number=1, title="Test", word_count=2600, summary="summary", content="body" * 600)
    quality = {'overall': 0.72, 'scores': {}, 'grade': 'B', 'passed': True, 'issues': [], 'word_count': 2600}

    with patch.object(sched.db, 'get_novel', return_value={
        'id': 'test', 'title': 'test', 'author': 'AI', 'genre': '玄幻',
        'synopsis': '', 'world_name': '', 'world_era': '', 'world_geo': '',
        'power_system': '', 'main_arc': '', 'current_arc': '开篇',
        'arc_chapter_start': 1, 'characters': [], 'chapters': [],
        'plot_points': [
            {'type': 'plot', 'content': '调查铜镜来源', 'is_resolved': 0},
            {'type': 'plot', 'content': '已完成旧目标', 'is_resolved': 1},
            {'type': 'foreshadowing', 'content': '不是剧情目标', 'is_resolved': 0},
        ],
    }):
        with patch.object(sched.db, 'get_all_foreshadowing', return_value=[
            {'description': '青铜铃会在月圆夜响起', 'status': 'active'},
            {'description': '镜中人知道真相', 'status': 'overdue'},
            {'description': '已回收旧伏笔', 'status': 'resolved'},
        ]):
            with patch.object(sched.db, 'get_provider', return_value={'api_key': 'sk-test', 'base_url': '', 'models': ['gpt-4o']}):
                with patch.object(sched.db, 'add_chapter', return_value=1):
                    with patch.object(sched.db, 'log'):
                        with patch.object(sched.db, 'record_scheduler_run'):
                            with patch.object(sched.db, 'conn'):
                                with patch('novel_writer.generator.Generator') as MockGen:
                                    mock_gen = MockGen.return_value
                                    mock_gen.batch_generate.return_value = (ch, quality)
                                    mock_gen.score_quality.return_value = quality
                                    mock_gen.de_ai.return_value = ("de_ai_body", 0)
                                    mock_gen.retrieve_relevant_context.return_value = []
                                    mock_gen.store_chapter_embedding.return_value = None

                                    result = sched.run_once('test')

    assert 'success' in result
    state = mock_gen.batch_generate.call_args.args[0]
    assert state.plot.foreshadowing == ["青铜铃会在月圆夜响起", "镜中人知道真相"]
    assert state.plot.next_plot_points == ["调查铜镜来源"]


@patch('novel_writer.scheduler.Database')
def test_scheduler_run_once_syncs_story_state_updates(_mock_db_cls):
    """scheduler.run_once should persist generated plot/foreshadowing state updates."""
    from novel_writer.config import Config as Cfg
    from novel_writer.scheduler import Scheduler

    sched = Scheduler(Cfg())
    _mock_db_cls.return_value = sched.db

    ch = ChapterMeta(number=3, title="Test", word_count=2600, summary="summary", content="body" * 600)
    quality = {'overall': 0.72, 'scores': {}, 'grade': 'B', 'passed': True, 'issues': [], 'word_count': 2600}

    with patch.object(sched.db, 'get_novel', return_value={
        'id': 'test', 'title': 'test', 'author': 'AI', 'genre': '玄幻',
        'synopsis': '', 'world_name': '', 'world_era': '', 'world_geo': '',
        'power_system': '', 'main_arc': '', 'current_arc': '开篇',
        'arc_chapter_start': 1, 'characters': [], 'chapters': [],
        'plot_points': [],
    }):
        with patch.object(sched.db, 'get_all_foreshadowing', return_value=[]):
            with patch.object(sched.db, 'get_provider', return_value={'api_key': 'sk-test', 'base_url': '', 'models': ['gpt-4o']}):
                with patch.object(sched.db, 'add_chapter', return_value=1):
                    with patch.object(sched.db, 'log'):
                        with patch.object(sched.db, 'record_scheduler_run'):
                            with patch.object(sched.db, 'conn'):
                                with patch('novel_writer.generator.Generator') as MockGen:
                                    mock_gen = MockGen.return_value

                                    def batch_generate(state, n, rag_context=None, outline=None):
                                        state.plot.next_plot_points = ["寻找失踪证人"]
                                        state.plot.resolved_foreshadowing.append({"content": "青铜铃响起", "chapter": 3})
                                        return ch, quality

                                    mock_gen.batch_generate.side_effect = batch_generate
                                    mock_gen.score_quality.return_value = quality
                                    mock_gen.de_ai.return_value = ("de_ai_body", 0)
                                    mock_gen.retrieve_relevant_context.return_value = []
                                    mock_gen.store_chapter_embedding.return_value = None

                                    with patch('novel_writer.scheduler._sync_next_plot_points') as sync_plot:
                                        with patch('novel_writer.scheduler._sync_resolved_foreshadowing') as sync_fs:
                                            result = sched.run_once('test')

    assert 'success' in result
    sync_plot.assert_called_once()
    sync_fs.assert_called_once()
    assert sync_fs.call_args.args[3] == 3
