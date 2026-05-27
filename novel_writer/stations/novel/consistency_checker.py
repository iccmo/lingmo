"""
工位：一致性校验
输入：novel_id, chapter_num, content
输出：issues list, confidence score
"""
class ConsistencyChecker:
    name = "consistency_checker"
    required_every_chapter = True

    def run(self, ctx: dict) -> dict:
        novel_id = ctx["novel_id"]
        chapter_num = ctx["chapter_num"]
        db = ctx["db"]
        issues = []

        chars = db.get_character_state(novel_id, chapter_num)
        prev = db.get_character_state(novel_id, chapter_num - 1) if chapter_num > 1 else []
        prev_map = {c["char_name"]: c for c in prev}

        for c in chars:
            name = c["char_name"]
            p = prev_map.get(name)
            if not p: continue
            if p.get("physical_state") == "injured" and c.get("physical_state") == "healthy":
                issues.append({"type": "character", "severity": "error",
                    "description": f"{name}上章受伤本章健康，需说明恢复",
                    "fix": f"添加{name}恢复过程的描述"})
            elif p.get("physical_state") == "healthy" and c.get("physical_state") == "injured":
                issues.append({"type": "character", "severity": "info",
                    "description": f"{name}本章受伤，确认有明确原因"})

        fs = db.get_active_foreshadowing(novel_id)
        for f in fs:
            if f.get("status") == "overdue":
                issues.append({"type": "foreshadowing", "severity": "warning",
                    "description": f"伏笔#{f['id']}已过期",
                    "fix": f"在第{chapter_num+1}章回收或放弃"})
                with db.conn() as c:
                    c.execute("UPDATE foreshadowing_tracker SET status='overdue' WHERE id=? AND status='active'", (f["id"],))

        errors = [i for i in issues if i["severity"] == "error"]
        for i in issues:
            db.log_consistency_issue(novel_id, chapter_num, i["type"], i["severity"], i["description"], i.get("fix", ""))

        confidence = max(0, 100 - len(errors) * 15 - len(issues) * 3)

        return {
            "status": "ok" if not errors else "issues_found",
            "issues": issues,
            "error_count": len(errors),
            "confidence": confidence,
        }
