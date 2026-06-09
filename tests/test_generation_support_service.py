from novel_writer.database import Database
from novel_writer.routers import deps
from novel_writer.routers.novel.generation_support_service import build_constraints, build_creation_brief
from novel_writer.state import GenerationState


def test_build_constraints_detects_dormant_characters_by_chapter_recency(tmp_path):
    db = Database(str(tmp_path / "constraints.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="出场节奏")
        with db.conn() as conn:
            for char_key, name, role in [
                ("protagonist", "叶凡", "主角"),
                ("mentor", "师父", "导师"),
                ("ally", "小红", "配角"),
                ("scout", "阿七", "配角"),
                ("guard", "阿九", "配角"),
                ("villain", "黑衣人", "反派"),
                ("dormant", "柳青烟", "配角"),
            ]:
                conn.execute(
                    """INSERT INTO characters
                       (novel_id, char_key, name, role, personality, background, power_level, secrets)
                       VALUES (?, ?, ?, ?, '', '', '', '[]')""",
                    ("book", char_key, name, role),
                )

        db.save_character_state("book", 1, "柳青烟")
        db.save_character_state("book", 2, "叶凡")
        db.save_character_state("book", 3, "师父")
        db.save_character_state("book", 4, "小红")
        db.save_character_state("book", 5, "阿七")
        db.save_character_state("book", 6, "阿九")
        db.save_character_state("book", 7, "黑衣人")
        for chapter_num, name in enumerate(
            ["B路人", "C路人", "D路人", "E路人", "F路人", "G路人", "H路人", "I路人"],
            start=2,
        ):
            db.save_character_state("book", chapter_num, name)
        db.save_character_state("book", 7, "A_recent", physical_state="重伤")

        constraints = build_constraints("book", next_chapter=8)

        assert "A_recent - 重伤" in constraints
        assert "久未出场" in constraints
        assert "柳青烟" in constraints
        assert "黑衣人" not in constraints.split("久未出场", 1)[1]
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_build_constraints_includes_overdue_foreshadowing(tmp_path):
    db = Database(str(tmp_path / "overdue.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="伏笔回收")
        db.save_foreshadowing("book", 1, "青铜铃会在月圆夜响起", due_by=3)
        thread = db.get_active_foreshadowing("book")[0]
        with db.conn() as conn:
            conn.execute(
                "UPDATE foreshadowing_tracker SET status='overdue' WHERE id=?",
                (thread["id"],),
            )

        constraints = build_constraints("book", next_chapter=4)

        assert "伏笔需在本章回收" in constraints
        assert "青铜铃会在月圆夜响起" in constraints
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_build_constraints_tolerates_dirty_foreshadowing_due_by(tmp_path):
    db = Database(str(tmp_path / "dirty-due.db"))
    old_db = deps._db
    old_gen_state = deps._gen_state
    try:
        deps.init_deps(db, GenerationState())
        db.create_novel(id="book", title="脏伏笔")
        db.save_foreshadowing("book", 1, "木匣里的信没有拆开", due_by=None)
        thread = db.get_active_foreshadowing("book")[0]
        with db.conn() as conn:
            conn.execute(
                "UPDATE foreshadowing_tracker SET due_by_chapter=? WHERE id=?",
                ("第十章左右", thread["id"]),
            )

        constraints = build_constraints("book", next_chapter=4)

        assert "活跃伏笔" in constraints
        assert "自由创作" not in constraints
    finally:
        deps._db = old_db
        deps._gen_state = old_gen_state


def test_build_creation_brief_includes_soul_and_character_blueprints(tmp_path):
    db = Database(str(tmp_path / "creation-brief.db"))
    db.create_novel(id="book", title="创作设定")
    db.save_soul_fingerprint("book", "freedom-fate", 7, "自由选择本身会揭露命运")
    db.save_character_blueprints(
        "book",
        [
            {
                "id": "hero",
                "name": "叶凡",
                "role": "主角",
                "entrance": "雨夜抱着裂开的玉佩进城",
                "signature": "左手总握紧玉佩",
                "coreWound": "父亲失踪",
                "voiceSample": "我自己选，也自己扛。",
            }
        ],
    )

    brief = build_creation_brief(db, "book")

    assert "灵魂注入" in brief
    assert "自由vs命运" in brief
    assert "自由选择本身会揭露命运" in brief
    assert "角色蓝图硬约束" in brief
    assert "叶凡（主角）" in brief
    assert "父亲失踪" in brief
    assert "我自己选，也自己扛。" in brief
