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

        total = directness + rhythm + trust + authenticity + density

        return {
            "status": "ok",
            "score": total,
            "dimensions": {"directness": directness, "rhythm": rhythm, "trust": trust, "authenticity": authenticity, "density": density},
            "grade": "A" if total >= 40 else "B" if total >= 30 else "C" if total >= 20 else "D",
            "needs_revision": total < 35,
        }

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
