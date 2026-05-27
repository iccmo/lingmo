# 跨章一致性评分 + 约束内容优化 + 长跑测试框架 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用跨章结构评分替代单章 LLM Judge，优化约束从角色标签到具体情节约束，搭建 10 章连续生成长跑测试框架验证 30 章+防崩坏效果。

**Architecture:** 三个子系统独立但协同：(1) ConsistencyScorer station 从 5 维度对全书做结构化评分，(2) ConstraintBuilder 增强版查询 location/relationship/knowledge 表生成情节级约束，(3) BatchRunner 脚本顺序生成 N 章并记录每章质量指标和退化信号。

**Tech Stack:** Python 3.12, SQLite, 现有 stations/ 模式, React + TypeScript 前端

---

## File Structure

```
novel_writer/stations/
  consistency_scorer.py    (CREATE) — 5-dimension cross-chapter scoring, replaces LLM Judge for consistency
  constraint_builder.py    (MODIFY) — enhance with location/relationship/knowledge/physical constraints
  batch_runner.py          (CREATE) — sequential N-chapter generation with metrics tracking

novel_writer/
  database.py              (MODIFY) — add get_character_location(), get_relationship_changes(), get_knowledge_state()
  server.py                (MODIFY) — wire consistency scorer, add /batch-generate endpoint
  brain_agent.py           (MODIFY) — integrate consistency scorer into quality gate

frontend/src/components/novels/
  ConsistencyScoreView.tsx (CREATE) — radar/sparkline UI for 5-dimension scores
```

---

### Task 1: DB 查询方法 — 位置/关系/知识追踪

**Files:**
- Modify: `novel_writer/database.py` (append 3 new methods)

这些方法是约束增强和一致性评分的数据基础。

- [ ] **Step 1: 添加 `get_character_location` 方法**

在 `database.py` 的 `get_cost_ledger` 方法之后追加：

```python
def get_character_location(self, novel_id: str, char_name: str) -> str | None:
    """Get a character's latest known location from character_state table."""
    with self.conn() as c:
        row = c.execute(
            """SELECT location FROM character_state
               WHERE novel_id=? AND char_name=? AND location != ''
               ORDER BY chapter_num DESC LIMIT 1""",
            (novel_id, char_name)
        ).fetchone()
        return row["location"] if row else None
```

- [ ] **Step 2: 添加 `get_relationship_changes` 方法**

```python
def get_relationship_changes(self, novel_id: str) -> list[dict]:
    """Get relationship state transitions from character_state.relationships JSON."""
    with self.conn() as c:
        rows = c.execute(
            """SELECT chapter_num, char_name, relationships FROM character_state
               WHERE novel_id=? AND relationships != '[]' AND relationships != ''
               ORDER BY chapter_num""",
            (novel_id,)
        ).fetchall()
    result: list[dict] = []
    for r in rows:
        try:
            rels = json.loads(r["relationships"])
            for rel in rels:
                result.append({
                    "chapter_num": r["chapter_num"],
                    "char_name": r["char_name"],
                    "target": rel.get("target", ""),
                    "relation": rel.get("relation", ""),
                    "change": rel.get("change", ""),
                })
        except (json.JSONDecodeError, TypeError):
            pass
    return result
```

- [ ] **Step 3: 添加 `get_knowledge_state` 方法**

```python
def get_knowledge_state(self, novel_id: str, char_name: str) -> list[str]:
    """Get what a character knows (from character_state.knowledge JSON array)."""
    with self.conn() as c:
        rows = c.execute(
            """SELECT knowledge FROM character_state
               WHERE novel_id=? AND char_name=? AND knowledge != '[]' AND knowledge != ''
               ORDER BY chapter_num DESC LIMIT 5""",
            (novel_id, char_name)
        ).fetchall()
    all_knowledge: list[str] = []
    for r in rows:
        try:
            items = json.loads(r["knowledge"])
            all_knowledge.extend(items)
        except (json.JSONDecodeError, TypeError):
            pass
    return list(dict.fromkeys(all_knowledge))  # dedup preserve order
```

- [ ] **Step 4: 验证导入**

```bash
cd /Users/z/CodeBuddy/wechat && python3 -c "
from novel_writer.database import Database
db = Database('data/novel_writer.db')
loc = db.get_character_location('gongmou', '顾栖岩')
rels = db.get_relationship_changes('gongmou')
know = db.get_knowledge_state('gongmou', '顾栖岩')
print(f'Location: {loc}')
print(f'Relationships: {len(rels)} changes')
print(f'Knowledge items: {len(know)}')
"
```

- [ ] **Step 5: Commit**

```bash
git add novel_writer/database.py
git commit -m "feat: add DB methods for location, relationship, knowledge tracking"
```

---

### Task 2: ConsistencyScorer — 跨章一致性评分站

**Files:**
- Create: `novel_writer/stations/consistency_scorer.py`

5 维度 100 分制，替代单章 LLM Judge 的结构化评分。

- [ ] **Step 1: 创建 consistency_scorer.py**

```python
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
```

- [ ] **Step 2: 验证导入和基本运行**

```bash
cd /Users/z/CodeBuddy/wechat && python3 -c "
from novel_writer.stations.consistency_scorer import ConsistencyScorer
from novel_writer.database import Database
db = Database('data/novel_writer.db')
scorer = ConsistencyScorer()
result = scorer.run({'novel_id': 'gongmou', 'db': db})
print(f'Score: {result[\"score\"]}/{result[\"max_score\"]}')
print(f'Grade: {result[\"grade\"]}')
print(f'Trend: {result[\"trend\"]}')
print(f'Weakest: {result[\"weakest_dimension\"]}')
print()
for dim, data in result['dimensions'].items():
    print(f'  {dim}: {data[\"score\"]}/{data[\"max\"]} — {data[\"detail\"]}')
    for issue in data.get('issues', []):
        print(f'    ⚠️ {issue}')
"
```

- [ ] **Step 3: Commit**

```bash
git add novel_writer/stations/consistency_scorer.py
git commit -m "feat: ConsistencyScorer — 5-dimension cross-chapter structural scoring"
```

---

### Task 3: 约束内容增强 — 从标签到情节约束

**Files:**
- Modify: `novel_writer/stations/constraint_builder.py` (rewrite `run()` method)

增强约束内容，添加：物理状态连续性、位置追踪、关系状态、知识一致性。

- [ ] **Step 1: 重写 constraint_builder.py 的 `run()` 方法**

```python
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
```

- [ ] **Step 2: 测试增强版约束生成**

```bash
cd /Users/z/CodeBuddy/wechat && python3 -c "
from novel_writer.stations.constraint_builder import ConstraintBuilder
from novel_writer.database import Database
db = Database('data/novel_writer.db')
builder = ConstraintBuilder()
result = builder.run({'novel_id': 'gongmou', 'chapter_num': 27, 'db': db})
print(f'Hard constraints ({result[\"hard_count\"]}):')
print(result['hard_constraints'])
print()
print(f'Soft suggestions ({result[\"soft_count\"]}):')
print(result['soft_suggestions'])
print()
print(f'Total chars: {len(result[\"hard_constraints\"]) + len(result[\"soft_suggestions\"])}')
"
```

- [ ] **Step 3: Commit**

```bash
git add novel_writer/stations/constraint_builder.py
git commit -m "feat: enhance constraint builder with location/relationship/knowledge/physical tracking"
```

---

### Task 4: BatchRunner — 长跑测试框架

**Files:**
- Create: `novel_writer/stations/batch_runner.py`

- [ ] **Step 1: 创建 batch_runner.py**

```python
"""
长跑测试框架 — 连续生成 N 章并记录质量退化信号。

用法：
  runner = BatchRunner(db, provider)
  report = runner.run("gongmou", chapters=10, compression="L1", quality_threshold=0.75)
  print(runner.format_report(report))
"""
import time
import json
from typing import Any
from .consistency_scorer import ConsistencyScorer


class BatchRunner:
    def __init__(self, db, get_provider_fn, run_generation_fn):
        self.db = db
        self.get_provider = get_provider_fn
        self.run_generation = run_generation_fn
        self.scorer = ConsistencyScorer()

    def run(self, novel_id: str, chapters: int = 10,
            compression: str = "L1", quality_threshold: float = 0.75) -> dict:
        """
        Generate N chapters sequentially with fixed constraint level.
        Track metrics per chapter and detect degradation signals.
        """
        novel = self.db.get_novel(novel_id)
        if not novel:
            return {"error": "Novel not found"}
        start_ch = len([c for c in novel.get("chapters", []) if c.get("word_count", 0) > 0]) + 1

        results: list[dict] = []
        degradation_signals: list[dict] = []
        t0 = time.time()

        for i in range(chapters):
            ch_num = start_ch + i
            print(f"\n{'='*50}")
            print(f"[BATCH] {novel_id} Ch{ch_num} ({i+1}/{chapters}) — compression={compression}")
            print(f"{'='*50}")

            ch_t0 = time.time()
            try:
                # Run single chapter generation
                gen_result = self.run_generation(novel_id, compression, quality_threshold)
                duration = time.time() - ch_t0

                # Collect single-chapter metrics
                quality = gen_result.get("quality", {})
                chapter_info = {
                    "chapter_num": ch_num,
                    "duration_sec": round(duration, 1),
                    "quality_score": quality.get("overall", 0),
                    "grade": quality.get("grade", "?"),
                    "word_count": gen_result.get("word_count", 0),
                    "retries": gen_result.get("retries", 0),
                    "compression": compression,
                    "auto_recovery": gen_result.get("auto_recovery", False),
                }

                # Run cross-chapter consistency score
                cs = self.scorer.run({"novel_id": novel_id, "db": self.db})
                chapter_info["consistency_score"] = cs["score"]
                chapter_info["consistency_grade"] = cs["grade"]

                results.append(chapter_info)

                # Degradation detection
                if len(results) >= 3:
                    recent_3 = [r["quality_score"] for r in results[-3:]]
                    if all(q < 0.75 for q in recent_3):
                        degradation_signals.append({
                            "chapter": ch_num,
                            "signal": "连续3章质量<0.75",
                            "scores": recent_3,
                        })
                    if all(r.get("consistency_score", 100) < 60 for r in results[-3:]):
                        degradation_signals.append({
                            "chapter": ch_num,
                            "signal": "连续3章一致性<60",
                            "scores": [r.get("consistency_score", 0) for r in results[-3:]],
                        })

                print(f"[BATCH] Ch{ch_num} done: Q={chapter_info['quality_score']:.2f}({chapter_info['grade']}) "
                      f"CS={chapter_info['consistency_score']}/100({chapter_info['consistency_grade']}) "
                      f"words={chapter_info['word_count']} retries={chapter_info['retries']} "
                      f"time={duration:.0f}s")

            except Exception as e:
                print(f"[BATCH ERROR] Ch{ch_num}: {e}")
                results.append({
                    "chapter_num": ch_num,
                    "error": str(e),
                    "duration_sec": time.time() - ch_t0,
                })
                degradation_signals.append({
                    "chapter": ch_num,
                    "signal": f"生成失败: {str(e)[:100]}",
                })
                break

        total_time = time.time() - t0

        # Final cross-chapter score
        final_cs = self.scorer.run({"novel_id": novel_id, "db": self.db})

        # Aggregate stats
        valid = [r for r in results if "quality_score" in r]
        avg_q = sum(r["quality_score"] for r in valid) / max(1, len(valid))
        avg_cs = sum(r.get("consistency_score", 0) for r in valid) / max(1, len(valid))

        return {
            "novel_id": novel_id,
            "compression": compression,
            "chapters_generated": len(valid),
            "total_time_sec": round(total_time, 1),
            "avg_time_per_chapter_sec": round(total_time / max(1, len(valid)), 1),
            "avg_quality": round(avg_q, 3),
            "avg_consistency": round(avg_cs, 1),
            "final_consistency_score": final_cs["score"],
            "final_consistency_grade": final_cs["grade"],
            "final_consistency_trend": final_cs["trend"],
            "degradation_signals": degradation_signals,
            "chapters": results,
            "passed": len(degradation_signals) == 0,
        }

    def format_report(self, report: dict) -> str:
        """Format batch run report as readable text."""
        lines = [
            "=" * 60,
            f"  长跑测试报告 — {report['novel_id']}",
            "=" * 60,
            f"  约束级别: {report['compression']}",
            f"  生成章数: {report['chapters_generated']}",
            f"  总耗时:   {report['total_time_sec']:.0f}s ({report['avg_time_per_chapter_sec']:.0f}s/章)",
            f"  平均质量: {report['avg_quality']:.2f}",
            f"  平均一致性: {report['avg_consistency']:.0f}/100",
            f"  最终一致性: {report['final_consistency_score']}/100 ({report['final_consistency_grade']})",
            f"  趋势: {report['final_consistency_trend']}",
            "",
        ]

        if report["degradation_signals"]:
            lines.append("  ⚠️ 退化信号:")
            for sig in report["degradation_signals"]:
                lines.append(f"    Ch{sig['chapter']}: {sig['signal']}")
        else:
            lines.append("  ✅ 未检测到退化信号")

        lines.append("")
        lines.append("  逐章详情:")
        lines.append(f"  {'章':<4} {'质量':<6} {'一致性':<8} {'字数':<6} {'重试':<4} {'耗时':<6}")
        lines.append("  " + "-" * 40)
        for ch in report["chapters"]:
            if "error" in ch:
                lines.append(f"  {ch['chapter_num']:<4} ERROR: {ch['error'][:30]}")
            else:
                lines.append(
                    f"  {ch['chapter_num']:<4} "
                    f"{ch['quality_score']:.2f}({ch['grade']:<1}) "
                    f"{ch.get('consistency_score', 0):<5}/100 "
                    f"{ch['word_count']:<6} "
                    f"{ch['retries']:<4} "
                    f"{ch['duration_sec']:.0f}s"
                )
        lines.append("=" * 60)
        return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add novel_writer/stations/batch_runner.py
git commit -m "feat: BatchRunner — sequential N-chapter generation with degradation detection"
```

---

### Task 5: 接入 Brain Agent + Server

**Files:**
- Modify: `novel_writer/brain_agent.py:63-78` (integrate ConsistencyScorer into quality gate)
- Modify: `novel_writer/server.py:1350-1360` (add batch-generate endpoint, wire scorer)

- [ ] **Step 1: Brain Agent 质量关卡接入 ConsistencyScorer**

在 `brain_agent.py` 的 `get_quality_report` 方法中添加跨章评分：

```python
# In brain_agent.py, add import at top:
from .stations.consistency_scorer import ConsistencyScorer

# In __init__, add:
self.consistency_scorer = ConsistencyScorer()

# In produce_chapter, replace the gate logic (lines 63-78) with:
# ═══ 终检：质量关卡（含跨章一致性） ═══
errors = consistency_result.get("error_count", 0)
deslop_score = result.get("deslop", {}).get("score", 50)
confidence = consistency_result.get("confidence", 100)

# Cross-chapter consistency score
cs_result = self.consistency_scorer.run({
    "novel_id": novel_id, "db": self.db
})
result["cross_chapter_score"] = cs_result

if errors >= 3 or cs_result["grade"] in ("C", "D"):
    gate = "🔴 BLOCK"
elif errors >= 1 or deslop_score < 35 or cs_result["grade"] == "B":
    gate = "⚠️ WARN"
else:
    gate = "✅ PASS"
```

- [ ] **Step 2: Server 添加 batch-generate 端点和 consistency-score API**

在 `server.py` 中添加两个新端点（在 `# ═══════════════ Publish ═══════════════` 之前）：

```python
@app.get("/api/novels/{novel_id}/consistency-score")
def get_consistency_score(novel_id: str):
    """Get cross-chapter consistency score (5-dimension structural scoring)."""
    from .stations.consistency_scorer import ConsistencyScorer
    scorer = ConsistencyScorer()
    result = scorer.run({"novel_id": novel_id, "db": db})
    return result


@app.post("/api/novels/{novel_id}/batch-generate")
def trigger_batch_generate(novel_id: str, background: BackgroundTasks, data: dict = {}):
    """Generate N chapters sequentially with fixed constraint level for long-run testing."""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    chapters = int((data or {}).get("chapters", 10))
    compression = (data or {}).get("compression", "L1").strip().upper()
    quality_threshold = float((data or {}).get("quality_threshold", 0.75))
    if compression not in ("L0", "L1", "L2", "L3", "NONE"):
        compression = "L1"
    if chapters < 1 or chapters > 20:
        raise HTTPException(400, "chapters must be 1-20")
    background.add_task(_run_batch_generation, novel_id, chapters, compression, quality_threshold)
    return {
        "status": "batch_started",
        "novel_id": novel_id,
        "chapters": chapters,
        "compression": compression,
    }
```

并添加 `_run_batch_generation` 函数：

```python
def _run_batch_generation(novel_id: str, chapters: int, compression: str, quality_threshold: float):
    """Background task: run batch generation with metrics tracking."""
    from .stations.batch_runner import BatchRunner
    try:
        runner = BatchRunner(db, _get_provider, _run_single_generation)
        report = runner.run(novel_id, chapters, compression, quality_threshold)
        _gen_status[novel_id] = {
            "status": "batch_complete",
            "message": f"批量生成完成: {report['chapters_generated']}/{chapters}章",
            "progress": 100,
            "batch_report": report,
        }
        print(runner.format_report(report))
    except Exception as e:
        import traceback
        _gen_status[novel_id] = {
            "status": "batch_failed",
            "message": f"批量生成失败: {str(e)[:100]}",
            "progress": 0,
        }
        traceback.print_exc()


def _run_single_generation(novel_id: str, compression: str, quality_threshold: float) -> dict:
    """Wrapper for single chapter generation used by BatchRunner."""
    _gen_directions[novel_id + "_compression"] = compression
    _gen_directions[novel_id + "_qthreshold"] = str(quality_threshold)
    _run_generation(novel_id)
    # Return captured quality info
    status = _gen_status.get(novel_id, {})
    return {
        "quality": {
            "overall": status.get("overall", 0),
            "grade": status.get("grade", "?"),
        },
        "word_count": status.get("word_count", 0),
        "retries": status.get("retries", 0),
        "auto_recovery": status.get("auto_recovery", False),
    }
```

- [ ] **Step 3: Commit**

```bash
git add novel_writer/brain_agent.py novel_writer/server.py
git commit -m "feat: integrate ConsistencyScorer into Brain gate + add batch-generate endpoint"
```

---

### Task 6: 前端 — ConsistencyScoreView 组件

**Files:**
- Create: `frontend/src/components/novels/ConsistencyScoreView.tsx`

- [ ] **Step 1: 创建 ConsistencyScoreView.tsx**

```typescript
import { useState, useEffect } from 'react';

interface Dimension {
  score: number;
  max: number;
  detail: string;
  issues: string[];
}

interface ConsistencyData {
  score: number;
  max_score: number;
  pct: number;
  grade: string;
  trend: string;
  dimensions: Record<string, Dimension>;
  weakest_dimension: string;
  recommendation: string;
}

const DIM_LABELS: Record<string, string> = {
  character_arc: '角色弧光',
  foreshadowing_health: '伏笔健康',
  plot_continuity: '情节连续',
  world_integrity: '世界完整',
  structural_balance: '结构平衡',
};

const GRADE_COLORS: Record<string, string> = {
  S: 'text-emerald-500 border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20',
  A: 'text-sky-500 border-sky-200 bg-sky-50 dark:bg-sky-950/20',
  B: 'text-amber-500 border-amber-200 bg-amber-50 dark:bg-amber-950/20',
  C: 'text-orange-500 border-orange-200 bg-orange-50 dark:bg-orange-950/20',
  D: 'text-red-500 border-red-200 bg-red-50 dark:bg-red-950/20',
};

const TREND_ICONS: Record<string, string> = {
  improving: '📈',
  declining: '📉',
  stable: '➡️',
  insufficient_data: '…',
};

interface Props { novelId: string }

export function ConsistencyScoreView({ novelId }: Props) {
  const [data, setData] = useState<ConsistencyData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/novels/${novelId}/consistency-score`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [novelId]);

  if (loading) return <div className="skeleton h-16 rounded-lg" />;
  if (!data) return <p className="text-xs text-ink-subtle py-2">暂无一致性数据</p>;

  return (
    <div className="space-y-3">
      {/* Overall Grade */}
      <div className={`flex items-center justify-between p-2 rounded-lg border ${GRADE_COLORS[data.grade] || GRADE_COLORS.B}`}>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold">{data.grade}</span>
          <div>
            <div className="text-xs font-medium text-ink">
              {data.score}/{data.max_score} ({Math.round(data.pct * 100)}%)
            </div>
            <div className="text-[10px] text-ink-subtle">
              {TREND_ICONS[data.trend] || ''} {data.trend}
            </div>
          </div>
        </div>
        <div className="text-[10px] text-ink-subtle text-right max-w-[180px]">
          {data.recommendation}
        </div>
      </div>

      {/* Dimension Bars */}
      <div className="space-y-1.5">
        {Object.entries(data.dimensions).map(([key, dim]) => {
          const pct = dim.max > 0 ? (dim.score / dim.max) * 100 : 0;
          const barColor =
            pct >= 80 ? 'bg-emerald-500' :
            pct >= 60 ? 'bg-sky-500' :
            pct >= 40 ? 'bg-amber-500' : 'bg-red-500';
          const isWeakest = key === data.weakest_dimension;

          return (
            <div key={key}>
              <div className="flex items-center justify-between text-[10px] mb-0.5">
                <span className={`text-ink-subtle ${isWeakest ? 'font-semibold text-amber-500' : ''}`}>
                  {DIM_LABELS[key] || key}
                  {isWeakest && ' ⚠️'}
                </span>
                <span className="text-ink-muted font-mono">
                  {dim.score}/{dim.max}
                </span>
              </div>
              <div className="h-1.5 bg-paper rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${barColor}`}
                  style={{ width: `${Math.max(2, pct)}%` }}
                />
              </div>
              {dim.issues.length > 0 && (
                <div className="mt-0.5 space-y-0.5">
                  {dim.issues.map((issue, i) => (
                    <p key={i} className="text-[9px] text-ink-subtle pl-1 border-l-2 border-amber-300 dark:border-amber-700">
                      {issue}
                    </p>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 将组件嵌入 StoryBibleView 或 NovelDetail 页面**

在 `StoryBibleView.tsx` 的系统评分区域（替换当前的简单 selfCheck 显示）引入 ConsistencyScoreView：

在 `StoryBibleView.tsx` 文件顶部添加 import：
```typescript
import { ConsistencyScoreView } from './ConsistencyScoreView';
```

将现有的 selfCheck 区块（lines 72-82）替换为：
```typescript
{/* Cross-Chapter Consistency Score (§NEW) */}
<ConsistencyScoreView novelId={novelId} />
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/novels/ConsistencyScoreView.tsx frontend/src/components/novels/StoryBibleView.tsx
git commit -m "feat: ConsistencyScoreView — 5-dimension radar UI with grade/trend/issues"
```

---

### Task 7: 端到端验证 — 运行长跑测试

- [ ] **Step 1: 重启服务并验证 API**

```bash
kill $(lsof -t -i :8000) 2>/dev/null; sleep 1
cd /Users/z/CodeBuddy/wechat && PYTHONPATH=/Users/z/CodeBuddy/wechat python3 -m uvicorn novel_writer.server:app --host 0.0.0.0 --port 8000 &
sleep 3
# Verify new endpoints
curl -s http://localhost:8000/api/novels/gongmou/consistency-score | python3 -m json.tool
```

- [ ] **Step 2: 运行增强版约束生成（单章）验证**

```bash
curl -s -X POST http://localhost:8000/api/novels/gongmou/generate \
  -H "Content-Type: application/json" \
  -d '{"direction":"继续推进主线","quality_threshold":0.75,"compression":"L1"}'
# Monitor until complete, verify no auto-recovery
```

- [ ] **Step 3: 运行批量生成长跑测试（3章先行验证）**

```bash
curl -s -X POST http://localhost:8000/api/novels/gongmou/batch-generate \
  -H "Content-Type: application/json" \
  -d '{"chapters":3,"compression":"L1","quality_threshold":0.75}'
# Monitor batch progress
```

- [ ] **Step 4: 分析测试报告**

检查 terminal 输出的格式化报告，确认：
- 退化信号是否正确检测
- 一致性评分是否合理（不应有 false positive）
- 约束内容是否从标签升级为情节约束

- [ ] **Step 5: Commit final verification**

```bash
git add -A
git commit -m "chore: end-to-end verification of consistency scoring + batch runner"
```

---

## 自审检查

**1. Spec coverage:** 三个子系统各有 task: ConsistencyScorer (Task 2), ConstraintBuilder 增强 (Task 3), BatchRunner (Task 4). 集成层在 Task 5, 前端在 Task 6, 验证在 Task 7.

**2. Placeholder scan:** 所有代码块包含完整实现，无 TBD/TODO。测试步骤包含具体命令。

**3. Type consistency:** ConsistencyScorer.run() 返回 dict 与前端接口对齐。BatchRunner 的 run_generation_fn 签名与 _run_single_generation 匹配。
