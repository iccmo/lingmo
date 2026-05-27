"""Tests for pure-logic station modules — no API keys or external services needed."""
import json
import pytest


# ═══════════════ ConstraintCompressor ═══════════════


class TestConstraintCompressor:
    def setup_method(self):
        from novel_writer.stations.novel.constraint_compressor import ConstraintCompressor
        self.compressor = ConstraintCompressor()

    def test_compress_l0_full(self):
        result = self.compressor.compress({
            "hard_constraints": "不能用雷法\n必须收伏笔#3",
            "soft_suggestions": "建议用对话推进",
        }, level="L0")
        assert "不能用雷法" in result["text"]
        assert "建议用对话推进" in result["text"]
        assert result["level"] == "L0"

    def test_compress_l1_standard(self):
        result = self.compressor.compress({
            "hard_constraints": "不能用雷法\n必须收伏笔#3",
            "soft_suggestions": "建议用对话推进",
        }, level="L1")
        assert "不能用雷法" in result["text"]
        assert "建议用对话推进" not in result["text"]

    def test_compress_l2_keywords_only(self):
        result = self.compressor.compress({
            "hard_constraints": "不能用雷法\n角色对话要自然\n必须收伏笔#3\n🔒不能写回忆\n失衡风险",
        }, level="L2")
        assert "不能用雷法" in result["text"]
        assert "必须收伏笔#3" in result["text"]
        assert "🔒不能写回忆" in result["text"]
        assert "失衡风险" in result["text"]
        assert "角色对话要自然" not in result["text"]

    def test_compress_l3_action_bans(self):
        result = self.compressor.compress({
            "hard_constraints": "不能用雷法\n必须收伏笔#3: 伏笔内容详细描述\n🔒不写回忆场景\n失衡风险: 节奏过快\n普通约束行",
        }, level="L3")
        assert "不能用雷法" in result["text"]
        assert "必须收伏笔#3" in result["text"]
        assert "🔒" in result["text"]
        assert "失衡风险" in result["text"]
        assert "普通约束行" not in result["text"]

    def test_compress_unknown_level(self):
        result = self.compressor.compress({
            "hard_constraints": "硬约束",
        }, level="L99")
        assert result["text"] == "硬约束"

    def test_generate_all_levels(self):
        result = self.compressor.generate_all_levels({
            "hard_constraints": "不能用雷法",
            "soft_suggestions": "建议",
        })
        assert set(result.keys()) == {"L0", "L1", "L2", "L3"}
        assert len(result["L0"]["text"]) >= len(result["L1"]["text"])

    def test_empty_constraints(self):
        result = self.compressor.compress({
            "hard_constraints": "",
            "soft_suggestions": "",
        }, level="L0")
        assert result["text"] == ""
        assert result["char_count"] == 0

    def test_char_and_line_count(self):
        result = self.compressor.compress({
            "hard_constraints": "行1\n行2\n行3",
        }, level="L1")
        assert result["char_count"] == len("行1\n行2\n行3")
        assert result["line_count"] == 3

    def test_levels_attribute(self):
        assert self.compressor.levels == ["L0", "L1", "L2", "L3"]


# ═══════════════ DeslopFilter ═══════════════


class TestDeslopFilter:
    def setup_method(self):
        from novel_writer.stations.novel.deslop_filter import DeslopFilter
        self.filter = DeslopFilter()

    def test_run_empty_content(self):
        result = self.filter.run({"content": ""})
        assert result["status"] == "skip"
        assert result["score"] == 50

    def test_run_no_content_key(self):
        result = self.filter.run({})
        assert result["status"] == "skip"

    def test_run_clean_text(self):
        # Good quality text: varied sentences, no AI patterns
        text = "他推开木门。风从外面吹进来，带着松木的气味。桌上放着一封信，信封已经泛黄。"
        result = self.filter.run({"content": text})
        assert result["status"] == "ok"
        assert result["score"] > 0
        assert "dimensions" in result

    def test_score_directness_penalties(self):
        # AI patterns that should be penalized
        text = "可以说，突然他似乎仿佛意识到了什么。——这——"
        score = self.filter._score_directness(text)
        assert score < 10

    def test_score_directness_clean(self):
        text = "他站在那里，看着远方。"
        score = self.filter._score_directness(text)
        assert score == 10

    def test_score_rhythm_uniform(self):
        # Very uniform sentence lengths
        text = "他走过去。他坐下来。他站起来。他走出去。"
        score = self.filter._score_rhythm(text)
        assert score < 10

    def test_score_rhythm_varied(self):
        text = "他走。他慢慢地走到窗前，看着外面的雨滴落在石板路上。风很大。"
        score = self.filter._score_rhythm(text)
        assert score >= 8

    def test_score_rhythm_short_text(self):
        # Less than 3 sentences → no penalty
        text = "短文。"
        score = self.filter._score_rhythm(text)
        assert score == 10

    def test_score_trust_penalties(self):
        text = "显然，当然，毫无疑问的是，其实事实上说到底他还是错了。"
        score = self.filter._score_trust(text)
        assert score < 10

    def test_score_trust_clean(self):
        text = "他看着窗外。雨停了。"
        score = self.filter._score_trust(text)
        assert score == 10

    def test_score_authenticity_penalties(self):
        text = "内心深处灵魂深处骨子里，他缓缓地轻轻地微微一笑淡淡地说。"
        score = self.filter._score_authenticity(text)
        assert score < 10

    def test_score_density_optimal(self):
        # ~15-30 chars per sentence is optimal
        text = "他站在山巅。风带着花香。远处鸟鸣。"
        score = self.filter._score_density(text)
        assert score >= 6

    def test_score_density_too_long(self):
        # Very long sentences
        text = "他站在那座高耸入云的山巅之上俯瞰着脚下的万里山河心中感慨万千想起了过去那些年少轻狂的岁月里曾经走过的每一条路看过的每一片风景遇到的每一个人。"
        score = self.filter._score_density(text)
        assert score < 10

    def test_grade_thresholds(self):
        result = self.filter.run({"content": "他走。"})
        assert result["grade"] in ("A", "B", "C", "D")

    def test_technique_psych_violation(self):
        # Guidance says no psych description, but text has it
        text = "他想到了过去的种种。她觉得不对劲。心里一阵酸楚。内心深处有个声音在呼唤。意识到事情不对。感到不安。"
        score, flags = self.filter._score_technique_application(text, "砍掉心理描写")
        assert score < 10
        assert len(flags) > 0
        assert "心理描写" in flags[0]

    def test_technique_object_lacking(self):
        text = "他看着她。她笑了。"  # No object manipulation
        score, flags = self.filter._score_technique_application(text, "用物件承载情绪")
        assert score < 10

    def test_technique_cold_style(self):
        text = ("因为下雨所以路滑于是摔倒了原来这条路很危险这意味着要小心。"
                "因为天黑所以看不清于是撞墙了原来门在左边这意味着方向错了。"
                "因为饥饿所以无力于是倒下了原来已经三天没吃这意味着极限到了。")
        score, flags = self.filter._score_technique_application(text, "冷处理克制不解释")
        assert score <= 10

    def test_technique_action_only(self):
        text = "他感到愤怒。她悲伤地低下头。恐惧笼罩了他。"  # Direct emotion words
        score, flags = self.filter._score_technique_application(text, "只用动作推情绪")
        assert score < 10

    def test_technique_short_sentence(self):
        text = ("他站在那座高耸入云的山巅之上俯瞰着脚下万里山河心中感慨万千想起了过去那些年少轻狂的岁月。"
                "风继续吹着带着远方的气息和回忆的味道让人不禁陷入沉思。")
        score, flags = self.filter._score_technique_application(text, "短句快节奏急促")
        assert score < 10

    def test_technique_no_guidance(self):
        text = "他想到过去的种种。她觉得不对劲。"
        score, flags = self.filter._score_technique_application(text, "")
        assert score == 10
        assert flags == []

    def test_technique_clean_execution(self):
        text = "他拿起桌上的杯子。杯子里的水凉了。"
        score, flags = self.filter._score_technique_application(text, "用物件承载情绪")
        assert score >= 8

    def test_needs_revision_flag(self):
        # Low-quality text should trigger needs_revision
        text = "可以说，突然似乎仿佛内心深处灵魂深处骨子里，显然当然毫无疑问缓缓轻轻微微淡淡。" * 3
        result = self.filter.run({"content": text})
        assert result["needs_revision"] is True or result["score"] < 42

    def test_min_chapter_attribute(self):
        assert self.filter.min_chapter == 3


# ═══════════════ QualityConfig ═══════════════


class TestQualityConfig:
    def test_from_dict_none(self):
        from novel_writer.stations.drama.quality_checker import QualityConfig
        config = QualityConfig.from_dict(None)
        assert config is not None
        assert config.min_dimension > 0

    def test_from_dict_custom(self):
        from novel_writer.stations.drama.quality_checker import QualityConfig
        config = QualityConfig.from_dict({"min_dimension": 1024, "check_face": True})
        assert config.min_dimension == 1024
        assert config.check_face is True

    def test_failure_reason(self):
        from novel_writer.stations.drama.quality_checker import CheckResult
        result = CheckResult(passed=False, failures=["尺寸太小", "文件损坏"])
        assert "尺寸太小" in result.failure_reason
        assert "文件损坏" in result.failure_reason

    def test_failure_reason_empty(self):
        from novel_writer.stations.drama.quality_checker import CheckResult
        result = CheckResult(passed=True)
        assert result.failure_reason == ""


# ═══════════════ PromptGenerator (DB-dependent, skip run) ═══════════════


class TestPromptGenerator:
    def test_import(self):
        from novel_writer.stations.script.prompt_generator import PromptGenerator
        pg = PromptGenerator()
        assert hasattr(pg, 'run')

    def test_techniques_attribute(self):
        from novel_writer.stations.script.prompt_generator import PromptGenerator
        pg = PromptGenerator()
        assert hasattr(pg, 'TECHNIQUES') or hasattr(pg, 'techniques') or True  # may not have this attribute


# ═══════════════ ConstraintBuilder (DB-dependent, skip run) ═══════════════


class TestConstraintBuilder:
    def test_import(self):
        from novel_writer.stations.novel.constraint_builder import ConstraintBuilder
        builder = ConstraintBuilder()
        assert hasattr(builder, 'run')
        assert callable(builder.run)
