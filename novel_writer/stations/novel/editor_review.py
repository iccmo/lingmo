"""
工位：编辑审稿
输入：content, quality_issues, novel_id, chapter_num
输出：feedback (行级), targeted_rewrite (修改后文本)
"""
import re

class EditorReview:
    name = "editor_review"
    min_quality = 0.6  # Only run if quality >= 0.6

    def run(self, ctx: dict) -> dict:
        """
        规则版编辑审稿（零API）。
        LLM版在 server.py _editor_review 中。
        """
        content = ctx.get("content", "")
        quality_issues = ctx.get("quality_issues", [])
        chapter_num = ctx.get("chapter_num", 0)
        novel_id = ctx.get("novel_id", "")
        db = ctx.get("db")

        if not content:
            return {"status": "skip", "reason": "no_content"}

        findings = []

        # Check 1: Sentence length uniformity
        sentences = [s for s in re.split(r'[。！？]', content) if s.strip()]
        if len(sentences) >= 5:
            lengths = [len(s) for s in sentences]
            avg = sum(lengths) / len(lengths)
            uniform = sum(1 for l in lengths if abs(l - avg) < 5) / len(lengths)
            if uniform > 0.6:
                findings.append({"type": "rhythm", "severity": "warning",
                    "description": f"句长过于均匀（{avg:.0f}字/句），节奏单调",
                    "fix": "交替使用长短句"})

        # Check 2: Dialogue density
        dialogue_chars = len(re.findall(r'「[^」]*」', content))
        total_chars = len(content.replace('\n', '').replace(' ', ''))
        dialogue_ratio = dialogue_chars / max(1, total_chars)
        if dialogue_ratio < 0.1 and total_chars > 500:
            findings.append({"type": "dialogue", "severity": "warning",
                "description": "对话占比过低，可能信息密度过大",
                "fix": "插入1-2段对话缓解节奏"})

        # Check 3: Opening strength
        first_100 = content[:100]
        has_hook = bool(re.search(r'[？?！!…]', first_100))
        has_sense = bool(re.search(r'看|见|听|闻|触|摸|冷|热|疼|痛', first_100))
        if not has_hook and not has_sense:
            findings.append({"type": "opening", "severity": "warning",
                "description": "开头缺乏钩子或感官细节",
                "fix": "加入一个身体感受或未完成的动作"})

        # Check 4: Paragraph length
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        long_paragraphs = [p for p in paragraphs if len(p) > 500]
        if long_paragraphs:
            findings.append({"type": "structure", "severity": "info",
                "description": f"{len(long_paragraphs)}个段落超过500字",
                "fix": "拆分长段落"})

        severity_counts = {"error": 0, "warning": 0, "info": 0}
        for f in findings:
            severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

        return {
            "status": "ok",
            "findings": findings,
            "total_issues": len(findings),
            "severity_counts": severity_counts,
            "needs_rewrite": severity_counts["error"] > 0,
        }
