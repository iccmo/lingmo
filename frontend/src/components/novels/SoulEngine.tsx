import { useState } from 'react';
import { toast } from 'sonner';
import { AlertTriangle } from 'lucide-react';

/* ─── The 16 Fundamental Polarities ─── */
interface Polarity {
 id: string; emoji: string; name: string;
 poles: [string, string];
 question: string; // The question this polarity forces you to ask
 prompt: string; // What gets injected into generation
 deadlySins: string[]; // What ruins this polarity
 masters: { author: string; work: string; note: string }[];
}

const CATEGORIES = [
 { key: 'all', label: '全部' },
 { key: 'metaphysical', label: '存在' },
 { key: 'social', label: '社会' },
 { key: 'inner', label: '内心' },
 { key: 'relational', label: '关系' },
 { key: 'temporal', label: '时间' },
];

const POLARITIES: (Polarity & { category: string })[] = [
 // ── 存在 · METAPHYSICAL ──
 { category: 'metaphysical', id: 'scale-intimacy', emoji: '🌌', name: '宏大 ↔ 亲密', poles: ['宇宙尺度', '人性微光'], question: '当你在宇宙尺度上看人类——一粒尘埃上的爱恨——什么还值得在乎？', prompt: '在宏大与亲密之间反复切换。先让读者感受宇宙的冷漠和无垠，再把镜头拉到一个人具体的心跳。尺度越大，那个微小的动作越有力量。', deadlySins: ['只写宏大忘了具体的人','只写人忘了宇宙背景'], masters: [{author:'刘慈欣',work:'《三体》',note:'水滴毁灭舰队 vs 罗辑一家的晚餐'},{author:'卡尔维诺',work:'《宇宙奇趣》',note:'宇宙诞生是一个睡前故事'},{author:'博尔赫斯',work:'《巴别图书馆》',note:'无限图书馆里一个读书的人'}] },
 { category: 'metaphysical', id: 'meaning-absurdity', emoji: '🏰', name: '意义 ↔ 荒诞', poles: ['寻找意义', '世界无意义'], question: '如果你寻找的一切意义——到头来世界根本不回应——那你为什么还在找？', prompt: '不要让角色轻易找到答案。让他们在系统面前反复碰壁。读者不应该感到"哦原来如此"——应该感到"原来真的没有答案"。', deadlySins: ['给出明确的答案','系统突然合理','角色最终理解了一切'], masters: [{author:'卡夫卡',work:'《城堡》',note:'K永远进不了城堡'},{author:'贝克特',work:'《等待戈多》',note:'等一个永远不会来的人'},{author:'加缪',work:'《局外人》',note:'不配合意义系统的人被毁灭'}] },
 { category: 'metaphysical', id: 'freedom-fate', emoji: '', name: '自由 ↔ 命运', poles: ['我要选择', '我已注定'], question: '如果你最自由的选择——恰好印证了你逃不掉的命运——你是自由的还是被困的？', prompt: '每一章让角色做一个选择。但选择的后果不是他们能控制的。自由的行动导致宿命的结果——这是最深的悲剧。', deadlySins: ['命运可轻松改变','自由选择无后果','宿命让角色放弃努力'], masters: [{author:'金庸',work:'《天龙八部》',note:'乔峰的命运早在血统中注定'},{author:'索福克勒斯',work:'《俄狄浦斯王》',note:'逃避预言恰好实现预言'},{author:'马尔克斯',work:'《百年孤独》',note:'每一代都反抗命运也都重复命运'}] },
 { category: 'metaphysical', id: 'life-death', emoji: '', name: '生 ↔ 死', poles: ['活着', '死去'], question: '如果死亡是唯一的确定性——活着的时候什么是值得的？', prompt: '死亡应该是每一个重大决定的背景。不是因为角色要死——是因为读者知道人会死。在有限的时间里，每个选择都有重量。', deadlySins: ['死亡当情节工具','角色对死亡无感','活着被当理所当然'], masters: [{author:'余华',work:'《活着》',note:'所有人都死了——活着本身就是答案'},{author:'托尔斯泰',work:'《伊凡·伊里奇之死》',note:'临死才发现一生没真正活过'},{author:'海明威',work:'《老人与海》',note:'老人可能死在海上——但他必须去'}] },
 { category: 'metaphysical', id: 'reality-illusion', emoji: '🪞', name: '真实 ↔ 幻象', poles: ['客观现实', '主观幻象'], question: '你怎么知道你看到的不是自己编的故事？', prompt: '模糊现实和虚幻的边界。不要告诉读者哪个是真的——让他们在两个版本的真相之间摇摆。最有力的叙事者是那些不可靠的叙事者。', deadlySins: ['明确告诉读者什么是真的','叙事者完全可靠','虚幻只是逃避现实'], masters: [{author:'博尔赫斯',work:'《小径分岔的花园》',note:'所有可能性同时存在'},{author:'卡尔维诺',work:'《看不见的城市》',note:'马可·波罗描述的城市——真的存在吗？'},{author:'纳博科夫',work:'《洛丽塔》',note:'亨伯特的叙述本身就是一场自我欺骗'}] },
 { category: 'metaphysical', id: 'order-chaos', emoji: '', name: '秩序 ↔ 混沌', poles: ['想要秩序', '世界是混沌'], question: '你精心构建的秩序——会不会本身就是一种幻觉？', prompt: '建立秩序，然后让它瓦解。不是一次性的——是反复的。角色越是努力建立秩序，混沌就越是以意想不到的方式回来。', deadlySins: ['秩序永远获胜','混沌被完全驯服'], masters: [{author:'戈尔丁',work:'《蝇王》',note:'一群孩子试图建立秩序——最后变成猎杀'},{author:'马尔克斯',work:'《百年孤独》',note:'马孔多被历史反复摧毁'},{author:'刘震云',work:'《一句顶一万句》',note:'一句话建立秩序，另一句话崩塌'}] },
 { category: 'metaphysical', id: 'sacred-profane', emoji: '⛪', name: '神圣 ↔ 世俗', poles: ['超越性的', '日常的'], question: '在去超市买菜的路上——神圣感还存在吗？', prompt: '不要把神圣和世俗分开。在最日常的动作里——泡茶、等车、叠衣服——让读者感受到超越日常的东西。', deadlySins: ['神圣只在教堂/寺庙里','日常完全没有超越性','用说教表达神圣'], masters: [{author:'但丁',work:'《神曲》',note:'地狱之旅的开始是一个平凡的中年危机'},{author:'陀思妥耶夫斯基',work:'《卡拉马佐夫兄弟》',note:'上帝是否存在——在一个谋杀案中追问'},{author:'远藤周作',work:'《沉默》',note:'上帝在最屈辱的沉默中反而最在场'}] },

 // ── 社会 · SOCIAL ──
 { category: 'social', id: 'individual-society', emoji: '🚲', name: '个人 ↔ 时代', poles: ['我想活着', '时代碾压我'], question: '当时代的重量压在一个人身上——他还剩下什么属于自己的？', prompt: '不要写时代——写一个人在时代中具体的挣扎。不是"战争很残酷"——是"他蹲在战壕里数剩下的子弹，一颗，两颗，三颗。"', deadlySins: ['宏观叙事无具体的人','苦难被抽象化','时代只是装饰'], masters: [{author:'老舍',work:'《骆驼祥子》',note:'祥子不是在拉车——是时代在拉他'},{author:'托尔斯泰',work:'《战争与和平》',note:'拿破仑入侵时，娜塔莎在舞会上心碎'},{author:'奥威尔',work:'《1984》',note:'温斯顿不是反抗——是被体制摧毁'}] },
 { category: 'social', id: 'power-powerlessness', emoji: '', name: '权力 ↔ 无力', poles: ['掌控', '被掌控'], question: '当你终于得到了权力——你变成了你曾经反抗的人吗？', prompt: '权力的腐蚀不是一夜之间——是一个决定接一个决定，每一步都合理，结果却不可接受。让读者理解为什么会这样，而不只是谴责。', deadlySins: ['权力持有者纯粹邪恶','无权者纯粹善良','权力没有代价'], masters: [{author:'莎士比亚',work:'《麦克白》',note:'一个合理的选择链通向地狱'},{author:'奥威尔',work:'《动物农场》',note:'猪变成了人——革命背叛了自己'},{author:'阿特伍德',work:'《使女的故事》',note:'权力不是暴力——是让人监视自己'}] },
 { category: 'social', id: 'justice-injustice', emoji: '', name: '正义 ↔ 不公', poles: ['应得的', '不应得的'], question: '如果你帮助了一个人——却让另外一百个人受到了同样的伤害——你做的是正义吗？', prompt: '不要写简单的善恶对立。写"正确的选择也伤害了正确的人"。正义不是答案——正义是问题。', deadlySins: ['好人全好坏人全坏','正义总是获胜','牺牲没有代价'], masters: [{author:'狄更斯',work:'《双城记》',note:'革命追求正义却制造新的不公'},{author:'雨果',work:'《悲惨世界》',note:'冉阿让偷面包被判十九年——公正吗？'},{author:'托尔斯泰',work:'《复活》',note:'法律惩罚了罪犯，但谁惩罚了制造罪犯的社会？'}] },
 { category: 'social', id: 'tradition-progress', emoji: '', name: '传统 ↔ 进步', poles: ['守住旧的', '拥抱新的'], question: '进步是不是另一种形式的遗忘？', prompt: '不要站队——写两边的合理性。保守者看到了进步者看不到的代价，进步者看到了保守者不敢想象的未来。', deadlySins: ['传统被写成愚蠢','进步被写成背叛','没有中间地带的人'], masters: [{author:'托尔斯泰',work:'《安娜·卡列尼娜》',note:'列文的农业改革和安娜的个人解放——两种进步'},{author:'屠格涅夫',work:'《父与子》',note:'两代人——谁也说服不了谁'},{author:'福克纳',work:'《喧哗与骚动》',note:'旧南方的贵族在新时代里崩溃'}] },
 { category: 'social', id: 'center-margin', emoji: '🌿', name: '中心 ↔ 边缘', poles: ['主流', '边缘'], question: '被排除在中心之外的人——他们的故事谁来讲？', prompt: '不要以怜悯的眼光写边缘人——以他们的眼光看中心。让读者发现：所谓的中心，从边缘看过去，原来如此荒谬。', deadlySins: ['边缘人只是符号','边缘被浪漫化','中心视角居高临下'], masters: [{author:'莫里森',work:'《宠儿》',note:'一个被奴役的母亲——从她的眼睛看美国'},{author:'阿契贝',work:'《瓦解》',note:'非洲村庄的视角看殖民——西方人是闯入者'},{author:'伍尔夫',work:'《一间自己的房间》',note:'如果莎士比亚的妹妹有同样的才华——她会有机会吗？'}] },

 // ── 内心 · INNER ──
 { category: 'inner', id: 'desire-constraint', emoji: '🥀', name: '欲望 ↔ 约束', poles: ['想要', '不能要'], question: '当欲望撞上现实的墙——人到底是妥协了，还是背叛了自己？', prompt: '每个角色都有想要但永远得不到的东西。不是外部的阻碍——是他们内心的两股力量在拉扯。写清楚：他们放弃了什么来得到什么。', deadlySins: ['完美的结局','角色轻松得到','没有代价的选择'], masters: [{author:'张爱玲',work:'《倾城之恋》',note:'白流苏算到最后，算不过自己的心'},{author:'福楼拜',work:'《包法利夫人》',note:'想要浪漫，撞上平庸的现实'},{author:'菲茨杰拉德',work:'《了不起的盖茨比》',note:'想要过去的爱，但时间不会倒流'}] },
 { category: 'inner', id: 'body-mind', emoji: '🌾', name: '肉体 ↔ 精神', poles: ['身体感受', '头脑思考'], question: '当身体在饥饿、疼痛、欲望中——精神还属于自己吗？', prompt: '不要写"他很难过"——写他的胃在收缩，背后的汗浸透了衬衫，嘴里有一股金属味。让身体替精神说话。', deadlySins: ['抽象的心理描写','干净的痛苦','体面的语言'], masters: [{author:'莫言',work:'《红高粱》',note:'饥饿、疼痛、欲望——比思想更真实'},{author:'余华',work:'《活着》',note:'福贵的身体在受苦，精神在承受'},{author:'陀思妥耶夫斯基',work:'《罪与罚》',note:'拉斯柯尼科夫的发烧比哲学更能说明问题'}] },
 { category: 'inner', id: 'sanity-madness', emoji: '🎪', name: '理智 ↔ 疯狂', poles: ['清醒', '疯狂'], question: '如果疯狂是唯一合理的反应——那什么才是真正的疯狂？', prompt: '不要写"他疯了"——写"这个世界在他眼里突然变得清晰了，只是没有人相信他看到的。"', deadlySins: ['疯狂被当作笑话','理智永远正确','疯狂没有自己的逻辑'], masters: [{author:'陀思妥耶夫斯基',work:'《地下室手记》',note:'一个清醒的疯子比他更不自由'},{author:'伍尔夫',work:'《达洛维夫人》',note:'塞普蒂默斯的疯狂是对战争最诚实的回应'},{author:'凯西',work:'《飞越疯人院》',note:'疯人院里的病人比外面的人更自由'}] },
 { category: 'inner', id: 'innocence-experience', emoji: '🧒', name: '纯真 ↔ 世故', poles: ['相信美好', '看透一切'], question: '知道世界的真相之后——你还能相信什么？', prompt: '不要写"他失去了纯真"——写"他以为自己看透了一切，但某个瞬间——一把旧钥匙、一首老歌——让他发现自己还在等。"', deadlySins: ['纯真被嘲笑','世故被美化','两者没有张力'], masters: [{author:'狄更斯',work:'《远大前程》',note:'匹普从纯真到世故再回到纯真'},{author:'菲茨杰拉德',work:'《了不起的盖茨比》',note:'盖茨比在腐化世界里保留最纯真的梦'},{author:'塞林格',work:'《麦田里的守望者》',note:'看透了所有虚伪——但想守护孩子的纯真'}] },
 { category: 'inner', id: 'hope-despair', emoji: '', name: '希望 ↔ 绝望', poles: ['还有明天', '没有明天'], question: '如果希望本身是一种残忍——你还要不要抱有希望？', prompt: '不要让角色轻易找到希望。也不要把绝望写成终点。真正的力量在于：明明知道可能没有明天，今天还是做了该做的事。', deadlySins: ['轻率的希望','绝望被当作答案','角色从未真正怀疑过'], masters: [{author:'贝克特',work:'《等待戈多》',note:'戈多不来——但他们还在等'},{author:'加缪',work:'《西西弗神话》',note:'推石头上山——知道它会滚下来——继续推'},{author:'科马克·麦卡锡',work:'《路》',note:'世界末日。父亲对孩子说：你是好人。'}] },
 { category: 'inner', id: 'reason-passion', emoji: '', name: '理性 ↔ 激情', poles: ['想清楚', '忍不住'], question: '你最理智的决定——背后是不是藏着一个你自己都不愿承认的冲动？', prompt: '让角色的理性成为激情的伪装。他们对自己解释"我是因为A才这么做的"——但读者看得清楚：是因为B。', deadlySins: ['理性永远正确','激情被写成愚蠢','角色完全了解自己的动机'], masters: [{author:'奥斯汀',work:'《理智与情感》',note:'两姐妹——一个代表理智，一个代表情感'},{author:'勃朗特',work:'《呼啸山庄》',note:'希斯克利夫的激情摧毁了一切——包括他自己'},{author:'纳博科夫',work:'《洛丽塔》',note:'亨伯特用最精美的语言包装最丑陋的欲望'}] },

 // ── 关系 · RELATIONAL ──
 { category: 'relational', id: 'silence-expression', emoji: '🌊', name: '沉默 ↔ 表达', poles: ['说不出的', '说出来的'], question: '最真实的东西——说出来就变味了。那怎么写？', prompt: '把最重要的情感放在对话的间隙、动作的细节、景物的变化里。角色说出来的往往不是他们真正想说的。', deadlySins: ['角色直接说出内心','旁白替读者解释','过度描写情绪'], masters: [{author:'海明威',work:'《老人与海》',note:'没有一个字说孤独'},{author:'古龙',work:'《多情剑客无情剑》',note:'李寻欢的寂寞在喝酒的动作里'},{author:'沈从文',work:'《边城》',note:'翠翠等一个人，整个湘西在替她说'}] },
 { category: 'relational', id: 'belonging-alienation', emoji: '', name: '归属 ↔ 疏离', poles: ['想要归属', '永远疏离'], question: '你在人群中间——但你知道你不属于这里。留下假装，还是离开？', prompt: '写角色在人群中的孤独感。他们可以交谈、合作、相爱——但始终有一个无法跨越的距离。', deadlySins: ['角色轻易找到归属','疏离只是性格缺陷','孤独被浪漫化'], masters: [{author:'古龙',work:'《多情剑客无情剑》',note:'江湖中无数朋友——最孤独的人'},{author:'加缪',work:'《局外人》',note:'母亲的死没有流泪——疏离从此刻开始'},{author:'塞林格',work:'《麦田里的守望者》',note:'讨厌所有人——最想保护孩子'}] },
 { category: 'relational', id: 'love-hate', emoji: '💔', name: '爱 ↔ 恨', poles: ['爱', '恨'], question: '你最恨的那个人——是不是因为你先爱过他？', prompt: '爱和恨不是对立的——它们是从同一口井里打上来的水。最深的恨来自最深的爱。', deadlySins: ['爱恨分明','恨没有爱的背景','爱变成恨没有过程'], masters: [{author:'勃朗特',work:'《呼啸山庄》',note:'希斯克利夫的爱和恨是同一种狂热的两个名字'},{author:'莎士比亚',work:'《奥赛罗》',note:'因为爱得太深——所以怀疑起来就毁了一切'},{author:'杜拉斯',work:'《情人》',note:'爱和恨在记忆里已经分不清'}] },
 { category: 'relational', id: 'trust-betrayal', emoji: '🔪', name: '信任 ↔ 背叛', poles: ['信任', '背叛'], question: '你被最信任的人背叛之后——你还能信任任何人吗？包括你自己？', prompt: '背叛不是突然的——是一点一点积累的。读者应该能看到每一个走向背叛的微小脚步，每一步都情有可原。', deadlySins: ['背叛者纯粹邪恶','背叛没有前兆','被背叛后角色轻易恢复'], masters: [{author:'莎士比亚',work:'《尤里乌斯·凯撒》',note:'布鲁图斯刺杀凯撒——因为爱罗马'},{author:'格林',work:'《文静的美国人》',note:'你以为你在帮忙——其实你在毁灭'},{author:'石黑一雄',work:'《长日将尽》',note:'一辈子忠诚——最后发现忠诚给错了人'}] },
 { category: 'relational', id: 'intimacy-distance', emoji: '', name: '亲密 ↔ 距离', poles: ['靠近', '远离'], question: '两个人离得最近的时候——是不是恰好是他们即将分开的时候？', prompt: '写两个人之间的"刚刚好的距离"。太近会灼伤，太远会冻死。让他们在靠近和远离之间反复——每一次靠近都比上一次更危险。', deadlySins: ['完美的亲密关系','距离被当作冷漠','没有张力的关系'], masters: [{author:'川端康成',work:'《雪国》',note:'岛村和驹子——永远在靠近，永远到不了'},{author:'村上春树',work:'《挪威的森林》',note:'渡边和直子——爱得越深，距离越远'},{author:'卡尔维诺',work:'《如果在冬夜，一个旅人》',note:'读者和故事之间的距离——永远在接近，永远没到达'}] },

 // ── 时间 · TEMPORAL ──
 { category: 'temporal', id: 'past-present', emoji: '⏳', name: '过去 ↔ 现在', poles: ['回不去的', '留不住的'], question: '如果过去永远不会过去——你现在在过的到底是谁的生活？', prompt: '让过去入侵现在。不是通过回忆——是通过习惯、恐惧、条件反射。角色以为自己放下了——但身体还记得。', deadlySins: ['过去只是背景','角色轻易释怀','过去被完全解决'], masters: [{author:'福克纳',work:'《喧哗与骚动》',note:'过去不是过去了——过去甚至还没有发生'},{author:'普鲁斯特',work:'《追忆似水年华》',note:'一块玛德琳蛋糕里藏着整个失去的世界'},{author:'石黑一雄',work:'《远山淡影》',note:'叙述者在现在说的话——句句都是过去'}] },
 { category: 'temporal', id: 'home-exile', emoji: '🏡', name: '故乡 ↔ 流亡', poles: ['回去', '回不去'], question: '你终于回到了故乡——但故乡已经不认识你了。你回的是哪里？', prompt: '写一个人永远在"回去"的路上——但回去的地方已经不存在了。家不是一个地点——是一个你永远在靠近但永远到达不了的方向。', deadlySins: ['故乡是完美的天堂','流亡只是地理问题','回去就解决一切'], masters: [{author:'纳博科夫',work:'《说吧，记忆》',note:'用最精美的英语写再也回不去的俄罗斯'},{author:'昆德拉',work:'《不能承受的生命之轻》',note:'离开捷克的托马斯——回不去的不是国家，是那个时刻'},{author:'荷马',work:'《奥德赛》',note:'奥德修斯花了十年回家——回到的是一个变了的世界'}] },
 { category: 'temporal', id: 'repetition-novelty', emoji: '', name: '重复 ↔ 新意', poles: ['再来一次', '只此一次'], question: '日复一日重复同样的事——这是囚禁，还是另一种自由？', prompt: '在重复中找差异。不是写重复的内容——是写重复的动作在每一次重复中微妙的不同。第三次和第一次的"早上好"不是同一个意思。', deadlySins: ['重复被写成无聊','新意被过度追求','没有节奏感'], masters: [{author:'贝克特',work:'《等待戈多》',note:'每一天都一样——但每一遍等待都是新的'},{author:'昆德拉',work:'《不能承受的生命之轻》',note:'一次不算数——只发生一次的事等于没有发生'},{author:'普鲁斯特',work:'《追忆似水年华》',note:'在重复的社交仪式中，时间悄然改变了所有人'}] },
 { category: 'temporal', id: 'creation-destruction', emoji: '', name: '创造 ↔ 毁灭', poles: ['建造', '摧毁'], question: '你是不是在创造的同时——就在毁灭着什么？', prompt: '每一次创造都有代价。建造一个家，可能意味着砍掉一片森林。写出创造中的毁灭——不是善恶问题，是代价问题。', deadlySins: ['创造纯粹美好','毁灭只为邪恶','代价被忽略'], masters: [{author:'玛丽·雪莱',work:'《弗兰肯斯坦》',note:'创造生命——结果创造了怪物'},{author:'麦卡锡',work:'《路》',note:'世界毁灭后——父亲在废墟中为孩子创造意义'},{author:'梅尔维尔',work:'《白鲸》',note:'亚哈的追猎是一种创造——创造了一种毁灭一切的执念'}] },
];

/* ─── Types ─── */
interface SoulFingerprint {
 primaryPolarity: string;
 position: number; // 1-10, where on the spectrum
 answer: string; // The author's personal answer to the question
}

function loadFingerprint(novelId: string): SoulFingerprint | null {
 try { return JSON.parse(localStorage.getItem(`soul-fingerprint-${novelId}`) || 'null'); }
 catch { return null; }
}
function saveFingerprint(novelId: string, fp: SoulFingerprint) {
 localStorage.setItem(`soul-fingerprint-${novelId}`, JSON.stringify(fp));
}

/* ─── Component ─── */
export function SoulEngine({ novelId }: { novelId: string; genre: string }) {
 const [fp, setFp] = useState<SoulFingerprint | null>(() => loadFingerprint(novelId));
 const [selected, setSelected] = useState<string | null>(fp?.primaryPolarity || null);
 const [answer, setAnswer] = useState(fp?.answer || '');
 const [position, setPosition] = useState(fp?.position || 5);
 const [showPrompt, setShowPrompt] = useState(false);
 const [categoryFilter, setCategoryFilter] = useState('all');
 const [polaritySearch, setPolaritySearch] = useState('');

 const polarity = POLARITIES.find(p => p.id === selected);

 function save() {
 if (!selected || !answer.trim()) { toast.error('请选择核心矛盾并写下你的回答'); return; }
 const data: SoulFingerprint = { primaryPolarity: selected, position, answer: answer.trim() };
 setFp(data);
 saveFingerprint(novelId, data);
 toast.success('灵魂已注入');
 }

 function clear() {
 setFp(null); setSelected(null); setAnswer(''); setPosition(5);
 localStorage.removeItem(`soul-fingerprint-${novelId}`);
 }

 const injectionPrompt = polarity && answer.trim()
 ? `【灵魂注入 · 核心矛盾：${polarity.name}】\n${polarity.question}\n\n作者的回答：${answer}\n\n写作法则：${polarity.prompt}\n\n绝对不能：${polarity.deadlySins.join('、')}`
 : '';

 return (
 <div className="p-4 bg-card border border-border rounded-xl">
 <div className="flex items-center justify-between mb-3">
 <div>
 <h3 className="font-heading text-base font-semibold text-ink">💎 灵魂构建</h3>
 <p className="text-[11px] text-ink-muted">
 {fp
 ? `核心矛盾：${polarity?.name}`
 : '选择你的书要追问的那个矛盾——灵魂就诞生于这个张力之中'}
 </p>
 </div>
 {fp && (
 <button onClick={clear} className="text-[10px] text-ink-muted hover:text-destructive transition-colors">清除</button>
 )}
 </div>

 {/* Grid of polarities with category filter */}
 {!selected && (
 <div className="space-y-2">
 <p className="text-xs text-ink-muted leading-relaxed mb-3">
 每一部神作都在追问一个<strong>不可解的矛盾</strong>。30组——选择你的书要追问的那一个。
 </p>
 {/* Search */}
 <input value={polaritySearch} onChange={e => setPolaritySearch(e.target.value)}
 placeholder="搜索矛盾（如：爱、死亡、自由）..."
 className="w-full text-xs rounded-lg border border-input bg-card px-3 py-1.5 mb-2
 placeholder:text-ink-subtle focus:outline-none focus:border-accent transition-all" />

 {/* Category tabs */}
 <div className="flex gap-1 mb-2 flex-wrap">
 {CATEGORIES.map(cat => (
 <button key={cat.key} onClick={() => setCategoryFilter(cat.key)}
 className={`text-[10px] px-2.5 py-1 rounded-full border transition-colors ${
 categoryFilter === cat.key
 ? 'bg-accent text-white border-accent'
 : 'border-border text-ink-muted hover:text-ink'
 }`}>
 {cat.label}
 </button>
 ))}
 </div>
 <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[400px] overflow-y-auto">
 {POLARITIES.filter(p => {
 if (categoryFilter !== 'all' && p.category !== categoryFilter) return false;
 if (polaritySearch) {
 const q = polaritySearch.toLowerCase();
 return p.name.includes(q) || p.question.includes(q) || p.poles.some(pl => pl.includes(q));
 }
 return true;
 }).map(p => (
 <button key={p.id} onClick={() => { setSelected(p.id); setAnswer(''); setPosition(5); }}
 className="p-2.5 rounded-xl border border-border hover:border-accent/30 hover:bg-accent-soft/5 transition-all text-left group">
 <div className="flex items-center gap-1.5 mb-0.5">
 <span className="text-base">{p.emoji}</span>
 <span className="text-[11px] font-bold text-ink group-hover:text-accent transition-colors">{p.name}</span>
 </div>
 <p className="text-[9px] text-ink-muted leading-relaxed line-clamp-2">{p.question}</p>
 </button>
 ))}
 </div>
 <p className="text-[9px] text-ink-subtle text-center">
 {POLARITIES.length} 组矛盾 · 存在/社会/内心/关系/时间五类 · 每组3位大师参考
 </p>
 </div>
 )}

 {/* Selected polarity detail */}
 {polarity && !fp && (
 <div className="space-y-3 animate-[fadeSlideIn_0.2s_ease-out]">
 <button onClick={() => setSelected(null)} className="text-[10px] text-ink-muted hover:text-ink">← 重新选择</button>

 <div className="p-4 rounded-xl bg-gradient-to-br from-accent-soft/30 to-transparent border border-accent/10">
 <div className="text-3xl mb-2">{polarity.emoji}</div>
 <h4 className="font-heading text-lg font-bold text-ink">{polarity.name}</h4>
 <p className="text-sm text-ink mt-1 font-medium">{polarity.question}</p>
 </div>

 {/* Position slider */}
 <div className="p-3 rounded-lg bg-paper border border-border">
 <p className="text-[10px] text-ink-muted mb-2">你的书更接近哪一端？</p>
 <input type="range" min="1" max="10" value={position}
 onChange={e => setPosition(Number(e.target.value))}
 className="w-full h-1.5 rounded-full appearance-none bg-gradient-to-r from-accent/40 via-accent to-purple-500/40 cursor-pointer
 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent" />
 <div className="flex justify-between text-[8px] text-ink-subtle mt-0.5">
 <span>{polarity.poles[0]}</span>
 <span>5 平衡</span>
 <span>{polarity.poles[1]}</span>
 </div>
 </div>

 {/* Writing rule */}
 <div className="p-3 rounded-lg bg-accent-soft/20 border border-accent/10">
 <p className="text-[10px] font-semibold text-accent uppercase tracking-wide mb-1">✎ 写作法则</p>
 <p className="text-xs text-ink leading-relaxed">{polarity.prompt}</p>
 </div>

 {/* Deadly sins */}
 <div className="p-3 rounded-lg bg-destructive-soft/50 dark:bg-red-950/20 border border-red-100 dark:border-red-900/30">
 <p className="text-[10px] font-semibold text-destructive uppercase tracking-wide mb-1"><AlertTriangle size={12} className="text-warn inline" /> 如果你这样做，张力就消失了</p>
 {polarity.deadlySins.map((s, i) => (
 <p key={i} className="text-[11px] text-destructive ">✕ {s}</p>
 ))}
 </div>

 {/* Master references */}
 <div className="space-y-1.5">
 <p className="text-[10px] font-semibold text-ink-muted uppercase tracking-wide">大师示范</p>
 {polarity.masters.map(m => (
 <div key={m.author} className="p-2.5 rounded-lg bg-paper border border-border text-[11px]">
 <span className="text-ink font-semibold">{m.author}</span>
 <span className="text-ink-subtle mx-1">· {m.work}</span>
 <p className="text-ink-muted mt-0.5">{m.note}</p>
 </div>
 ))}
 </div>

 {/* Answer */}
 <div>
 <label className="text-[10px] font-semibold text-ink-muted uppercase tracking-wide">
 你的回答 <span className="text-ink-subtle font-normal">——这个问题，你打算怎么追问？</span>
 </label>
 <textarea value={answer} onChange={e => setAnswer(e.target.value)}
 placeholder="不是回答这个问题——是描述你打算如何探索它..."
 rows={3}
 className="w-full mt-1.5 rounded-lg border border-input bg-card text-ink text-xs px-3 py-2 resize-none
 placeholder:text-ink-subtle focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all" />
 </div>

 <button onClick={save} disabled={!answer.trim()}
 className="w-full py-2.5 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors text-sm font-medium disabled:opacity-50">
 💎 这是我的灵魂
 </button>
 </div>
 )}

 {/* Saved fingerprint */}
 {fp && polarity && (
 <div className="space-y-3 animate-[fadeSlideIn_0.2s_ease-out]">
 <div className="p-4 rounded-xl bg-gradient-to-br from-accent-soft/30 to-transparent border border-accent/10">
 <div className="text-3xl mb-2">{polarity.emoji}</div>
 <h4 className="font-heading text-lg font-bold text-ink">{polarity.name}</h4>
 <p className="text-sm text-ink mt-1 font-medium">{polarity.question}</p>
 </div>

 <div className="p-3 rounded-lg bg-paper border border-border">
 <p className="text-[10px] text-ink-muted mb-1">你的位置</p>
 <div className="flex items-center gap-2 text-xs">
 <span>{polarity.poles[0]}</span>
 <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
 <div className="h-full bg-accent rounded-full" style={{ width: `${fp.position * 10}%` }} />
 </div>
 <span>{polarity.poles[1]}</span>
 </div>
 </div>

 <div className="p-3 rounded-lg bg-accent-soft/20 border border-accent/10">
 <p className="text-[10px] text-ink-muted mb-1">你的回答</p>
 <p className="text-xs text-ink leading-relaxed italic">「{fp.answer}」</p>
 </div>

 <div>
 <button onClick={() => setShowPrompt(!showPrompt)}
 className="flex items-center gap-1.5 text-[11px] text-accent hover:underline">
 {showPrompt ? '▾' : '▸'} 查看注入 Prompt
 </button>
 {showPrompt && (
 <pre className="mt-2 p-3 rounded-lg bg-ink text-white text-[10px] leading-relaxed whitespace-pre-wrap font-mono max-h-[250px] overflow-y-auto">
 {injectionPrompt}
 </pre>
 )}
 </div>

 <button onClick={() => { setFp(null); setAnswer(fp.answer); }}
 className="w-full py-2 rounded-lg border border-border text-ink-muted hover:text-ink transition-colors text-sm">
 修改灵魂
 </button>
 </div>
 )}
 </div>
 );
}
