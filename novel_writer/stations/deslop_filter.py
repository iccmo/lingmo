"""
工位：去AI味（集成 pi-deslop 5维评分体系）
输入：content
输出：filtered_content, deslop_score (0-50)
"""
import re

class DeslopFilter:
    name = "deslop_filter"
    min_chapter = 3  # 前3章不跑

    def run(self, ctx: dict) -> dict:
        text = ctx.get("content", "")
        if not text:
            return {"status": "skip", "score": 50}

        # 5维评分（每维10分）
        directness = self._score_directness(text)
        rhythm = self._score_rhythm(text)
        trust = self._score_trust(text)
        authenticity = self._score_authenticity(text)
        density = self._score_density(text)

        # 第6维：技法执行度（如果注入了技法指导）
        technique_guidance = ctx.get("technique_guidance", "")
        technique_score = 10
        technique_flags: list[str] = []
        if technique_guidance:
            technique_score, technique_flags = self._score_technique_application(
                text, technique_guidance
            )

        total = directness + rhythm + trust + authenticity + density + technique_score
        max_total = 60

        result = {
            "status": "ok",
            "score": total,
            "max_score": max_total,
            "dimensions": {
                "directness": directness, "rhythm": rhythm,
                "trust": trust, "authenticity": authenticity,
                "density": density, "technique_application": technique_score,
            },
            "grade": "A" if total >= 48 else "B" if total >= 36 else "C" if total >= 24 else "D",
            "needs_revision": total < 42,
        }
        if technique_flags:
            result["technique_flags"] = technique_flags
        return result

    def _score_directness(self, text: str) -> int:
        penalty = 0
        penalty += len(re.findall(r'可以说|值得注意的是|需要指出|显而易见', text)) * 2
        penalty += len(re.findall(r'突然|竟然|似乎|仿佛|不由得|只见|谁知', text))
        penalty += len(re.findall(r'——', text))  # em dash overuse
        return max(0, 10 - penalty)

    def _score_rhythm(self, text: str) -> int:
        sentences = [s for s in re.split(r'[。！？]', text) if s.strip()]
        if len(sentences) < 3: return 10
        lengths = [len(s) for s in sentences]
        # Penalize too-uniform sentence lengths
        avg = sum(lengths) / len(lengths)
        variance = sum((l - avg)**2 for l in lengths) / len(lengths)
        if variance < 50: return 6  # too uniform
        if variance < 100: return 8
        return 10

    def _score_trust(self, text: str) -> int:
        penalty = 0
        penalty += len(re.findall(r'显然|当然|毫无疑问|可想而知', text)) * 2
        penalty += len(re.findall(r'其实|事实上|说到底', text))
        return max(0, 10 - penalty)

    def _score_authenticity(self, text: str) -> int:
        penalty = 0
        penalty += len(re.findall(r'内心深处|灵魂深处|骨子里', text)) * 2
        penalty += len(re.findall(r'缓缓|轻轻|微微一笑|淡淡', text))
        return max(0, 10 - penalty)

    def _score_density(self, text: str) -> int:
        chars = len(text.replace('\n', '').replace(' ', ''))
        sentences = len([s for s in re.split(r'[。！？]', text) if s.strip()])
        if sentences == 0: return 10
        # Optimal: 15-30 chars per sentence
        avg_chars = chars / sentences
        if 15 <= avg_chars <= 30: return 10
        if 10 <= avg_chars <= 40: return 8
        if 5 <= avg_chars <= 50: return 6
        return 4

    def _score_technique_application(self, text: str, guidance: str) -> tuple[int, list[str]]:
        """Check if technique guidance was followed. Returns (score, flags)."""
        score = 10
        flags: list[str] = []

        # ── Check: "砍掉心理描写" / "不要心理描写" ──
        if any(w in guidance for w in ["心理描写", "内心独白", "心理活动"]):
            psych_patterns = [
                r'他想[到起]', r'她觉得?', r'心里', r'内心',
                r'意识到', r'感到', r'觉得', r'明白[了过]',
                r'知道.*了', r'想起', r'回忆',
            ]
            psych_count = sum(len(re.findall(p, text)) for p in psych_patterns)
            if psych_count > 8:
                score -= 4
                flags.append(f"技法未执行：{psych_count}处心理描写（要求砍掉）")
            elif psych_count > 4:
                score -= 2
                flags.append(f"技法部分执行：仍有{psych_count}处心理描写")

        # ── Check: "物件先行" / "用物件承载情绪" ──
        if any(w in guidance for w in ["物件", "物体", "物品", "东西"]):
            obj_count = len(re.findall(r'[把拿握攥捧端举触摸擦拭敲打扔摔]', text))
            if obj_count < 5:
                score -= 2
                flags.append(f"技法未执行：物件动作不足({obj_count}处)")

        # ── Check: "冷处理" / "克制" / "不解释" ──
        if any(w in guidance for w in ["冷处理", "克制", "不解释", "不多说"]):
            explain_patterns = [r'因为', r'所以', r'于是', r'原来', r'这意味']
            explain_count = sum(len(re.findall(p, text)) for p in explain_patterns)
            if explain_count > 10:
                score -= 3
                flags.append(f"技法未执行：{explain_count}处因果解释（要求冷处理）")
            elif explain_count > 6:
                score -= 1
                flags.append(f"技法部分执行：仍有{explain_count}处解释")

        # ── Check: "用动作推情绪" / "只写动作" ──
        if any(w in guidance for w in ["只用动作", "动作推", "只写动作", "动作说话"]):
            emotion_words = re.findall(r'[喜怒哀乐恐惧悲忧恨爱怨怜羞惭窘](?!悦)', text)
            if len(emotion_words) > 5:
                score -= 3
                flags.append(f"技法未执行：{len(emotion_words)}处直接情绪词（要求用动作）")
            elif len(emotion_words) > 2:
                score -= 1
                flags.append(f"技法部分执行：仍有{len(emotion_words)}处情绪词")

        # ── Check: "短句" / "节奏快" ──
        if any(w in guidance for w in ["短句", "快节奏", "急促"]):
            sentences = [s for s in re.split(r'[。！？\n]', text) if s.strip()]
            if sentences:
                avg_len = sum(len(s) for s in sentences) / len(sentences)
                if avg_len > 25:
                    score -= 2
                    flags.append(f"技法未执行：平均句长{avg_len:.0f}字（要求短句）")

        return max(0, score), flags
