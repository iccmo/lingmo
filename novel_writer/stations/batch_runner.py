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
