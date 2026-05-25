"""
工位：圣经提取
输入：novel_id, chapter_num, content, title
输出：提取的角色/伏笔/地点/时间线数量
"""
import json, re

class BibleExtractor:
    name = "bible_extractor"
    required_every_chapter = True

    def run(self, ctx: dict) -> dict:
        """
        从 server.py _extract_story_bible 移植。
        如果 LLM 可用就用 LLM 提取，否则用规则兜底。
        """
        novel_id = ctx["novel_id"]
        chapter_num = ctx["chapter_num"]
        content = ctx.get("content", "")
        title = ctx.get("title", "")
        db = ctx["db"]

        if not content:
            return {"status": "no_content", "extracted": 0}

        # Try rules-based extraction (zero API cost)
        extracted = self._rules_extract(novel_id, chapter_num, content, title, db)

        return {
            "status": "ok",
            "method": "rules",
            "extracted": sum(extracted.values()),
            "details": extracted,
        }

    def _rules_extract(self, novel_id: str, chapter_num: int, content: str, title: str, db) -> dict:
        """Rules-based extraction from chapter content."""
        counts = {"characters": 0, "foreshadowing": 0, "locations": 0, "timeline": 0}

        # Characters: detect names mentioned (from existing characters table)
        novel = db.get_novel(novel_id) or {}
        known_names = [c.get("name", "") for c in (novel.get("characters") or []) if c.get("name")]
        for name in known_names:
            if name and name in content:
                # Check if state already exists for this chapter
                exists = [c for c in (db.get_character_state(novel_id, chapter_num) or [])
                         if c["char_name"] == name]
                if not exists:
                    try:
                        db.save_character_state(novel_id, chapter_num, name,
                            emotion=self._detect_emotion(content, name),
                            physical_state="健康",
                            goal="未知",
                            location=self._detect_location(content),
                        )
                        counts["characters"] += 1
                    except Exception:
                        pass

        # Foreshadowing: detect mystery/intrigue signals
        mystery_signals = ["秘密", "隐瞒", "真相", "不对劲", "奇怪", "异常", "从未", "没人知道"]
        if any(s in content for s in mystery_signals):
            try:
                signal_text = next((s for s in mystery_signals if s in content), "")
                db.save_foreshadowing(novel_id, chapter_num,
                    f"第{chapter_num}章出现{signal_text}信号",
                    hint_text=content[content.find(signal_text)-20:content.find(signal_text)+30] if signal_text else "",
                )
                counts["foreshadowing"] += 1
            except Exception:
                pass

        # Timeline
        try:
            db.save_timeline_event(novel_id, chapter_num,
                absolute_time=f"第{chapter_num}章",
                relative_time="未知",
                event_summary=(content[:100] if content else title),
            )
            counts["timeline"] += 1
        except Exception:
            pass

        return counts

    def _detect_emotion(self, content: str, name: str) -> str:
        context = content[max(0, content.find(name)-50):content.find(name)+100] if name in content else content[:200]
        emotions = {"怒": "愤怒", "恨": "愤怒", "哭": "悲伤", "泪": "悲伤", "笑": "愉快", "怕": "恐惧"}
        for key, emo in emotions.items():
            if key in context: return emo
        return "中性"

    def _detect_location(self, content: str) -> str:
        locs = re.findall(r'(?:在|到|从|去)(.{2,6}(?:山|镇|城|殿|阁|院|府|楼|谷|峰|岛|村|市|区))', content[:500])
        return locs[0] if locs else "未知"
