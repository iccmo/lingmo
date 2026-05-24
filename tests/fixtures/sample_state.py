"""Pre-built StoryState fixtures for pipeline tests."""

from novel_writer.story_state import StoryState, World, Plot, Character, ChapterMeta


def build_sample_state(total_chapters: int = 5) -> StoryState:
    """Build a StoryState with world, characters, and chapters."""
    state = StoryState(
        novel_id="sword-immortal",
        title="剑道独尊",
        author="AI",
        synopsis="少年林逸以剑入道，斩尽天下不公",
        genre="玄幻",
        world=World(
            name="天元大陆",
            era="上古",
            geography="大陆分九州，中州为修行圣地",
            power_system="练气→筑基→金丹→元婴→化神",
            factions=[
                {"name": "青云宗", "description": "东荒第一宗门", "leader": "青云真人"},
                {"name": "林家", "description": "青云城四大家族之一", "leader": "林震天"},
            ],
            rules=["金丹以上不可对凡人出手", "剑修以剑心代替金丹"],
        ),
        characters=[
            Character(
                id="protagonist", name="林逸", role="主角",
                personality="坚韧不拔，心思缜密",
                background="青云城林家庶子，天生剑骨",
                current_power_level="练气三层",
                secrets=["体内封印着上古剑魂"],
                status="alive",
            ),
            Character(
                id="sword-spirit", name="剑尘", role="配角",
                personality="桀骜不驯",
                background="上古剑神残魂",
                current_power_level="残魂",
                status="alive",
            ),
            Character(
                id="rival", name="林啸天", role="反派",
                personality="野心勃勃",
                background="林家现任族长之子",
                current_power_level="金丹中期",
                status="alive",
            ),
        ],
        plot=Plot(
            premise="少年林逸以剑入道，斩尽天下不公",
            main_arc="从废柴到剑道至尊，揭开古剑和剑神的秘密",
            current_arc="开篇：觉醒",
            arc_chapter_start=1,
            next_plot_points=["参加宗门大比", "探索后山禁地"],
            foreshadowing=["古剑来历不明", "林逸父亲失踪之谜"],
        ),
        tags=["剑道", "废柴逆袭"],
    )

    # Add generated chapters
    chapters_data = [
        (1, "锈剑", 2684, "林逸在演武场被羞辱，后山发现锈剑", "锈剑中究竟藏着什么秘密？"),
        (2, "剑魂苏醒", 2520, "剑尘残魂苏醒，传授林逸剑道", "林啸天暗中监视着林逸的一举一动"),
        (3, "初露锋芒", 2480, "林逸在宗门考核中击败筑基对手", "柳青烟注意到了林逸的特殊之处"),
        (4, "剑心初成", 2610, "林逸闭关凝聚剑心", "天外邪魔的爪牙开始活动"),
        (5, "宗门大比", 2750, "大比中林逸对决林啸天", "剑心的秘密即将暴露"),
    ]
    for num, title, wc, summary, hook in chapters_data[:total_chapters]:
        state.chapters.append(ChapterMeta(
            number=num, title=title, word_count=wc,
            summary=summary, ending_hook=hook,
        ))

    return state


def sample_outline() -> list[dict]:
    """Sample outline items."""
    return [
        {"number": 6, "title": "第六章：剑意对决", "summary": "林逸和林啸天的决战，剑心之力爆发"},
        {"number": 7, "title": "第七章：长老召见", "summary": "柳青烟正式收林逸为徒"},
    ]


def sample_rag_context() -> list[dict]:
    """Sample RAG context."""
    return [
        {"chapter_number": 1, "title": "锈剑", "chunk_text": "林逸在后山禁地发现一柄锈剑", "similarity": 0.85},
        {"chapter_number": 3, "title": "初露锋芒", "chunk_text": "林逸以剑道基础击败筑基期对手", "similarity": 0.72},
    ]


def high_quality_body() -> str:
    """A high-quality chapter body (~2500 chars)."""
    return """青云城演武场上，人声鼎沸。

"下一场——林逸，对林浩！"

话音未落，台下已是哄笑一片。林逸攥紧拳头，一步步走上擂台。他的衣衫破旧，脸色苍白，看起来风一吹就会倒下。

"废物，识相的就自己滚下去，省得我动手。"林浩双手抱胸，一脸不屑。

林逸没有回答。他只是默默从腰间抽出那柄锈迹斑斑的铁剑。剑身布满裂纹，仿佛一碰就会碎。

"就这破剑？"林浩大笑，"我今天让你三招！"

话音刚落，林逸动了。

很普通的一剑，甚至可以说是笨拙。但就是这一剑，竟精准刺中了林浩拳风的中心——

"噗！"

血光迸溅。

林浩惨叫一声，整条手臂都被震开。他不可置信地低头看着自己虎口崩裂的右手，脸上血色尽失。

"这怎么可能......"

全场死寂。

林逸手中的锈剑在颤抖，发出一阵低沉的嗡鸣。那声音仿佛来自远古，带着说不出的苍凉。

"够了！"

一声冷喝，林啸天身形一晃出现在擂台上。他冷冷盯着林逸，眼中闪过一丝寒芒。

"你能接下林浩一拳，算你过关。不过——"他压低声音，"别以为这样就能翻身。"

林逸迎上他的目光，平静道："拭目以待。"

台下，柳青烟微微眯起了眼睛。她刚才分明看到，那柄锈剑在出招的瞬间闪过了一道不易察觉的金光。

这个小家伙，不简单。

夜幕降临，林逸独自坐在后山崖边。月光洒在那柄锈剑上，剑身上的锈迹似乎淡了几分。

"小子。"

一个苍老的声音突然在他脑海中响起。

林逸猛地站起："谁？！"

"别紧张。老夫剑尘，乃上古剑神一缕残魂。你体内有罕见的剑骨之体，正合老夫传承。"

林逸握紧锈剑，心跳如擂鼓。三年来的屈辱、白眼、嘲讽，在这一刻全都涌上心头。

"前辈......请收我为徒。"

剑尘沉默片刻，缓缓道："剑道之路，九死一生。你确定？"

"我确定。"

"好。今夜开始，我教你真正的剑道——以剑心代金丹，以剑意破万法！"

林逸跪下，朝着锈剑深深一拜。

月光下，锈剑上第一道裂纹悄然愈合。"""


def low_quality_body() -> str:
    """A low-quality body (too short, no protagonist, no hook)."""
    return """在这个世界里，修炼是一件非常重要的事情。随着时间推移，越来越多的人开始修炼。

不仅如此，修炼的方法也变得越来越多样化。总的来说，修炼是一件好事。

首先，修炼可以强身健体。其次，修炼可以延年益寿。最后，修炼可以让人获得力量。

可以这么说，修炼是人类进步的阶梯。从某种程度上来讲，没有修炼就没有现在的文明。"""
