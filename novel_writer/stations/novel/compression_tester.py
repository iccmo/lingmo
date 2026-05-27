"""
约束压缩 A/B 测试框架
对比 L0/L1/L2/L3 四种压缩级别产生的约束质量

Pi 方法论：用数据验证"最少即最优"
"""
from .constraint_builder import ConstraintBuilder
from .constraint_compressor import ConstraintCompressor


class CompressionTester:
    """A/B test: compare compression levels across novels"""

    def __init__(self, db):
        self.db = db
        self.builder = ConstraintBuilder()
        self.compressor = ConstraintCompressor()

    def test_novel(self, novel_id: str, chapter_num: int) -> dict:
        """Test all compression levels for one novel"""
        result = self.builder.run({
            "novel_id": novel_id, "chapter_num": chapter_num, "db": self.db
        })

        levels = {}
        for level in ["L0", "L1", "L2", "L3"]:
            c = self.compressor.compress(result, level)
            levels[level] = {
                "char_count": c["char_count"],
                "line_count": c["line_count"],
                "sample": c["text"][:100],
            }

        return {
            "novel_id": novel_id,
            "chapter_num": chapter_num,
            "hard_count": result["hard_count"],
            "soft_count": result["soft_count"],
            "levels": levels,
            "best_level": self._recommend_level(levels),
        }

    def test_all_novels(self) -> dict:
        """Test across all novels with generated chapters"""
        novels = self.db.list_novels()
        results = {}

        for novel in novels:
            nid = novel["id"]
            chs = novel.get("total_chapters", 0)
            if chs > 0:
                results[nid] = self.test_novel(nid, chs + 1)

        # Aggregate stats
        stats: dict[str, list[int]] = {"L0": [], "L1": [], "L2": [], "L3": []}
        for nid, r in results.items():
            for level in ["L0", "L1", "L2", "L3"]:
                stats[level].append(r["levels"][level]["char_count"])

        avg = {l: round(sum(v) / max(1, len(v))) for l, v in stats.items()}

        return {
            "novels_tested": len(results),
            "results": results,
            "average_char_counts": avg,
            "recommendation": f"推荐 L{['L0','L1','L2','L3'].index(self._best_overall(results))} ({avg.get(self._best_overall(results), '?')}字平均)",
        }

    def _recommend_level(self, levels: dict) -> str:
        """Recommend best level: smallest non-empty with max constraints"""
        for level in ["L3", "L2", "L1", "L0"]:
            if levels[level]["char_count"] > 0:
                return level
        return "L0"

    def _best_overall(self, results: dict) -> str:
        counts = {"L3": 0, "L2": 0, "L1": 0, "L0": 0}
        for r in results.values():
            for level in ["L3", "L2", "L1", "L0"]:
                if r["levels"][level]["char_count"] > 0:
                    counts[level] += 1
        return max(counts, key=lambda k: counts[k])
