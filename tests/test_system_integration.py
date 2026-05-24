"""系统集成自检 — 验证核心管线路径"""
import pytest
import json, os

def test_styleprofile_creation():
    """所有24种体裁的StyleProfile都能正常创建"""
    from novel_writer.generator import STYLE_POOL
    assert len(STYLE_POOL) >= 20
    for genre, profile in STYLE_POOL.items():
        assert profile.target_word_count[0] > 0
        assert profile.target_word_count[1] >= profile.target_word_count[0]

def test_writer_voices():
    """所有作家声音都有体裁适配"""
    from novel_writer.generator import WRITER_VOICES
    assert len(WRITER_VOICES) >= 10
    for key, voice in WRITER_VOICES.items():
        assert voice.narrative_distance in ("close", "medium", "omniscient")

def test_genre_to_style_mapping():
    """体裁映射覆盖全部常见输入"""
    from novel_writer.generator import GENRE_TO_STYLE
    assert "玄幻" in GENRE_TO_STYLE
    assert "科幻" in GENRE_TO_STYLE
    assert "悬疑" in GENRE_TO_STYLE
    assert "历史" in GENRE_TO_STYLE
    assert "未知体裁" not in GENRE_TO_STYLE or GENRE_TO_STYLE.get("其他") == "玄幻"

def test_name_generation():
    """命名系统产出合法名字"""
    from novel_writer.generator import random_protagonist_name
    for genre in ["玄幻", "都市", "悬疑", "女频", "武侠"]:
        name, given = random_protagonist_name(genre)
        assert 2 <= len(name) <= 4
        assert 1 <= len(given) <= 3

def test_arc_position():
    """全书节奏定位覆盖所有区间"""
    from novel_writer.generator import Generator
    ctx1 = Generator._arc_position_context(1)
    assert "开篇" in ctx1
    ctx30 = Generator._arc_position_context(30)
    assert "黑暗" in ctx30 or "绝望" in ctx30
    ctx49 = Generator._arc_position_context(49)
    assert "结局" in ctx49

def test_forbidden_derivation():
    """不写什么自动推导"""
    from novel_writer.generator import Generator, StyleProfile
    s = StyleProfile(writer_voice="海明威", thought_system="权力即流变")
    fb = Generator._derive_forbidden(s, "官场")
    assert "禁止" in fb
    assert len(fb) > 50

def test_soul_statement_injection():
    """灵魂声明注入"""
    from novel_writer.generator import Generator, StyleProfile
    s = StyleProfile(soul_statement="我相信每一个选择都有代价")
    result = Generator._soul_statement_injection(s)
    assert "每一个选择都有代价" in result

def test_central_question_injection():
    """核心追问注入 — 含自动推导"""
    from novel_writer.generator import Generator, StyleProfile
    from novel_writer.story_state import StoryState, World, Plot
    s = StyleProfile(thought_system="权力即流变，制度比人可靠")
    st = StoryState('t','t','','','玄幻',World('','','',''),characters=[],plot=Plot('','','o',1))
    result = Generator._central_question_injection(s, st)
    assert "权力" in result or "制度" in result

def test_writer_voice_context():
    """作家声音含体裁适配"""
    from novel_writer.generator import Generator, StyleProfile
    s = StyleProfile(writer_voice="海明威")
    result = Generator._writer_voice_context(s, "玄幻")
    assert "冰山" in result or "古龙" in result or "短句" in result

def test_emotion_budget():
    """情绪预算生成"""
    from novel_writer.generator import Generator, StyleProfile
    from novel_writer.story_state import StoryState, World, Plot
    s = StyleProfile()
    st = StoryState('t','','','','玄幻',World('','','',''),characters=[],plot=Plot('','','o',1))
    result = Generator._emotion_budget_context(st, s)
    assert "焦虑" in result or "开篇" in result
