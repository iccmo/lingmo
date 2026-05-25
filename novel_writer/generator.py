"""AI 章节生成引擎 — 支持全自动模式和创作者模式"""

import json
import random
import re
import time
from dataclasses import dataclass, field

from openai import OpenAI

from .config import Config, config
from .story_state import ChapterMeta, StoryState

# ==================== 数据结构 ====================

@dataclass
class DraftOption:
    """一个草稿走向"""
    id: str                # "A" / "B" / "C"
    title: str             # 章节标题
    direction: str         # 一句话方向概述
    preview: str           # 300-500 字开头预览
    hook: str              # 结尾钩子


@dataclass
class StyleProfile:
    """每个小说独立的风格参数档案 — 由数据驱动演化"""
    novel_id: str = ""
    target_word_count: tuple = (1800, 2200)
    hook_interval_words: int = 600
    dialogue_ratio: tuple = (0.35, 0.55)
    paragraph_len: tuple = (50, 150)
    opening_type: str = "atmosphere"
    hook_types: list = field(default_factory=lambda: ["对话中断","信息不对称","物品悬念"])
    pace_pattern: str = "强弱交替"
    scene_changes_per_chapter: int = 3
    title_style: str = "意象"
    title_max_chars: int = 6
    climax_types: list = field(default_factory=lambda: ["打脸","突破","揭秘"])
    avoid_cliches: list = field(default_factory=list)
    special_rules: list = field(default_factory=list)
    quality_rules: list = field(default_factory=list)  # 体裁专项质检规则
    version: int = 1
    updated_at: str = ""

    # 精装层 — 故事意识
    emotional_budget: dict = field(default_factory=lambda: {
        "anxiety": 5,         # 当前焦虑度 1-10
        "trust": 5,           # 信任度 1-10
        "satisfaction": 5,    # 满足度 1-10
        "target_anxiety": 6,  # 本章目标焦虑度
        "min_paragraphs": 8,  # 最少段落数
    })
    rhythm_mode: str = "auto"  # auto / tension / relief / speed / linger
    gap_rule: int = 3          # 每章最少"不解释"元素数
    writer_voice: str = "爆款网文"  # 作家声音 key
    knowledge_base: str = ""         # 知识基底：研究中发现的真实细节，注入每章提示
    reading_level: str = "adult"     # adult / young_adult / literary — 阅读难度级别
    knowledge_confidence: dict = field(default_factory=dict)  # 知识可信度标记 {chapter: warning}
    thought_system: str = ""         # 思想系统：贯穿全书的哲学/价值观链条
    central_question: str = ""       # 核心追问：全书反复在问但从不给出唯一答案的问题
    chapter_questions: dict = field(default_factory=dict)  # 每章对核心追问的探索角度 {ch_num: angle}
    soul_statement: str = ""         # 书的灵魂：它相信什么、害怕什么、希望什么——每章生成前唤起
    last_chapter_emotion: str = ""   # 上一章留下的情绪——本章开头带它一程，然后转向
    open_questions: list[str] = field(default_factory=list)   # 当前未解答的问题（好奇心账本）
    regeneration_log: list[dict] = field(default_factory=list)  # 章节重写记录
    symbols: list[str] = field(default_factory=list)            # 贯穿全书的符号系统
    target_platform: str = "fanqie"  # fanqie / qidian / jinjiang / universal
    classic_threshold: float = 0.78  # 经典门槛：前5章均分低于此值→推倒重来
    max_iterations: int = 3          # 最多尝试几轮（每轮换不同参数）
    expected_reader_belief: str = ""  # 读者此刻对"真相"的猜测——本章先确认再推翻
    rupture_chapter: int = 0          # 蓄意破坏规则的章节号（0=自动检测触发条件）


@dataclass
class QualityReport:
    """质量检测结果"""
    passed: bool
    word_count: int
    issues: list[str] = field(default_factory=list)



# ═══════════════════ Style Pools ═══════════════════

STYLE_POOL: dict[str, StyleProfile] = {
    "玄幻": StyleProfile(
        target_word_count=(1800, 2200), hook_interval_words=600,
        dialogue_ratio=(0.35, 0.50), opening_type="hybrid",
        hook_types=["对话中断","信息不对称","物品悬念","氛围递进"],
        pace_pattern="强弱交替", scene_changes_per_chapter=3,
        title_style="意象", climax_types=["突破","打脸","揭秘"],
        quality_rules=["每章至少1个战斗/冲突场景","境界提升必须有灵力流动描写","丹药/功法需与已有设定一致"],
    ),
    "都市": StyleProfile(
        target_word_count=(1600, 2000), hook_interval_words=500,
        dialogue_ratio=(0.40, 0.55), opening_type="impact",
        hook_types=["对话中断","信息不对称","动作中断"],
        pace_pattern="强弱交替", scene_changes_per_chapter=4,
        title_style="悬念", climax_types=["打脸","揭秘","收获"],
        quality_rules=["爽点必须在主角视角下呈现","至少1个打脸/碾压名场面","配角反应必须写到位（围观群众震惊/嘲讽/反转）"],
    ),
    "悬疑": StyleProfile(
        target_word_count=(2000, 2500), hook_interval_words=800,
        dialogue_ratio=(0.45, 0.60), opening_type="atmosphere",
        hook_types=["氛围递进","物品悬念","信息不对称","旧钩回咬"],
        pace_pattern="渐进加速", scene_changes_per_chapter=2,
        title_style="意象", climax_types=["揭秘","反转"],
        quality_rules=["每章至少1个线索/伏笔推进","谜团不能在本章全部解开","人物动机必须有隐藏层（表面与真实不一致）"],
    ),
    "科幻末世": StyleProfile(
        target_word_count=(1800, 2200), hook_interval_words=600,
        dialogue_ratio=(0.30, 0.45), opening_type="dilemma",
        hook_types=["信息不对称","动作中断","物品悬念"],
        pace_pattern="三强一缓", scene_changes_per_chapter=3,
        title_style="悬念", climax_types=["揭秘","突破","收获"],
        quality_rules=[
            "资源/物资数量必须前后一致",
            "幸存者心理状态要有递进",
            "末世规则一旦建立不能随意更改",
            "技术设定必须通过场景承载——不单独出现超过150字的纯世界观说明段落",
            "AI/系统的行为必须有逻辑约束（不能万能），每次能力展示要揭示一条隐藏限制",
            "情感冲突优先于技术冲突——读者关心的是角色怎么了，不是科技怎么了",
        ],
    ),
    "系统流": StyleProfile(
        target_word_count=(1500, 2000), hook_interval_words=500,
        dialogue_ratio=(0.35, 0.50), opening_type="dilemma",
        hook_types=["对话中断","信息不对称","物品悬念","动作中断"],
        pace_pattern="强弱交替", scene_changes_per_chapter=4,
        title_style="剧透", climax_types=["打脸","突破","收获"],
        quality_rules=["系统面板/数值必须前后一致","打脸前必须有数值对比铺垫","每章至少1次系统通知/任务触发"],
    ),
    "官场": StyleProfile(
        target_word_count=(2000, 2800), hook_interval_words=600,
        dialogue_ratio=(0.50, 0.65), opening_type="hybrid",
        hook_types=["信息不对称","对话中断","旧钩回咬"],
        pace_pattern="渐进加速", scene_changes_per_chapter=2,
        title_style="意象", climax_types=["揭秘","反转"],
        quality_rules=[
            "每章至少涉及一个真实感强的政治/经济时事要素（土地财政、反腐、改制、地方债、产业政策等），融入剧情不显生硬",
            "每章至少出现一个玄学/风水/命理元素（如盲派命理、玄空风水、奇门遁甲、紫微斗数），展现主角深不可测的传统文化修养",
            "每章必须揭露至少一层官场黑暗面——利益输送、权钱交易、站队博弈、晋升内幕、政商勾连",
            "必须展现政策落地后对底层民众的冲击——拆迁户的绝望、基层公务员的挣扎、边缘人的失语",
        ],
        special_rules=[
            "现实主义优先：剧情跨度至少3天（不是所有事发生在同一天），真实的官场一个批文等三个月、一个项目等半年",
            "加入无聊但真实的细节：填表、等签字、会议室里耗时间、酒局上的虚与委蛇、办公室政治八卦",
            "主角每章必须做至少一个主动决策，决策要有政治博弈的算计，但不是每步都赢——真实世界胜率不到六成",
            "对话必须真实：该骂就骂——私下场合用他妈的、操、老子、你懂个屁等日常口头禅。正式场合用官腔套话。两会切换自然，不要像过家家",
            "揭露的权力操作要具体：不是'他腐败'而是'他把那块地以低于市场价30%的价格卖给了小舅子的公司'",
            "每个正面交锋前至少铺垫2-3天的暗流涌动——私下通话、饭局试探、外围打听",
        ],
    ),
    "女频": StyleProfile(
        target_word_count=(1800, 2200), hook_interval_words=600,
        dialogue_ratio=(0.45, 0.60), opening_type="impact",
        hook_types=["对话中断","信息不对称","氛围递进"],
        pace_pattern="强弱交替", scene_changes_per_chapter=3,
        title_style="意象", climax_types=["揭秘","打脸","收获"],
        quality_rules=["男女主互动每章至少1处（对话/碰撞/内心戏）","感情线必须有递进（不能原地踏步）","女主行为能力不能弱化（独立人格）"],
    ),
    "武侠": StyleProfile(
        target_word_count=(2000, 2800), hook_interval_words=700,
        dialogue_ratio=(0.35, 0.55), opening_type="hybrid",
        hook_types=["动作中断","信息不对称","对话中断"],
        pace_pattern="渐进加速", scene_changes_per_chapter=3,
        title_style="意象", climax_types=["打脸","突破","揭秘"],
        quality_rules=["每章至少1个打斗/对决场景","武学逻辑必须自洽","江湖道义与主角底线不能前后矛盾"],
    ),
    "仙侠": StyleProfile(
        target_word_count=(2000, 3000), hook_interval_words=700,
        dialogue_ratio=(0.30, 0.50), opening_type="atmosphere",
        hook_types=["氛围递进","物品悬念","信息不对称"],
        pace_pattern="渐进加速", scene_changes_per_chapter=2,
        title_style="意象", climax_types=["突破","揭秘","反转"],
        quality_rules=["修炼体系必须前后一致","每章至少1处修行/突破描写","天道/因果/气运概念需贯穿"],
    ),
    "历史": StyleProfile(
        target_word_count=(2000, 3000), hook_interval_words=800,
        dialogue_ratio=(0.40, 0.55), opening_type="hybrid",
        hook_types=["信息不对称","对话中断","旧钩回咬"],
        pace_pattern="渐进加速", scene_changes_per_chapter=2,
        title_style="意象", climax_types=["揭秘","反转","打脸"],
        quality_rules=["历史细节必须准确（官职/地名/社会结构）","穿越者优势每章至少1处展现","制度斗争逻辑严谨"],
    ),
    "游戏": StyleProfile(
        target_word_count=(1600, 2200), hook_interval_words=500,
        dialogue_ratio=(0.30, 0.50), opening_type="dilemma",
        hook_types=["物品悬念","信息不对称","动作中断"],
        pace_pattern="强弱交替", scene_changes_per_chapter=4,
        title_style="剧透", climax_types=["突破","打脸","收获"],
        quality_rules=["数值/等级/装备描述前后一致","每章至少1次打斗/副本/掉落","系统提示每章出现至少1次"],
    ),
    "灵异": StyleProfile(
        target_word_count=(1800, 2400), hook_interval_words=500,
        dialogue_ratio=(0.40, 0.55), opening_type="atmosphere",
        hook_types=["氛围递进","物品悬念","旧钩回咬"],
        pace_pattern="渐进加速", scene_changes_per_chapter=2,
        title_style="悬念", climax_types=["揭秘","反转"],
        quality_rules=["恐怖氛围逐章递增","每章至少1处诡异/超自然事件","灵异规则必须自洽且不可过度解释"],
    ),
    "同人": StyleProfile(
        target_word_count=(2000, 2800), hook_interval_words=600,
        dialogue_ratio=(0.45, 0.60), opening_type="impact",
        hook_types=["信息不对称","对话中断","旧钩回咬"],
        pace_pattern="强弱交替", scene_changes_per_chapter=3,
        title_style="悬念", climax_types=["揭秘","打脸","反转"],
        quality_rules=["角色性格必须忠于原作","画风/世界观不崩","在原作基础上创新而非照搬"],
    ),
    "轻小说": StyleProfile(
        target_word_count=(1500, 2000), hook_interval_words=500,
        dialogue_ratio=(0.50, 0.65), opening_type="impact",
        hook_types=["对话中断","信息不对称"],
        pace_pattern="强弱交替", scene_changes_per_chapter=3,
        title_style="悬念", climax_types=["打脸","揭秘","收获"],
        quality_rules=["对话轻松幽默","章节节奏轻快","情节反转不影响整体氛围"],
    ),
    "体育": StyleProfile(
        target_word_count=(1800, 2400), hook_interval_words=700,
        dialogue_ratio=(0.35, 0.50), opening_type="dilemma",
        hook_types=["动作中断","信息不对称","物品悬念"],
        pace_pattern="三强一缓", scene_changes_per_chapter=3,
        title_style="悬念", climax_types=["突破","打脸"],
        quality_rules=["比赛描述专业且紧张","每章至少1场比赛/训练场景","竞技逻辑合理不可超现实"],
    ),
    "军事": StyleProfile(
        target_word_count=(2000, 2800), hook_interval_words=700,
        dialogue_ratio=(0.30, 0.45), opening_type="dilemma",
        hook_types=["信息不对称","动作中断"],
        pace_pattern="三强一缓", scene_changes_per_chapter=3,
        title_style="悬念", climax_types=["突破","揭秘"],
        quality_rules=["军事术语/战术逻辑必须专业","每章至少1处战斗/指挥决策","武器性能/战争规则前后一致"],
    ),
    "奇幻": StyleProfile(
        target_word_count=(2000, 2800), hook_interval_words=700,
        dialogue_ratio=(0.35, 0.50), opening_type="atmosphere",
        hook_types=["氛围递进","物品悬念","信息不对称"],
        pace_pattern="渐进加速", scene_changes_per_chapter=2,
        title_style="意象", climax_types=["揭秘","反转","突破"],
        quality_rules=["魔法/种族/世界规则前后一致","每章至少1处奇幻设定展现","主角成长曲线合理"],
    ),
    "二次元": StyleProfile(
        target_word_count=(1500, 2000), hook_interval_words=500,
        dialogue_ratio=(0.50, 0.65), opening_type="impact",
        hook_types=["对话中断","信息不对称","物品悬念"],
        pace_pattern="强弱交替", scene_changes_per_chapter=4,
        title_style="悬念", climax_types=["打脸","揭秘","收获"],
        quality_rules=["二次元画风贯穿（中二/萌系/吐槽）","战斗/能力设定有燃点","角色萌点每章至少1处"],
    ),
    "种田": StyleProfile(
        target_word_count=(1800, 2200), hook_interval_words=800,
        dialogue_ratio=(0.40, 0.55), opening_type="atmosphere",
        hook_types=["氛围递进","信息不对称","物品悬念"],
        pace_pattern="渐进加速", scene_changes_per_chapter=2,
        title_style="意象", climax_types=["收获","揭秘"],
        quality_rules=["资源积累过程细致合理","每章至少1处建设/生产/收获","生活气息浓厚但节奏不拖沓"],
    ),
    "无限流": StyleProfile(
        target_word_count=(1800, 2400), hook_interval_words=500,
        dialogue_ratio=(0.35, 0.50), opening_type="dilemma",
        hook_types=["信息不对称","物品悬念","动作中断"],
        pace_pattern="三强一缓", scene_changes_per_chapter=4,
        title_style="悬念", climax_types=["突破","揭秘","反转"],
        quality_rules=["副本/世界的规则每篇自洽但不重复","每次轮回/穿越必有成长/收获","任务/系统提示每章至少1次"],
    ),
}

GENRE_TO_STYLE: dict[str, str] = {
    # 玄幻/仙侠/武侠体系
    "玄幻":"玄幻", "仙侠":"仙侠", "武侠":"武侠",
    "东方玄幻":"玄幻", "西方奇幻":"奇幻", "剑与魔法":"奇幻",
    # 都市/现实
    "都市":"都市", "现实":"都市", "官场":"官场",
    "职场":"都市", "医疗":"都市", "刑侦":"都市",
    # 悬疑/灵异/恐怖
    "悬疑":"悬疑", "灵异":"灵异", "恐怖":"灵异",
    "推理":"悬疑", "惊悚":"灵异",
    # 科幻/末世
    "科幻":"科幻末世", "末世":"科幻末世", "末日":"科幻末世",
    "星际":"科幻末世", "机甲":"科幻末世",
    # 系统/游戏
    "系统流":"系统流", "游戏":"游戏", "网游":"游戏",
    "电竞":"游戏", "虚拟现实":"游戏", "VR":"游戏",
    # 历史/架空
    "历史":"历史", "架空历史":"历史", "穿越":"历史",
    "朝代":"历史", "三国":"历史", "宋":"历史", "明":"历史",
    # 女频/言情
    "现代言情":"女频", "古代言情":"女频", "纯爱":"女频",
    "言情":"女频", "耽美":"女频", "百合":"女频",
    "女尊":"女频", "宫斗":"女频", "总裁":"女频",
    # 小众类型
    "同人":"同人", "二次元":"二次元", "轻小说":"轻小说",
    "动漫":"二次元", "综漫":"同人",
    "种田":"种田", "美食":"种田",
    "体育":"体育", "竞技":"体育", "足球":"体育", "篮球":"体育",
    "军事":"军事", "抗战":"军事", "特种兵":"军事",
    "无限流":"无限流", "诸天流":"无限流", "快穿":"无限流",
    # 奇幻/日系
    "奇幻":"奇幻", "魔幻":"奇幻", "西幻":"奇幻",
    # fallback
    "其他":"玄幻",
}


def _get_style_for_genre(genre: str) -> StyleProfile:
    """Get the default StyleProfile for a genre."""
    key = GENRE_TO_STYLE.get(genre, "玄幻")
    return STYLE_POOL.get(key, STYLE_POOL["玄幻"])


# ==================== 核心引擎 ====================

# ═══════════════════ Writer Voice System ═══════════════════

@dataclass
class WriterVoice:
    """作家声音 — 独立于体裁的风格层。同一个故事，不同声音写出来完全不同。"""
    name: str                            # 声音名称
    description: str                     # 一句话描述
    narrative_distance: str = "close"    # close(贴身POV) / medium(有限第三人称) / omniscient(全知)
    sentence_rhythm: str = "varied"      # short(短句为主) / varied(长短交替) / flowing(长句流水)
    unsaid_ratio: float = 0.3           # 留白比例：多少东西不直接说（0=全说, 1=几乎不说）
    moral_complexity: str = "gray"       # clear(黑白分明) / gray(灰色地带) / ambiguous(刻意模糊)
    imagery_density: str = "sparse"      # sparse(一个意象贯穿) / moderate(每章1-2个新意象) / rich(意象密集)
    dialogue_style: str = "natural"      # natural(日常口语) / stylized(风格化) / punchy(金句频出)
    special_rule: str = ""               # 自定义规则
    genre_adaptations: dict = field(default_factory=dict)  # 体裁适配：{genre: adaptation_rule}

# 预设作家声音
WRITER_VOICES: dict[str, WriterVoice] = {
    "金庸": WriterVoice(
        name="金庸", description="古典叙事，家国情怀，人物有成长弧",
        narrative_distance="omniscient", sentence_rhythm="flowing",
        unsaid_ratio=0.4, moral_complexity="gray", imagery_density="moderate",
        dialogue_style="stylized",
        special_rule="人物对话有古典韵味，不写脏话。打斗描写有招式名。每个角色都有自己的价值观，反派也有可敬之处。"
    ),
    "余华": WriterVoice(
        name="余华", description="冷感写实，用最简单的句子讲最残酷的事",
        narrative_distance="close", sentence_rhythm="short",
        unsaid_ratio=0.5, moral_complexity="ambiguous", imagery_density="sparse",
        dialogue_style="natural",
        special_rule="绝不用形容词煽情。用事实和细节让读者自己心碎。重复是武器——同一句话在不同章节重复出现，含义不同。",
        genre_adaptations={
            "玄幻": "余华写玄幻=把修仙写成生存。修炼不是升仙，是活下去的唯一方式。丹药不是宝贝，是救命稻草。被废修为不是丢面子，是丢了活路。不要写'他愤怒'——写'他的手在发抖，不是因为怕，是因为冷'。",
            "都市": "余华写都市=把城市当成废墟。每个打工人都是活着的人，只是活得不太好。租房、挤地铁、被裁——这些不是情节，是日常。死亡在隔壁，但今天要上班。",
        }
    ),
    "刘慈欣": WriterVoice(
        name="刘慈欣", description="硬科幻诗人，用宇宙尺度写人性",
        narrative_distance="omniscient", sentence_rhythm="flowing",
        unsaid_ratio=0.3, moral_complexity="gray", imagery_density="rich",
        dialogue_style="stylized",
        special_rule="用一个科学概念作为每章的情感支点。人类的渺小和伟大同时呈现。数据可以抒情——'1370年'比'很久'更有力。"
    ),
    "东野圭吾": WriterVoice(
        name="东野圭吾", description="推理外壳下的人性手术刀",
        narrative_distance="medium", sentence_rhythm="varied",
        unsaid_ratio=0.5, moral_complexity="ambiguous", imagery_density="sparse",
        dialogue_style="natural",
        special_rule="每章结尾反转的不是剧情，是读者对一个人的判断。一个人看起来是好人→看起来是坏人→其实是好人但做了不可原谅的事。"
    ),
    "爆款网文": WriterVoice(
        name="爆款网文", description="高密度爽点，快节奏强冲突",
        narrative_distance="close", sentence_rhythm="short",
        unsaid_ratio=0.1, moral_complexity="clear", imagery_density="sparse",
        dialogue_style="punchy",
        special_rule="每章至少2个爽点。打脸要打透——铺垫(憋屈)→反转(扬眉吐气)→余韵(围观群众反应)。主角不能连续失败超过2章。"
    ),
    "文学实验": WriterVoice(
        name="文学实验", description="打破叙事常规，让读者参与构建意义",
        narrative_distance="close", sentence_rhythm="varied",
        unsaid_ratio=0.7, moral_complexity="ambiguous", imagery_density="rich",
        dialogue_style="natural",
        special_rule="可以打破线性时间。第一人称和第三人称可以在同一章切换。有些段落可以是主角的日记/梦境/未寄出的信。结尾不一定有答案——留一个问题比给一个答案更有力。"
    ),
    "张爱玲": WriterVoice(
        name="张爱玲", description="都市情感解剖师，一句话戳穿所有体面",
        narrative_distance="close", sentence_rhythm="varied",
        unsaid_ratio=0.5, moral_complexity="ambiguous", imagery_density="moderate",
        dialogue_style="stylized",
        special_rule="对话里藏着刀——表面上聊天气，实际上在捅对方。比喻必须有痛感。写爱情但不相信爱情。每一个温柔的场景里都要埋一根刺。"
    ),
    "鲁迅": WriterVoice(
        name="鲁迅", description="冷眼看世界，用讽刺做手术刀",
        narrative_distance="medium", sentence_rhythm="short",
        unsaid_ratio=0.4, moral_complexity="gray", imagery_density="sparse",
        dialogue_style="stylized",
        special_rule="多写看客。群体比个体更丑陋。讽刺不用直说——写一件看似正常的事，让读者自己觉得不对劲。结尾可以用一句话把全篇翻过来。"
    ),
    "村上春树": WriterVoice(
        name="村上春树", description="爵士乐般的叙事，孤独但不绝望",
        narrative_distance="close", sentence_rhythm="flowing",
        unsaid_ratio=0.6, moral_complexity="ambiguous", imagery_density="moderate",
        dialogue_style="stylized",
        special_rule="日常和超现实无缝衔接——煮意面的时候猫突然说话了，不解释。音乐、食物、酒是常驻意象。主人公永远被动——事情发生在他身上，他不去找。孤独不是问题，伴侣只是背景。"
    ),
    "海明威": WriterVoice(
        name="海明威", description="冰山理论，只写露出水面的八分之一",
        narrative_distance="close", sentence_rhythm="short",
        unsaid_ratio=0.8, moral_complexity="ambiguous", imagery_density="sparse",
        dialogue_style="natural",
        special_rule="每句不超过15字。不用形容词。不用'他觉得''他想起'——直接写他做了什么。对话是两个人对着互相听不懂。省略就是力量——不写的永远比写的更重。",
        genre_adaptations={
            "玄幻": "你这章不是在写海明威。你是在用古龙的方式写玄幻。战斗只写结果不写过程——'剑光闪过。地上多了一只手。'。境界突破用一句话——'他坐在山洞里。三天后，他出来了。已经是筑基了。'。对话极简——高手见面不说话，喝完酒就走。",
            "都市": "都市版海明威=极简写实。不写'他很孤独'，写'他在便利店买了两个人的晚饭，收银员没问另一个人在哪'。工作场景只写动作——递材料、按电梯、看表。所有情感都在不说话的时候。",
            "科幻": "科幻版海明威=用极简写浩大。不解释技术原理。写'飞船出了问题'而不是'量子引擎的第三级冷却系统发生了热失控'。用最少的字写最大的空间——'窗外是银河。窗内是两个人。没说话。'",
        }
    ),
    "莫言": WriterVoice(
        name="莫言", description="魔幻现实主义，用泥土和血肉写史诗",
        narrative_distance="omniscient", sentence_rhythm="flowing",
        unsaid_ratio=0.2, moral_complexity="gray", imagery_density="rich",
        dialogue_style="stylized",
        special_rule="把最残忍的事用最华丽的语言写出来。感官描写极致——气味、温度、触感比视觉重要。一个村庄就是一个宇宙。肮脏和神圣共存，不区分。",
        genre_adaptations={
            "玄幻": "莫言写玄幻=不是飞升成仙，是在泥里打滚的修真。修炼资源是带着血腥味的。丹药有体温。飞剑割破的手掌流的是真实的血。不要写'灵气充沛'——写'空气里有一种青草的腥味'。门派斗争就是村口械斗那味儿。",
            "都市": "都市版莫言=把写字楼写成高粱地。资本斗争就是饥饿年代的争食。每一笔钱都有体温。每一个成功人士都带着洗不掉的出身泥巴。",
        }
    ),
    "马尔克斯": WriterVoice(
        name="马尔克斯", description="魔幻即日常，时间可以折叠",
        narrative_distance="omniscient", sentence_rhythm="flowing",
        unsaid_ratio=0.3, moral_complexity="gray", imagery_density="rich",
        dialogue_style="stylized",
        special_rule="最不可能的事用最平常的语气说。时间跳跃是叙事工具——这一句在现在，下一句在二十年后的未来，不解释。一个家庭的衰败就是整个世界的衰败。"
    ),
    "古龙": WriterVoice(
        name="古龙", description="留白武侠，一句话一个场景",
        narrative_distance="close", sentence_rhythm="short",
        unsaid_ratio=0.9, moral_complexity="ambiguous", imagery_density="sparse",
        dialogue_style="punchy",
        special_rule="每段不超过三句话。对话像枪战——快、准、不留情面。战斗只写结果不写过程。高手见面不说话，喝完酒就走。女人比剑更危险。",
        genre_adaptations={
            "玄幻": "古龙写玄幻=不需要解释力量体系。打斗前铺垫气氛——喝酒、看月亮、聊往事。打斗只一句——然后站着的人收剑。境界即心境，不是数据。法宝有名字、有故事、有个性。修炼最快的捷径是不修炼——想通了就突破。",
            "悬疑": "古龙写悬疑=谜底不重要，重要的是谁在撒谎。每章结尾不是真相揭露，是又一个人露出了可疑的一面。线索用对话递出，不写推理过程。",
        }
    ),
    "汪曾祺": WriterVoice(
        name="汪曾祺", description="人间烟火，用最淡的笔写最深的味",
        narrative_distance="close", sentence_rhythm="flowing",
        unsaid_ratio=0.5, moral_complexity="gray", imagery_density="moderate",
        dialogue_style="natural",
        special_rule="多写食物、植物、天气——这些比剧情重要。人物对话带着地方口音的味道。不批判任何人——连反派都有可爱之处。结尾就像结束一餐饭——自然、满足、没有多余的话。"
    ),
}

# ═══════════════════ Name System ═══════════════════

# --- Surnames by character ---
_SURNAME_GUYA     = ["慕","容","沈","顾","谢","温","裴","晏","卫","段"]   # 古雅温润
_SURNAME_DAQII    = ["萧","楚","陆","秦","霍","殷","江","商","钟","傅"]   # 大气磅礴
_SURNAME_QINGGUI  = ["苏","林","盛","程","许","周","陈","宋","季","叶"]   # 清贵端正
_SURNAME_FUXING   = ["欧阳","慕容","上官","令狐","独孤","南宫","夏侯","东方","皇甫","司马"]

# --- Given names by source ---
_GIVEN_SHIJING    = ["清扬","子衿","攸宁","静姝","燕婉","景行","清猗","鹿鸣","南有","乔木"]  # 诗经
_GIVEN_CHUCI      = ["正则","灵均","杜若","怀瑾","握瑜","望舒","云旗","兰皋","芳蔼","江离"]  # 楚辞
_GIVEN_TANGSHI    = ["清秋","长风","归舟","渡远","停云","孤帆","落照","烟渚","微雨","疏影"]  # 唐诗意境
_GIVEN_SHANSHUI   = ["临渊","栖岩","映月","听澜","落微","栖霞","漱玉","枕流","涵虚","叠翠"]  # 山水自然
_GIVEN_PINGE      = ["无咎","知微","知行","守拙","见素","怀仁","慎独","抱朴","养正","存诚"]  # 品格修养
_GIVEN_YIJING     = ["沉渊","寒舟","长渊","沧海","烟波","断鸿","残雪","孤鸿","暮云","霜天"]  # 意境苍茫

# --- Female-specific names (女性专用, 不在男频出现) ---
_GIVEN_FEMALE     = ["扶烟","念卿","雪棠","清辞","若水","青黛","素心","纤凝","惊鸿","霜序",
                     "映月","听澜","落微","望舒","杜若","芳蔼","静姝","燕婉","清猗"]

# --- Neutral/unisex names to exclude from male pool ---
_GIVEN_FEMININE_CODED = {"叠翠","芳蔼","静姝","燕婉","清猗","清辞","雪棠","扶烟","念卿",
                          "若水","青黛","素心","纤凝","惊鸿","霜序","映月","听澜","落微"}

# --- Male given by genre ---
_MALE_GIVEN_BY_GENRE: dict[str, list[str]] = {
    "玄幻":     _GIVEN_CHUCI + _GIVEN_YIJING + _GIVEN_SHANSHUI,
    "仙侠":     _GIVEN_CHUCI + _GIVEN_SHANSHUI,
    "武侠":     _GIVEN_PINGE + _GIVEN_TANGSHI,
    "都市":     _GIVEN_TANGSHI + _GIVEN_PINGE,
    "悬疑":     _GIVEN_YIJING + _GIVEN_SHANSHUI,
    "灵异":     _GIVEN_YIJING + _GIVEN_CHUCI,
    "科幻":     _GIVEN_TANGSHI + _GIVEN_SHANSHUI,
    "末世":     _GIVEN_YIJING + _GIVEN_PINGE,
    "系统流":   _GIVEN_PINGE + _GIVEN_TANGSHI,
    "历史":     _GIVEN_SHIJING + _GIVEN_CHUCI,
    "女频":     _GIVEN_FEMALE,
    "现代言情": _GIVEN_FEMALE,
    "古代言情": _GIVEN_FEMALE,
    "纯爱":     _GIVEN_FEMALE,
    "言情":     _GIVEN_FEMALE,
}

# --- Surname by genre ---
_SURNAME_BY_GENRE: dict[str, list[str]] = {
    "玄幻":     _SURNAME_GUYA + _SURNAME_DAQII + _SURNAME_FUXING,
    "仙侠":     _SURNAME_GUYA + _SURNAME_FUXING,
    "武侠":     _SURNAME_DAQII + _SURNAME_GUYA,
    "都市":     _SURNAME_QINGGUI,
    "悬疑":     _SURNAME_GUYA + _SURNAME_DAQII,
    "灵异":     _SURNAME_GUYA,
    "科幻":     _SURNAME_QINGGUI,
    "末世":     _SURNAME_DAQII + _SURNAME_QINGGUI,
    "系统流":   _SURNAME_QINGGUI,
    "历史":     _SURNAME_GUYA + _SURNAME_DAQII + _SURNAME_FUXING,
    "女频":     _SURNAME_GUYA + _SURNAME_QINGGUI + _SURNAME_FUXING,
    "现代言情": _SURNAME_QINGGUI + _SURNAME_GUYA,
    "古代言情": _SURNAME_GUYA + _SURNAME_FUXING,
    "纯爱":     _SURNAME_QINGGUI,
    "言情":     _SURNAME_GUYA + _SURNAME_QINGGUI,
}


# --- 声调: 1=阴平 2=阳平 3=上声 4=去声 ---
_PINYIN_TONE: dict[str, str] = {
    # 1声 (阴平)
    "清":"1","秋":"1","风":"1","归":"1","舟":"1","烟":"1","波":"1","霜":"1","天":"1","疏":"1",
    "听":"1","栖":"1","孤":"1","微":"1","青":"1","纤":"1","芳":"1","江":"1","书":"1","攸":"1",
    "萧":"1","苏":"1","温":"1","钟":"1","商":"1","东":"1","司":"1","欧":"1","花":"1","春":"1",
    "霄":"1","渊":"1","溪":"1","轻":"1","依":"1","幽":"1","笙":"1","松":"1","关":"1",
    # 2声 (阳平)
    "沉":"2","寒":"2","长":"2","停":"2","云":"2","明":"2","霞":"2","叠":"2","辞":"2",
    "扶":"2","言":"2","时":"2","林":"2","陈":"2","秦":"2","裴":"2","容":"2","留":"2",
    "阳":"2","南":"2","玄":"2","存":"2","怀":"2","无":"2","层":"2","华":"2","衡":"2",
    "寻":"2","年":"2","颜":"2","兰":"2","裘":"2","凭":"2","函":"2","奇":"2","恒":"2",
    "严":"2","原":"2","翎":"2","璃":"2","鳞":"2",
    # 3声 (上声)
    "远":"3","雪":"3","影":"3","水":"3","雨":"3","鸟":"3","古":"3","晚":"3","锦":"3",
    "沈":"3","楚":"3","柳":"3","许":"3","顾":"3","景":"3","守":"3","马":"3","野":"3",
    "渺":"3","紫":"3","隐":"3","简":"3","览":"3","芷":"3","颖":"3","浅":"3","衍":"3",
    # 4声 (去声)
    "渡":"4","落":"4","照":"4","断":"4","暮":"4","度":"4","静":"4","漱":"4","抱":"4",
    "陆":"4","谢":"4","卫":"4","段":"4","宋":"4","季":"4","叶":"4","傅":"4","念":"4",
    "慕":"4","霍":"4","晏":"4","令":"4","上":"4","夏":"4","杜":"4","若":"4","素":"4",
    "宁":"4","靖":"4","黛":"4","映":"4","见":"4","慎":"4","正":"4","信":"4",
    "梦":"4","境":"4","镜":"4","劲":"4","净":"4","靖":"4",
}


def _tone_balance(name: str) -> bool:
    """Check if a 2-char given name has tonal variety (not same tone)."""
    if len(name) < 2:
        return True
    t1 = _PINYIN_TONE.get(name[0], "0")
    t2 = _PINYIN_TONE.get(name[1], "0")
    return t1 != t2  # Good names have contrasting tones


def random_protagonist_name(genre: str = "玄幻") -> tuple[str, str]:
    """
    Generate (full_name, given_name) with genre-appropriate style.
    - Genre-matched surname + given name pools
    - Male genres exclude feminine-coded names
    - Tonal contrast enforced (平仄相间)
    """
    import random

    is_female = genre in ("现代言情", "古代言情", "纯爱", "女频", "言情")
    surnames = _SURNAME_BY_GENRE.get(genre, _SURNAME_GUYA + _SURNAME_DAQII)
    givens = _MALE_GIVEN_BY_GENRE.get(genre, _GIVEN_CHUCI + _GIVEN_YIJING)

    # Filter out feminine-coded names for male genres
    if not is_female:
        givens = [g for g in givens if g not in _GIVEN_FEMININE_CODED]
        if not givens:
            givens = _GIVEN_CHUCI + _GIVEN_YIJING + _GIVEN_SHANSHUI + _GIVEN_PINGE

    # Try up to 30 times to find a tonally balanced, non-repetitive name
    for _ in range(30):
        given = random.choice(givens)
        last = random.choice(surnames)
        # Skip if surname and given share the same first character
        if last[0] == given[0]:
            continue
        if _tone_balance(given):
            return f"{last}{given}", given

    # Fallback
    given = random.choice(givens)
    last = random.choice(surnames)
    return f"{last}{given}", given


class Generator:
    """AI 章节生成器 — 双模式"""

    def __init__(self, cfg: Config = config):
        self.cfg = cfg
        self.client = OpenAI(
            api_key=cfg.openai_api_key,
            base_url=cfg.openai_base_url or None,
            timeout=300.0,
            max_retries=2,
        )
        self.fallback_client: OpenAI | None = None  # DeepSeek 等备选
        self._fallback_model: str = ""

    def _init_fallback(self):
        """懒加载备选模型客户端——从数据库查找不同于主模型的供应商"""
        if self.fallback_client is not None:
            return
        try:
            from .database import Database
            db = Database()
            providers = db.list_providers()
            # Find a different provider with a valid key
            for p in providers:
                key = db.get_provider(p["id"]).get("api_key", "") if hasattr(db, 'get_provider') else p.get("api_key", "")
                if not key or len(key) < 8:
                    continue
                # Skip if same base_url as main (would hit same API)
                if p.get("base_url", "") == self.cfg.openai_base_url:
                    continue
                models = p.get("models", [])
                if not models:
                    continue
                try:
                    self.fallback_client = OpenAI(
                        api_key=key,
                        timeout=300.0,
                        max_retries=2,
                        base_url=p.get("base_url", "https://api.openai.com/v1"),
                    )
                    self._fallback_model = models[0]
                    print(f"[LLM] 备选客户端已初始化: {p['id']} -> {self._fallback_model}")
                    return
                except Exception as e:
                    print(f"[LLM] 备选客户端({p['id']})初始化失败: {e}", file=__import__("sys").stderr)
        except Exception as e:
            print(f"[LLM] WARNING: 无法查找备选供应商: {e}", file=__import__("sys").stderr)

    # ==================== 模式 A：全自动 ====================

    def generate(self, state: StoryState, rag_context: list[dict] | None = None,
                outline: list[dict] | None = None, style: StyleProfile | None = None,
                author_input: str = "") -> ChapterMeta:
        """全自动模式：基于 state 直接生成下一章"""
        messages = self._build_prompt(state, author_input=author_input, rag_context=rag_context, outline=outline, style=style)
        # Use streaming if callback is set (live preview), otherwise non-streaming
        if hasattr(self, '_on_stream_chunk') and self._on_stream_chunk:
            raw = self._call_llm_streaming(messages)
        else:
            raw = self._call_llm_with_retry(messages)
        title, body, meta = self._parse_response(raw, state.total_chapters + 1)

        # Quality will be scored by caller (_run_generation), no internal retry

        # 构建章节元数据
        chapter = ChapterMeta(
            number=state.total_chapters + 1,
            title=title,
            word_count=len(body),
            summary=meta.get("summary", body[:200]) if meta.get("summary") else body[:200],
            content=body,
            key_events=meta.get("key_events", []),
            revelations=meta.get("revelations", []),
            ending_hook=meta.get("ending_hook", body[-100:] if not meta.get("ending_hook") else ""),
        )

        # 更新状态
        self._update_state(state, chapter, meta)
        return chapter

    def batch_generate(
        self,
        state: StoryState,
        n: int = 2,
        rag_context: list[dict] | None = None,
        outline: list[dict] | None = None,
        style: StyleProfile | None = None,
        author_input: str = "",
    ) -> tuple[ChapterMeta, dict]:
        """
        生成 n 个版本，用 score_quality 评分，返回最佳版本。
        n 个版本使用不同的 temperature（基值±0.1 波动），增加多样性。

        Args:
            state: 当前故事状态
            n: 生成版本数（默认2，建议不超过3）
            rag_context: RAG 检索结果
            outline: 大纲

        Returns:
            (best_chapter, best_quality)
        """
        best_chapter = None
        best_quality: dict[str, object] = {'overall': 0}

        base_temp = self.cfg.temperature
        for i in range(n):
            # 轻微温度波动增加多样性
            temp_offset = (i - (n - 1) / 2) * 0.1
            self.cfg.temperature = min(1.0, max(0.5, base_temp + temp_offset))

            chapter = self.generate(state, rag_context=rag_context, outline=outline, style=style, author_input=author_input)
            body = chapter.content or chapter.summary
            quality = self.score_quality(body, state, style=style)

            if quality['overall'] > best_quality['overall']:
                best_chapter = chapter
                best_quality = quality

        # 恢复原始温度
        self.cfg.temperature = base_temp

        return best_chapter, best_quality

    def revise_opening(self, state: 'StoryState', target_chapters: int = 3,
                        style: 'StyleProfile | None' = None) -> list[ChapterMeta]:
        """
        全书生成完毕后，回头重写开篇章节。
        重写时注入：已知结局的全部信息，在开头精准埋设呼应结局的伏笔。
        """
        total = state.total_chapters
        if total < 10:
            return []
        revised = []
        # Collect future knowledge to inject
        future_summary = self._summarize_future(state, target_chapters)
        for ch_num in range(1, target_chapters + 1):
            print(f"[REVISE] 重写第{ch_num}章（已知全书{total}章）...")
            messages = self._build_prompt(state, author_input="",
                rag_context=None, outline=None, style=style)
            # Inject revision knowledge
            revision_note = f"""
## ⚠️ 重写模式 ⚠️
这是全书写完后的回修。你已经知道结局。现在回到第{ch_num}章——这个时候读者还不知道任何事情，但你知道一切。

未来的关键信息（这些在第{ch_num}章时不该泄露，但可以微妙暗示）：
{future_summary}

重写规则：
1. 保持原有剧情80%不变——改动只针对伏笔铺设
2. 每一处改动必须能在第{total}章被回响——不只为改而改
3. 可以加一句对话/一个细节/一个物品，让它在未来成为重读时的密码
4. 不要改变人物的出场方式和核心性格
5. 篇幅与原版基本一致"""
            messages[0]["content"] += revision_note
            raw = self._call_llm_with_retry(messages)
            title, body, meta = self._parse_response(raw, ch_num)
            body = self._self_edit(body, state, style)
            cleaned, _ = self.de_ai(body)
            revision_chapter = ChapterMeta(number=ch_num, title=title,
                word_count=len(cleaned), summary=meta.get("summary", cleaned[:200]),
                content=cleaned, key_events=meta.get("key_events", []),
                revelations=meta.get("revelations", []),
                ending_hook=meta.get("ending_hook", cleaned[-100:]))
            revised.append(revision_chapter)
        return revised

    def _summarize_future(self, state: 'StoryState', after_chapter: int) -> str:
        """Extract key future events for revision injection."""
        future = [ch for ch in state.chapters if ch.number > after_chapter]
        if not future:
            return "无后续章节信息。"
        lines = []
        # Key endings
        last = state.chapters[-1] if state.chapters else None
        if last:
            lines.append(f"大结局：{last.summary[:200] if last.summary else '（无摘要）'}")
        # Major revelations
        for ch in future[-5:]:
            for rev in ch.revelations[:2]:
                lines.append(f"第{ch.number}章揭示：{rev}")
        # Character fates
        for ch in future[-3:]:
            lines.append(f"第{ch.number}章：{ch.title} — {ch.summary[:100] if ch.summary else ''}")
        if not lines:
            return "无关键未来信息。"
        return '\n'.join(lines)

    def generate_chapters(
        self,
        state: StoryState,
        n: int = 5,
        rag_context: list[dict] | None = None,
        outline: list[dict] | None = None,
        style: 'StyleProfile | None' = None,
    ) -> list[ChapterMeta]:
        """
        连续生成 n 个章节，每章追加到 state.chapters，使下一章看到全文。

        Returns: 新生成的 n 个 ChapterMeta
        """
        new_chapters: list[ChapterMeta] = []
        for i in range(n):
            # Use batch_generate for best-of-k quality
            chapter, quality = self.batch_generate(state, n=1, rag_context=rag_context,
                                                    outline=outline, style=style)
            body = chapter.content or chapter.summary
            # Quality check
            quality = self.score_quality(body, state, style=style)
            retries = 0
            while quality['overall'] < 0.5 and retries < 2:
                retries += 1
                chapter, quality = self.batch_generate(state, n=1, rag_context=rag_context,
                                                        outline=outline, style=style)
                body = chapter.content or chapter.summary
                quality = self.score_quality(body, state, style=style)
            # Snapshot before self-edit
            pre_edit_body = body
            # Self-edit pass (light LLM refinement)
            body = self._self_edit(body, state, style)
            # De-AI (regex)
            cleaned, _ = self.de_ai(body)
            # Humanize (LLM) — 去掉AI写作特征
            cleaned = self.humanize(cleaned)
            # Save version snapshot
            self._save_version(state.novel_id, chapter.number, pre_edit_body, "pre-edit")
            chapter.content = cleaned
            chapter.word_count = len(cleaned)
            # Append so next chapter sees this one's full text via state.latest_chapter
            state.chapters.append(chapter)
            # Track character voices from this chapter
            self._extract_character_voices(cleaned, state)
            # Track emotion for continuity
            if style:
                style.last_chapter_emotion = self._detect_ending_emotion(chapter.ending_hook, cleaned)
                # Track curiosity questions from revelations
                for rev in chapter.revelations[:2]:
                    if rev not in style.open_questions:
                        style.open_questions.append(rev)
                # Remove answered questions (from key_events that resolve something)
                for ev in chapter.key_events[:2]:
                    for q in list(style.open_questions):
                        if any(w in q for w in ev.split()[:3]):
                            style.open_questions.remove(q)
                # Keep max 5
                style.open_questions = style.open_questions[-5:]
            # Track cost for this chapter
            if self._last_usage:
                self._save_cost_log(state.novel_id, chapter.number, "generate")
            new_chapters.append(chapter)
        return new_chapters

    def fact_check(self, body: str, genre: str = "") -> dict:
        """
        事实核查：让AI自己审计自己的章节，标记所有可能不准确的事实性陈述。
        Returns {"issues": [{text, reason, severity}], "score": 1-10}
        """
        prompt = f"""你是事实核查编辑。请审查以下章节，标记所有可能是AI幻觉的事实性陈述。

重点关注：
- 历史人物、事件、年代——是否可能张冠李戴
- 科学/技术描述——是否符合真实原理
- 法律程序、官制、制度——是否真实存在
- 地理信息——城市、地名、距离是否准确
- 数据——百分比、数量、时间是否经得起推敲
- 引用——诗词、典故、名言——是否存在、是否准确

输出JSON格式：
{{"issues": [{{"text": "原文中可疑的文字", "reason": "为什么不确信", "severity": "high/medium/low"}}], "overall_score": 8}}

只标记真正可疑的——明显是虚构创作的不算（如修炼体系、架空地名）。只输出JSON。

章节：
{body[:5000]}

核查结果JSON："""
        try:
            result = self._call_llm_with_retry([
                {"role":"system","content":"你是事实核查专家。只输出JSON。"},
                {"role":"user","content": prompt}
            ], max_tokens=1024)
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception:
            pass
        return {"issues": [], "overall_score": 10}

    def humanize(self, body: str) -> str:
        """
        去AI味深度清洗——不是替换套话，是让AI读自己的文字然后指出哪里不像人写的。
        """
        prompt = f"""你是一位资深编辑，专门识别AI生成的文字。请阅读以下章节，找出3处最明显像AI写的地方，然后只修改那3处。

AI写作的典型特征：
- 段落长度均匀——每段都是3-4行，天然整齐
- 每个场景切换都有光滑过渡词（'与此同时''在此之后'）
- 对话太干净——没人打断、没人说半句话、没人答非所问
- 情绪用标签而不是行动——'他愤怒地说'是AI，'他把杯子放在桌上。杯子碎了。'是人
- 每个角色说话方式一样——没有口头禅、没有结巴、没有独特的称呼方式
- 所有信息按逻辑顺序排列——但人写东西经常跳、经常先扔一个结果再解释原因
- 段落开头常常是'他/她/它'——主语单调
- 所有因果关系都被解释了（A发生了，于是B。读者不需要想）
- 形容词和比喻安全而平庸
- 情绪描写用'他感到''他觉得'而不是用身体反应

修改规则：
1. 打碎1处光滑过渡——让场景切换突兀一点，像人写的
2. 把1段完整解释改成不完整暗示——删掉因果说明，让读者自己想
3. 改写1处对话——加入打断、半句话、或者一个人问A另一个人答B

保持总字数不变。只修改3处。输出完整修改后的章节正文。

原稿：
{body[:5000]}

修改后："""
        try:
            result = self._call_llm_with_retry([
                {"role":"system","content":"你是反AI写作专家。你只修改3处，不打乱原文。"},
                {"role":"user","content": prompt}
            ], max_tokens=8192)
            if result and len(result) > len(body) * 0.7:
                return result.strip()
        except Exception:
            pass
        return body

    def revise_chapter(self, chapter_content: str, critique: str,
                       state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """
        基于自然语言批评重写章节。只改被批评的部分，保留未被批评的一切。
        """
        messages = [
            {"role": "system", "content": f"""你是一位专业编辑。你的任务是根据以下批评重写章节。

批评要点：
{critique}

重写规则：
1. 只修改批评指出的问题——未被批评的部分必须保留
2. 保持原有剧情、角色、对话的核心不变
3. 保持总字数在±15%以内
4. 保持原有的章节标题
5. 不改变任何角色的命运或重大事件

输出完整重写后的章节正文。"""},
            {"role": "user", "content": f"原稿：\n\n{chapter_content}\n\n请根据批评重写。直接输出修改后的完整章节。"},
        ]
        try:
            revised = self._call_llm_with_retry(messages, max_tokens=8192)
            if revised and len(revised) > len(chapter_content) * 0.6:
                return revised.strip()
        except Exception:
            pass
        return chapter_content  # Fallback: return original

    def extract_narrative_dna(self, sample_chapters: list[dict],
                               target_genre: str = "") -> dict:
        """
        提取叙事基因并翻译为目标体裁的结构语法。
        如果 target_genre 不空，DNA 会被翻译——保留结构模式，替换内容词汇。
        """
        return self._extract_dna_raw(sample_chapters, target_genre)

    def _extract_dna_raw(self, sample_chapters: list[dict], target_genre: str = "") -> dict:
        """
        从样本章节中提取叙事基因——结构模式、情感节奏、角色弧线。
        返回可以被新书复用的叙事架构。
        """
        if not sample_chapters or len(sample_chapters) < 3:
            return {"error": "需要至少3章样本"}
        samples_text = '\n---\n'.join(
            f"第{i+1}章「{ch.get('title','')}」({ch.get('word_count',0)}字):\n{ch.get('content','')[:500]}"
            for i, ch in enumerate(sample_chapters[:10]))

        dna_prompt = f"""你是叙事结构分析师。从以下章节样本中提取这本书的叙事基因。

分析维度：
1. 篇章结构：每章的开头策略（冲突/氛围/困境/对话）、中段节奏、结尾钩子类型
2. 情感曲线：每章的情感起点→终点变化（用1-10标注紧张度/希望度）
3. 角色功能：每个主要角色承担什么叙事功能（推动者/阻碍者/揭示者/陪衬者）
4. 信息释放节奏：每多少字释放一个关键信息或转折
5. 独特结构特征：这本书有什么其他书没有的叙事手法

输出JSON格式，每个维度单独一个字段。要具体、可量化、可复用——这些数据将被用来指导新书写作。

样本章节：
{samples_text[:4000]}

叙事基因JSON："""

        dna = ""
        try:
            dna = self._call_llm_with_retry([
                {"role":"system","content":"你是叙事结构分析师。输出可量化的JSON结构数据。"},
                {"role":"user","content": dna_prompt}
            ], max_tokens=2048)
        except:
            return {"error": "提取失败"}

        import json as _json
        json_match = re.search(r'\{[\s\S]*\}', dna)
        if json_match:
            try:
                result = _json.loads(json_match.group(0))
                # Translate DNA for target genre
                if target_genre and target_genre != "玄幻":
                    result = self._translate_dna(result, target_genre)
                    result["_translated_for"] = target_genre
                return result
            except:
                return {"raw": dna[:1000]}
        return {"raw": dna[:1000]}

    @staticmethod
    def _translate_dna(dna: dict, target_genre: str) -> dict:
        """将提取的叙事DNA翻译为目标体裁的结构语法——保留结构模式，替换内容词汇。"""
        genre_vocab = {
            "都市": {"冲突":"对话冲突或信息不对称","高潮":"关系转折或权力转移","爽点":"打脸/碾压/揭秘","敌人":"对手/竞争者"},
            "悬疑": {"冲突":"线索断裂或嫌疑人出现","高潮":"真相逼近或伪解答","爽点":"线索串联/伏笔回收","敌人":"未知威胁"},
            "科幻": {"冲突":"技术危机或伦理困境","高潮":"科学发现或系统崩溃","爽点":"概念闪光/规模震撼","敌人":"失控的系统或未知文明"},
            "女频": {"冲突":"感情冲突或身份危机","高潮":"表白/分手/重逢","爽点":"心动时刻/身份反转","敌人":"情敌或社会压力"},
            "官场": {"冲突":"权力博弈或站队选择","高潮":"站队揭晓或调查结论","爽点":"权谋制胜/信息碾压","敌人":"政敌或制度本身"},
            "历史": {"冲突":"制度矛盾或外敌压力","高潮":"战役/变法/宫变","爽点":"以弱胜强/制度创新","敌人":"旧势力或外敌"},
            "游戏": {"冲突":"BOSS战或副本危机","高潮":"通关/爆装/觉醒","爽点":"稀有掉落/战力暴涨","敌人":"怪物/敌对玩家"},
        }
        vocab = genre_vocab.get(target_genre, {})
        if not vocab:
            return dna

        # Translate content-specific fields
        for field in ["hook_pattern", "climax_type", "opening_strategy"]:
            if field in dna and isinstance(dna[field], str):
                for old, new in vocab.items():
                    dna[field] = dna[field].replace(old, new)

        # Translate list fields
        for field in ["key_techniques", "structural_features"]:
            if field in dna and isinstance(dna[field], list):
                dna[field] = [vocab.get(item, item) if isinstance(item, str) else item for item in dna[field]]

        # Add translation note
        if "special_rules_translated" not in dna:
            dna["special_rules_translated"] = []
        dna["special_rules_translated"].append(f"以下规则已从源体裁翻译为「{target_genre}」：{', '.join(vocab.keys())}")
        return dna

    def ab_test_opening(self, synopsis: str, genre: str = "玄幻",
                         voices: list[str] | None = None) -> dict:
        """
        A/B测试：用不同作家声音生成第一章，评分后返回最优配置。
        voices: 要测试的作家声音列表，默认测试全部14种。
        Returns {best_voice, best_chapter, all_results}
        """
        if voices is None:
            voices = list(WRITER_VOICES.keys())
        results = {}
        for voice_key in voices:
            voice = WRITER_VOICES.get(voice_key)
            if not voice: continue
            style = _get_style_for_genre(genre)
            style.writer_voice = voice_key
            # Build minimal state
            from .story_state import Plot, StoryState, World
            state = StoryState(novel_id="ab_test", title="AB测试", author="AI",
                synopsis=synopsis, genre=genre,
                world=World(name="测试世界", era="当代", geography="", power_system=""),
                characters=[], plot=Plot(premise=synopsis, main_arc=synopsis, current_arc="开篇", arc_chapter_start=1),
                chapters=[])
            try:
                chapter = self.generate(state, style=style)
                body = chapter.content or chapter.summary
                quality = self.judge_quality(body, state, style)
                results[voice_key] = {
                    "title": chapter.title,
                    "quality": quality.get("overall", 0),
                    "grade": quality.get("grade", "?"),
                    "sample": body[:200],
                }
            except Exception as e:
                results[voice_key] = {"error": str(e)[:100]}
        # Find best
        best = max(results.items(), key=lambda x: x[1].get("quality", 0)) if results else (None, {})
        return {"best_voice": best[0], "best_chapter": best[1], "all_results": results}

    def generate_chapter_classic(self, state: 'StoryState', style: 'StyleProfile | None' = None,
                                  rag_context=None, outline=None) -> ChapterMeta:
        """
        经典模式：生成多个版本，只通过符合全部质量门槛的版本。
        不通过的直接淘汰，最多生成 5 版，全不通过则返回最佳版本并标记。
        """
        best_chapter, best_quality = None, {"overall": -1, "issues": []}
        rejected_log: list[dict] = []  # Save rejected versions for analysis
        for attempt in range(5):
            chapter = self.generate(state, rag_context=rag_context, outline=outline, style=style)
            body = chapter.content or chapter.summary

            # 1. Basic quality check
            quality = self.judge_quality(body, state, style)
            if quality.get("overall", 0) < 0.75:
                rejected_log.append({"attempt": attempt+1, "reason": f"总分{quality['overall']:.2f}<0.75", "detail": quality})
                print(f"[CLASSIC] Attempt {attempt+1}: 总分{quality['overall']:.2f}<0.75，淘汰")
                continue

            # 2. Classic-specific structural check
            classic_ok, classic_issues = self._classic_check(body, state, style)
            if not classic_ok:
                rejected_log.append({"attempt": attempt+1, "reason": f"经典检查: {classic_issues}", "detail": classic_issues})
                print(f"[CLASSIC] Attempt {attempt+1}: 经典检查不通过: {classic_issues}")
                continue

            # 3. Cross-chapter consistency
            if state.total_chapters >= 1:
                consistency_ok, consistency_issues = self._cross_chapter_check(body, state, style)
                if not consistency_ok:
                    rejected_log.append({"attempt": attempt+1, "reason": f"跨章一致性: {consistency_issues}", "detail": consistency_issues})
                    print(f"[CLASSIC] Attempt {attempt+1}: 跨章一致性不通过: {consistency_issues}")
                    continue

            # 4. Quotability — at least 2 lines worth quoting
            quotable = self._count_quotable_lines(body)
            if quotable < 2:
                rejected_log.append({"attempt": attempt+1, "reason": f"只{quotable}句可引用", "detail": quotable})
                print(f"[CLASSIC] Attempt {attempt+1}: 只{quotable}句可引用，<2，淘汰")
                continue

            # All checks passed
            print(f"[CLASSIC] ✅ Attempt {attempt+1}: 通过全部经典门槛!")
            body = self._self_edit(body, state, style)  # 轻量精修
            chapter.content = body
            best_chapter, best_quality = chapter, quality
            break

        # Save rejected log for analysis
        if rejected_log:
            try:
                from pathlib import Path
                log_dir = Path("data") / "debug_versions" / state.novel_id
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / f"ch{state.total_chapters+1}_rejections.json"
                log_file.write_text(json.dumps(rejected_log, ensure_ascii=False, indent=2))
                print(f"[CLASSIC] 📋 淘汰记录已保存: {log_file}")
            except Exception:
                pass

        if not best_chapter:
            # Fallback: generate one more time without classic filter
            print("[CLASSIC] ⚠️ 5次尝试未达经典标准，降级为普通生成")
            chapter = self.generate(state, rag_context=rag_context, outline=outline, style=style)
            body = self._self_edit(chapter.content or chapter.summary, state, style)
            chapter.content, _ = self.de_ai(body)
            return chapter

        return best_chapter

    def _classic_check(self, body: str, state: 'StoryState', style: 'StyleProfile | None' = None) -> tuple[bool, list[str]]:
        """经典门槛检查：不是'好不好看'，是'值不值得读第二遍'。"""
        issues = []
        paras = [p for p in body.split('\n') if p.strip()]
        if not paras:
            return False, ["空章节"]

        # 1. Opening must grab immediately
        first_50 = body[:50].strip()
        if not first_50 or len(first_50) < 20:
            issues.append("开头不足20字——没有建立起场景感")
        if first_50 and any(kw in first_50 for kw in ['在这个', '众所周知', '随着', '清晨，阳光']):
            issues.append(f"开头有AI套话: '{first_50[:30]}'")

        # 2. At least one moment of genuine emotional impact
        impact_markers = ['沉默', '没有说话', '手指', '盯着', '转身', '愣住了',
                         '叹了口气', '笑了一下，但', '没有回头', '走了']
        if not any(m in body for m in impact_markers):
            issues.append("没有情感冲击时刻——全程都在推进剧情但读者无感")

        # 3. At least one unexpected element (not cliché)
        unexpected = ['但他没有', '但是', '然而', '没想到', '出乎', '不对',
                     '不对劲', '不像是', '怎么会']
        if not any(u in body for u in unexpected):
            issues.append("没有转折或意外——读者能猜到每一段的下一段")

        # 4. Scene purpose density — at most 1 single-purpose scene
        scene_count = len([p for p in paras if len(p) > 50])
        if scene_count < 3:
            issues.append(f"只有{scene_count}个有效场景，<3——故事密度不够")

        # 5. Ending must leave a specific feeling
        last_80 = body[-80:].strip() if len(body) > 80 else body
        weak_endings = ['他走了', '就这样', '然后', '完', '结束']
        if any(last_80.startswith(w) or last_80.endswith(w) for w in weak_endings):
            issues.append(f"结尾无力: '{last_80[:40]}'")

        return len(issues) == 0, issues

    def _cross_chapter_check(self, body: str, state: 'StoryState', style=None) -> tuple[bool, list[str]]:
        """跨章一致性：和前文的情绪、节奏、角色位置是否匹配。"""
        issues = []
        prev = state.latest_chapter
        if not prev or not prev.content:
            return True, []

        # 1. Emotional continuity — if previous chapter ended with high tension, this one should acknowledge
        prev_ending = prev.content[-200:] if len(prev.content) > 200 else prev.content
        if '？' in prev_ending and '？' not in body[:200]:
            issues.append("上章以疑问结尾，本章开头没有回应那个疑问")

        # 2. Voice continuity for protagonist
        protagonist = state.protagonist
        if protagonist and protagonist.voice_sample:
            if protagonist.name in body:
                voice_paras = [p for p in body.split('\n') if protagonist.name in p and ('"' in p or '"' in p or '：' in p)]
                if not voice_paras:
                    issues.append(f"主角{protagonist.name}在本章没有对话——和其声音特征不一致")

        return len(issues) == 0, issues

    @staticmethod
    def _writing_warmup(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """生成一段主角视角的50字随笔——帮LLM进入角色声音，不写进正文。"""
        protagonist = state.protagonist if state else None
        if not protagonist:
            return ""
        voice = protagonist.voice_sample if protagonist.voice_sample else ""
        name = protagonist.name
        ch = state.total_chapters + 1
        warmup = f"{name}站在第{ch}章的开头。"
        if voice:
            warmup += f"上次ta说话是这样的：「{voice[:50]}」"
        warmup += "现在，故事继续——"
        return f"【写作预热——以下不写进正文，只是帮你进入状态】\n{warmup}"

    @staticmethod
    def _detect_ending_emotion(ending_hook: str, body: str) -> str:
        """Detect the dominant emotion at chapter end for continuity tracking."""
        last_200 = body[-200:] if len(body) > 200 else body
        hook = ending_hook or ""
        combined = last_200 + hook
        if '？' in combined or '?' in combined:
            return "困惑"
        if '！' in combined or '!' in combined:
            return "愤怒"
        if any(w in combined for w in ['死', '失去', '再也', '没有', '走', '离开']):
            return "悲伤"
        if any(w in combined for w in ['会', '一定', '能', '准备', '开始', '出发']):
            return "希望"
        if any(w in combined for w in ['突然', '竟然', '没想到', '不对', '发现']):
            return "不安"
        return "困惑"  # default

    @staticmethod
    def _count_quotable_lines(body: str) -> int:
        """Count sentences that a reader might want to quote/share."""
        quotable = 0
        sentences = [s.strip() for s in body.replace('！', '。').replace('？', '。').split('。') if 15 < len(s.strip()) < 50]
        for s in sentences:
            # A quotable line: paradox, insight, poetic image, or sharp observation
            if any(kw in s for kw in ['不是', '没有', '其实', '从来', '永远', '唯一', '最后',
                                       '第一次', '有人', '没人', '所有人', '一个人',
                                       '不再是', '不会', '不可能', '也许']):
                quotable += 1
        return quotable

    def _save_cost_log(self, novel_id: str, chapter_number: int, purpose: str = "generate"):
        """Save per-call cost to DB."""
        try:
            from .database import Database
            db = Database()
            u = self._last_usage
            db.log_cost(novel_id, chapter_number, u.get("model", ""),
                        u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
                        u.get("total_tokens", 0), u.get("cost", 0.0), purpose)
        except Exception as e:
            print(f"[COST] Failed to log: {e}", file=__import__("sys").stderr)

    def _save_version(self, novel_id: str, chapter_number: int, content: str, reason: str = ""):
        """Snapshot chapter content before modification."""
        try:
            from .database import Database
            db = Database()
            db.save_chapter_version(novel_id, chapter_number, content, reason)
        except Exception:
            pass

    # ==================== 模式 B：创作者 ====================

    def draft_directions(
        self,
        state: StoryState,
        author_input: str,
        n: int = 3,
    ) -> list[DraftOption]:
        """根据作者输入，生成 n 个剧情走向草稿"""
        direction_prompt = self._build_direction_prompt(state, author_input, n)
        raw = self._call_llm_with_retry(direction_prompt, max_tokens=2048)
        return self._parse_directions(raw)

    def expand(
        self,
        state: StoryState,
        chosen: DraftOption,
        edits: str = "",
    ) -> tuple[str, str]:
        """
        展开选定方向为完整章节。
        返回 (title, body)
        """
        expand_prompt = self._build_expand_prompt(state, chosen, edits)
        raw = self._call_llm_with_retry(expand_prompt)
        title, body, _meta = self._parse_response(raw, state.total_chapters + 1)
        return title, body

    # ==================== Prompt 构建 ====================

    def _foreshadowing_context(self, state: StoryState) -> str:
        """Compressed foreshadowing list — max 15 items, oldest tagged with source chapter."""
        items = state.plot.foreshadowing
        if not items:
            return "已埋伏笔：暂无"
        display = items[:15]
        lines = ["已埋伏笔："]
        for item in display:
            lines.append(f"  - {item}")
        if len(items) > 15:
            lines.append(f"  （另有 {len(items) - 15} 条早期伏笔已存档，如本章涉及请在正文中自然回收）")
        return '\n'.join(lines)

    @staticmethod
    def _arc_position_context(chapter_num: int) -> str:
        """全书节奏曲线 — 根据章节位置给出情绪/节奏指导。
        默认按 50 章规划。如果 book 更长，位置比例自动缩放。"""
        # Default arc for a ~50 chapter book
        arc = [
            (1, 3, "开篇", "高密度钩子——每章至少2个悬念点，快速建立核心冲突和世界观。节奏快。"),
            (4, 8, "展开", "引出配角、展开世界、埋下伏笔。节奏放缓，但每章结尾必须有未回答的问题。"),
            (9, 15, "第一个高潮", "至少一条伏笔回收。主角面临第一次重大失败。情绪爬升。"),
            (16, 25, "中段攀升", "敌人真正出现，压力持续增加。关系网复杂化。每章都要有挫折感。"),
            (26, 35, "黑暗时刻", "全书的情绪最低点。主角失去重要的人/东西。读者应该感到绝望。"),
            (36, 42, "反攻爬升", "主角开始反击。每一章向前推进一步，但仍有代价。节奏加速。"),
            (43, 48, "终局高潮", "最终对决。所有伏笔回收。每章都是关键战役。节奏最快。"),
            (49, 50, "结局", "余韵。给读者一个值得回忆的结尾。不需要完美，但需要值得。"),
        ]
        for start, end, label, guidance in arc:
            if start <= chapter_num <= end:
                return f"第{chapter_num}章处于《{label}》篇章。情绪基调：{guidance}"
        # Beyond 50 — scale proportionally
        extended_label = "展开" if chapter_num < 75 else ("中段" if chapter_num < 100 else "结局")
        return f"第{chapter_num}章处于《{extended_label}》篇章。按当前位置自然推进剧情。"

    @staticmethod
    def _emotion_budget_context(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """读者情绪预算 — 根据上一章的结尾，计算本章应该给读者什么情感体验。"""
        budget = style.emotional_budget if style else {"anxiety": 5, "trust": 5, "satisfaction": 5, "target_anxiety": 6}
        ch = state.total_chapters + 1
        # Analyze previous chapter ending
        prev = state.latest_chapter
        prev_anxiety = budget.get("anxiety", 5)
        prev_trust = budget.get("trust", 5)
        prev_sat = budget.get("satisfaction", 5)

        # Determine if we need to release or build tension
        if ch <= 3:
            guidance = "开篇：快速建立担忧但不耗尽读者。每章给一点希望（满足+1），拿走更大的安全感（焦虑+2）。"
        elif prev and prev.ending_hook:
            # Hook types determine next step
            if '？' in prev.ending_hook or '?' in prev.ending_hook:
                guidance = f"上章以疑问结尾（焦虑{prev_anxiety}→{min(10,prev_anxiety+1)}）。本章开头先给一点线索（满足度+1），中段制造新不安，结尾推到更高焦虑。"
            elif '！' in prev.ending_hook or '!' in prev.ending_hook:
                guidance = f"上章以惊叹/反转结尾（满足度{prev_sat}→{max(1,prev_sat-1)}）。本章开头消化上章的冲击，中段建立新方向，结尾留悬念。连续两章不能都惊叹。"
            elif '……' in prev.ending_hook or '...' in prev.ending_hook:
                guidance = f"上章以沉默/留白结尾（信任度{prev_trust}→{min(10,prev_trust+2)}）。本章多给内心戏和对话，让读者靠近角色。留白堆积到一定程度必须炸。"
            else:
                guidance = "上章结尾中性。本章必须制造一个清晰的情感方向——焦虑或满足，不能持平。"
        else:
            guidance = "首次生成。专注建立核心冲突：主角想要什么？什么阻止他？读者需要担心什么？"

        return f"读者当前：焦虑{prev_anxiety}/10，信任{prev_trust}/10，满足{prev_sat}/10。\n{guidance}"

    @staticmethod
    def _rhythm_guide(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """段落级节奏控制 — 告诉LLM哪里快哪里慢，不是机械的'500字一钩子'。"""
        mode = style.rhythm_mode if style else "auto"
        ch = state.total_chapters + 1

        if mode == "tension":
            return "🔴 紧张模式：短段落(15-40字)为主。对话密集、动作打断、信息快速切换。每个换段都是一个信息点的更新。"
        elif mode == "relief":
            return "🟢 释放模式：中等段落(50-120字)为主。有内心戏、环境描写、角色关系的温暖时刻。允许读者喘一口气。"
        elif mode == "speed":
            return "⚡ 加速模式：超短段落(10-30字)为主。三句话内切换场景。每一段都在推进剧情。不给思考时间。"
        elif mode == "linger":
            return "🟡 停留模式：长段落(100-200字)可以用。描写一个画面、一个表情、一个氛围。别急着往下走，让读者在这个场景里待一会儿。"
        else:  # auto
            if ch <= 3:
                return "开篇混合节奏：对话段20-40字快切，描写段50-100字慢铺。开头100字加速进入场景，中段允许一段长描写，结尾加速。"
            return "根据内容自然变速：冲突/对话→短快。情感/描写→中慢。场景切换→三句话内完成。结尾→加速。"

    @staticmethod
    def _gap_rule(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """留白约束 — 每章最少保留N处不解释的元素，让读者自己填补。"""
        n = style.gap_rule if style else 3
        items = [
            "一个角色的行为动机：他做了一件事，但不说为什么。读者自己去想。",
            "一句对话的含义：角色说了一句看似无关的话，其实很重要。但本章不解释。",
            "一个细节的暗示：出现了一个物品/声音/味道，似乎不正常。但没有人注意到。",
            "一个场景的缺席：本该出现的某人没出现。没有理由。",
            "一句没说出口的话：角色想说什么，但咽回去了。读者知道他想说什么。",
        ]
        import random as _rd
        _rd.seed(int(time.time() * 1000000) + id(state))
        chosen = _rd.sample(items, min(n, len(items)))
        return '本章至少保留 ' + str(len(chosen)) + ' 个「不解释」元素：\n' + '\n'.join(f'- {c}' for c in chosen)

    @staticmethod
    def _echo_guide(state: 'StoryState') -> str:
        """回响系统 — 找到前文中值得被本章呼应的元素，注入提示。"""
        if state.total_chapters < 3:
            return '全书刚开始，尚无前文可回响。但本章结尾必须埋设至少一个「将来会被回响」的细节——一句未说完的话、一个未解释的动作、一个看似无意义但被反复提及的物品。'
        chs = state.chapters[-10:] if len(state.chapters) >= 10 else state.chapters
        if not chs:
            return "本章正常推进，建立新设定和冲突。"
        # Pick 1-2 echo-worthy moments from past chapters
        echoes = []
        for ch in chs:
            if ch.ending_hook and len(ch.ending_hook) > 30:
                echoes.append(f"第{ch.number}章结尾钩子：「{ch.ending_hook[:60]}」——本章可以用一个侧面细节回应这个未解悬念")
            if ch.key_events:
                for ev in ch.key_events[:2]:
                    echoes.append(f"第{ch.number}章关键事件「{ev}」——本章可以让一个角色无意中提及或受其影响")
        if echoes:
            chosen = random.sample(echoes, min(2, len(echoes)))
            return "本章必须与前文形成回响（至少一处）：\n" + "\n".join(f"- {e}" for e in chosen)
        return "本章可以自由推进。如有机会，用角色的一句话或一个动作回顾过去某章的轻微细节。"

    @staticmethod
    def _reread_layer(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """重读密码 — 第一遍不起眼，重读时脊背发凉的元素。"""
        ch = state.total_chapters + 1
        if ch <= 2:
            return "埋下最初的密码：一个看似无关的细节——一个人的表情、一件物品的位置、一句被忽略的对话。这个细节在10章后会被重新照亮。现在写它的时候，不要让它显得重要。"

        # Track what readers know vs what they should discover on reread
        types = [
            ("身份密码",
             "写一个角色做了一件完全符合其隐藏身份的事——但第一遍读的时候，读者会以为只是偶然。这个行为在未来的章节会被重新定义。"),
            ("物品密码",
             "引入或再次出现一个物品，给它加21个字以内的描写。这个物品不是道具——它是未来的证据。重读时读者会意识到它一直在这里。"),
            ("对话密码",
             "两个角色的对话，表面上在说一件事，实际上在说另一件完全不同的事。读者第一遍只听到表面。重读时才知道每句话的真正含义。"),
            ("缺席密码",
             "某个本该在场的人没有出现。不提他为什么没来——但重读时，这个缺席会成为线索。"),
            ("矛盾密码",
             "叙述本身出现一个轻微的自我矛盾——时间线上差了半小时，一个人的位置在两段之间变了。不是错误，是故意。重读时会发现这是整章的关键。"),
        ]
        import random as _rd
        _rd.seed(int(time.time() * 1000000) + id(state) + ch)
        chosen = _rd.sample(types, min(2, len(types)))
        return "本章必须埋设以下重读密码（不要标注它们——它们应该看起来只是正常叙事的一部分）：\n" + "\n".join(
            f"- {name}：{desc}" for name, desc in chosen)

    @staticmethod
    def _reader_prediction_model(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """读者预测模型 — 读者此刻认为的'真相'，本章先确认再推翻。"""
        ch = state.total_chapters + 1
        if ch <= 3:
            return "读者还没有形成确定的猜测。本章的任务是让读者开始猜测——给他至少两条互相矛盾的线索，让他自己选一个相信。"
        belief = style.expected_reader_belief if style else ""
        if not belief:
            return "读者已经拥有一定信息。本章至少给出两个线索：一个支持读者目前的猜测（让他点头），一个与猜测矛盾但证据更强（让他重新思考）。不要解释矛盾——让他自己拼。"
        return f"读者此刻大概率认为：{belief}\n\n本章的结构：\n1. 前半章——给出更多证据支持这个猜测（读者会觉得自己很聪明）\n2. 转折点——出现一个无法用当前解释覆盖的信息\n3. 后半章——新的可能性比旧的更有力量\n\n不要直接告诉读者'你错了'。让他自己发现。"

    @staticmethod
    def _orchestrated_rupture(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """蓄意的规则破坏 — 极少章节才有的特权。自动检测触发条件。"""
        ch = state.total_chapters + 1
        rch = style.rupture_chapter if style else 0

        # Auto-detect trigger conditions if not manually set
        if rch == 0 and style and style.central_question:
            # Trigger rupture when:
            # 1. All major character arcs are converging (late middle)
            # 2. Previous chapter had the highest emotional tension so far
            # 3. There's a belief about to be shattered
            total = state.total_chapters
            if total >= 8 and total % 20 in (8, 9, 10):  # Every ~20 chapters, at the 8-10 range
                prev = state.latest_chapter
                if prev and prev.ending_hook and len(prev.ending_hook) > 40:
                    rch = ch

        if rch == ch:
            return f"""⚡ 破坏许可 ⚡

本章是蓄意的破坏章。你已经写了{ch-1}章遵守所有规则。现在是整本书的转折点——核心追问已经到了最尖锐的时刻，旧的形式已经承载不了此刻的情感重量。

可选破坏方式（只选一种）：
- 叙事视角突然切换：从第三人称跳到第一人称，从主角的视角跳到一个从未有过声音的配角
- 时间折叠：本章不按线性走——过去和现在交替出现，不标注时间
- 直接对话读者：用第二人称「你」写一段——叙事者面对读者讲话
- 完全沉默：全章没有一句对话——用纯叙述和描写推进
- 诗化：全章用散文诗的方式写——段落即是节拍，重复即是力量

要求：破坏必须有理由——本章的情感内容要求这种形式。本章结束后，下一章恢复正常叙事。"""

        if rch and ch in [rch - 1, rch + 1]:
            return "蓄意破坏在前一章或后一章——本章保持正常叙事，但要为/从破坏中过渡。叙事可以略带不稳定感。"

        return ""

    @staticmethod
    def _narrator_position(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """叙事者位置 — 谁在讲故事，站在什么时间点上。"""
        ch = state.total_chapters + 1
        voice = WRITER_VOICES.get(style.writer_voice) if style and style.writer_voice else None
        nd = voice.narrative_distance if voice else "close"

        if nd == "close":
            pos = "你不在未来回看过去。你就在主角的此刻。你不知道接下来会发生什么。你的所知所见仅限于主角——他看不到的，你也看不到。"
        elif nd == "medium":
            pos = "你比主角知道得多一点——但不多。你可以切换到另一个角色的视角，但不能全知。你知道此刻各方在做什么，但不知道他们的内心。"
        else:
            pos = "你是全知叙事者。你可以俯瞰场景、穿越时间、看透人心。但你必须有选择地使用这种权力——不是每一段都揭示全部，而是偶尔给一个'读者有权知道但角色不知道'的信息。"

        # Time position
        if ch <= 3:
            time_pos = "你站在故事的起点。没有任何事已经发生。一切都是第一次。"
        elif ch >= state.total_chapters * 0.7 if state.total_chapters > 0 else 0:
            time_pos = "你站在故事的后期。前面的章节已经堆积了大量的历史。某些角色已经变了。某些关系已经死了。叙事的声音应该带着重量——不是沉重，是厚度。"
        else:
            time_pos = "你站在故事的中段。往前看，已经发生了很多。往后看，还有很多要发生。叙事的声音应该有节奏感——不是每一章都一样重。"

        return f"{pos}\n\n时间位置：{time_pos}"

    @staticmethod
    def _derive_forbidden(style: 'StyleProfile | None' = None, genre: str = "玄幻") -> str:
        """从作家声音+思想系统+体裁自动推导'本书绝不写什么'。"""
        forbidden = []

        # From writer voice
        if style and style.writer_voice:
            voice = WRITER_VOICES.get(style.writer_voice)
            if voice:
                if voice.unsaid_ratio > 0.7:
                    forbidden.append("禁止解释人物动机——读者自己判断他为什么这么做")
                    forbidden.append("禁止内心独白超过两句话——用行动和对话代替心理描写")
                if voice.sentence_rhythm == "short":
                    forbidden.append("禁止超过20字的句子——如果一句话太长，拆成两句")
                if voice.imagery_density == "sparse":
                    forbidden.append("禁止用比喻凑字数——要么用一个贯穿全章的核心意象，要么不用比喻")
                if voice.moral_complexity == "ambiguous":
                    forbidden.append("禁止任何角色做出明确的道德判断——'他是对的''她是好人'这类句子绝对不能出现")
                if voice.narrative_distance == "close":
                    forbidden.append("禁止跳出主角视角写'他不知道的是…'或'与此同时在另一个地方…'")

        # From thought system
        if style and style.thought_system:
            ts = style.thought_system[:500].lower()
            if "权力" in ts:
                forbidden.append("禁止用'正义''邪恶'做任何权力的标签——权力只分有效和无效")
            if "道德" in ts or "善恶" in ts:
                forbidden.append("禁止作者在旁白中做道德评判——展示行为，不贴标签")
            if "制度" in ts or "结构" in ts:
                forbidden.append("禁止将任何问题归结为'某人坏'——问'什么制度让他能这么做'")
            if "文化" in ts or "社会" in ts:
                forbidden.append("禁止用个人悲剧解释社会问题——个人是结构的症状，不是原因")

        # From genre
        genre_forbidden = {
            "官场": ["禁止情色描写——权力已经够刺激了，不需要用性来加码",
                     "禁止写'他热爱人民'——官场不写信念，写利益和博弈"],
            "历史": ["禁止穿越/系统/金手指——这是严肃历史文，不是爽文",
                     "禁止篡改已知历史结局——真实历史的重量就是最好的剧情"],
            "科幻": ["禁止用'量子'解释一切——要么用真实科学原理，要么不解释",
                     "禁止AI/外星人成为纯粹的邪恶——它们有自己的逻辑"],
            "悬疑": ["禁止在前三章给出任何确定的答案——每个线索只能引出更多问题",
                     "禁止凶手是精神病人——这是最懒的悬疑套路"],
        }
        for g, rules in genre_forbidden.items():
            if g in genre or (genre and g in genre):
                forbidden.extend(rules)

        # From knowledge_base — if real knowledge exists, forbid fake AI knowledge
        if style and style.knowledge_base and len(style.knowledge_base) > 100:
            forbidden.append("禁止编造任何听起来像AI幻觉的'事实'——如果不知道，就不写，不要用模糊的通用描述代替")

        # Universal rule: simplicity bias
        forbidden.append("禁止连续3句以上超过25字的句子——简单句更接近心脏跳动的节奏")

        if not forbidden:
            return "无特别禁止事项。但请自然写作，避免AI套话和机械感。"

        return "以下内容本章绝对不能出现：\n" + "\n".join(f"- {f}" for f in forbidden[:8])

    def _pre_research(self, chapter_context: str, genre: str, style: 'StyleProfile | None' = None) -> str:
        """
        每章动笔前做一次'专家访谈'——生成该章需要的真实领域知识。
        让读者感觉'这个作者真的懂'。
        """
        if style and style.knowledge_base and len(style.knowledge_base) > 200:
            return style.knowledge_base[:2000]  # Use existing knowledge base

        research_prompt = f"""你是{genre}领域的专家。为以下章节场景提供5条具体、冷门、可以写进小说的真实知识。
这些知识要让读者感觉'这个作者真的懂这一行'。不能是百度百科级别的常识——必须是行业内才知道的细节。

⚠️ 硬约束：每条知识必须是你能100%确认的真实信息。如果你不确定——说'不确定'并跳过。
不要编造任何听起来像事实的东西。宁可少一条，不能有一条假的。

章节情境：{chapter_context[:300]}

输出5条真实细节（每条30字内），包含具体数字、术语、流程或典故。"""
        try:
            knowledge = self._call_llm_with_retry([
                {"role":"system","content":"你是各领域专家。只输出具体、冷门、可验证的真实知识。"},
                {"role":"user","content": research_prompt}
            ], max_tokens=512)
            return knowledge.strip() if knowledge else ""
        except:
            return ""

    @staticmethod
    def _knowledge_injection(style: 'StyleProfile | None' = None) -> str:
        """注入研究级真实细节 — 让读者感受到'这个作者知道我不知道的东西'。"""
        kb = style.knowledge_base if style else ""
        if not kb:
            return "如无特定知识基底，请在细节描写中使用真实世界的参照物——真实的官制/历史事件/科技原理做类比。不要编造听起来像AI的知识。"
        return f"知识基底（本章细节应从以下真实知识库中取材。⚠️ 不要编造任何不在知识库中但'听起来像真的'的事实——宁可模糊，不能编造）：\n{kb[:2000]}"

    @staticmethod
    def _thought_system_injection(style: 'StyleProfile | None' = None) -> str:
        """注入思想系统 — 每个角色的命运是这套哲学的实验案例。"""
        ts = style.thought_system if style else ""
        if not ts:
            return "如无特定思想系统，至少确保本章有一个可以支撑讨论的核心观点——读者读完可以跟别人说'你觉得主角做的对吗'。"
        return f"思想主线（贯穿全书，本章的每个重大选择都应与此呼应）：\n{ts[:1000]}"

    @staticmethod
    def _reading_level_guide(style: 'StyleProfile | None' = None) -> str:
        """阅读层级校准 — 词汇量、句式、文化引用深度。"""
        level = style.reading_level if style else "adult"
        guides = {
            "adult": "面向成年读者：词汇量正常，可以引用文史哲，句式中等复杂度。不用刻意简化也不用刻意炫技。",
            "young_adult": "面向青少年：句子偏短，词汇偏向日常，减少生僻典故。但不要幼稚化——青少年比你想象的聪明。",
            "literary": "面向文学读者：可以复杂句式、生僻词汇、多重隐喻。但不为复杂而复杂——每个复杂句子都要有它存在的理由。",
        }
        return guides.get(level, guides["adult"])

    @staticmethod
    def _title_artistry(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """章节标题艺术 — 标题是第一章的第一印象。"""
        ch = state.total_chapters + 1
        prev_titles = [c.title for c in (state.chapters[-5:] if state.chapters else [])]
        prev_pattern = "、".join(prev_titles) if prev_titles else "无"
        return f"""章节标题规则：
- 标题长度：2-8个字
- 不可与以下标题重复或雷同：{prev_pattern}
- 前三章的标题必须有明显变化——如果第一章是2字意象，第二章可以是悬念型，第三章可以是动作型
- 好的标题示例：意象型「空椅」「暗流」悬念型「谁在钓鱼」「不是他」动作型「破门」「亮剑」情绪型「她没有哭」反差型「好人」「那天阳光很好」
- 禁止：'{ch}''第{ch}章'等序号当标题——这等于放弃黄金广告位"""

    @staticmethod
    def _word_of_mouth_moment(state: 'StoryState') -> str:
        """口碑引爆点 — 每章至少一个值得读者讨论/截图/分享的瞬间。"""
        ch = state.total_chapters + 1
        import random
        moments = [
            "一句神回复——角色在压力下说出一句又狠又真实的话，读者会截图发朋友圈",
            "一个让人心疼的细节——不需要煽情，用一个微小的动作或物品让读者自己心碎",
            "一个道德困境——主角面对两个选择，都有道理，读者会在评论区吵起来",
            "一个意想不到的反转——不是悬疑的反转，是读者对某个角色的判断被推翻",
            "一句'这说的不就是我吗'——让读者产生强烈的自我投射",
            "一个画面感极强的场景——读完闭上眼睛还能看到那个画面",
        ]
        chosen = random.choice(moments)
        return f"口碑引爆点：本章必须有一个{chosen}。这个瞬间不需要长——可能只是一句话、一个动作。但它必须让读者想截图、想转发、想在评论区讨论。平台算法会奖励高互动率的章节。"

    @staticmethod
    def _monetization_guide(state: 'StoryState') -> str:
        """付费转化优化 — 免费章→VIP章的过渡策略。"""
        ch = state.total_chapters + 1
        total = state.total_chapters

        if ch <= 10:
            return """💰 免费引流期（前10章）：目标是把读者喂饱但让他更饿。
- 每章结尾必须让读者立刻点下一章（免费章的追读率决定VIP转化率）
- 不要省着写——免费章是你唯一的广告
- 第8-10章开始埋VIP预告：'接下来的内容需要VIP——你不想错过的'"""

        if 11 <= ch <= 20:
            return """💰 付费转化窗口（11-20章）：这是从免费到付费的桥。
- 这个阶段的质量决定付费转化率（通常3-5%的免费读者会付费）
- 情节进入第一个大高潮——这个高潮必须足够强，让读者觉得'我必须知道接下来发生什么'
- 第15章左右是番茄最常见的付费墙位置——本章必须是全书目前写得最好的一章"""

        if 21 <= ch <= 30:
            return """💰 付费留存期（21-30章）：刚付费的读者最容易流失。
- 刚付了费的读者在看第21章——如果他觉得不值，会立刻弃书并给差评
- 前3章VIP内容（21-23）必须是全书质量最高的章节——让读者觉得'这钱花得值'
- 不要一付费就水字数——这是最愚蠢的做法"""

        if ch >= 50:
            return """💰 稳定收入期（50章+）：读者已经形成付费习惯。
- 保持稳定质量和更新频率——付费读者最怕断更
- 每20章安排一个大高潮——给读者持续的付费理由
- 考虑在第50、80、100章设置特别章节（番外/配角的视角）——提升打赏率"""

        return ""

    @staticmethod
    def _algorithm_optimization(state: 'StoryState') -> str:
        """番茄推荐引擎优化——每章在生成时就知道平台算法在打分什么。"""
        ch = state.total_chapters + 1
        if ch <= 3:
            return """⚠️ 这是前3章——番茄的'首秀'流量窗口。平台用这3章的完读率决定是否给你的书分配后续流量。
算法加分项：前300字必须有冲突/悬念(决定80%读者是否继续)；第1章结尾必须有让读者必须点下一章的钩子；每500字至少一个小刺激点。
算法扣分项：大段说明/旁白(完读率杀手)；平淡的日常描写(读者直接划走)；主角迟迟不出场或没有性格(前200字内立人设)。"""

        if ch % 10 == 0:
            return """⚠️ 每10章是平台算法的一个评估节点——完读率和追读率数据在此更新。
本章建议：结尾用一个有争议的问题或选择——让读者在评论区讨论（互动率=算法加权）。
章节标题要吸引点击（标题点击率也是算法指标之一）。"""

        if ch % 5 == 0:
            return "每5章建议在结尾留一个'读者提问'——提升互动率。标题避免和前几章重复模式。"

        return "保持稳定质量。每章2000-2800字——这是番茄算法最喜欢的章节长度区间。结尾必须有明确钩子。"

    @staticmethod
    def _platform_adaptation(style: 'StyleProfile | None' = None) -> str:
        """平台适配 — 不同平台读者的阅读习惯不同。"""
        platform = style.target_platform if style else "fanqie"
        rules = {
            "fanqie": "番茄读者：碎片时间阅读、扫读为主、前3章决定留存。每章1500-2200字，章末强钩子，标题要吸引点击。",
            "qidian": "起点读者：深度阅读、追更习惯、对字数敏感。每章2500-3500字，节奏可以慢一点但世界观要扎实。",
            "jinjiang": "晋江读者：情感驱动、CP关注度高、评论区活跃。每章2000-3000字，感情线必须有推进，对话占比高。",
            "universal": "通用平台：兼顾碎片和深度读者。每章2000-2800字，钩子和内容深度并重。",
        }
        return rules.get(platform, rules["universal"])

    @staticmethod
    def _ending_mode(state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """结局模式 — 最后3章的专属规则。"""
        remaining = (style.target_word_count if style else (2000,2800))
        total_planned = 50  # default
        ch = state.total_chapters + 1
        if ch < total_planned - 2:
            return ""
        if ch == total_planned - 2:
            return """⚠️ 终章倒数第3章 ⚠️

你是全书的倒数第3章。现在是结束的开始——不再开启新的大剧情线。回收最重要的3条伏笔。让所有角色的位置向结局对齐。节奏加速——不再引入新人物，不再展开新设定。"""
        if ch == total_planned - 1:
            return """⚠️ 终章倒数第2章 ⚠️

你是全书的倒数第2章。最后的高潮。核心追问达到最尖锐的时刻。主角做出不可逆转的决定。这个决定必须让人感觉'他从第1章就在走向这个选择'。"""
        if ch == total_planned:
            return """⚠️ 终章 ⚠️

你是全书的最后一章。不需要交代一切。不需要每个人都得到结局。你需要的是：
1. 用一个画面呼应第1章的某个画面——形成闭环
2. 给主角一个瞬间——ta站在那里，读者知道ta变了
3. 留下一件不解决的事——让读者合上书后还在想
4. 最后一段必须简单——越简单越有力。不要总结。不要升华。"""

        return ""

    @staticmethod
    def _narrative_consciousness(style: 'StyleProfile | None' = None) -> str:
        """叙事意识统一体 — 将所有配置融合成一个'人格'。"""
        if not style:
            return ""
        parts = []
        parts.append(f"你是一本{style.writer_voice or '原创'}风格的小说。")
        if style.thought_system:
            parts.append(f"你的思想底色：{style.thought_system[:200]}")
        if style.central_question:
            parts.append(f"你一直在追问：{style.central_question}")
        if style.soul_statement:
            parts.append(f"你相信：{style.soul_statement[:200]}")
        voice = WRITER_VOICES.get(style.writer_voice) if style.writer_voice else None
        if voice:
            parts.append(f"你的语调：{voice.sentence_rhythm}的句子，{voice.dialogue_style}的对话，{voice.imagery_density}的意象密度。")
            parts.append(f"你的克制：留白{int(voice.unsaid_ratio*100)}%，道德立场{voice.moral_complexity}。")
        if style.open_questions:
            parts.append(f"读者脑中的问题：{'；'.join(style.open_questions[-3:])}")
        return " ".join(parts)

    @staticmethod
    def _symbol_assignment(style: 'StyleProfile | None' = None, state: 'StoryState | None' = None) -> str:
        """符号分配 — 贯穿全书的重复意象系统。"""
        ch = (state.total_chapters + 1) if state else 1
        symbols = style.symbols if style else []
        if not symbols:
            return "无预设符号系统。本章若出现一个物品/动作/画面——考虑让它成为全书的重复意象之一。"
        # Each chapter gets assigned 1-2 symbols from the pool
        assigned = symbols[ch % len(symbols)] if symbols else None
        if not assigned:
            return ""
        return f"本章分配的符号：「{assigned}」\n这个符号在本章看似只是叙事的一部分。它将在至少一章之后被重新照亮——届时读者会想起它第一次出现的时刻。现在不要让它显得重要。"

    @staticmethod
    def _soul_statement_injection(style: 'StyleProfile | None' = None) -> str:
        """书的灵魂 — 它相信什么、害怕什么、希望什么。"""
        ss = style.soul_statement if style else ""
        if not ss:
            return ""
        return f"这本书的灵魂：\n{ss}\n\n本章不是在推进剧情。本章是在为这个灵魂作证。你的每一个句子都应该忠于它相信的东西、尊重它害怕的东西、朝向它希望的东西。"

    @staticmethod
    def _curiosity_ledger(style: 'StyleProfile | None' = None) -> str:
        """好奇心账本 — 读者的未解问题。"""
        questions = style.open_questions if style else []
        if not questions:
            return "读者当前没有特定的未解问题。本章至少提出两个让他们想继续读的问题——一个关于剧情，一个关于角色。"
        qs_str = '\n'.join(f"  {i+1}. {q}" for i, q in enumerate(questions[-5:]))
        return f"读者脑中当前未解的问题：\n{qs_str}\n\n本章规则：\n- 必须解答至少一个上述问题（至少部分解答）\n- 必须提出至少一个新的、更深层次的问题\n- 不能让问题清单超过5个（太乱）或少于2个（失去动力）"

    @staticmethod
    def _emotion_continuity(style: 'StyleProfile | None' = None, state: 'StoryState | None' = None) -> str:
        """情绪连续体 — 上一章留下的情绪，本章带着它转向。"""
        prev_emotion = style.last_chapter_emotion if style else ""
        if not prev_emotion:
            return "本章从头建立情绪。结尾决定下章的情绪起点。"
        # Guide the emotional transition
        transitions = {
            "不安": "读者上章结束感到不安。本章开头先确认这种不安不是多余的——让一个细节证明它。然后中段给出一个安全感（哪怕短暂），结尾带来一种新的不安——和前一个不同但更深的。",
            "悲伤": "读者上章结束感到悲伤。本章开头不要立刻扭转它——让悲伤蔓延。中段出现一个温暖时刻（不必解决问题，只是陪伴），结尾悲伤还在，但多了一层东西——可能是愤怒，可能是释然，可能是更深的悲伤。",
            "希望": "读者上章结束感到希望。本章开头让希望更具体——一个行动、一个决定。中段测试这个希望——它遇到阻力但不破产。结尾希望变形——不再是单纯的乐观，而是'我知道很难但我还是要做'。",
            "愤怒": "读者上章结束感到愤怒。本章开头不要冷却它——给愤怒一个出口。中段让主角行动——不是复仇，是改变。结尾愤怒还在，但已经转化为力量。",
            "困惑": "读者上章结束感到困惑。本章开头不要立刻解释——让困惑更深。然后给一条线索——不是答案，是方向。结尾困惑还在，但读者感觉到'接近了'。",
        }
        guidance = transitions.get(prev_emotion, f"读者上章结束感到{prev_emotion}。本章开头带着它，自然地转向下一个情绪。")
        return f"上章结尾情绪：{prev_emotion}\n{guidance}"

    @staticmethod
    def _central_question_injection(style: 'StyleProfile | None' = None, state: 'StoryState | None' = None) -> str:
        """核心追问 + 主题弧进化 + 章节深度定位。"""
        cq = style.central_question if style else ""
        if not cq and style and style.thought_system:
            ts = style.thought_system[:200]
            if "权力" in ts: cq = "权力到底有没有道德属性？"
            elif "人" in ts and ("AI" in ts or "机器" in ts or "意识" in ts): cq = "当机器可以模拟爱，人类还分得清真假吗？"
            elif "制度" in ts: cq = "好的制度能不能由坏人执行？"
            elif "命运" in ts or "天道" in ts: cq = "如果你知道自己一生的结局，你还会走这条路吗？"
            elif "孤独" in ts: cq = "一个人能不能选择不孤独？"
        if not cq:
            return "如无核心追问，本章至少提出一个没有标准答案的问题。"
        ch = (state.total_chapters + 1) if state else 1
        # Theme evolution — 主题弧：每10章深入一层
        depth = (ch - 1) // 10  # 0=表层, 1=质疑, 2=代价, 3=悖论, 4=超越
        depth_names = ["表层探索","质疑与动摇","代价与后果","悖论与无解","超越与接受"]
        depth_name = depth_names[min(depth, len(depth_names)-1)]
        prev_depth = depth_names[min(max(0,depth-1), len(depth_names)-1)]

        # Reader fatigue management — every 10th chapter is a breather
        is_breather = (ch % 10 == 0 and ch > 3)
        if is_breather:
            angle = "本章是一章喘气章——不需要推进主题深度。写点轻松的人间戏：吃饭、闲聊、日常。让读者在几章高密度思考后喘口气。主题暂时悬置——它会自己回来的。"
        else:
            angle = f"本章处于主题探索的【{depth_name}】阶段（上一阶段是{prev_depth}）。"

        return f"核心追问：{cq}\n\n本章的深度位置：{angle}\n\n要求：本章不能给出标准答案。如果你在【表層】阶段，只是提出困惑；在【质疑】阶段，开始推翻之前的答案；在【代价】阶段，展示坚持信念的后果；在【超越】阶段，不再寻找答案——接受问题本身就是活着的一部分。"

    @staticmethod
    def _writer_voice_context(style: 'StyleProfile | None' = None, genre: str = "玄幻") -> str:
        """作家声音 — 叙事人格注入 + 体裁适配。"""
        if not style or not style.writer_voice:
            return ""
        voice = WRITER_VOICES.get(style.writer_voice)
        if not voice:
            return ""
        base = f"""叙事人格：{voice.description}。
叙事距离：{voice.narrative_distance}。{'贴身POV——读者只能看到主角看到的、想到的。不要跳出写全知视角。' if voice.narrative_distance=='close' else '有限第三人称——可以切换视角，但每段只跟一个人。' if voice.narrative_distance=='medium' else '全知视角——可以写任何人的内心，可以俯瞰场景。'}
句式节奏：{voice.sentence_rhythm}。{'多用短句。每句不超过20字。用句号，少用逗号连句。' if voice.sentence_rhythm=='short' else '长短交替——长句用来描写和内心，短句用来对话和冲突。' if voice.sentence_rhythm=='varied' else '长句流水——允许50字以上的句子，用散文式的铺陈营造氛围。'}
留白比例：{voice.unsaid_ratio*100:.0f}%。{'几乎不解释动机和因果。读者自己拼。' if voice.unsaid_ratio>0.5 else '适当留白——说明必要的，但给读者想象空间。' if voice.unsaid_ratio>0.3 else '把逻辑讲清楚——读者不需要猜发生了什么。'}
道德复杂性：{voice.moral_complexity}。{'没有纯粹的好人和坏人。每个人都有可理解的理由。' if voice.moral_complexity=='gray' else '刻意模糊——不告诉读者谁是对的。' if voice.moral_complexity=='ambiguous' else '黑白分明——有明确的正义和邪恶。'}
意象密度：{voice.imagery_density}。{'用一个核心意象贯穿全章——重复它，变形它。' if voice.imagery_density=='sparse' else '每章1-2个新意象，和情感主题挂钩。' if voice.imagery_density=='moderate' else '意象密集——用比喻和象征填满叙述，让每个物体都有第二层含义。'}
对话风格：{voice.dialogue_style}。{'日常口语——角色说人话，不说书面语。可以有嗯、啊、停顿、打断。' if voice.dialogue_style=='natural' else '风格化——对话有节奏感，可以半文半白，可以像舞台剧。' if voice.dialogue_style=='stylized' else '金句频出——每段对话至少有一句读者会划线分享的话。'}
特殊规则：{voice.special_rule}"""
        # Genre adaptation
        adapt = voice.genre_adaptations.get(genre, "")
        if adapt:
            base += f"\n\n体裁适配（{genre}）：{adapt}"
        return base

    def _build_prompt(self, state: StoryState, author_input: str = "", style: StyleProfile | None = None,
                      rag_context: list[dict] | None = None,
                      outline: list[dict] | None = None) -> list[dict]:
        """构建全自动模式的 messages"""

        # Build outline section
        outline_section = ""
        if outline:
            outline_items = []
            for o in outline[:5]:  # Max 5 outline items for context
                outline_items.append(f"- 第{o.get('number','?')}章「{o.get('title','')}」: {o.get('summary','')}")
            if outline_items:
                outline_section = f"""
## 章节大纲（请按此方向写作）
{chr(10).join(outline_items)}
"""

        # Build RAG context section
        rag_section = ""
        if rag_context:
            rag_items = []
            for r in rag_context[:5]:
                rag_items.append(f"- 第{r.get('chapter_number','?')}章「{r.get('title','')}」: {r.get('chunk_text','')[:200]}")
            if rag_items:
                rag_section = f"""
## 相关历史剧情（语义检索）
{chr(10).join(rag_items)}
"""

                # Load style profile (fall back to genre default)
        if style is None:
            style = _get_style_for_genre(state.genre)
        is_opening = state.total_chapters < 3

        rules = [
            f"生成第{state.total_chapters + 1}章，{style.target_word_count[0]}-{style.target_word_count[1]}字",
            f"场景切换{style.scene_changes_per_chapter}次以上",
        ]
        if is_opening:
            if style.opening_type == "atmosphere":
                rules.append("开篇：时间+地点+一个不寻常的细节，紧张感逐步叠加，不急于亮底牌")
            elif style.opening_type == "dilemma":
                rules.append("开篇：主角已经处于困境中，直接面对后果。不解释发生了什么")
            elif style.opening_type == "impact":
                rules.append("开篇：感官信息直接砸下来（声音/温度/视觉），立刻让读者置身其中")
            else:
                rules.append("开篇：场景定位 + 一个反常细节 + 困境暗示，三要素都要有")
            rules.append("前300字不解释世界观，让读者自己拼")
            if state.total_chapters == 0:
                rules.append("第1章必须在2000字内亮出核心设定/金手指")
            rules.append(f"对话占比{style.dialogue_ratio[0]*100:.0f}-{style.dialogue_ratio[1]*100:.0f}%，通过对话推进设定")
            rules.append("结尾最后一句话必须以问号、感叹号、省略号或破折号结尾。必须包含一个未回答的问题或刚出现的威胁——让读者不可能不点下一章。注意：最后三个字必须是？！……——之一，不能用句号结尾")
        else:
            rules.append(f"对话占比{style.dialogue_ratio[0]*100:.0f}-{style.dialogue_ratio[1]*100:.0f}%，通过对话推进剧情")
            rules.append("结尾：让主角面临一个必须立刻做出的选择，或让隐藏的威胁突然显现。最后一段用不超过20字的极短句制造紧迫感，优先使用问号或感叹号")
        hook_names = "、".join(style.hook_types[:3])
        rules.append(f"每{style.hook_interval_words}字左右设一个微钩子，优先用: {hook_names}")
        rules.append(f"段落{style.paragraph_len[0]}-{style.paragraph_len[1]}字，长短交替，避免均匀段落。对话密集处段落自然短（10-30字），叙述处段落稍长（80-150字），绝对不要出现连续3段以上的纯说明/纯叙述")
        cliches = "、".join(style.avoid_cliches) if style.avoid_cliches else "在这个世界里、随着时间推移、不仅如此"
        rules.append(f"禁止使用以下AI套话句式: {cliches}")
        # Antagonist rule — genre-specific threat behavior
        antagonist = next((c for c in state.characters if c.role == "反派"), None)
        if antagonist:
            if state.genre in ("都市", "现实"):
                rules.append(f"反派「{antagonist.name}」本章必须让主角感受到一个可感知的威胁后果——不需要反派亲自出场，但必须有一件因反派而起的事让主角处境恶化。可选：主角的盟友被调走(主角亲眼看到空办公室)、主角的项目被冻结(收到书面通知)、主角在会议上被公开架空(其他人都收到了'打招呼'后的沉默)、主角发现自己在被跟踪或监听")
            elif state.genre in ("玄幻", "仙侠", "武侠"):
                rules.append(f"反派「{antagonist.name}」本章必须有至少一个直接冲突场景：偷袭/截杀/约战/夺宝。冲突必须具体描写，不能一笔带过")
            elif state.genre in ("悬疑", "灵异", "恐怖"):
                rules.append(f"反派「{antagonist.name}」本章必须留下至少一个可感知的威胁痕迹：跟踪/匿名信/嫁祸/证人消失。威胁逐步逼近，制造窒息感")
            else:
                rules.append(f"反派「{antagonist.name}」本章必须有至少一个主动出击的行为——他不能只是说话，必须做一件让主角处境恶化的事")

        rules.append(f"节奏模式: {style.pace_pattern}")
        if style.title_style == "意象":
            rules.append(f"章节标题: {style.title_max_chars}字以内意象/概念，暗示本章核心")
        elif style.title_style == "悬念":
            rules.append(f"章节标题: 一句话悬念，不超过{style.title_max_chars}字")
        else:
            rules.append(f"章节标题: 直接点明核心爽点，不超过{style.title_max_chars}字")
        for r in style.special_rules:
            rules.append(r)
        requirements = "## 写作要求" + ("（开篇专用）" if is_opening else "") + "\n" + "\n".join(
            f"{i+1}. {r}" for i, r in enumerate(rules)) + "\n"


        system = f"""你是一位职业网文作家，专攻{state.genre}类型。你的文笔老练、节奏紧凑、善于制造冲突和钩子。{outline_section}{rag_section}
## 世界观
- 世界名称：{state.world.name}
- 时代背景：{state.world.era}
- 修炼体系：{state.world.power_system}
- 地理：{state.world.geography}

## 角色档案
{state.character_context()}

## 故事进度
主线：{state.plot.main_arc}
当前篇章：{state.plot.current_arc}（从第{state.plot.arc_chapter_start}章开始）
后续剧情目标：{', '.join(state.plot.next_plot_points) if state.plot.next_plot_points else '自行发展'}
{self._foreshadowing_context(state)}

## 最近章节摘要
{state.recent_context(5) if state.total_chapters > 0 else '这是小说的第一章。'}

## 上一章全文（注意保持文风、对话习惯、描写节奏一致）
{state.latest_chapter.content if state.latest_chapter and state.latest_chapter.content else '（无）'}

## 全书节奏定位
{self._arc_position_context(state.total_chapters + 1)}

## 情绪预算（读者当前神经状态——据此设计本章的"收"与"放"）
{self._emotion_budget_context(state, style)}

## 节奏控制（段落级的加速与停留——不是"500字一钩"的打卡式节奏）
{self._rhythm_guide(state, style)}

## 留白约束（好文章70%没说——本章必须保留的几处"不解释"）
{self._gap_rule(state, style)}

## 本书绝不出现在本章的东西（这是减法的力量——能写好但坚决不写，比什么都重要）
{self._derive_forbidden(style, state.genre)}

## 知识注入（作者花了功夫知道的真实细节——你不是在编故事，你是在分享你知道的事）
{self._knowledge_injection(style)}

## 思想链条（全书的思想主线——本章的每个角色命运都应该是这套思想的案例）
{self._thought_system_injection(style)}

## 叙事意识——你是谁（这不是规则列表——这是你的人格。下面这段是你对自己的理解。吸收它，成为它）
{self._narrative_consciousness(style)}
{self._ending_mode(state, style)}

## 平台适配（这本书要发布在什么平台——读者预期不同，写法不同）
{self._platform_adaptation(style)}

## 番茄算法优化（你的章节在被一个AI推荐引擎打分——以下行为会加分或扣分）
{self._algorithm_optimization(state)}

## 付费转化优化（免费章→VIP章的过渡是收入的关键。本章在付费漏斗中的位置决定了它应该怎么写）
{self._monetization_guide(state)}

## 口碑引爆点（平台赚广告费靠留存，读者口碑靠'这句话我想转发'。本章必须有一个值得被讨论、被截图、被分享的瞬间）
{self._word_of_mouth_moment(state)}

## 阅读层级（这本书写给谁看——词汇量、句式复杂度、文化引用深度都由此决定）
{self._reading_level_guide(style)}

## 章节标题艺术（标题不是标签——它是读者在第一秒看到的钩子。好的章节标题让人想点开，好的章节标题序列形成节奏）
{self._title_artistry(state, style)}

## 书的灵魂（这本书相信什么、害怕什么、希望什么——本章不是写剧情，是在为这个灵魂作证）
{self._soul_statement_injection(style)}

## 符号分配（本章出现的这个符号，将在未来的章节被重新照亮——现在它看起来只是叙事的一部分）
{self._symbol_assignment(style, state)}

## 核心追问（这本书唯一在问的问题。本章提供一种回答——但不给标准答案。不同角色用不同的命运回答同一个问题）
{self._central_question_injection(style, state)}

## 情绪连续体（上章在你心里留下了一种情绪——本章开头带着它，然后转向一个新的情绪方向）
{self._emotion_continuity(style, state)}

## 好奇心账本（读者脑中当前未解答的问题——本章必须解答至少一个，并至少新增一个更深的问题）
{self._curiosity_ledger(style)}

## 场景密度（本章每个场景必须承担至少三个功能——推进剧情+揭示人物+提供信息/情感冲击。不能有只做一件事的场景）
场景要求：每个场景同时推进剧情、揭示角色性格、并提供一条读者之前不知道的信息。如果一个场景只做了一件事，重写它。

## 回响标记（经典不是写出来的——是前文和后文互相照亮。本章必须与前文形成至少一处回响）
{self._echo_guide(state)}

## 重读密码（第一遍阅读时不起眼、第二遍阅读时脊背发凉的元素。这些是给愿意重读的读者的礼物）
{self._reread_layer(state, style)}

## 读者预测模型（读者此刻认为的'真相'是什么？本章先让读者觉得'我猜对了'——然后让他发现他猜错了，但新解释比他猜的更有力）
{self._reader_prediction_model(state, style)}

## 蓄意破坏——如果你被允许（极少章节才激活此权限。如果本章不是破坏章，忽略此条）
{self._orchestrated_rupture(state, style)}

## 叙事者的位置（谁在讲这个故事，站在什么时间点上讲——这是小说和故事的区别）
{self._narrator_position(state, style)}

## 作家声音（这不是写作指南，这是你的叙事人格——吸收它，成为它，不要模仿它）
{self._writer_voice_context(style, state.genre)}

{self._writing_warmup(state, style)}

{requirements}
"""

        user = f"请写第{state.total_chapters + 1}章。"
        if outline:
            next_ol = [o for o in outline if o.get('number') == state.total_chapters + 1]
            if next_ol:
                n = next_ol[0]
                user += f"\n本章大纲：{n.get('title','')} — {n.get('summary','')}"
        ending_hook = ""
        if state.latest_chapter and state.latest_chapter.ending_hook:
            ending_hook = f"\n上一章结尾钩子：{state.latest_chapter.ending_hook}"
        if author_input:
            user += f"\n本章方向：{author_input}"
        user += ending_hook

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _build_direction_prompt(
        self, state: StoryState, author_input: str, n: int
    ) -> list[dict]:
        """构建方向草稿的 prompt"""
        context = self._build_prompt(state, author_input)
        direction_instruction = f"""
基于以上设定，请为第{state.total_chapters + 1}章生成 {n} 个不同的剧情走向。

每个走向包含：
1. 标记：A/B/C
2. 走向概述（一句话）
3. 开头预览（200-300字）
4. 本章结尾钩子

格式：
### 走向A
**概述**：...
**预览**：...
**钩子**：...

### 走向B
...

要求：
- 3个走向要有明显差异（不同冲突点、不同节奏、不同侧重点）
- 每个走向都合理且符合人物设定
- 作者方向是：{author_input}
"""
        return [
            {"role": "system", "content": context[0]["content"]},
            {"role": "user", "content": direction_instruction},
        ]

    def _build_expand_prompt(
        self, state: StoryState, chosen: DraftOption, edits: str
    ) -> list[dict]:
        """构建展开全文的 prompt"""
        base = self._build_prompt(state, "")
        expand_instruction = f"""
请写第{state.total_chapters + 1}章完整正文，2000-3000字。

选定方向：{chosen.direction}
预览开头：{chosen.preview}
结尾钩子：{chosen.hook}
"""
        if edits:
            expand_instruction += f"\n作者修改意见：{edits}"

        return [
            {"role": "system", "content": base[0]["content"]},
            {"role": "user", "content": expand_instruction},
        ]

    # ==================== LLM 调用 ====================

    @staticmethod
    def _strip_thinking(content: str) -> str:
        """Remove <think>...</think> blocks from reasoning model output."""
        if '<think>' in content:
            content = re.sub(r'<think>[\s\S]*?</think>\s*', '', content)
        return content.strip()

    # Cost tracking — per-call accumulator
    _last_usage: dict = {}

    @staticmethod
    def _calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD based on model pricing (per 1M tokens)."""
        pricing = {
            "deepseek-chat": (0.14, 0.28),
            "deepseek-v4-pro": (0.14, 0.28),
            "deepseek-v4-flash": (0.14, 0.28),
            "minimax": (0.50, 2.00),
        }
        ip, op = pricing.get(model, pricing.get(model.split("-")[0], (0.50, 2.00)))
        return (prompt_tokens * ip + completion_tokens * op) / 1_000_000

    def _call_llm_with_retry(
        self,
        messages: list[dict],
        max_tokens: int = 8192,
    ) -> str:
        """调用 LLM，主模型失败则切备选。Non-streaming version for post-processing."""
        primary_errors: list[str] = []
        fallback_errors: list[str] = []

        for attempt in range(3):
            try:
                resp = self.client.chat.completions.create(
                    model=self.cfg.model,
                    messages=messages,
                    temperature=self.cfg.temperature,
                    max_tokens=max_tokens,
                )
                content = resp.choices[0].message.content or ""
                content = self._strip_thinking(content)
                if content.strip():
                    if resp.usage:
                        self._last_usage = {
                            "model": self.cfg.model,
                            "prompt_tokens": resp.usage.prompt_tokens,
                            "completion_tokens": resp.usage.completion_tokens,
                            "total_tokens": resp.usage.total_tokens,
                            "cost": self._calc_cost(self.cfg.model, resp.usage.prompt_tokens, resp.usage.completion_tokens),
                        }
                    return content
                print(f"[LLM] 主模型返回空内容 (attempt {attempt+1})")
            except Exception as e:
                err = f"[attempt {attempt+1}] {type(e).__name__}: {str(e)[:300]}"
                primary_errors.append(err)
                print(f"[LLM] 主模型({self.cfg.model})错误: {err}", file=__import__("sys").stderr)
            time.sleep(2 ** attempt)

        self._init_fallback()
        if self.fallback_client:
            for attempt in range(2):
                try:
                    resp = self.fallback_client.chat.completions.create(
                        model=getattr(self, '_fallback_model', 'gpt-4o-mini'),
                        messages=messages,
                        temperature=0.85,
                        max_tokens=max_tokens,
                    )
                    content = resp.choices[0].message.content or ""
                    content = self._strip_thinking(content)
                    if content.strip():
                        if resp.usage:
                            self._last_usage = {
                                "model": getattr(self, '_fallback_model', 'gpt-4o-mini'),
                                "prompt_tokens": resp.usage.prompt_tokens,
                                "completion_tokens": resp.usage.completion_tokens,
                                "total_tokens": resp.usage.total_tokens,
                                "cost": self._calc_cost(getattr(self, '_fallback_model', 'gpt-4o-mini'), resp.usage.prompt_tokens, resp.usage.completion_tokens),
                            }
                        print("[LLM] 备选模型成功")
                        return content
                except Exception as e:
                    err = f"[attempt {attempt+1}] {type(e).__name__}: {str(e)[:300]}"
                    fallback_errors.append(err)
                time.sleep(2 ** attempt)

        err_parts = [f"主模型({self.cfg.model})失败: {'; '.join(primary_errors[-2:])}"]
        if fallback_errors:
            err_parts.append(f"备选失败: {'; '.join(fallback_errors[-1:])}")
        raise RuntimeError(" | ".join(err_parts))

    def _call_llm_streaming(
        self,
        messages: list[dict],
        max_tokens: int = 8192,
    ) -> str:
        """Streaming version — yields partial content via callback to enable live preview."""
        primary_errors: list[str] = []
        fallback_errors: list[str] = []

        # 尝试主模型（streaming）
        for attempt in range(3):
            try:
                stream = self.client.chat.completions.create(
                    model=self.cfg.model,
                    messages=messages,
                    temperature=self.cfg.temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    stream_options={"include_usage": True},
                )
                chunks: list[str] = []
                usage = None
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        chunks.append(text)
                        # Callback for live preview
                        if hasattr(self, '_on_stream_chunk') and self._on_stream_chunk:
                            self._on_stream_chunk(''.join(chunks))
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage = chunk.usage
                content = ''.join(chunks)
                content = self._strip_thinking(content)
                if content.strip():
                    if usage:
                        self._last_usage = {
                            "model": self.cfg.model,
                            "prompt_tokens": usage.prompt_tokens,
                            "completion_tokens": usage.completion_tokens,
                            "total_tokens": usage.total_tokens,
                            "cost": self._calc_cost(self.cfg.model, usage.prompt_tokens, usage.completion_tokens),
                        }
                    return content
                print(f"[LLM] 主模型返回空内容 (attempt {attempt+1})")
            except Exception as e:
                err = f"[attempt {attempt+1}] {type(e).__name__}: {str(e)[:300]}"
                primary_errors.append(err)
                print(f"[LLM] 主模型({self.cfg.model})错误: {err}", file=__import__("sys").stderr)
            time.sleep(2 ** attempt)  # 指数退避

        # 尝试备选模型
        self._init_fallback()
        if self.fallback_client:
            for attempt in range(2):
                try:
                    resp = self.fallback_client.chat.completions.create(
                        model=getattr(self, '_fallback_model', 'gpt-4o-mini'),
                        messages=messages,
                        temperature=0.85,
                        max_tokens=max_tokens,
                    )
                    content = resp.choices[0].message.content or ""
                    content = self._strip_thinking(content)
                    if content.strip():
                        if resp.usage:
                            self._last_usage = {
                                "model": "deepseek-chat",
                                "prompt_tokens": resp.usage.prompt_tokens,
                                "completion_tokens": resp.usage.completion_tokens,
                                "total_tokens": resp.usage.total_tokens,
                                "cost": self._calc_cost("deepseek-chat", resp.usage.prompt_tokens, resp.usage.completion_tokens),
                            }
                        print("[LLM] 备选模型成功")
                        return content
                except Exception as e:
                    err = f"[attempt {attempt+1}] {type(e).__name__}: {str(e)[:300]}"
                    fallback_errors.append(err)
                    print(f"[LLM] 备选模型错误: {err}", file=__import__("sys").stderr)
                time.sleep(2 ** attempt)

        # Build clear error message
        err_parts = [f"主模型({self.cfg.model})失败: {'; '.join(primary_errors[-2:])}"]
        if fallback_errors:
            err_parts.append(f"备选失败: {'; '.join(fallback_errors[-1:])}")
        raise RuntimeError(" | ".join(err_parts))

    # ==================== 响应解析 ====================

    _TITLE_PATTERNS = [
        re.compile(r"第[零一二三四五六七八九十百千\d]+章\s*[：:\s]*(.+)"),
        re.compile(r"^#+\s*(.+?)(?:\n|$)"),
        re.compile(r"^(.+?)(?:\n|$)", re.MULTILINE),
    ]

    def _parse_response(
        self, raw: str, chapter_num: int
    ) -> tuple[str, str, dict]:
        """
        从 LLM 响应中提取 (标题, 正文, 元数据)。

        支持的格式：
        1. Markdown: ## 标题 / ## 正文 / ## 元数据
        2. 自然文本：第一行是标题
        3. 自由格式：尝试从文本中分离
        """

        # 尝试 Markdown 格式分割
        sections = self._split_markdown_sections(raw)

        if "标题" in sections or "title" in sections:
            title = sections.get("标题") or sections.get("title", "")
        else:
            title = self._extract_title_from_text(raw, chapter_num)

        body = sections.get("正文") or sections.get("body", "") or raw
        meta_raw = sections.get("元数据") or sections.get("meta", "") or sections.get("metadata", "")
        meta = self._parse_meta_json(meta_raw)

        # 如果标题为空，从正文第一行提取
        if not title.strip():
            title = self._extract_title_from_text(body, chapter_num)

        return title.strip(), body.strip(), meta

    def _split_markdown_sections(self, raw: str) -> dict[str, str]:
        """按 ## 标题 分割文本为 key-value"""
        sections = {}
        current_key = "body"
        current_content = []

        for line in raw.split("\n"):
            m = re.match(r"^##\s+(.+)", line)
            if m:
                if current_content:
                    sections[current_key.lower()] = "\n".join(current_content).strip()
                current_key = m.group(1).strip()
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections[current_key.lower()] = "\n".join(current_content).strip()

        return sections

    def _extract_title_from_text(self, text: str, chapter_num: int) -> str:
        """从文本中提取章节标题"""
        # 匹配 "第N章 标题" 格式
        m = re.search(rf"第{chapter_num}[章節]\s*[：:\s]*(.+)", text)
        if m:
            return m.group(1).strip()
        # 取第一行，去掉 markdown 标记
        first_line = text.strip().split("\n")[0]
        first_line = re.sub(r'^#+\s*', '', first_line).strip()
        # 如果第一行是 "第X章：标题" 则只取标题部分
        m2 = re.search(r"第\d+[章節]\s*[：:\s]*(.+)", first_line)
        if m2:
            return m2.group(1).strip()
        if len(first_line) < 60:
            return first_line
        return f"第{chapter_num}章"

    def _parse_meta_json(self, raw: str) -> dict:
        """从文本中提取 JSON 元数据"""
        # 尝试找 ```json ... ``` 块
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试找裸 JSON
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    def _parse_directions(self, raw: str) -> list[DraftOption]:
        """解析方向草稿"""
        options = []
        # 按 "走向A" "走向B" 等分割
        blocks = re.split(r"\n(?=###\s*走向[A-C])", raw)
        if len(blocks) < 2:
            blocks = re.split(r"\n(?=##\s*走向[A-C])", raw)

        for block in blocks:
            label_match = re.search(r"走向\s*([A-C])", block)
            if not label_match:
                continue
            label = label_match.group(1)

            overview = ""
            preview = ""
            hook = ""
            for part in re.split(r"\*\*(.+?)\*\*", block):
                part = part.strip()
                if "概述" in part:
                    idx = block.find(part) + len(part)
                    rest = block[idx:].strip()
                    rest = rest.lstrip("：:").strip()
                    overview = rest.split("\n")[0].strip()
                elif "预览" in part:
                    idx = block.find(f"**{part}**") + len(part) + 4
                    rest = block[idx:].strip()
                    rest = rest.lstrip("：:").strip()
                    preview = rest.split("**钩子**")[0].split("**概述**")[0].strip()[:500]
                elif "钩子" in part:
                    idx = block.find(f"**{part}**") + len(part) + 4
                    rest = block[idx:].strip()
                    rest = rest.lstrip("：:").strip()
                    hook = rest.split("\n")[0].strip()

            if overview:
                options.append(DraftOption(
                    id=label,
                    title=f"走向{label}",
                    direction=overview,
                    preview=preview[:500],
                    hook=hook,
                ))

        return options

    # ==================== 质量检测 ====================

    def _check_quality(self, body: str, state: StoryState) -> QualityReport:
        """质量检测"""
        issues = []
        word_count = len(body)

        if word_count < 1500:
            issues.append(f"字数不足 ({word_count} < 1500)")
        if word_count > 8000:
            issues.append(f"字数过多 ({word_count} > 8000)")

        # 主角出场检测
        protagonist = state.protagonist
        if protagonist and protagonist.name not in body:
            issues.append(f"主角「{protagonist.name}」未出场")

        # 重复度检测
        if state.total_chapters >= 1:
            prev_chapter = state.latest_chapter
            if prev_chapter and prev_chapter.summary:
                # 简单检测：如果正文和上一章摘要高度重叠（>50% 共同子串）
                pass  # 复杂重复度检测留到 V2

        return QualityReport(
            passed=len(issues) == 0,
            word_count=word_count,
            issues=issues,
        )

    # ==================== 状态更新 ====================

    def _update_state(
        self,
        state: StoryState,
        chapter: ChapterMeta,
        meta: dict,
    ):
        """在生成后更新故事状态"""
        # 推进剧情 — 伏笔模糊匹配回收
        resolved = meta.get("resolved_foreshadowing", [])
        new_foreshadowing = meta.get("new_foreshadowing", [])
        if isinstance(resolved, list):
            for item in resolved:
                matched = self._fuzzy_match(item, state.plot.foreshadowing)
                if matched:
                    state.plot.foreshadowing.remove(matched)
                    state.plot.resolved_foreshadowing.append({
                        "content": matched, "chapter": chapter.number,
                    })
        if isinstance(new_foreshadowing, list):
            for item in new_foreshadowing:
                # 去重：不重复添加相似伏笔
                if not self._fuzzy_match(item, state.plot.foreshadowing):
                    state.plot.foreshadowing.append(item)

        # 更新剧情目标
        new_points = meta.get("updated_plot_points", [])
        if isinstance(new_points, list) and new_points:
            state.plot.next_plot_points = new_points

        # 角色状态更新
        char_updates = meta.get("character_updates", {})
        if isinstance(char_updates, dict):
            for char in state.characters:
                if char.name in char_updates:
                    update = char_updates[char.name]
                    if "power_level" in update:
                        char.current_power_level = update["power_level"]
                    if "status" in update:
                        char.status = update["status"]

    def _fuzzy_match(self, item: str, candidates: list[str], threshold: float = 0.4) -> str | None:
        """在 candidates 中找最相似的，Jaccard 系数 > threshold 返回匹配项。"""
        if not item or not candidates:
            return None
        item_chars = set(item.replace(" ", ""))
        best_score, best_match = 0.0, None
        for c in candidates:
            c_chars = set(c.replace(" ", ""))
            if not item_chars or not c_chars:
                continue
            score = len(item_chars & c_chars) / len(item_chars | c_chars)
            if score > best_score:
                best_score, best_match = score, c
        return best_match if best_score >= threshold else None

    def _extract_character_voices(self, body: str, state: 'StoryState'):
        """从章节正文提取角色对白特征，更新 Character.voice_* 字段。"""
        for char in state.characters:
            if not char.name:
                continue
            # Find dialogue segments attributed to this character
            # Pattern: name followed by "说/道/问/喊/叫/叹" or name before "："
            pattern = re.compile(
                rf'{re.escape(char.name)}\s*(?:说|道|问|喊|叫|叹|笑|冷[笑哼]|怒[喝道]|淡[淡然])[：:]?\s*[""](.+?)[""]'
                r'|'
                rf'{re.escape(char.name)}[：:]\s*(.+?)(?:\n|$)',
                re.DOTALL,
            )
            dialogues = []
            for m in pattern.finditer(body):
                dlg = m.group(1) or m.group(2)
                if dlg:
                    dialogues.append(dlg.strip())

            if not dialogues:
                continue  # no dialogue this chapter, keep old voice

            # Compute voice metrics
            sentences = []
            for d in dialogues:
                # Split on Chinese/English punctuation
                parts = re.split(r'[。！？；…\.\!\?\;\n]', d)
                sentences.extend([s.strip() for s in parts if s.strip()])

            if sentences:
                char.voice_avg_sentence_len = round(
                    sum(len(s) for s in sentences) / len(sentences), 1
                )
                char.voice_question_ratio = round(
                    sum(1 for s in sentences if '？' in s or '?' in s) / len(sentences), 2
                )
                # Common words: 2-char words appearing >= 2 times
                all_text = ''.join(dialogues)
                word_freq: dict[str, int] = {}
                for i in range(len(all_text) - 1):
                    w = all_text[i:i+2]
                    if re.match(r'[一-鿿]{2}', w):
                        word_freq[w] = word_freq.get(w, 0) + 1
                char.voice_common_words = [w for w, c in word_freq.items() if c >= 2][:8]
                # Representative sample: longest dialogue line
                char.voice_sample = max(dialogues, key=len) if dialogues else ""

            # Persist to DB
            try:
                from .database import Database
                db = Database()
                db.save_character_voice(state.novel_id, char.id, {
                    "avg_sentence_len": char.voice_avg_sentence_len,
                    "question_ratio": char.voice_question_ratio,
                    "common_words": char.voice_common_words,
                    "sample": char.voice_sample,
                })
            except Exception:
                pass  # Non-critical, continue without persistence

    def audit_foreshadowing(self, state: 'StoryState') -> dict:
        """每 10 章审计一次伏笔状态。返回未回收、超期列表和警告。"""
        total_open = len(state.plot.foreshadowing)
        oldest_open = 0
        stale = []
        # Find oldest unrecovered — scan from current arc start
        chapter_num = state.total_chapters
        for item in state.plot.foreshadowing:
            # Try to extract chapter number from item like "[第X章埋]"
            m = re.search(r'\[第(\d+)章埋\]', item)
            buried_chapter = int(m.group(1)) if m else 0
            if buried_chapter > 0:
                age = chapter_num - buried_chapter
                if oldest_open == 0 or buried_chapter < oldest_open:
                    oldest_open = buried_chapter
                if age > 10:
                    stale.append({
                        "content": re.sub(r'\[第\d+章埋\]\s*', '', item),
                        "buried_chapter": buried_chapter,
                        "age": age,
                    })

        warning = ""
        if len(stale) >= 3:
            warning = f"有 {len(stale)} 条伏笔超过 10 章未回收，建议在近期章节中处理"
        elif len(stale) > 0:
            names = [s['content'][:20] for s in stale[:3]]
            warning = f"伏笔「{'」「'.join(names)}」超过10章未回收"

        return {
            "total_open": total_open,
            "total_resolved": len(state.plot.resolved_foreshadowing),
            "oldest_open_chapter": oldest_open,
            "stale": stale,
            "warning": warning,
        }



    def judge_quality(self, body: str, state: 'StoryState', style: 'StyleProfile | None' = None) -> dict:
        """
        LLM Judge: send chapter to LLM for holistic quality evaluation.
        Returns same dict format as score_quality with richer feedback.
        Falls back to regex score_quality on failure.
        """
        judge_prompt = f"""你是资深网文编辑，请评估以下章节质量。每维评 1-10 分并给出简短理由。

## 评分维度
1. **钩子强度** (1-10)：结尾是否让人必须看下一章？悬念/反转/危机是否有效？
2. **节奏感** (1-10)：段落长短交替是否自然？场景切换是否流畅？有无拖沓或跳跃？
3. **对话自然度** (1-10)：对话是否推动剧情？人物说话是否有区分度？有无废话/解释性对话？
4. **可读性** (1-10)：句子是否流畅？有无 AI 套话痕迹？读起来累不累？
5. **反派压迫感** (1-10)：反派在本章中是否有具体的、让主角处境恶化的行动？（不是旁白说"他很危险"，而是他做了什么让读者感到威胁）
6. **是否想追读** (1-10)：以一个付费读者的身份回答——你会不会点下一章？为什么？

## 评估要求
- 每个分数必须基于章节正文内容给出，不能凭感觉
- 理由必须引用具体段落或对话作为证据（15字以内，不需要引用原文）
- 综合意见：一句话指出本章最大的问题（如果有的话）
- 反派压迫感评判标准：官场/都市文不要求反派亲自出场，但必须有"可感知的威胁后果"（盟友被调走/项目被冻结/被公开架空/被跟踪）。只有台词没有行动 → ≤4分；有间接行动但主角未察觉 → 5-6分；主角直接承受了反派行动的后果 → 7-9分

## 输出格式（严格 JSON，不要 markdown 代码块标记）
{{
  "hook": {{"score": 7, "reason": "结尾的反问句制造了悬念但缺乏紧迫感"}},
  "pacing": {{"score": 8, "reason": "打斗段落后紧跟对话段落，节奏松弛有度"}},
  "dialogue": {{"score": 6, "reason": "配角对话偏功能化，缺乏个性语气词"}},
  "readability": {{"score": 8, "reason": "句式有变化但第三段偏长可以拆分"}},
  "antagonist": {{"score": 4, "reason": "赵明德只说了几句话就退场，没有主动出击"}},
  "want_next": {{"score": 7, "reason": "想知道丹药能否炼成，但反派动机铺垫不够"}},
  "biggest_issue": "反派鬼手的威胁感没有建立起来，导致结尾反转冲击力不足"
}}

## 章节正文
{body[:6000]}

## 评估结果（纯 JSON）："""

        messages = [
            {"role": "system", "content": "你是专业网文编辑评估系统。你只输出 JSON，不加任何解释、markdown、前缀或后缀。评估基于具体文本证据。"},
            {"role": "user", "content": judge_prompt},
        ]
        try:
            raw = self._call_llm_with_retry(messages, max_tokens=1024)
            # Extract JSON — might be wrapped in ``` or have trailing text
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                result = json.loads(json_match.group(0))
                # Convert 1-10 to 0-1 scale
                scores = {}
                dims = {"hook", "pacing", "dialogue", "readability", "antagonist", "want_next"}
                for dim in dims:
                    item = result.get(dim, {})
                    if isinstance(item, dict):
                        scores[dim] = round(item.get("score", 5) / 10, 2)
                    else:
                        scores[dim] = 0.5
                scores["coherence"] = min(1.0, len(body) / 2500 * 0.7 + 0.3)
                scores["consistency"] = 0.85  # baseline, voice check adds separately
                scores["show_dont_tell"] = 1.0  # LLM already evaluates holistically
                overall = sum(scores.values()) / len(scores)
                return {
                    "scores": scores,
                    "overall": round(overall, 2),
                    "passed": overall >= 0.5,
                    "grade": "A" if overall >= 0.8 else "B" if overall >= 0.6 else "C" if overall >= 0.4 else "D",
                    "issues": [result.get("biggest_issue", "")] if result.get("biggest_issue") else [],
                    "word_count": len(body),
                    "judge_detail": result,
                    "method": "llm",
                }
        except Exception as e:
            print(f"[JUDGE] LLM judge failed ({e}), falling back to regex", file=__import__("sys").stderr)

        # Fallback to regex scoring
        return self.score_quality(body, state, style)

    def score_quality(self, body: str, state: 'StoryState', style: 'StyleProfile | None' = None) -> dict:
        """
        Multi-dimension quality scoring (0-1 each) + genre-specific checks.
        Returns dict with scores and overall pass/fail.
        """
        scores = {}
        issues = []
        paragraphs = [p for p in body.split('\n') if p.strip()]  # Shared across dimensions

        # 1. Coherence (连贯性) — word count baseline
        wc = len(body)
        if wc >= 2500:
            scores['coherence'] = 0.9
        elif wc >= 2000:
            scores['coherence'] = 0.7
        elif wc >= 1500:
            scores['coherence'] = 0.5
        elif wc >= 800:
            scores['coherence'] = 0.3
        else:
            scores['coherence'] = 0.1
            issues.append(f'字数不足({wc})')

        # 2. Consistency (一致性) — protagonist presence + power level + dialogue style
        protagonist = state.protagonist
        if protagonist and protagonist.name in body:
            scores['consistency'] = 0.75
            # Bonus: power level mentioned
            if protagonist.current_power_level and protagonist.current_power_level in body:
                scores['consistency'] += 0.1
            # Bonus: character dialogue present (not pure narration)
            proto_dialogue_lines = [p for p in paragraphs if protagonist.name in p and ('”' in p or '”' in p or '：' in p[-10:])]
            if proto_dialogue_lines:
                scores['consistency'] += 0.1
            # Bonus: voice consistency — dialogue sentence length within ±40% of tracked voice
            if protagonist.voice_avg_sentence_len > 0 and proto_dialogue_lines:
                proto_sentences = []
                for p in proto_dialogue_lines:
                    parts = re.split(r'[。！？；…]', p)
                    proto_sentences.extend([s.strip() for s in parts if s.strip()])
                if proto_sentences:
                    avg_this_chapter = sum(len(s) for s in proto_sentences) / len(proto_sentences)
                    if 0.6 < avg_this_chapter / max(protagonist.voice_avg_sentence_len, 1) < 1.4:
                        scores['consistency'] += 0.05
            scores['consistency'] = min(scores['consistency'], 0.95)
        else:
            scores['consistency'] = 0.2
            if protagonist:
                issues.append(f'主角「{protagonist.name}」未出场')

        # 3. Pacing (节奏) — paragraph structure with dialogue-aware scoring
        if len(paragraphs) >= 8:
            avg_len = sum(len(p) for p in paragraphs) / len(paragraphs)
            # Count short paragraphs (dialogue-heavy, < 40 chars)
            short_count = sum(1 for p in paragraphs if len(p) < 40)
            dialogue_heavy = short_count / len(paragraphs) > 0.4  # >40% short = dialogue-focused
            if 25 < avg_len < 250:
                scores['pacing'] = 0.85
            elif dialogue_heavy and avg_len >= 15:
                scores['pacing'] = 0.80  # dialogue chapters naturally have shorter avg
            elif avg_len >= 200:
                scores['pacing'] = 0.55
                issues.append('段落偏长，建议拆分')
            else:
                scores['pacing'] = 0.65

        # Uniformity penalty — if most paragraphs are similar length (AI tell)
        if len(paragraphs) >= 5:
            lengths = [len(p) for p in paragraphs]
            avg_l = sum(lengths) / len(lengths)
            variance = sum((l - avg_l) ** 2 for l in lengths) / len(lengths)
            if variance < avg_l * 5:  # Too uniform
                scores['pacing'] = max(0.4, scores['pacing'] - 0.15)
                if '段落过少' not in issues and '段落偏长' not in issues:
                    issues.append('段落长度过于均匀——这是AI写作的特征，需要刻意打破')

        # 4. Hook strength (钩子) — multi-paragraph ending analysis
        last_n = min(5, len(paragraphs))
        last_paras = '\n'.join(paragraphs[-last_n:]) if last_n else ''
        last_para = paragraphs[-1] if paragraphs else ''

        # Explicit hook markers (high weight — ?, !, …, —)
        hook_explicit = ['？', '！', '……', '...', '——']
        # Foreshadowing markers (medium weight)
        hook_foreshadow = ['突然', '竟然', '难道', '什么', '怎么', '为何',
                           '未免', '莫非', '隐隐', '恍惚', '不知',
                           '那一刻', '就在这时', '忽然', '猛然', '骤然']
        # Tension/urgency markers (medium-low weight, wider scan)
        hook_tension = ['寒意', '恐惧', '不安', '阴影', '诡异', '熟悉',
                        '认出', '一模一样', '当年', '父亲', '母亲', '失踪',
                        '他要去', '她要去', '等着', '来了', '回头',
                        '身后', '门外', '楼下', '黑暗中', '血', '死',
                        '快', '跑', '追', '杀', '逃', '躲', '怕']

        explicit_hits = sum(1 for kw in hook_explicit if kw in last_paras)
        foreshadow_hits = sum(1 for kw in hook_foreshadow if kw in last_paras)
        tension_hits = sum(1 for kw in hook_tension if kw in last_paras)

        # Bonus: literary cliffhanger — last para is very short (< 25 chars) AND has tension nearby
        literary_bonus = 0
        if len(last_para) < 25 and (tension_hits > 0 or foreshadow_hits > 0):
            literary_bonus = 0.2

        hook_score = min((explicit_hits * 0.5 + foreshadow_hits * 0.3 + tension_hits * 0.2) / 3 + literary_bonus, 1.0)
        scores['hook'] = min(0.35 + hook_score * 0.65, 1.0)
        if scores['hook'] < 0.5:
            issues.append('结尾钩子弱')

        # 5. Readability (可读性) — dialogue ratio + sentence variation
        dialogue_lines = sum(1 for p in paragraphs if p.strip().startswith('"') or p.strip().startswith('"') or '“' in p or '"' in p)
        dialogue_ratio = dialogue_lines / max(len(paragraphs), 1)
        if 0.15 < dialogue_ratio < 0.6:
            scores['readability'] = 0.85
        elif dialogue_ratio > 0:
            scores['readability'] = 0.6
        else:
            scores['readability'] = 0.4
            issues.append('缺少对话')

        # Subject variety — if >50% of paragraphs start with 他/她/它/主角名, it's AI-like
        if len(paragraphs) >= 5:
            pronouns = ['他', '她', '它']
            char_names = [c.name for c in state.characters] if state else []
            pronoun_starts = sum(1 for p in paragraphs if p.strip() and p.strip()[0] in pronouns + char_names)
            if pronoun_starts / len(paragraphs) > 0.6:
                scores['readability'] = max(0.4, scores['readability'] - 0.1)
                issues.append('段落主语单一（过多段落以"他"开头）——这是AI写作特征')

        # 6. Show-Don't-Tell — detect consecutive exposition paragraphs
        exposition_blocks = 0
        max_consecutive_exposition = 0
        for p in paragraphs:
            has_dialogue = '“' in p or '"' in p or '：' in p
            has_action = any(v in p for v in ['道', '说', '走', '看', '拿', '打', '跑', '跳', '推', '拉',
                                               '站', '坐', '抓', '踢', '冲', '杀', '飞', '落', '倒'])
            if not has_dialogue and not has_action:
                exposition_blocks += 1
                max_consecutive_exposition = max(max_consecutive_exposition, exposition_blocks)
            else:
                exposition_blocks = 0
        # Genre-aware exposition threshold
        expo_threshold = 5  # default
        if isinstance(style, StyleProfile) and style.quality_rules:
            for rule in style.quality_rules:
                if '说明段落' in rule or '世界观说明' in rule or 'exposition' in rule.lower():
                    expo_threshold = 7  # sci-fi/historical allows longer exposition
                    break
        scores['show_dont_tell'] = 1.0
        if max_consecutive_exposition >= expo_threshold:
            scores['show_dont_tell'] = 0.3
            issues.append(f'连续{max_consecutive_exposition}段纯说明/叙述，建议增加对话或动作')
        elif max_consecutive_exposition >= expo_threshold - 1:
            scores['show_dont_tell'] = 0.6
            issues.append('存在连续纯叙述段落')

        # Genre-specific quality checks (modifier, not a scored dimension)
        genre_penalty = 0
        genre_issues: list[str] = []
        if isinstance(style, StyleProfile) and style.quality_rules:
            for rule in style.quality_rules:
                # Check: "每章至少1个战斗/冲突场景"
                if '战斗' in rule or '冲突场景' in rule:
                    fight_keywords = ['击', '斩', '杀', '拳', '剑', '掌', '轰', '爆', '碎', '战', '刺']
                    if not any(kw in body for kw in fight_keywords):
                        genre_issues.append(rule)
                        genre_penalty += 0.05
                # Check: "系统面板/数值必须前后一致" / "资源数量"
                if '系统面板' in rule or '数值' in rule or '资源' in rule:
                    # Simple check: if system notifications are mentioned, verify format
                    if '系统' in body:
                        sys_refs = body.count('系统')
                        if sys_refs < 2:  # likely inconsistent if only mentioned once
                            genre_issues.append(rule)
                            genre_penalty += 0.03
                # Check: "感情线必须有递进"
                if '感情' in rule or '互动' in rule:
                    # Check for male-female interaction markers
                    romance_kw = ['脸红', '心跳', '靠近', '牵手', '眼神', '温柔', '担心', '在乎']
                    if not any(kw in body for kw in romance_kw):
                        genre_issues.append(rule)
                        genre_penalty += 0.05
                # Check: "每章至少1个线索/伏笔推进"
                if '线索' in rule or '伏笔推进' in rule:
                    clue_kw = ['发现', '线索', '痕迹', '疑点', '奇怪', '不对', '难道']
                    if not any(kw in body for kw in clue_kw):
                        genre_issues.append(rule)
                        genre_penalty += 0.05
            if genre_issues:
                issues.extend(genre_issues)

        overall = sum(scores.values()) / len(scores) - genre_penalty
        result = {
            'scores': scores,
            'overall': round(overall, 2),
            'passed': overall >= 0.5 and len(issues) <= 1,
            'grade': 'A' if overall >= 0.8 else 'B' if overall >= 0.6 else 'C' if overall >= 0.4 else 'D',
            'issues': issues,
            'word_count': wc,
        }
        return result


    # ==================== Self-Edit Pass ====================

    def _self_edit(self, body: str, state: 'StoryState', style: 'StyleProfile | None' = None) -> str:
        """
        LLM self-editing pass: send the chapter back for refinement.
        Fixes pacing issues, removes redundancy, smooths transitions.
        Returns edited body (same length, improved quality).
        """
        edit_prompt = f"""你是一位资深网文编辑。请对以下章节进行四处精修，不要重写全文：

1. **拆散说明段**：找出连续3段以上纯叙述/纯说明的文字（没有对话、没有动作的段落），在其中插入角色的内心独白、动作描写或简短对话，打破沉闷的说明感。每段说明最多保留2句，其余拆分。
2. **节奏**：场景推进过快的地方（情绪没到位就跳了）补半句过渡；同一场景描写过长的地方压缩。
3. **冗余**：删除重复出现的形容词/比喻/动作描写。同一意象出现≥3次，只保留最好的那次。
4. **过渡**：场景切换处必须有过渡词或过渡句，禁止直接跳场景。

要求：
- 保持总字数不变（±10%）
- 保持原有对话、人物、剧情完全不变
- 不要在章节末尾加任何新内容
- 直接输出修改后的完整章节正文，不要加注释或标记

原文：
{body}

修改后的章节："""

        messages = [
            {"role": "system", "content": "你是资深网文编辑，你的任务是对稿件进行精准微调。你只修改节奏、冗余和过渡，不改剧情、人物、对白。输出格式：直接输出修改后的完整正文。"},
            {"role": "user", "content": edit_prompt},
        ]
        try:
            edited = self._call_llm_with_retry(messages, max_tokens=4096)
            if edited and len(edited) > len(body) * 0.6:
                return edited.strip()
        except Exception:
            pass
        return body  # fallback: return original

    # ═══════════════════ V3: De-AI Post-processing ═══════════════════

    AI_PATTERNS = [
        # Cliché transitions
        (r'在这个世界[里中上]?', ''),
        (r'随着时间[的之]推移[,，]?', ''),
        (r'不仅如此[,，]?', ''),
        (r'总的?[而之]?[言来]之?[说]?[,，]?', ''),
        (r'毫无疑[问][,，]?', ''),
        (r'值得注意[的是][,，]?', ''),
        (r'与此同[时][,，]?', ''),
        (r'换句话[说][,，]?', ''),
        # Formulaic sequencing
        (r'首先[,，]?\s*', ''),
        (r'其次[,，]?\s*', ''),
        (r'最后[,，]?\s*', ''),
        (r'第一[步点][,，]?\s*', ''),
        (r'第二[步点][,，]?\s*', ''),
        # Overused AI phrases
        (r'可以[说想]?是', '是'),
        (r'从某种[意义程度]上[来说讲]', ''),
        (r'在很大[的]?程度[上]?', ''),
        (r'不可否认[的是]?[,，]?', ''),
        (r'显[然而]易见[的是]?[,，]?', ''),
    ]

    # ═══════════════════ V4: Viral Pattern Analysis ═══════════════════

    def analyze_viral_patterns(self, sample_chapters: list[dict]) -> dict:
        """
        Analyze writing patterns from viral novel chapters.

        Args:
            sample_chapters: [{"title": str, "body": str}, ...] — top 10 chapters

        Returns:
            dict with 7 analysis dimensions + key_findings
        """
        if not sample_chapters:
            return {"error": "no chapters provided"}

        # Build analysis prompt
        chapter_texts = []
        for i, ch in enumerate(sample_chapters[:10]):
            body = ch.get("body", "")[:2000]  # truncate to save tokens
            chapter_texts.append(f"### 第{i+1}章「{ch.get('title','')}」\n{body}")

        prompt = f"""你是一位网文数据分析师。请分析以下爆款小说的前{len(sample_chapters)}章，输出纯统计数据。

{chr(10).join(chapter_texts)}

请按以下维度输出结构化分析（JSON格式），不要写任何写作建议或主观评价：

1. **opening_strategy**: 开篇前200字用什么钩子类型？（冲突/悬念/反差/对话），给出百分比分布
2. **hook_density**: 每章平均多少个转折/冲突点，平均每多少字一个钩子
3. **dialogue_ratio**: 对话占总字数的比例（0-1之间的小数）
4. **climax_type_distribution**: 高潮/爽点类型分布（打脸/突破/揭秘/夺宝/收小弟/其他），百分比
5. **ending_hook_distribution**: 章尾钩子类型分布（危机预告/信息反转/悬念中断/情感爆发/实力展示），百分比
6. **paragraph_stats**: 段落长度统计 {{"avg_len": int, "max_len": int, "min_len": int}}
7. **key_findings**: 至少5条可量化的规律（如"前3章每章标题都含数字""反派在前5章必须出场""对话段落平均2行"等）

只输出JSON，格式：
```json
{{"opening_strategy": "...", "dialogue_ratio": 0.0, ...}}
```
"""

        try:
            raw = self._call_llm_with_retry(
                [{"role": "user", "content": prompt}],
                max_tokens=2048,
            )
            # Extract JSON from response
            import re as _re
            match = _re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, _re.DOTALL)
            if match:
                return json.loads(match.group(1))
            # Try bare JSON
            match = _re.search(r'\{.*\}', raw, _re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"error": "no JSON found in response", "raw": raw[:500]}
        except Exception as e:
            return {"error": str(e)}

    def de_ai(self, body: str) -> tuple[str, int]:
        """
        Remove AI writing patterns. Returns (cleaned_body, changes_made).
        """
        import re
        changes = 0
        result = body

        for pattern, replacement in self.AI_PATTERNS:
            new_result, count = re.subn(pattern, replacement, result)
            if count > 0:
                changes += count
                result = new_result

        # Break up uniform paragraph lengths (AI tendency)
        paragraphs = result.split('\n')
        if len(paragraphs) > 3:
            # Only merge very short orphan paragraphs (< 50 chars) into reasonable-length neighbors (< 150)
            for i in range(len(paragraphs) - 1, 0, -1):
                if len(paragraphs[i]) < 50 and 30 < len(paragraphs[i-1]) < 150:
                    if random.random() < 0.3:
                        paragraphs[i-1] = paragraphs[i-1] + '\n' + paragraphs[i]
                        paragraphs.pop(i)
                        changes += 1

        result = '\n'.join(paragraphs)
        return result, changes


    # ═══════════════════ V3: Context Retrieval (LIKE-based, Chinese-friendly) ═══════════════════

    def retrieve_relevant_context(self, query: str, novel_id: str, top_k: int = 5) -> list[dict]:
        try:
            from .database import Database
            db = Database()
            with db.conn() as conn:
                rows = conn.execute(
                    "SELECT cs.novel_id, cs.chapter_num, c.title, cs.summary_text as summary "
                    "FROM chapter_summaries cs "
                    "JOIN chapters c ON c.novel_id = cs.novel_id AND c.number = cs.chapter_num "
                    "WHERE cs.novel_id = ? AND cs.summary_text LIKE ? "
                    "ORDER BY c.number DESC LIMIT ?",
                    (novel_id, '%' + query + '%', top_k)).fetchall()
                return [{
                    "chapter_number": r["chapter_num"],
                    "title": r["title"] or "",
                    "chunk_text": r["summary"] or "",
                    "similarity": 1.0,
                } for r in rows]
        except Exception as e:
            print(f"[RAG] Error: {e}")
            return []


