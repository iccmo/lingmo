"""TEST.md UT-SS-01 ~ UT-SS-11"""
import json

from novel_writer.story_state import ChapterMeta, Plot, StoryState, World


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


def test_total_chapters_uses_latest_chapter_number_for_generation(minimal_state):
    minimal_state.chapters = [
        ChapterMeta(number=1, title="第一章", word_count=1000, summary="一"),
        ChapterMeta(number=3, title="第三章", word_count=1000, summary="三"),
    ]

    assert minimal_state.total_chapters == 3

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


def test_recent_context_and_latest_chapter_use_chapter_numbers(minimal_state):
    minimal_state.chapters = [
        ChapterMeta(number=5, title="第五章", word_count=1000, summary="五", narrative_facts=["第五章事实"]),
        ChapterMeta(number=2, title="第二章", word_count=1000, summary="二", narrative_facts=["第二章事实"]),
        ChapterMeta(number=4, title="第四章", word_count=1000, summary="四", narrative_facts=["第四章事实"]),
    ]

    assert minimal_state.latest_chapter is not None
    assert minimal_state.latest_chapter.number == 5

    recent = minimal_state.recent_context(2)
    assert "第4章" in recent
    assert "第5章" in recent
    assert "第2章" not in recent
    assert recent.index("第4章") < recent.index("第5章")

    memory = minimal_state.memory_context(max_chapters=2)
    assert "第五章事实" in memory
    assert "第四章事实" in memory
    assert "第二章事实" not in memory


def test_memory_context_keeps_opening_anchor_facts_for_long_novels(minimal_state):
    minimal_state.chapters = []
    for number in range(1, 51):
        facts = [f"第{number}章普通事实"]
        if number == 1:
            facts = ["叶凡已经知道母亲留下黑水城线索", "古玉裂纹只能在月光下显形"]
        minimal_state.chapters.append(ChapterMeta(
            number=number,
            title=f"第{number}章",
            word_count=1200,
            summary=f"摘要{number}",
            narrative_facts=facts,
        ))

    memory = minimal_state.memory_context(max_chapters=12, max_items=18)

    assert "叶凡已经知道母亲留下黑水城线索" in memory
    assert "古玉裂纹只能在月光下显形" in memory
    assert "第50章普通事实" in memory
    assert "第49章普通事实" in memory
    assert "第20章普通事实" not in memory
    assert len(memory.splitlines()) <= 18


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
