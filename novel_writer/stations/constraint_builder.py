"""
工位：约束编译
输入：novel_id, next_chapter
输出：constraint_text (50-200字), hard_soft split

v2 增强：从角色标签升级为情节级约束
  - 物理状态连续性（受伤未愈 → 不能用X）
  - 位置追踪（当前在Y城 → 不能突然在Z城）
  - 关系状态演进（X与Y关系从敌对阵→微妙同盟 → 不能突然倒退）
  - 知识一致性（X已知Z的秘密 → 不能表现不知情）
  - 情绪弧卫兵（情绪演化方向标记）
"""
import json, re

class ConstraintBuilder:
    name = "constraint_builder"
    required_every_chapter = True

    def run(self, ctx: dict) -> dict:
        novel_id = ctx["novel_id"]
        next_ch = ctx["chapter_num"]
        db = ctx["db"]

        hard: list[str] = []
        soft: list[str] = []

        # ═══ 静态角色个性（保留） ═══
        novel = db.get_novel(novel_id) or {}
        static_chars = novel.get("characters", [])
        for sc in static_chars:
            if sc.get("name") and sc.get("personality"):
                hard.append(f"{sc['name']}:{sc['personality'][:20]}")

        # ═══ 增强1: 物理状态连续性 ═══
        chars = db.get_character_state(novel_id)
        latest: dict[str, dict] = {}
        for c in chars:
            if c["char_name"] not in latest or c["chapter_num"] > latest[c["char_name"]]["chapter_num"]:
                latest[c["char_name"]] = c

        for name, c in latest.items():
            state = c.get("physical_state", "")
            if state and state != "健康" and state != "healthy":
                loc = f"({c.get('chapter_num','?')}章)" if c.get('chapter_num') else ""
                if "伤" in str(state) or "残" in str(state):
                    part = self._affected_part(state)
                    hard.append(f"{name}{state}{loc}，不能用{part}")
                if "死亡" in str(state) or state == "dead":
                    hard.append(f"{name}已死{loc}，不能出场")
                if "失踪" in str(state) or state == "missing":
                    hard.append(f"{name}失踪{loc}，出现需合理解释")

        # ═══ 增强2: 位置追踪 ═══
        for name, c in latest.items():
            loc = c.get("location", "")
            if loc:
                hard.append(f"{name}在{loc}(Ch{c.get('chapter_num','?')})，不能无故出现在别处")

        # ═══ 增强3: 情绪弧卫兵 ═══
        for name, c in list(latest.items())[-8:]:
            emotion = c.get("emotion", "")
            if emotion:
                # Track recent emotions for this character
                char_emotions = [s.get("emotion", "") for s in chars
                               if s["char_name"] == name and s.get("emotion")]
                if len(char_emotions) >= 3:
                    last_three = char_emotions[-3:]
                    if len(set(last_three)) == 1 and last_three[0] == emotion:
                        soft.append(f"{name}情绪已连续{len(char_emotions)}章'{emotion}'，建议推进")

        # ═══ 增强4: 知识一致性 ═══
        for name, c in list(latest.items())[-5:]:
            knowledge = db.get_knowledge_state(novel_id, name)
            if knowledge:
                key_items = [k for k in knowledge if len(k) > 5][:3]
                if key_items:
                    hard.append(f"{name}已知:{'、'.join(key_items)[:60]}")

        # ═══ 增强5: 关系状态演进 ═══
        rel_changes = db.get_relationship_changes(novel_id)
        recent_rels: dict[str, dict] = {}
        for r in rel_changes:
            key = f"{r['char_name']}↔{r['target']}"
            if r.get("change"):
                recent_rels[key] = r
        for key, r in list(recent_rels.items())[-3:]:
            hard.append(f"{key}:{r['relation']}(Ch{r['chapter_num']})不可倒退")

        # ═══ 伏笔 ═══
        fs = db.get_active_foreshadowing(novel_id)
        overdue = [f for f in fs if f.get("status") == "overdue" or
                   (f.get("due_by_chapter") and int(f.get("due_by_chapter", 0)) <= next_ch)]
        for f in overdue[:2]:
            hard.append(f"伏笔#{f['id']}必须收:{f['description'][:30]}")

        # ═══ 代价 ═══
        costs = db.get_cost_ledger(novel_id)
        gains = len([e for e in costs if e.get("gain")])
        losses = len([e for e in costs if e.get("loss")])
        if gains > losses + 2:
            hard.append("代价严重失衡:本章必须有失去")
        elif gains > losses + 1:
            soft.append("代价略失衡，建议本章加入代价")

        # ═══ 世界观 ═══
        if novel.get("power_system"):
            hard.append(novel["power_system"][:40])

        # ═══ 冰山 ═══
        unsaid = db.get_unsaid(novel_id)
        for u in (unsaid or [])[-3:]:
            hard.append(f"🔒已知但不写:{u['entry'][:40]}")

        # ═══ 世界规则 ═══
        world = db.get_world_state(novel_id)
        for w in [w for w in world if w.get("is_broken")][-2:]:
            hard.append(f"规则{w['rule_name']}已被破坏(Ch{w.get('chapter_num','?')})不可再犯")

        hard_text = "\n".join(hard) if hard else ""
        soft_text = "\n".join(soft) if soft else ""

        return {
            "status": "ok",
            "hard_constraints": hard_text,
            "soft_suggestions": soft_text,
            "hard_count": len(hard),
            "soft_count": len(soft),
        }

    def _affected_part(self, state: str) -> str:
        if "左臂" in str(state): return "左手"
        if "右臂" in str(state): return "右手"
        if "腿" in str(state): return "腿"
        if "眼" in str(state): return "视力"
        if "头" in str(state): return "头部"
        return "受伤部位"
