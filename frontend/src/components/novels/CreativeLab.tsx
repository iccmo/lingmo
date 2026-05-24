import { useState, useMemo } from 'react';
import { DeepQuality } from 'src/components/novels/DeepQuality';
import type { ChapterMeta } from 'src/types';

/* ─── AI Reader Persona ─── */
const READER_PERSONAS = [
  { name: '番茄老书虫', emoji: '📚', style: '看了5000小时网文，口味刁钻，最恨套路', traits: ['挑剔', '经验丰富', '追求新鲜感'] },
  { name: '追更狂魔', emoji: '🔥', style: '每天追更5本书，一章不好看立刻弃书', traits: ['没耐心', '追求爽感', '弃书果断'] },
  { name: '女频编辑', emoji: '💅', style: '十年女频编辑，对人物关系和情感线极度敏感', traits: ['细腻', '重感情', '讨厌直男写法'] },
  { name: '硬核设定控', emoji: '🤓', style: '逻辑党，世界观漏洞一眼看穿，在评论区写千字分析', traits: ['理性', '考据', '逻辑洁癖'] },
];

function personaReaction(summary: string, persona: typeof READER_PERSONAS[number]): string[] {
  const reactions: string[] = [];
  const s = summary;

  if (persona.name === '番茄老书虫') {
    if (/系统|穿越|重生|退婚/.test(s)) reactions.push('😒 又是系统文开局...不过看你写得怎样吧');
    if (/反转|意外|惊人/.test(s)) reactions.push('👀 哦？这个反转有点意思，继续看看');
    if (/修炼|突破|升级/.test(s)) reactions.push('📖 升级流，节奏还行，别太拖就行');
  }
  if (persona.name === '追更狂魔') {
    if (/战斗|打斗|对决|激战/.test(s)) reactions.push('🔥 打斗！爽！多写点多写点');
    if (/日常|闲聊|散步|吃饭/.test(s)) reactions.push('😴 这一段我会跳过去...快点进入正题');
    if (/危机|生死|最后|来不及/.test(s)) reactions.push('⚡ 好紧张！下一章呢？下一章呢？');
  }
  if (persona.name === '女频编辑') {
    if (/感情|心动|爱|情|温柔/.test(s)) reactions.push('💕 这段感情描写很细腻，读者会嗑到');
    if (/打斗|击杀|砍|杀/.test(s)) reactions.push('🤔 动作戏可以，但别忘了人物情感动机');
    if (/对话|说|道|问|答/.test(s) && s.length > 100) reactions.push('👍 对话写得不错，人物有区分度');
  }
  if (persona.name === '硬核设定控') {
    if (/突破|升级|进阶|晋升/.test(s)) reactions.push('🧐 突破的逻辑说得通吗？前面有铺垫吗？');
    if (/规则|体系|设定|境界/.test(s)) reactions.push('📝 设定党狂喜，多写点世界规则');
    if (/突然|莫名|不知|为什么/.test(s)) reactions.push('⚠️ 这里有逻辑漏洞，为什么会这样？前面没解释');
  }
  if (reactions.length === 0) reactions.push('🤔 再看看...');
  return reactions;
}

/* ─── Trope Detector ─── */
const TROPES = [
  { name: '退婚流', pattern: /退婚|被退|被赶出|被逐出|被开除/, tip: '建议在第5章前给退婚方一个合理的动机，让读者觉得不是无脑打脸' },
  { name: '系统降临', pattern: /系统|叮|宿主|任务|奖励|兑换/, tip: '系统文竞争激烈，建议给系统一个独特的性格或限制，与其他系统文区分' },
  { name: '穿越开局', pattern: /穿越|重生|醒来|回到|上一世|前世/, tip: '穿越文开篇竞争白热化。建议前500字内给出一个独特的穿越机制或记忆片段' },
  { name: '废柴逆袭', pattern: /废物|废柴|废材|不能修炼|没有天赋|最弱/, tip: '经典但有效。关键要在"废"的原因上做文章——是被人封印？身世特殊？' },
  { name: '扮猪吃虎', pattern: /隐藏|低调|扮猪|装|不露|低调/, tip: '爽点在于"揭露时刻"。规划好什么时候让主角展示真实实力' },
  { name: '打脸爽文', pattern: /打脸|嘲笑|看不起|轻视|震惊|后悔/, tip: '打脸节奏要快。不要铺垫3章才打一个脸——那是10年前的写法' },
  { name: '金手指', pattern: /奇遇|获得|传承|秘籍|宝物|神器|空间/, tip: '给金手指加限制，否则后期战力崩塌。比如"每天只能用一次"或"消耗寿命"' },
  { name: '修炼体系', pattern: /练气|筑基|金丹|元婴|化神|大乘|渡劫|斗者|斗师/, tip: '体系要简明。读者最多记住5个等级，多了会混乱' },
];

function detectTropes(chapters: ChapterMeta[]): { trope: typeof TROPES[number]; count: number }[] {
  const allText = chapters.filter(c => c.summary).map(c => c.summary).join(' ');
  return TROPES.map(t => ({
    trope: t,
    count: (allText.match(t.pattern) || []).length,
  })).filter(t => t.count > 0).sort((a, b) => b.count - a.count);
}

function authorDNA(chapters: ChapterMeta[]): { strengths: string[]; weaknesses: string[]; bestGenre: string } {
  const allText = chapters.filter(c => c.summary).map(c => c.summary + ' ' + (c.ending_hook || '')).join(' ');
  const strengths: string[] = [];
  const weaknesses: string[] = [];

  const dialogueMarkers = (allText.match(/[说问道答讲喊叫骂]/g) || []).length;
  const actionMarkers = (allText.match(/[打攻击杀砍刺射爆炸飞跑]/g) || []).length;
  const hookMarkers = (allText.match(/悬念|反转|危机|秘密|真相|惊人/g) || []).length;

  if (dialogueMarkers > actionMarkers * 0.6) strengths.push('对话写作');
  else weaknesses.push('对话密度');

  if (actionMarkers > dialogueMarkers * 0.5) strengths.push('动作场面');
  else weaknesses.push('动作描写');

  if (hookMarkers >= chapters.length * 0.5) strengths.push('结尾钩子');
  else weaknesses.push('章节结尾');

  if (chapters.length > 0) {
    const avgQ = chapters.filter(c => c.quality_score).reduce((s, c) => s + (c.quality_score || 0), 0) / Math.max(1, chapters.filter(c => c.quality_score).length);
    if (avgQ >= 0.7) strengths.push('整体质量');
    else weaknesses.push('质量稳定性');
  }

  // Best genre suggestion
  let bestGenre = '玄幻';
  if (dialogueMarkers > actionMarkers * 2) bestGenre = '都市/官场';
  else if (actionMarkers > dialogueMarkers * 2) bestGenre = '玄幻/仙侠';
  else if (hookMarkers > chapters.length) bestGenre = '悬疑/灵异';

  return { strengths, weaknesses, bestGenre };
}

/* ─── Reader Heatmap ─── */
function paragraphReactions(paragraphs: string[]): { text: string; reaction: string; emoji: string; color: string }[] {
  return paragraphs.filter(p => p.trim().length > 10).slice(0, 12).map(p => {
    let reaction = '普通阅读', emoji = '📖', color = 'bg-zinc-100 dark:bg-zinc-800';
    if (/战斗|打斗|激战|对决|杀|砍|刺|爆/.test(p)) { reaction = '肾上腺素飙升'; emoji = '🔥'; color = 'bg-red-100 dark:bg-red-900/30 border-red-200 dark:border-red-800'; }
    else if (/秘密|真相|揭露|原来|竟然|隐藏/.test(p)) { reaction = '好奇心被点燃'; emoji = '🤔'; color = 'bg-purple-100 dark:bg-purple-900/30 border-purple-200 dark:border-purple-800'; }
    else if (/笑|搞笑|逗|吐槽|欢乐|囧/.test(p)) { reaction = '笑出声'; emoji = '😂'; color = 'bg-amber-100 dark:bg-amber-900/30 border-amber-200 dark:border-amber-800'; }
    else if (/泪|哭|悲伤|死|失去|离别/.test(p)) { reaction = '眼眶湿润'; emoji = '😢'; color = 'bg-blue-100 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800'; }
    else if (/突破|升级|成功|赢了|击败|获得/.test(p)) { reaction = '极度舒适'; emoji = '😌'; color = 'bg-emerald-100 dark:bg-emerald-900/30 border-emerald-200 dark:border-emerald-800'; }
    else if (/危机|危险|陷阱|最后|倒计时|来不及/.test(p)) { reaction = '紧张屏息'; emoji = '😰'; color = 'bg-orange-100 dark:bg-orange-900/30 border-orange-200 dark:border-orange-800'; }
    return { text: p.slice(0, 80), reaction, emoji, color };
  });
}

/* ─── Publishing Advisor ─── */
function publishingAdvice(chapters: ChapterMeta[]): { bestChapter: number; bestDay: string; bestTime: string; strategy: string } {
  const gen = chapters.filter(c => c.word_count > 0 && c.quality_score);
  if (gen.length < 3) return { bestChapter: 0, bestDay: '—', bestTime: '—', strategy: '至少需要3章才能生成发布策略' };

  const best = gen.reduce((a, b) => (a.quality_score || 0) > (b.quality_score || 0) ? a : b);
  const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
  const avgQ = gen.reduce((s, c) => s + (c.quality_score || 0), 0) / gen.length;

  return {
    bestChapter: best.number,
    bestDay: '周五、周六',
    bestTime: '晚上 20:00-22:00',
    strategy: gen.length <= 5
      ? `建议首发3章吸引读者，第${best.number}章是你的最强章，放在第4或第5位发布以保持热度`
      : avgQ >= 0.75
        ? `存稿质量优秀（均分${avgQ.toFixed(2)}），建议加快发布节奏：每天2章，把最强章${best.number}安排在周五晚高峰`
        : `存稿均分${avgQ.toFixed(2)}，建议保持每天1章稳定更新。重点打磨第${best.number}章，作为吸引读者的"爆款章"`,
  };
}

export function CreativeLab({ chapters, genre, novelId }: { chapters?: ChapterMeta[]; genre: string; novelId: string }) {
  const [tab, setTab] = useState<'reader' | 'trope' | 'heatmap' | 'publish' | 'deep'>('reader');
  const [personaIdx, setPersonaIdx] = useState(0);
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null);

  const gen = (chapters || []).filter(c => c.word_count > 0);
  if (gen.length < 1) return null;

  const persona = READER_PERSONAS[personaIdx];
  const selectedCh = selectedChapter ? gen.find(c => c.number === selectedChapter) : gen[gen.length - 1];
  const reactions = personaReaction(selectedCh?.summary || '', persona);
  const tropes = useMemo(() => detectTropes(gen), [chapters]);
  const dna = useMemo(() => authorDNA(gen), [chapters]);
  const heatData = useMemo(() => {
    const s = selectedCh?.summary || '';
    return paragraphReactions(s.split('\n'));
  }, [selectedCh]);
  const advice = useMemo(() => publishingAdvice(gen), [gen]);

  const tabs = [
    { key: 'reader' as const, label: '👤 AI读者', desc: '角色扮演' },
    { key: 'trope' as const, label: '🔍 反套路', desc: '套路检测' },
    { key: 'heatmap' as const, label: '🔥 热力图', desc: '段落反应' },
    { key: 'publish' as const, label: '📅 发布', desc: '策略建议' },
    { key: 'deep' as const, label: '🔬 深度', desc: '质量分析' },
  ];

  return (
    <div className="p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-heading text-base font-semibold text-ink">🧪 创意实验室</h3>
        <div className="flex gap-1">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`text-[11px] px-2.5 py-1 rounded-md transition-colors ${
                tab === t.key ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink hover:bg-paper'
              }`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chapter selector */}
      <div className="flex gap-1.5 mb-3 flex-wrap">
        {gen.slice(-10).map(c => (
          <button key={c.number} onClick={() => setSelectedChapter(c.number)}
            className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
              selectedChapter === c.number || (!selectedChapter && c === gen[gen.length - 1])
                ? 'bg-accent-soft text-accent border-accent/30' : 'border-border text-ink-muted hover:text-ink'
            }`}>
            第{c.number}章
          </button>
        ))}
      </div>

      {/* Tab: AI Reader Persona */}
      {tab === 'reader' && (
        <div>
          {/* Persona selector */}
          <div className="flex gap-2 mb-3">
            {READER_PERSONAS.map((p, i) => (
              <button key={p.name} onClick={() => setPersonaIdx(i)}
                className={`flex-1 p-3 rounded-lg border text-left transition-all ${
                  i === personaIdx ? 'border-accent bg-accent-soft/50' : 'border-border hover:border-accent/20'
                }`}>
                <div className="text-lg">{p.emoji}</div>
                <div className="text-xs font-semibold text-ink mt-1">{p.name}</div>
                <div className="text-[10px] text-ink-muted mt-0.5">{p.style}</div>
              </button>
            ))}
          </div>
          {/* Chapter title */}
          <p className="text-xs text-ink-muted mb-3">
            正在阅读：第{selectedCh?.number}章「{selectedCh?.title}」
          </p>
          {/* Reactions */}
          <div className="space-y-2">
            {reactions.map((r, i) => (
              <div key={i} className="flex gap-2 p-3 rounded-lg bg-paper border border-border animate-[fadeSlideIn_0.2s_ease-out]"
                style={{ animationDelay: `${i * 0.1}s` }}>
                <span className="text-lg shrink-0">{r.slice(0, 2)}</span>
                <p className="text-sm text-ink leading-relaxed">{r.slice(2)}</p>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-ink-subtle mt-3 text-center">
            💡 切换不同读者角色，看不同人群怎么评价你的章节
          </p>
        </div>
      )}

      {/* Tab: Trope Detector + Author DNA */}
      {tab === 'trope' && (
        <div className="space-y-4">
          {/* Tropes detected */}
          <div>
            <h4 className="text-xs font-semibold text-ink mb-2">📋 检测到的套路</h4>
            {tropes.length === 0 ? (
              <p className="text-sm text-ink-muted">未检测到常见套路 — 你的写法很独特！</p>
            ) : (
              <div className="space-y-2">
                {tropes.slice(0, 6).map(t => (
                  <div key={t.trope.name} className="p-3 rounded-lg border border-border bg-paper">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-semibold text-ink">{t.trope.name}</span>
                      <span className="text-[10px] text-ink-subtle">出现 {t.count} 次</span>
                    </div>
                    <p className="text-[11px] text-ink-muted leading-relaxed">{t.trope.tip}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Author DNA */}
          <div className="pt-3 border-t border-border">
            <h4 className="text-xs font-semibold text-ink mb-2">🧬 你的作者 DNA</h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-emerald-50/50 dark:bg-emerald-900/10 border border-emerald-100 dark:border-emerald-900/30">
                <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium mb-1">💪 强项</p>
                {dna.strengths.map(s => (
                  <p key={s} className="text-xs text-ink">• {s}</p>
                ))}
              </div>
              <div className="p-3 rounded-lg bg-amber-50/50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/30">
                <p className="text-[10px] text-amber-600 dark:text-amber-400 font-medium mb-1">🎯 待提升</p>
                {dna.weaknesses.map(w => (
                  <p key={w} className="text-xs text-ink">• {w}</p>
                ))}
              </div>
            </div>
            <p className="text-xs text-accent mt-2 text-center">
              💡 推荐题材：<span className="font-semibold">{dna.bestGenre}</span>
            </p>
          </div>
        </div>
      )}

      {/* Tab: Reader Heatmap */}
      {tab === 'heatmap' && (
        <div>
          <p className="text-xs text-ink-muted mb-3">
            段落级读者反应预测 · 第{selectedCh?.number}章「{selectedCh?.title}」
          </p>
          {heatData.length === 0 ? (
            <p className="text-sm text-ink-muted text-center py-8">该章节摘要不足以生成热力图</p>
          ) : (
            <div className="space-y-1.5">
              {heatData.map((h, i) => (
                <div key={i} className={`p-2.5 rounded-lg border transition-all hover:shadow-sm ${h.color}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm">{h.emoji}</span>
                    <span className="text-[10px] font-semibold text-ink">{h.reaction}</span>
                  </div>
                  <p className="text-[11px] text-ink-muted leading-relaxed line-clamp-2">{h.text}</p>
                </div>
              ))}
            </div>
          )}
          {/* Color legend */}
          <div className="flex gap-3 mt-3 pt-2 border-t border-border text-[9px] text-ink-subtle flex-wrap">
            {[
              { emoji: '🔥', label: '兴奋' }, { emoji: '🤔', label: '好奇' }, { emoji: '😂', label: '好笑' },
              { emoji: '😢', label: '感动' }, { emoji: '😌', label: '舒适' }, { emoji: '😰', label: '紧张' },
            ].map(l => (
              <span key={l.label} className="flex items-center gap-1">{l.emoji} {l.label}</span>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Deep Quality */}
      {tab === 'deep' && (
        <DeepQuality novelId={novelId} chapters={chapters || []} />
      )}

      {/* Tab: Publishing Advisor */}
      {tab === 'publish' && (
        <div className="space-y-4">
          {/* Best chapter */}
          {advice.bestChapter > 0 && (
            <div className="p-4 rounded-lg bg-emerald-50/50 dark:bg-emerald-900/10 border border-emerald-100 dark:border-emerald-900/30">
              <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 mb-1">🏆 最强章</p>
              <p className="text-sm text-ink">第 {advice.bestChapter} 章 — 建议作为引流爆款章</p>
            </div>
          )}

          {/* Timing */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-paper border border-border">
              <p className="text-[10px] text-ink-muted mb-0.5">最佳发布日</p>
              <p className="text-sm font-semibold text-ink">{advice.bestDay}</p>
            </div>
            <div className="p-3 rounded-lg bg-paper border border-border">
              <p className="text-[10px] text-ink-muted mb-0.5">最佳时间段</p>
              <p className="text-sm font-semibold text-ink">{advice.bestTime}</p>
            </div>
          </div>

          {/* Strategy */}
          <div className="p-4 rounded-lg bg-accent-soft/30 border border-accent/10">
            <p className="text-xs font-semibold text-accent mb-1">📋 发布策略</p>
            <p className="text-sm text-ink leading-relaxed">{advice.strategy}</p>
          </div>

          {/* Platform tips */}
          <div className="pt-3 border-t border-border">
            <h4 className="text-xs font-semibold text-ink mb-2">📱 平台适配建议</h4>
            <div className="space-y-2 text-[11px]">
              <div className="flex gap-2">
                <span className="text-red-500 font-medium shrink-0">番茄小说:</span>
                <span className="text-ink-muted">章节2000-4000字最佳，结尾必须有强钩子，标题要吸睛。前3章决定80%留存率。</span>
              </div>
              <div className="flex gap-2">
                <span className="text-blue-500 font-medium shrink-0">起点中文网:</span>
                <span className="text-ink-muted">章节3000-6000字，允许慢热但要有深度。读者更看重世界观和人物弧线。</span>
              </div>
              <div className="flex gap-2">
                <span className="text-emerald-500 font-medium shrink-0">纵横中文网:</span>
                <span className="text-ink-muted">介于番茄和起点之间。3000-5000字，需要兼顾爽感和深度。</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
