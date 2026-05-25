"""
工位：约束编译
输入：novel_id, next_chapter
输出：constraint_text (50-200字), hard_soft split
"""
import json, re

class ConstraintBuilder:
    name = "constraint_builder"
    required_every_chapter = True

    def run(self, ctx: dict) -> dict:
        novel_id = ctx["novel_id"]
        next_ch = ctx["chapter_num"]
        db = ctx["db"]

        hard = []  # 必须遵守
        soft = []  # 建议遵守

        # ── 硬约束：角色状态 ──
        novel = db.get_novel(novel_id) or {}
        static_chars = novel.get("characters", [])
        chars = db.get_character_state(novel_id)
        latest = {}
        for c in chars:
            latest[c["char_name"]] = c

        for name, c in list(latest.items())[-8:]:
            state = c.get("physical_state", "")
            if state and state != "健康":
                if "伤" in str(state) or "残" in str(state):
                    hard.append(f"{name}不能用{self._affected_part(state)}")
                if state == "死亡":
                    hard.append(f"{name}已死，不能出场")
            if c.get("emotion") == "愤怒":
                hard.append(f"{name}不会示弱")

        # Static character traits
        for sc in static_chars:
            if sc.get("name") and sc.get("personality"):
                hard.append(f"{sc['name']}:{sc['personality'][:20]}")

        # ── 硬约束：伏笔 ──
        fs = db.get_active_foreshadowing(novel_id)
        overdue = [f for f in fs if f.get("status") == "overdue" or
                   (f.get("due_by_chapter") and int(f.get("due_by_chapter", 0)) <= next_ch)]
        for f in overdue[:2]:
            hard.append(f"伏笔#{f['id']}必须收:{f['description'][:30]}")

        # ── 硬约束：代价 ──
        costs = db.get_cost_ledger(novel_id)
        gains = len([e for e in costs if e.get("gain")])
        losses = len([e for e in costs if e.get("loss")])
        if gains > losses + 1:
            hard.append("代价失衡:本章必须有一次失去")

        # ── 硬约束：世界观 ──
        if novel.get("power_system"):
            hard.append(novel["power_system"][:40])

        # ── 软约束：关系线 ──
        tl = db.get_timeline(novel_id)
        if len(tl) > 3:
            relay = len([c for c in chars if c.get("emotion")]) / max(1, len(tl))
            if relay < 0.2:
                soft.append("关系线停滞，建议推进")

        # ── 冰山 ──
        unsaid = db.get_unsaid(novel_id)
        for u in (unsaid or [])[-3:]:
            hard.append(f"🔒已知但不写:{u['entry'][:40]}")

        # ── 世界规则 ──
        world = db.get_world_state(novel_id)
        for w in [w for w in world if w.get("is_broken")][-2:]:
            hard.append(f"规则{w['rule_name']}不可再破坏")

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
        return "受伤部位"
