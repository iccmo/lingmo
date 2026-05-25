"""
灵墨 Brain Agent — 编辑部主任。
不是装配线，是按需调度各工位。

Pi 方法论：
- 每个工位独立模块（Pi 扩展系统）
- Brain 按章状态决定调度哪些工位（Pi Agent Loop）
- 工位输出可验证、可重试（Pi 工具生命周期）
"""
from typing import Any
from .stations.constraint_builder import ConstraintBuilder
from .stations.consistency_checker import ConsistencyChecker
from .stations.deslop_filter import DeslopFilter


class BrainAgent:
    """编辑部主任：看稿子状态 → 决定调谁 → 调度 → 验收入库"""

    def __init__(self, db):
        self.db = db
        self.constraint_builder = ConstraintBuilder()
        self.consistency_checker = ConsistencyChecker()
        self.deslop_filter = DeslopFilter()
        self.log: list[dict] = []

    def produce_chapter(self, novel_id: str, chapter_num: int, generator, state, style,
                        rag_context=None, outline=None, author_input="", quality_threshold=0.75) -> dict:
        """
        生产一章的完整流程。Brain Agent 编排，不是固定流水线。
        """
        ctx = {"novel_id": novel_id, "chapter_num": chapter_num, "db": self.db}
        result = {"chapter_num": chapter_num, "stations_used": []}

        # ═══ 工位1：约束编译（每章必跑） ═══
        constraint_result = self.constraint_builder.run(ctx)
        result["constraints"] = constraint_result
        self.log.append({"station": "constraint_builder", "result": "ok"})

        # ═══ 工位2：正文生成（每章必跑） ═══
        constraints_text = constraint_result.get("hard_constraints", "")
        if constraints_text:
            author_input = f"【硬约束】\n{constraints_text}\n\n" + (f"【作者方向】{author_input}" if author_input else "")
        if constraint_result.get("soft_suggestions"):
            author_input += f"\n\n【建议】{constraint_result['soft_suggestions']}"
        result["stations_used"].append("chapter_writer")

        # ═══ 工位3：质量检查 → 不通过则编辑修正 ═══
        # 这步在 generator 层完成，Brain 只决定是否重试

        # ═══ 工位4：一致性校验（每章必跑） ═══
        consistency_result = self.consistency_checker.run(ctx)
        result["consistency"] = consistency_result
        self.log.append({"station": "consistency_checker", "result": consistency_result["status"]})

        # ═══ 工位5：去AI味（章号 > 3 才跑） ═══
        if chapter_num > self.deslop_filter.min_chapter:
            deslop_result = self.deslop_filter.run(ctx)
            result["deslop"] = deslop_result
            self.log.append({"station": "deslop_filter", "result": f"score={deslop_result['score']}/50"})
        else:
            self.log.append({"station": "deslop_filter", "result": "skipped (early chapter)"})

        # ═══ 终检：全部通过？ ═══
        passed = True
        if consistency_result.get("error_count", 0) > 0:
            passed = False
            result["blockers"] = consistency_result.get("issues", [])

        result["passed"] = passed
        result["log"] = self.log
        return result

    def get_quality_report(self, novel_id: str) -> dict:
        """汇总质检报告"""
        issues = self.db.get_consistency_log(novel_id)
        chars = self.db.get_character_state(novel_id)
        fs = self.db.get_active_foreshadowing(novel_id)

        return {
            "character_count": len(chars),
            "active_foreshadowing": len(fs),
            "consistency_issues": len(issues),
            "errors": len([i for i in issues if i.get("severity") == "error"]),
            "warnings": len([i for i in issues if i.get("severity") == "warning"]),
            "resolved": len([i for i in issues if i.get("was_fixed")]),
        }
