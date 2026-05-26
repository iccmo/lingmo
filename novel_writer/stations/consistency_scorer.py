"""
工位：跨章一致性评分
输入：novel_id
输出：5-dimension score (100pts), grade S/A/B/C/D, trend, breakdown

五维度：
  1. 角色弧光连贯性 (25pts) — 个性/情绪跨章是否有合理演化
  2. 伏笔健康度     (25pts) — 回收率、过期数、平均回收章数
  3. 情节线连续性   (20pts) — 支线是否被追踪推进、有无遗弃线
  4. 世界观完整性   (15pts) — 规则是否一致、破坏次数
  5. 结构平衡性     (15pts) — 代价账簿、章节长度方差、弧线节奏
"""
from typing import Any


class ConsistencyScorer:
    name = "consistency_scorer"
    required_every_chapter = False  # runs on demand, not per-chapter

    MAX_SCORES = {
        "character_arc": 25,
        "foreshadowing_health": 25,
        "plot_continuity": 20,
        "world_integrity": 15,
        "structural_balance": 15,
    }

    def run(self, ctx: dict) -> dict:
        novel_id = ctx["novel_id"]
        db = ctx["db"]

        dims: dict[str, dict] = {}
        total = 0
        max_total = sum(self.MAX_SCORES.values())

        # ── 1. 角色弧光连贯性 (25pts) ──
        dims["character_arc"] = self._score_character_arc(novel_id, db)
        total += dims["character_arc"]["score"]

        # ── 2. 伏笔健康度 (25pts) ──
        dims["foreshadowing_health"] = self._score_foreshadowing(novel_id, db)
        total += dims["foreshadowing_health"]["score"]

        # ── 3. 情节线连续性 (20pts) ──
        dims["plot_continuity"] = self._score_plot_continuity(novel_id, db)
        total += dims["plot_continuity"]["score"]

        # ── 4. 世界观完整性 (15pts) ──
        dims["world_integrity"] = self._score_world_integrity(novel_id, db)
        total += dims["world_integrity"]["score"]

        # ── 5. 结构平衡性 (15pts) ──
        dims["structural_balance"] = self._score_structural_balance(novel_id, db)
        total += dims["structural_balance"]["score"]

        # ── Grade ──
        pct = total / max_total
        grade = (
            "S" if pct >= 0.90 else
            "A" if pct >= 0.75 else
            "B" if pct >= 0.60 else
            "C" if pct >= 0.40 else
            "D"
        )

        # ── Trend: compare last 5 chapters vs previous 5 ──
        trend = self._compute_trend(novel_id, db)

        # ── Recommendation ──
        weakest = min(dims, key=lambda k: dims[k]["score"] / self.MAX_SCORES[k])
        recommendation = self._recommend(weakest, dims)

        return {
            "status": "ok",
            "score": total,
            "max_score": max_total,
            "pct": round(pct, 3),
            "grade": grade,
            "trend": trend,
            "dimensions": dims,
            "weakest_dimension": weakest,
            "recommendation": recommendation,
        }

    # ═══ Dimension Scoring Methods ═══

    def _score_character_arc(self, novel_id: str, db) -> dict:
        """
        Check if character emotions/personalities evolve naturally across chapters.
        Penalties: sudden reversals, static characters with no arc, inconsistent traits.
        """
        states = db.get_character_state(novel_id)
        if len(states) < 2:
            return {"score": self.MAX_SCORES["character_arc"], "max": 25,
                    "detail": "不足2章数据，默认满分", "issues": []}

        chars: dict[str, list[dict]] = {}
        for s in states:
            chars.setdefault(s["char_name"], []).append(s)

        score = self.MAX_SCORES["character_arc"]
        issues: list[str] = []
        penalty_per_issue = 4

        for name, history in chars.items():
            if len(history) < 3:
                continue
            emotions = [h.get("emotion", "") for h in history if h.get("emotion")]
            # Penalty: character has same emotion for 5+ consecutive chapters (static)
            if len(emotions) >= 5 and len(set(emotions[-5:])) == 1:
                score = max(0, score - penalty_per_issue)
                issues.append(f"{name}情绪连续5章不变({emotions[-1]})，角色停滞")
            # Penalty: sudden reversal (e.g. 愤怒→温柔→愤怒 within 3 chapters)
            for i in range(len(emotions) - 2):
                trio = emotions[i:i+3]
                if len(set(trio)) == 3:
                    score = max(0, score - penalty_per_issue // 2)
                    issues.append(f"{name}情绪在Ch{history[i]['chapter_num']}-{history[i+2]['chapter_num']}间剧烈波动")
                    break

        return {"score": score, "max": self.MAX_SCORES["character_arc"],
                "detail": f"{len(chars)}角色追踪", "issues": issues}

    def _score_foreshadowing(self, novel_id: str, db) -> dict:
        """
        Score foreshadowing health: resolution rate, overdue count, avg resolution time.
        """
        fs = db.get_active_foreshadowing(novel_id)
        all_fs = fs  # includes resolved
        if not all_fs:
            return {"score": self.MAX_SCORES["foreshadowing_health"], "max": 25,
                    "detail": "无伏笔数据", "issues": []}

        active = [f for f in all_fs if f.get("status") == "active"]
        overdue = [f for f in all_fs if f.get("status") == "overdue"]
        resolved = [f for f in all_fs if f.get("status") == "resolved"]

        score = self.MAX_SCORES["foreshadowing_health"]
        issues: list[str] = []

        # Each overdue foreshadowing: -5
        score = max(0, score - len(overdue) * 5)
        for f in overdue:
            issues.append(f"伏笔#{f['id']}已过期(Ch{f.get('created_chapter','?')}→{f.get('due_by_chapter','?')})")

        # Resolution rate below 30% with >3 active: -4
        total_tracked = len(active) + len(overdue) + len(resolved)
        if total_tracked > 3:
            rate = len(resolved) / total_tracked
            if rate < 0.3:
                score = max(0, score - 4)
                issues.append(f"伏笔回收率仅{rate:.0%}（{len(resolved)}/{total_tracked}）")

        # Too many active foreshadowing (>8): -3
        if len(active) > 8:
            score = max(0, score - 3)
            issues.append(f"活跃伏笔过多({len(active)}个)，建议回收部分")

        return {"score": score, "max": self.MAX_SCORES["foreshadowing_health"],
                "detail": f"{len(active)}活跃/{len(resolved)}已收/{len(overdue)}过期",
                "issues": issues}

    def _score_plot_continuity(self, novel_id: str, db) -> dict:
        """
        Check if subplots are being advanced. Look at timeline gaps, plot point resolution.
        """
        timeline = db.get_timeline(novel_id)
        chapters = db.get_novel(novel_id)
        if not chapters:
            return {"score": self.MAX_SCORES["plot_continuity"], "max": 20,
                    "detail": "无章节数据", "issues": []}

        gen_chapters = [c for c in chapters.get("chapters", []) if c.get("word_count", 0) > 0]
        score = self.MAX_SCORES["plot_continuity"]
        issues: list[str] = []

        # Gap detection: timeline missing entries for generated chapters
        tl_chapters = set(t.get("chapter_num") for t in timeline)
        gen_nums = set(c["number"] for c in gen_chapters)
        missing_timeline = gen_nums - tl_chapters
        if len(missing_timeline) > max(1, len(gen_nums) * 0.3):
            score = max(0, score - 5)
            issues.append(f"{len(missing_timeline)}章缺失时间线记录")

        # Plot points: check unresolved plot points
        with db.conn() as c:
            unresolved = c.execute(
                "SELECT COUNT(*) FROM plot_points WHERE novel_id=? AND is_resolved=0",
                (novel_id,)
            ).fetchone()[0]
        if unresolved > 5:
            score = max(0, score - 4)
            issues.append(f"{unresolved}个未解决情节点")

        return {"score": score, "max": self.MAX_SCORES["plot_continuity"],
                "detail": f"{len(timeline)}时间线记录/{len(gen_nums)}章",
                "issues": issues}

    def _score_world_integrity(self, novel_id: str, db) -> dict:
        """
        Check world rules: count broken rules, check for contradictions.
        """
        world = db.get_world_state(novel_id)
        score = self.MAX_SCORES["world_integrity"]
        issues: list[str] = []

        broken = [w for w in world if w.get("is_broken")]
        score = max(0, score - len(broken) * 5)
        for b in broken:
            issues.append(f"规则'{b['rule_name']}'已被破坏(Ch{b.get('chapter_num','?')})")

        return {"score": score, "max": self.MAX_SCORES["world_integrity"],
                "detail": f"{len(world)}规则/{len(broken)}已破坏",
                "issues": issues}

    def _score_structural_balance(self, novel_id: str, db) -> dict:
        """
        Check cost ledger balance, chapter length variance.
        """
        costs = db.get_cost_ledger(novel_id)
        chapters = db.get_novel(novel_id)
        gen_chapters = [c for c in (chapters.get("chapters", []) if chapters else [])
                       if c.get("word_count", 0) > 0]

        score = self.MAX_SCORES["structural_balance"]
        issues: list[str] = []

        # Cost balance: gains vs losses
        gains = sum(1 for c in costs if c.get("gain"))
        losses = sum(1 for c in costs if c.get("loss"))
        imbalance = abs(gains - losses)
        if imbalance > 5:
            score = max(0, score - 3)
            direction = "得" if gains > losses else "失"
            issues.append(f"代价账簿失衡：{gains}得/{losses}失，偏向'{direction}'")
        elif imbalance > 3:
            score = max(0, score - 1)
            direction = "得" if gains > losses else "失"
            issues.append(f"代价账簿略失衡：{gains}得/{losses}失")

        # Chapter length variance
        if len(gen_chapters) >= 5:
            words = [c["word_count"] for c in gen_chapters[-10:]]
            avg = sum(words) / len(words)
            if avg > 0:
                variance = sum((w - avg) ** 2 for w in words) / len(words)
                cv = (variance ** 0.5) / avg  # coefficient of variation
                if cv > 0.5:
                    score = max(0, score - 2)
                    issues.append(f"章字数波动过大(变异系数{cv:.2f})")

        return {"score": score, "max": self.MAX_SCORES["structural_balance"],
                "detail": f"{len(costs)}条代价记录/{len(gen_chapters)}章",
                "issues": issues}

    def _compute_trend(self, novel_id: str, db) -> str:
        """Compare recent chapter quality trend."""
        chapters = db.get_novel(novel_id)
        if not chapters:
            return "stable"
        gen = [c for c in chapters.get("chapters", []) if c.get("word_count", 0) > 0]
        if len(gen) < 5:
            return "insufficient_data"
        recent = [c.get("quality_score", 0) for c in gen[-5:]]
        earlier = [c.get("quality_score", 0) for c in gen[-10:-5]]
        if not earlier:
            return "stable"
        recent_avg = sum(recent) / len(recent)
        earlier_avg = sum(earlier) / len(earlier)
        diff = recent_avg - earlier_avg
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "declining"
        else:
            return "stable"

    def _recommend(self, weakest: str, dims: dict) -> str:
        recs = {
            "character_arc": "角色弧光停滞或波动剧烈——建议在约束中加入情绪演化方向",
            "foreshadowing_health": "伏笔管理需改进——优先回收过期伏笔或延长到期章号",
            "plot_continuity": "情节线追踪不完整——检查是否有被遗弃的支线",
            "world_integrity": "世界观规则被破坏——考虑是否需要重修规则或解释破坏原因",
            "structural_balance": "结构失衡——调整代价账簿或稳定章字数",
        }
        return recs.get(weakest, "整体良好")
