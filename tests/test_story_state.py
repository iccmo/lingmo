"""TEST.md UT-SS-01 ~ UT-SS-11"""
import json
import pytest
from novel_writer.story_state import StateManager, StoryState, World, Plot, Character, ChapterMeta

def test_save_and_load(state_manager, minimal_state):
    """UT-SS-01: Save and load State"""
    state_manager.save(minimal_state)
    loaded = state_manager.load("test-book")
    assert loaded is not None
    assert loaded.title == "测试之书"
    assert loaded.world.power_system == "练气→筑基→金丹"

def test_load_nonexistent(state_manager):
    """UT-SS-03: Load nonexistent returns None"""
    assert state_manager.load("nonexistent") is None

def test_add_chapter(state_manager, minimal_state):
    """UT-SS-04: Append chapter"""
    state_manager.save(minimal_state)
    ch = ChapterMeta(number=1, title="第一章", word_count=2500, summary="测试")
    state_manager.add_chapter(minimal_state, ch)
    assert minimal_state.total_chapters == 1
    loaded = state_manager.load("test-book")
    assert loaded.total_chapters == 1

def test_recent_context(state_manager, minimal_state):
    """UT-SS-05: recent_context returns last N summaries"""
    for i in range(1, 7):
        minimal_state.chapters.append(ChapterMeta(
            number=i, title=f"Ch{i}", word_count=2000,
            summary=f"摘要{i}", ending_hook=f"钩子{i}",
        ))
    ctx = minimal_state.recent_context(3)
    assert "摘要4" in ctx or "Ch4" in ctx
    assert "摘要6" in ctx or "Ch6" in ctx

def test_character_context(minimal_state):
    """UT-SS-06: character_context includes all characters"""
    ctx = minimal_state.character_context()
    assert "叶凡" in ctx
    assert "练气三层" in ctx

def test_list_novels(state_manager, minimal_state):
    """UT-SS-07: List all novels"""
    state_manager.save(minimal_state)
    # Create second novel
    s2 = StoryState(novel_id="book2", title="第二本", author="AI", synopsis="", genre="玄幻",
                     world=World(name="", era="", geography="", power_system=""),
                     characters=[], plot=Plot(premise="", main_arc="", current_arc="开篇"))
    state_manager.save(s2)
    ids = state_manager.list_novels()
    assert "test-book" in ids
    assert "book2" in ids

def test_delete_novel(state_manager, minimal_state):
    """UT-SS-08: Delete novel"""
    state_manager.save(minimal_state)
    state_manager.delete_novel("test-book")
    assert state_manager.load("test-book") is None

def test_roundtrip(minimal_state):
    """UT-SS-10: to_dict/from_dict roundtrip"""
    d = minimal_state.to_dict()
    restored = StoryState.from_dict(d)
    assert restored.title == minimal_state.title
    assert restored.world.name == minimal_state.world.name
    assert restored.characters[0].name == "叶凡"

def test_atomic_write(state_manager, minimal_state, tmp_path):
    """UT-SS-09: Atomic write - file not corrupted"""
    state_manager.save(minimal_state)
    # File should exist and be valid JSON
    path = state_manager.novel_path("test-book")
    with open(path) as f:
        data = json.load(f)
    assert data["title"] == "测试之书"

def test_protagonist(minimal_state):
    """Protagonist helper"""
    assert minimal_state.protagonist is not None
    assert minimal_state.protagonist.name == "叶凡"
