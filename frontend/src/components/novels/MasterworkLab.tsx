import { useState, useEffect, useMemo } from 'react';
import { toast } from 'sonner';
import type { ChapterMeta } from 'src/types';

/* ─── Data ─── */
interface WorldLaws {
  laws: { rule: string; test: RegExp }[];
}
interface CentralImage {
  name: string; description: string; chapters: { num: number; context: string; meaning: string }[];
}

function loadWorldLaws(novelId: string): WorldLaws {
  try { return JSON.parse(localStorage.getItem(`world-laws-${novelId}`) || '{"laws":[]}'); }
  catch { return { laws: [] }; }
}
function saveWorldLaws(novelId: string, data: WorldLaws) {
  localStorage.setItem(`world-laws-${novelId}`, JSON.stringify(data));
}

function loadCentralImage(novelId: string): CentralImage {
  try { return JSON.parse(localStorage.getItem(`central-image-${novelId}`) || '{"name":"","description":"","chapters":[]}'); }
  catch { return { name: '', description: '', chapters: [] }; }
}
function saveCentralImage(novelId: string, data: CentralImage) {
  localStorage.setItem(`central-image-${novelId}`, JSON.stringify(data));
}

/* ─── Law 3: World Laws ─── */
function WorldLawsPanel({ novelId }: { novelId: string }) {
  const [data, setData] = useState<WorldLaws>(() => loadWorldLaws(novelId));
  const [newRule, setNewRule] = useState('');

  useEffect(() => { saveWorldLaws(novelId, data); }, [data, novelId]);

  function addLaw() {
    if (!newRule.trim()) return;
    const testStr = newRule.split('').slice(0, 6).join('');
    setData(prev => ({
      laws: [...prev.laws, { rule: newRule.trim(), test: new RegExp(testStr) }],
    }));
    setNewRule('');
  }

  const EXAMPLES = [
    '这个世界的人从不直接说「我爱你」',
    '这个世界的力量必须付出等价的代价',
    '这个世界的善意总是被误解为软弱',
    '这个世界的真相永远比表面残酷三分',
  ];

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted leading-relaxed">
        不是修仙体系或魔法规则。是<strong>人际关系的物理法则</strong>——这个世界的人如何相处、如何表达、如何隐藏。
        一旦建立，全书不可违反。
      </p>

      <div className="flex gap-2">
        <input value={newRule} onChange={e => setNewRule(e.target.value)}
          placeholder='例：这个世界的人从不直接说「我爱你」...'
          onKeyDown={e => e.key === 'Enter' && addLaw()}
          className="flex-1 text-xs rounded-lg border border-input bg-card px-3 py-2
            placeholder:text-ink-subtle focus:outline-none focus:border-accent transition-all" />
        <button onClick={addLaw}
          className="text-xs px-3 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors shrink-0">
          添加法则
        </button>
      </div>

      {/* Quick examples */}
      <div className="flex gap-1.5 flex-wrap">
        {EXAMPLES.map((ex, i) => (
          <button key={i} onClick={() => setNewRule(ex)}
            className="text-[10px] px-2 py-1 rounded-full border border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-colors">
            {ex}
          </button>
        ))}
      </div>

      {data.laws.length > 0 && (
        <div className="space-y-2">
          {data.laws.map((law, i) => (
            <div key={i} className="flex items-center gap-2 p-3 rounded-lg bg-accent-soft/20 border border-accent/10">
              <span className="text-accent font-bold text-sm shrink-0">#{i + 1}</span>
              <p className="text-xs text-ink flex-1">{law.rule}</p>
              <button onClick={() => setData(prev => ({ laws: prev.laws.filter((_, j) => j !== i) }))}
                className="text-xs text-ink-muted hover:text-red-500 shrink-0">×</button>
            </div>
          ))}
        </div>
      )}

      {data.laws.length === 0 && (
        <p className="text-[10px] text-ink-subtle text-center py-4">
          还没有世界法则。点击上方示例快速添加，或自己定义。
        </p>
      )}
    </div>
  );
}

/* ─── Law 6: Central Image ─── */
function CentralImagePanel({ novelId, chapters }: { novelId: string; chapters?: ChapterMeta[] }) {
  const [data, setData] = useState<CentralImage>(() => loadCentralImage(novelId));
  const [scanning, setScanning] = useState(false);

  useEffect(() => { saveCentralImage(novelId, data); }, [data, novelId]);

  async function scanChapters() {
    if (!data.name) { toast.error('请先定义核心意象'); return; }
    setScanning(true);
    const found: CentralImage['chapters'] = [];
    const gen = (chapters || []).filter(c => c.word_count > 0);
    for (const ch of gen) {
      try {
        const r = await fetch(`/api/novels/${novelId}/chapters/${ch.number}`);
        const d = await r.json();
        const content = d.content || '';
        if (content.includes(data.name)) {
          const idx = content.indexOf(data.name);
          const context = content.slice(Math.max(0, idx - 20), idx + data.name.length + 30);
          found.push({ num: ch.number, context, meaning: '' });
        }
      } catch { /* skip */ }
    }
    setData(prev => ({ ...prev, chapters: found }));
    setScanning(false);
    toast.success(`在 ${found.length} 章中找到「${data.name}」`);
  }

  const meaningEvolution = data.chapters.filter(c => c.meaning).sort((a, b) => a.num - b.num);

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted leading-relaxed">
        找一个只属于这本书的<strong>具体物件</strong>。第一章出现，最后一章还在——但意思已经完全不同了。
        盖茨比的绿灯、活着的老牛、白鲸的白鲸。
      </p>

      <div className="grid grid-cols-2 gap-3">
        <input value={data.name} onChange={e => setData(prev => ({ ...prev, name: e.target.value }))}
          placeholder="意象名称（如：绿灯/老牛/白鲸）"
          className="text-xs rounded-lg border border-input bg-card px-3 py-2
            placeholder:text-ink-subtle focus:outline-none focus:border-accent transition-all" />
        <input value={data.description} onChange={e => setData(prev => ({ ...prev, description: e.target.value }))}
          placeholder="它代表什么？（如：永远追不到的未来）"
          className="text-xs rounded-lg border border-input bg-card px-3 py-2
            placeholder:text-ink-subtle focus:outline-none focus:border-accent transition-all" />
      </div>

      <button onClick={scanChapters} disabled={scanning || !data.name}
        className="text-xs px-4 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 w-full">
        {scanning ? '扫描中...' : `🔍 扫描所有章节中的「${data.name || '...'}」`}
      </button>

      {data.chapters.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] text-ink-subtle">
            出现在 {data.chapters.length}/{chapters?.filter(c => c.word_count > 0).length || 0} 章
            {data.chapters.length < 3 && ' — 建议让意象更频繁地出现'}
          </p>
          {data.chapters.map((c, i) => (
            <div key={i} className="p-2 rounded-lg bg-paper border border-border text-[11px]">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-ink-subtle font-mono">Ch{c.num}</span>
                {c.meaning && <span className="text-accent text-[10px]">{c.meaning}</span>}
                {!c.meaning && (
                  <input
                    placeholder="这一章它意味着什么？"
                    value=""
                    onChange={e => {
                      const updated = [...data.chapters];
                      updated[i] = { ...updated[i], meaning: e.target.value };
                      setData(prev => ({ ...prev, chapters: updated }));
                    }}
                    className="text-[10px] flex-1 bg-transparent border-b border-dashed border-border
                      placeholder:text-ink-subtle focus:outline-none focus:border-accent" />
                )}
              </div>
              <p className="text-ink-muted leading-relaxed">...{c.context}...</p>
            </div>
          ))}
        </div>
      )}

      {/* Meaning evolution */}
      {meaningEvolution.length >= 2 && (
        <div className="p-3 rounded-lg bg-emerald-50/30 dark:bg-emerald-950/10 border border-emerald-100 dark:border-emerald-900/30">
          <p className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400 mb-2">📈 意象含义演化</p>
          <div className="flex items-center gap-1 text-[10px]">
            {meaningEvolution.map((c, i) => (
              <span key={i} className="flex items-center gap-1">
                <span className="text-ink">{c.meaning}</span>
                {i < meaningEvolution.length - 1 && <span className="text-ink-subtle">→</span>}
              </span>
            ))}
          </div>
          <p className="text-[9px] text-ink-subtle mt-1">
            {meaningEvolution[0].meaning === meaningEvolution[meaningEvolution.length - 1].meaning
              ? '⚠️ 意象含义没有变化——它应该在不同章节承载不同的意义'
              : '✅ 意象含义在演化——这正是神作的标志'}
          </p>
        </div>
      )}
    </div>
  );
}

/* ─── Law 7: Echo Detector ─── */
function EchoDetector({ novelId, chapters }: { novelId: string; chapters?: ChapterMeta[] }) {
  const [ch1Content, setCh1Content] = useState('');
  const [lastContent, setLastContent] = useState('');
  const [echoes, setEchoes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const gen = (chapters || []).filter(c => c.word_count > 0);
  const hasBoth = gen.length >= 2;

  async function detect() {
    if (!hasBoth) return;
    setLoading(true);
    try {
      const [r1, r2] = await Promise.all([
        fetch(`/api/novels/${novelId}/chapters/${gen[0].number}`),
        fetch(`/api/novels/${novelId}/chapters/${gen[gen.length - 1].number}`),
      ]);
      const c1 = ((await r1.json()).content || '');
      const c2 = ((await r2.json()).content || '');
      setCh1Content(c1.slice(0, 500));
      setLastContent(c2.slice(0, 500));

      // Detect echoes: repeated significant phrases, motifs, character states
      const found: string[] = [];
      const sentences1 = c1.split(/[。！？!?]/).filter((s: string) => s.trim().length > 8);
      const sentences2 = c2.split(/[。！？!?]/).filter((s: string) => s.trim().length > 8);

      for (const s1 of sentences1.slice(0, 10)) {
        const key = s1.slice(0, 15).replace(/[，。！？\s]/g, '');
        if (key.length < 3) continue;
        for (const s2 of sentences2.slice(0, 10)) {
          if (s2.includes(key)) {
            found.push(`「${s1.trim().slice(0, 30)}...」 → 「${s2.trim().slice(0, 30)}...」`);
            break;
          }
        }
      }
      setEchoes(found.slice(0, 5));
      if (found.length === 0) toast.info('未检测到明显呼应——考虑在最终章回顾开篇的某个意象或台词');
      else toast.success(`发现 ${found.length} 处首尾呼应`);
    } catch { toast.error('检测失败'); }
    finally { setLoading(false); }
  }

  if (!hasBoth) return <p className="text-xs text-ink-muted py-4 text-center">需要至少2章</p>;

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted leading-relaxed">
        读完最后一章回头看第一章——第一章的某些话应该有全新的含义。
        如果第一章还是原来的意思，结局就没完成它的任务。
      </p>

      <button onClick={detect} disabled={loading}
        className="text-xs px-4 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 w-full">
        {loading ? '分析中...' : `🔍 检测第${gen[0].number}章 ↔ 第${gen[gen.length - 1].number}章的呼应`}
      </button>

      {echoes.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] text-emerald-500 font-medium">发现 {echoes.length} 处首尾呼应：</p>
          {echoes.map((e, i) => (
            <div key={i} className="p-2 rounded-lg bg-paper border border-border text-[10px] text-ink-muted leading-relaxed">
              {e}
            </div>
          ))}
        </div>
      )}

      {echoes.length === 0 && !loading && ch1Content && (
        <div className="p-3 rounded-lg bg-amber-50/30 dark:bg-amber-950/10 border border-amber-100 dark:border-amber-900/30 text-[10px] text-amber-600 dark:text-amber-400">
          ⚠️ 未检测到明显呼应。试试：让最后一章出现和第一章相同的场景（但意义不同）、同一句话（但说话的人不同）、同一个物件（但含义变了）。
        </div>
      )}
    </div>
  );
}

/* ─── Law 1: Question Penetration ─── */
function QuestionPenetration({ chapters, engineQuestion }: { chapters?: ChapterMeta[]; engineQuestion: string }) {
  const data = useMemo(() => {
    if (!engineQuestion || !chapters) return [];
    const gen = chapters.filter(c => c.word_count > 0 && c.summary).slice(-10);
    const keywords = engineQuestion.replace(/[？?，。、；：！!\s]/g, '').slice(0, 20);

    return gen.map(ch => {
      const summary = ch.summary || '';
      // How much does this chapter's summary relate to the core question?
      let matchScore = 0;
      for (let i = 0; i < keywords.length - 1; i++) {
        if (summary.includes(keywords.slice(i, i + 2))) matchScore += 15;
      }
      // Also check for question-related patterns
      if (/抉择|选择|两难|代价|牺牲/.test(summary)) matchScore += 20;
      if (/思考|疑问|困惑|不解|迷茫/.test(summary)) matchScore += 15;

      const level = matchScore >= 50 ? 'deep' : matchScore >= 20 ? 'surface' : 'absent';
      const label = level === 'deep' ? '🔵 深度触及' : level === 'surface' ? '🟡 略微相关' : '⚪ 未触及';
      return { chapter: ch.number, title: ch.title, score: Math.min(100, matchScore), level, label };
    });
  }, [chapters, engineQuestion]);

  if (!engineQuestion) return <p className="text-xs text-ink-muted py-4 text-center">请先在灵魂引擎中设置核心问题</p>;
  if (data.length === 0) return <p className="text-xs text-ink-muted py-4 text-center">需要已生成章节</p>;

  const deepCount = data.filter(d => d.level === 'deep').length;
  const absentCount = data.filter(d => d.level === 'absent').length;

  return (
    <div className="space-y-3">
      <div className="p-3 rounded-lg bg-accent-soft/20 border border-accent/10">
        <p className="text-[10px] text-ink-subtle mb-1">核心问题</p>
        <p className="text-sm text-ink font-medium">{engineQuestion}</p>
      </div>

      <p className="text-xs text-ink-muted leading-relaxed">
        每一章都应该直面这本书的核心问题——不是绕开，不是延后，是每一章都在追问。
      </p>

      {/* Score per chapter */}
      <div className="space-y-1.5">
        {data.map(d => (
          <div key={d.chapter} className="flex items-center gap-2 text-[11px]">
            <span className="text-ink-subtle w-10 tabular-nums shrink-0">Ch{d.chapter}</span>
            <div className="flex-1 h-5 bg-border/50 rounded-full overflow-hidden relative">
              <div className={`h-full rounded-full transition-all ${
                d.level === 'deep' ? 'bg-emerald-400' : d.level === 'surface' ? 'bg-amber-400' : 'bg-zinc-300 dark:bg-zinc-600'
              }`} style={{ width: `${Math.max(5, d.score)}%` }} />
            </div>
            <span className={`text-[10px] shrink-0 ${
              d.level === 'deep' ? 'text-emerald-500' : d.level === 'surface' ? 'text-amber-500' : 'text-ink-subtle'
            }`}>{d.label}</span>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className={`p-3 rounded-lg border text-[10px] ${
        absentCount === 0 && deepCount >= data.length * 0.5
          ? 'bg-emerald-50/30 dark:bg-emerald-950/10 border-emerald-100 dark:border-emerald-900/30 text-emerald-600 dark:text-emerald-400'
          : absentCount > data.length * 0.3
          ? 'bg-red-50/30 dark:bg-red-950/10 border-red-100 dark:border-red-900/30 text-red-600 dark:text-red-400'
          : 'bg-amber-50/30 dark:bg-amber-950/10 border-amber-100 dark:border-amber-900/30 text-amber-600 dark:text-amber-400'
      }`}>
        {absentCount === 0 && deepCount >= data.length * 0.5
          ? `✅ ${deepCount}/${data.length} 章深度触及核心问题。你的小说在追问，不是在填充。`
          : absentCount > data.length * 0.3
          ? `⚠️ ${absentCount}/${data.length} 章完全没有触及核心问题。这些章只是在推进情节——不是在追问。`
          : `${deepCount}章深度触及，${absentCount}章未触及。核心问题的追问还不够持续。`}
      </div>
    </div>
  );
}

/* ─── Scene Purpose (So What Test) ─── */
function ScenePurposePanel({ content, chapterNum, checking }: { content: string; chapterNum: number | null; checking: boolean }) {
  const analysis = useMemo(() => {
    if (!content) return null;
    const scenes = content.split('\n').filter(l => l.trim().length > 20);
    const results = scenes.slice(0, 8).map((scene, i) => {
      const hasConflict = /[打斗对决争辩吵冲突矛盾反抗].*/.test(scene);
      const hasChange = /突然|猛然|发现|意识到|决定|不再|终于|原来|竟然/.test(scene);
      const hasEmotion = /[喜怒哀乐悲恐惊忧恨羞].*/.test(scene);
      const isDialogue = /[「「""''“”说问道答]/.test(scene);
      const hasRevelation = /秘密|真相|揭露|发现|原来|竟然|隐藏/.test(scene);

      let purpose = '';
      let grade = 'weak';
      if (hasRevelation && hasEmotion) { purpose = '揭示+情感转折 ← 这就是读者付钱的原因'; grade = 'strong'; }
      else if (hasConflict && hasChange) { purpose = '冲突推动变化 ← 有效的戏剧场景'; grade = 'good'; }
      else if (isDialogue && hasConflict) { purpose = '对话中的冲突 ← 不错但需要变化'; grade = 'ok'; }
      else if (isDialogue && !hasConflict) { purpose = '对话但没有冲突 ← 问自己：这场对话非写不可吗？'; grade = 'weak'; }
      else if (!hasConflict && !hasChange && !hasEmotion) { purpose = '没有冲突/变化/情感 ← 读者会跳过这一段'; grade = 'dead'; }
      else { purpose = '有一定的功能但意图不够清晰'; grade = 'weak'; }

      return { scene: scene.slice(0, 60), purpose, grade };
    });

    const strongCount = results.filter(r => r.grade === 'strong' || r.grade === 'good').length;
    const deadCount = results.filter(r => r.grade === 'dead').length;
    return { results, strongCount, deadCount, total: results.length };
  }, [content]);

  if (checking) return <div className="space-y-2 py-4">{[90,75,60,85].map((w,i)=><div key={i} className="skeleton h-4 rounded" style={{width:`${w}%`}}/>)}</div>;
  if (!chapterNum) return <p className="text-xs text-ink-muted py-4 text-center">选择章节进行场景意图分析</p>;
  if (!analysis) return <p className="text-xs text-ink-muted py-4 text-center">无法分析该章节</p>;

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted leading-relaxed">
        每个场景必须回答一个问题：<strong>读者为什么需要看到这个？</strong>如果答案只是"推进情节"——那还不够。
      </p>

      {analysis.results.map((r, i) => (
        <div key={i} className={`p-2.5 rounded-lg border text-[11px] ${
          r.grade === 'strong' ? 'bg-emerald-50/30 dark:bg-emerald-950/10 border-emerald-100 dark:border-emerald-900/30' :
          r.grade === 'good' ? 'bg-sky-50/30 dark:bg-sky-950/10 border-sky-100 dark:border-sky-900/30' :
          r.grade === 'ok' ? 'bg-paper border-border' :
          r.grade === 'dead' ? 'bg-red-50/30 dark:bg-red-950/10 border-red-100 dark:border-red-900/30' :
          'bg-amber-50/30 dark:bg-amber-950/10 border-amber-100 dark:border-amber-900/30'
        }`}>
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold ${
              r.grade === 'strong' ? 'text-emerald-500' : r.grade === 'good' ? 'text-sky-500' :
              r.grade === 'dead' ? 'text-red-500' : 'text-amber-500'
            }`}>
              {r.grade === 'strong' ? '★' : r.grade === 'good' ? '●' : r.grade === 'dead' ? '✕' : '○'}
            </span>
            <span className="text-ink-muted">{r.purpose}</span>
          </div>
          <p className="text-ink-subtle leading-relaxed">「{r.scene}...」</p>
        </div>
      ))}

      <div className={`p-3 rounded-lg border text-[10px] ${
        analysis.deadCount === 0 && analysis.strongCount >= analysis.total * 0.3
          ? 'bg-emerald-50/30 dark:bg-emerald-950/10 border-emerald-100 text-emerald-600'
          : analysis.deadCount > 1
          ? 'bg-red-50/30 dark:bg-red-950/10 border-red-100 text-red-600'
          : 'bg-amber-50/30 dark:bg-amber-950/10 border-amber-100 text-amber-600'
      }`}>
        {analysis.deadCount === 0 && analysis.strongCount >= analysis.total * 0.3
          ? `✅ ${analysis.strongCount}/${analysis.total} 个场景有明确的存在理由`
          : analysis.deadCount > 1
          ? `⚠️ ${analysis.deadCount} 个场景没有冲突/变化/情感——读者会跳过。问自己：删掉这一段，故事缺了什么？`
          : `${analysis.strongCount}个强场景，${analysis.deadCount}个弱场景。每个场景都应该让读者更了解角色或更投入情节。`}
      </div>
    </div>
  );
}

/* ─── Re-read Value ─── */
function RereadValuePanel({ content, chapterNum, checking }: { content: string; chapterNum: number | null; checking: boolean }) {
  const analysis = useMemo(() => {
    if (!content) return null;
    // Hidden clues: sentences that hint at something without stating it
    const sentences = content.split(/[。！？!?]/).filter((s: string) => s.trim().length > 5);
    const clues = sentences.filter((s: string) =>
      /似乎|好像|仿佛|隐约|莫名|不知|未解|剩下|余下|残|留下/.test(s) && s.length < 60
    );
    // Double meanings: sentences that can be read two ways
    const doubles = sentences.filter((s: string) =>
      /其实|原来|并非|不是.*而是|表面|背后|真相/.test(s) && s.length < 80
    );
    // Foreshadowing density
    const foreshadowWords = (content.match(/后来|那时|多年后|当时还不知道|此刻他还|没想到/g) || []).length;
    const score = Math.min(100, clues.length * 12 + doubles.length * 15 + foreshadowWords * 20);
    return { clues: clues.slice(0, 5), doubles: doubles.slice(0, 3), score, foreshadowWords };
  }, [content]);

  if (checking) return <div className="space-y-2 py-4">{[90,75,60].map((w,i)=><div key={i} className="skeleton h-4 rounded" style={{width:`${w}%`}}/>)}</div>;
  if (!chapterNum) return <p className="text-xs text-ink-muted py-4 text-center">选择章节进行重读价值分析</p>;
  if (!analysis) return <p className="text-xs text-ink-muted py-4 text-center">无法分析该章节</p>;

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted leading-relaxed">
        一本值得重读的书，每一章都藏着第一遍读不到的线索。读者读完结局回头——<strong>"啊，原来这里已经暗示了"</strong>。
      </p>

      <div className="text-center p-4 rounded-xl bg-gradient-to-br from-accent-soft/30 to-transparent border border-accent/10">
        <div className={`text-3xl font-bold ${analysis.score >= 60 ? 'text-emerald-500' : analysis.score >= 30 ? 'text-amber-500' : 'text-red-500'}`}>
          {analysis.score}
        </div>
        <div className="text-[10px] text-ink-muted mt-1">重读价值分</div>
      </div>

      {analysis.clues.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-ink-muted mb-1.5">🔍 隐藏线索（第一遍容易忽略）</p>
          {analysis.clues.map((c, i) => (
            <p key={i} className="text-[10px] text-purple-600 dark:text-purple-400 leading-relaxed mb-1">「{c}」</p>
          ))}
        </div>
      )}

      {analysis.doubles.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-ink-muted mb-1.5">🔮 双层含义（重读时才明白）</p>
          {analysis.doubles.map((d, i) => (
            <p key={i} className="text-[10px] text-accent leading-relaxed mb-1">「{d}」</p>
          ))}
        </div>
      )}

      {analysis.clues.length === 0 && analysis.doubles.length === 0 && (
        <div className="p-3 rounded-lg bg-amber-50/30 dark:bg-amber-950/10 border border-amber-100 text-[10px] text-amber-600">
          ⚠️ 未检测到隐藏线索或双层含义。试试：在对话中埋一个只有知道结局才懂的暗示。让某个角色说一句"当时以为是玩笑"的话。
        </div>
      )}

      <div className="text-[10px] text-ink-subtle">
        线索 {analysis.clues.length} 条 · 双层含义 {analysis.doubles.length} 处 · 伏笔词 {analysis.foreshadowWords} 个
      </div>
    </div>
  );
}

/* ─── Emotional Layering ─── */
function EmotionLayerPanel({ content, chapterNum, checking }: { content: string; chapterNum: number | null; checking: boolean }) {
  const analysis = useMemo(() => {
    if (!content) return null;
    const emotions: { label: string; emoji: string; count: number; pattern: RegExp }[] = [
      { label: '喜悦', emoji: '😊', count: 0, pattern: /笑|开心|快乐|欢喜|高兴|喜悦|欣慰/g },
      { label: '悲伤', emoji: '😢', count: 0, pattern: /泪|哭|悲伤|难过|伤心|痛苦|哀|叹息/g },
      { label: '愤怒', emoji: '😠', count: 0, pattern: /怒|气|愤|恨|咬牙|握拳|暴/g },
      { label: '恐惧', emoji: '😨', count: 0, pattern: /怕|恐惧|慌|惊|抖|冷|寒/g },
      { label: '好奇', emoji: '🤔', count: 0, pattern: /疑惑|疑问|不解|诧异|奇怪|为什么|难道/g },
      { label: '温情', emoji: '💕', count: 0, pattern: /温柔|温暖|柔|软|轻轻|小心|呵护|拥抱/g },
      { label: '孤独', emoji: '🫥', count: 0, pattern: /孤独|寂寞|一个人|独自|空|无人|静悄悄/g },
      { label: '决心', emoji: '💪', count: 0, pattern: /决定|一定|必须|绝不|坚定|握紧|咬牙/g },
    ];
    for (const e of emotions) {
      e.count = (content.match(e.pattern) || []).length;
    }
    const active = emotions.filter(e => e.count > 0);
    const totalActive = active.length;
    const isLayered = totalActive >= 3;
    const dominant = active.sort((a, b) => b.count - a.count).slice(0, 3);
    return { active, totalActive, isLayered, dominant };
  }, [content]);

  if (checking) return <div className="space-y-2 py-4">{[90,75,60].map((w,i)=><div key={i} className="skeleton h-4 rounded" style={{width:`${w}%`}}/>)}</div>;
  if (!chapterNum) return <p className="text-xs text-ink-muted py-4 text-center">选择章节进行情感层次分析</p>;
  if (!analysis) return <p className="text-xs text-ink-muted py-4 text-center">无法分析该章节</p>;

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted leading-relaxed">
        神作的情感从来不是单一的。一场胜利里藏着失去的苦涩，一次重逢里带着岁月的苍凉。
        <strong>复杂的情感才是真实的。</strong>
      </p>

      <div className="text-center p-3 rounded-xl bg-paper border border-border">
        <div className={`text-2xl font-bold ${analysis.totalActive >= 4 ? 'text-emerald-500' : analysis.totalActive >= 2 ? 'text-amber-500' : 'text-red-500'}`}>
          {analysis.totalActive}/8
        </div>
        <div className="text-[10px] text-ink-muted mt-1">
          {analysis.totalActive >= 4 ? '✅ 情感层次丰富' : analysis.totalActive >= 2 ? '🟡 情感层次一般' : '⚠️ 情感层次单一'}
        </div>
      </div>

      {/* Emotion bars */}
      <div className="space-y-1">
        {analysis.active.sort((a, b) => b.count - a.count).map(e => (
          <div key={e.label} className="flex items-center gap-2 text-[10px]">
            <span className="w-10 text-right shrink-0">{e.emoji} {e.label}</span>
            <div className="flex-1 h-4 bg-border/50 rounded-full overflow-hidden">
              <div className="h-full bg-accent/60 rounded-full" style={{ width: `${Math.min(100, e.count * 8)}%` }} />
            </div>
            <span className="text-ink-subtle w-6 tabular-nums">{e.count}</span>
          </div>
        ))}
      </div>

      {/* Dominant emotion analysis */}
      {analysis.dominant.length >= 2 && (
        <div className={`p-3 rounded-lg border text-[10px] ${
          analysis.dominant.length >= 4
            ? 'bg-emerald-50/30 dark:bg-emerald-950/10 border-emerald-100 text-emerald-600'
            : 'bg-amber-50/30 dark:bg-amber-950/10 border-amber-100 text-amber-600'
        }`}>
          {analysis.dominant.length >= 4
            ? `✅ 主导情绪：${analysis.dominant.map(e => e.emoji+e.label).join(' + ')}。多种情绪交织——这正是真实的人类感受。`
            : `🟡 主导情绪：${analysis.dominant.map(e => e.emoji+e.label).join(' + ')}。尝试加入第三种情绪——比如在喜悦中掺入一丝忧伤。`}
        </div>
      )}
    </div>
  );
}

/* ─── Theme Deepening ─── */
function ThemeDeepenPanel({ content, chapterNum, checking, engineQuestion }: { content: string; chapterNum: number | null; checking: boolean; engineQuestion: string }) {
  const analysis = useMemo(() => {
    if (!content || !engineQuestion) return null;
    // Extract key concepts from the core question
    const qKeywords = engineQuestion.replace(/[？?，。、；：！!\s]/g, '');

    // Look for complication patterns: words that suggest the theme is being complicated
    const complicates = content.match(/但是|然而|不过|可是|却|反而|竟然|原来|并不是|也许|或许/g) || [];
    // Look for deepening patterns: words that suggest new understanding
    const deepens = content.match(/意识到|明白|原来如此|终于|不再|开始|渐渐|逐渐/g) || [];
    // Restatements without deepening
    const restates = content.match(/因为.*所以|因此|于是|就这样/g) || [];

    const complicateScore = Math.min(50, complicates.length * 10);
    const deepenScore = Math.min(50, deepens.length * 10);
    const restatePenalty = Math.min(30, restates.length * 5);
    const totalScore = Math.max(0, complicateScore + deepenScore - restatePenalty);

    let insight = '';
    if (totalScore >= 60) insight = '✅ 这一章让核心问题变得更复杂了——不是回答，是追问更深。';
    else if (totalScore >= 30) insight = '🟡 这一章涉及了核心问题，但没有推进对问题的理解。';
    else insight = '⚠️ 这一章绕开了核心问题。情节在推进，但问题在等待。';

    return { complicates: complicates.length, deepens: deepens.length, restates: restates.length, totalScore, insight };
  }, [content, engineQuestion]);

  if (checking) return <div className="space-y-2 py-4">{[90,75,60].map((w,i)=><div key={i} className="skeleton h-4 rounded" style={{width:`${w}%`}}/>)}</div>;
  if (!engineQuestion) return <p className="text-xs text-ink-muted py-4 text-center">请先在灵魂引擎中设置核心问题</p>;
  if (!chapterNum) return <p className="text-xs text-ink-muted py-4 text-center">选择章节进行主题深化分析</p>;
  if (!analysis) return <p className="text-xs text-ink-muted py-4 text-center">无法分析该章节</p>;

  return (
    <div className="space-y-3">
      <div className="p-3 rounded-lg bg-accent-soft/20 border border-accent/10">
        <p className="text-[10px] text-ink-subtle mb-1">核心问题</p>
        <p className="text-sm text-ink font-medium">{engineQuestion}</p>
      </div>

      <p className="text-xs text-ink-muted leading-relaxed">
        伟大的小说不会回答它提出的问题——它让问题变得更复杂。
        每一章不应该<strong>回答</strong>核心问题，而应该让读者对问题有<strong>新的理解</strong>。
      </p>

      {/* Score */}
      <div className="text-center p-4 rounded-xl bg-gradient-to-br from-accent-soft/30 to-transparent border border-accent/10">
        <div className={`text-3xl font-bold ${analysis.totalScore >= 60 ? 'text-emerald-500' : analysis.totalScore >= 30 ? 'text-amber-500' : 'text-red-500'}`}>
          {analysis.totalScore}
        </div>
        <div className="text-[10px] text-ink-muted mt-1">主题深化度</div>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-3 gap-2 text-[10px]">
        <div className="p-2.5 rounded-lg bg-emerald-50/30 dark:bg-emerald-950/10 border border-emerald-100 text-center">
          <div className="font-bold text-emerald-500">{analysis.complicates}</div>
          <div className="text-ink-subtle">转折词</div>
          <div className="text-[9px] text-ink-subtle mt-0.5">让问题变复杂</div>
        </div>
        <div className="p-2.5 rounded-lg bg-sky-50/30 dark:bg-sky-950/10 border border-sky-100 text-center">
          <div className="font-bold text-sky-500">{analysis.deepens}</div>
          <div className="text-ink-subtle">深化词</div>
          <div className="text-[9px] text-ink-subtle mt-0.5">推进理解</div>
        </div>
        <div className="p-2.5 rounded-lg bg-amber-50/30 dark:bg-amber-950/10 border border-amber-100 text-center">
          <div className="font-bold text-amber-500">{analysis.restates}</div>
          <div className="text-ink-subtle">因果词</div>
          <div className="text-[9px] text-ink-subtle mt-0.5">简单重复</div>
        </div>
      </div>

      <div className={`p-3 rounded-lg border text-[10px] ${
        analysis.totalScore >= 60
          ? 'bg-emerald-50/30 dark:bg-emerald-950/10 border-emerald-100 text-emerald-600'
          : analysis.totalScore >= 30
          ? 'bg-amber-50/30 dark:bg-amber-950/10 border-amber-100 text-amber-600'
          : 'bg-red-50/30 dark:bg-red-950/10 border-red-100 text-red-600'
      }`}>
        {analysis.insight}
      </div>
    </div>
  );
}

/* ─── Compression Loss ─── */
function CompressionLossPanel({ content, chapterNum, checking }: { content: string; chapterNum: number | null; checking: boolean }) {
  const analysis = useMemo(() => {
    if (!content) return null;
    const plotLines = content.split('\n').filter((l: string) => /[打攻击杀砍刺射爆炸飞跑跳冲撞推拉拽摔]|发现|得知|到达|离开|决定/.test(l) && l.length < 100).slice(0, 5);
    const totalChars = content.length;
    const plotChars = plotLines.reduce((s: number, l: string) => s + l.length, 0);
    const textureRatio = Math.round(((totalChars - plotChars) / Math.max(1, totalChars)) * 100);
    const details = (content.match(/[0-9]+[岁年天步尺元个件把张条座]|[红橙黄绿蓝靛紫黑白灰褐]|气味|味道|温度/g) || []).length;
    const detailDensity = Math.round((details / Math.max(1, totalChars / 100)));
    const nonInfoDialogue = (content.match(/[「「](?!.*因为|.*所以|.*告诉|.*通知)[^」」]{10,60}[」」]/g) || []).length;
    const score = Math.min(100, textureRatio * 0.5 + detailDensity * 5 + nonInfoDialogue * 8);
    return { plotLines, textureRatio, detailDensity, nonInfoDialogue, score };
  }, [content]);
  if (checking) return <div className="space-y-2 py-4">{[90,75,60].map((w,i)=><div key={i} className="skeleton h-4 rounded" style={{width:`${w}%`}}/>)}</div>;
  if (!chapterNum) return <p className="text-xs text-ink-muted py-4 text-center">选择章节</p>;
  if (!analysis) return <p className="text-xs text-ink-muted py-4 text-center">无法分析</p>;
  return (<div className="space-y-3"><p className="text-xs text-ink-muted leading-relaxed">神作不能被情节总结替代。<strong>情节是骨架，但灵魂在骨架之间的空隙里。</strong></p><div className="text-center p-4 rounded-xl bg-gradient-to-br from-accent-soft/30 to-transparent border border-accent/10"><div className={`text-3xl font-bold ${analysis.score>=60?'text-emerald-500':analysis.score>=30?'text-amber-500':'text-red-500'}`}>{analysis.textureRatio}%</div><div className="text-[10px] text-ink-muted mt-1">不可压缩的「肌理」占比</div></div><div className="p-3 rounded-lg bg-paper border border-border text-[10px]"><p className="text-ink-muted mb-1">只用三句话总结本章情节：</p>{analysis.plotLines.slice(0,3).map((l,i)=><p key={i} className="text-ink leading-relaxed">{i+1}. {l.slice(0,60)}</p>)}<p className="text-ink-subtle mt-2">{analysis.textureRatio<30?'⚠️ 这三句话涵盖了70%——剩下的在填充而非丰富。':analysis.textureRatio>=60?'✅ 大量细节、氛围、潜台词无法压缩——这就是不可压缩性。':'🟡 有一定肌理，但仍有不少可压缩段落。'}</p></div></div>);
}

/* ─── Character Mercy ─── */
function CharacterMercyPanel({ content, chapterNum, checking }: { content: string; chapterNum: number | null; checking: boolean }) {
  const analysis = useMemo(() => {
    if (!content) return null;
    const vulnerability = /[痛苦|悲伤|孤独|恐惧|挣扎|犹豫|动摇|犹疑|不舍|后悔|愧疚]/.test(content);
    const motivation = /因为|为了|保护|守护|想要|渴望|必须|不得不|无奈/.test(content);
    const understanding = /也许|或许|可能|如果|若是|假如|若|倘若/.test(content);
    const mercyScore = (vulnerability?30:0)+(motivation?30:0)+(understanding?25:0);
    return { vulnerability, motivation, understanding, mercyScore, level: mercyScore>=60?'慈悲':mercyScore>=30?'公允':'刻板' };
  }, [content]);
  if (checking) return <div className="space-y-2 py-4">{[90,75,60].map((w,i)=><div key={i} className="skeleton h-4 rounded" style={{width:`${w}%`}}/>)}</div>;
  if (!chapterNum) return <p className="text-xs text-ink-muted py-4 text-center">选择章节</p>;
  if (!analysis) return <p className="text-xs text-ink-muted py-4 text-center">无法分析</p>;
  return (<div className="space-y-3"><p className="text-xs text-ink-muted leading-relaxed">托尔斯泰写安娜的丈夫——被戴绿帽的官僚——你恨不起来。<strong>神作的作者对所有角色都有慈悲。</strong></p><div className="grid grid-cols-3 gap-2 text-center text-[10px]">{[{k:'脆弱性',v:analysis.vulnerability,i:'😢',j:'🪨',t:'有脆弱时刻',f:'刀枪不入'},{k:'动机',v:analysis.motivation,i:'🤔',j:'👹',t:'有合理动机',f:'纯粹邪恶'},{k:'理解',v:analysis.understanding,i:'👁️',j:'🔨',t:'尝试理解',f:'直接审判'}].map(m=><div key={m.k} className={`p-2.5 rounded-lg border ${m.v?'bg-emerald-50/30 dark:bg-emerald-950/10 border-emerald-100':'bg-red-50/30 dark:bg-red-950/10 border-red-100'}`}><div className="text-lg">{m.v?m.i:m.j}</div><div className="text-ink font-medium mt-1">{m.k}</div><div className="text-ink-subtle">{m.v?m.t:m.f}</div></div>)}</div><div className={`p-3 rounded-lg border text-[10px] ${analysis.level==='慈悲'?'bg-emerald-50/30 border-emerald-100 text-emerald-600':analysis.level==='公允'?'bg-amber-50/30 border-amber-100 text-amber-600':'bg-red-50/30 border-red-100 text-red-600'}`}>{analysis.level==='慈悲'?'✅ 角色具有脆弱性、合理动机和叙事理解——读者能看到每个人为什么成为现在的样子。':analysis.level==='公允'?'🟡 有一定角色维度，但还可以更深。试试给反派一个读者能共情的动机。':'⚠️ 角色过于刻板。每个反派都应该有"那个人也很可怜"的瞬间。'}</div></div>);
}

/* ─── Emotional Residue ─── */
function EmotionalResiduePanel({ content, chapterNum, checking }: { content: string; chapterNum: number | null; checking: boolean }) {
  const analysis = useMemo(() => {
    if (!content) return null;
    const first20 = content.slice(0, Math.floor(content.length*0.2));
    const last20 = content.slice(Math.floor(content.length*0.8));
    const emotions = ['喜悦','悲伤','愤怒','恐惧','好奇','温情','孤独','决心'];
    const getProfile = (t:string) => emotions.map(e=>({emoji:e,count:(t.match(new RegExp(`[${e.slice(0,3)}]`))||[]).length}));
    const beginProfile = getProfile(first20), endProfile = getProfile(last20);
    let shift = 0;
    for(let i=0;i<emotions.length;i++) shift += Math.abs((beginProfile[i]?.count||0)-(endProfile[i]?.count||0));
    const endsWithOpenness = /也许|或许|可能|如果|等待着|未知|尚未|还在|继续/.test(last20.slice(-200));
    const endsWithClosure = /终于|结束了|完成了|回到了|安息了|放下了/.test(last20.slice(-200));
    return { shift, endsWithOpenness, endsWithClosure, beginProfile, endProfile };
  }, [content]);
  if (checking) return <div className="space-y-2 py-4">{[90,75,60].map((w,i)=><div key={i} className="skeleton h-4 rounded" style={{width:`${w}%`}}/>)}</div>;
  if (!chapterNum) return <p className="text-xs text-ink-muted py-4 text-center">选择章节</p>;
  if (!analysis) return <p className="text-xs text-ink-muted py-4 text-center">无法分析</p>;
  return (<div className="space-y-3"><p className="text-xs text-ink-muted leading-relaxed">读完一章——读者应该在和开头<strong>不一样的情绪状态</strong>里。</p><div className="text-center p-4 rounded-xl bg-gradient-to-br from-accent-soft/30 to-transparent border border-accent/10"><div className={`text-3xl font-bold ${analysis.shift>=6?'text-emerald-500':analysis.shift>=2?'text-amber-500':'text-red-500'}`}>{analysis.shift}</div><div className="text-[10px] text-ink-muted mt-1">情感变化幅度</div></div><div className="grid grid-cols-2 gap-3 text-[10px]"><div className="p-2.5 rounded-lg bg-paper border border-border"><p className="text-ink-subtle mb-1">开头情绪</p>{analysis.beginProfile.filter(e=>e.count>0).slice(0,3).map((e,i)=><span key={i} className="text-ink">{e.emoji}×{e.count} </span>)}</div><div className="p-2.5 rounded-lg bg-paper border border-border"><p className="text-ink-subtle mb-1">结尾情绪</p>{analysis.endProfile.filter(e=>e.count>0).slice(0,3).map((e,i)=><span key={i} className="text-ink">{e.emoji}×{e.count} </span>)}</div></div><div className={`p-3 rounded-lg border text-[10px] ${analysis.endsWithOpenness&&!analysis.endsWithClosure?'bg-emerald-50/30 border-emerald-100 text-emerald-600':analysis.endsWithClosure&&!analysis.endsWithOpenness?'bg-amber-50/30 border-amber-100 text-amber-600':'bg-paper border-border text-ink-muted'}`}>{analysis.endsWithOpenness&&!analysis.endsWithClosure?'✅ 结尾是敞开的——故事结束，人物的生命还在继续。':analysis.endsWithClosure&&!analysis.endsWithOpenness?'🟡 结尾太干净了。神作的结尾不是关上门——是打开窗。':'结尾介于开放和闭合之间。有分寸感。'}</div></div>);
}

/* ─── Form-Soul Unity ─── */
function FormSoulUnityPanel({ content, chapterNum, checking, novelId }: { content: string; chapterNum: number | null; checking: boolean; novelId: string }) {
  const analysis = useMemo(() => {
    if (!content) return null;
    let polarity = '';
    try { const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${novelId}`)||'null'); polarity = fp?.primaryPolarity||''; } catch {}
    if (!polarity) return { hasSoul: false };
    const mismatches: string[] = [], matches: string[] = [];
    if (polarity==='silence-expression') {
      const explicit = (content.match(/他感到|她觉得|他想|她很|他非常/g)||[]).length;
      if (explicit>5) mismatches.push(`灵魂要求"沉默↔表达"但发现${explicit}处直接情感陈述`);
      else matches.push('情感通过动作和景物暗示——符合"沉默"法则');
    }
    if (polarity==='body-mind') {
      const abs = (content.match(/他觉得|她认为|他明白|她意识到/g)||[]).length;
      if (abs>4) mismatches.push(`灵魂要求"肉体↔精神"但发现${abs}处抽象心理描写`);
      const body = (content.match(/[温度气味触感疼痛饥饿冷热汗血]/g)||[]).length;
      if (body>5) matches.push(`发现${body}处身体感受细节——符合"肉体"法则`);
      else mismatches.push('缺乏具体的身体感受描写');
    }
    if (polarity==='desire-constraint') {
      if ((content.match(/轻松|顺利|成功|赢了|获得/g)||[]).length>3 && !content.includes('代价')) mismatches.push('角色获得太多而没有相应代价');
      else matches.push('角色在获取中付出了代价——符合"欲望↔约束"');
    }
    const score = Math.max(0,Math.min(100,50+matches.length*30-mismatches.length*20));
    return { hasSoul:true, polarity, mismatches, matches, score };
  }, [content, novelId]);
  if (checking) return <div className="space-y-2 py-4">{[90,75,60].map((w,i)=><div key={i} className="skeleton h-4 rounded" style={{width:`${w}%`}}/>)}</div>;
  if (!chapterNum) return <p className="text-xs text-ink-muted py-4 text-center">选择章节</p>;
  if (!analysis) return <p className="text-xs text-ink-muted py-4 text-center">无法分析</p>;
  if (!analysis.hasSoul) return <div className="p-4 text-center"><p className="text-xs text-ink-muted">尚未配置灵魂</p><p className="text-[10px] text-ink-subtle mt-1">在「灵魂构建」中选择核心矛盾后，这里将检测写作是否忠于灵魂</p></div>;
  return (<div className="space-y-3"><p className="text-xs text-ink-muted leading-relaxed">神作的<strong>形式就是内容</strong>。换了形式，内容就消失了。</p><div className="text-center p-4 rounded-xl bg-gradient-to-br from-accent-soft/30 to-transparent border border-accent/10"><div className={`text-3xl font-bold ${analysis.score>=70?'text-emerald-500':analysis.score>=40?'text-amber-500':'text-red-500'}`}>{analysis.score}</div><div className="text-[10px] text-ink-muted mt-1">形式-灵魂统一度</div></div>{analysis.matches.map((m,i)=><p key={i} className="text-[10px] text-emerald-600">✅ {m}</p>)}{analysis.mismatches.map((m,i)=><p key={i} className="text-[10px] text-red-500">⚠️ {m}</p>)}</div>);
}

/* ─── Main Component ─── */
export function MasterworkLab({ novelId, chapters, genre }: {
  novelId: string; chapters?: ChapterMeta[]; genre: string;
}) {
  // Build core question from soul answers
  const engineQuestion = (() => {
    try {
      const answers = JSON.parse(localStorage.getItem(`soul-answers-${novelId}`) || '{}');
      const parts: string[] = [];
      if (answers.authenticity) parts.push(answers.authenticity);
      if (answers.tension) parts.push(answers.tension);
      return parts.join(' | ') || '';
    } catch { return ''; }
  })();
  const [tab, setTab] = useState<'laws' | 'image' | 'echo' | 'question' | 'scene' | 'reread' | 'emotion' | 'deepen' | 'compression' | 'mercy' | 'residue' | 'formSoul'>('laws');
  const [checkChapter, setCheckChapter] = useState<number | null>(null);
  const [checkContent, setCheckContent] = useState('');
  const [checking, setChecking] = useState(false);

  const gen = (chapters || []).filter(c => c.word_count > 0);

  async function loadChapterForCheck(num: number) {
    setCheckChapter(num);
    setChecking(true);
    try {
      const r = await fetch(`/api/novels/${novelId}/chapters/${num}`);
      const d = await r.json();
      setCheckContent(d.content || '');
    } catch { toast.error('加载失败'); }
    finally { setChecking(false); }
  }

  const tabs = [
    { key: 'laws' as const, label: '🌍 法则', desc: '人际物理' },
    { key: 'image' as const, label: '🔮 意象', desc: '贯穿物件' },
    { key: 'echo' as const, label: '🔄 呼应', desc: '结局改写开头' },
    { key: 'question' as const, label: '❓ 追问', desc: '每章触及' },
    { key: 'scene' as const, label: '🎬 场景', desc: 'So What测试' },
    { key: 'reread' as const, label: '🔍 重读', desc: '隐藏线索' },
    { key: 'emotion' as const, label: '💗 层次', desc: '情感复杂度' },
    { key: 'deepen' as const, label: '📐 深化', desc: '主题递进' },
    { key: 'compression' as const, label: '📦 压缩', desc: '不可总结' },
    { key: 'mercy' as const, label: '🤲 慈悲', desc: '反派维度' },
    { key: 'residue' as const, label: '🫧 余味', desc: '情感残留' },
    { key: 'formSoul' as const, label: '🔗 统一', desc: '形式灵魂' },
  ];

  return (
    <div className="p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-heading text-base font-semibold text-ink">🏆 神作工坊</h3>
          <p className="text-[11px] text-ink-muted">七条神作法则的检测与执行</p>
        </div>
        <div className="flex gap-1 flex-wrap">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`text-[10px] px-2.5 py-1 rounded-md transition-colors ${
                tab === t.key ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink hover:bg-paper'
              }`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chapter selector for scene/reread/emotion/deepen tabs */}
      {(tab === 'scene' || tab === 'reread' || tab === 'emotion' || tab === 'deepen' || tab === 'compression' || tab === 'mercy' || tab === 'residue' || tab === 'formSoul') && (
        <div className="mb-3 flex gap-1.5 flex-wrap">
          <span className="text-[10px] text-ink-muted self-center mr-1">选择章节：</span>
          {gen.slice(-10).map(c => (
            <button key={c.number} onClick={() => loadChapterForCheck(c.number)}
              className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                checkChapter === c.number ? 'bg-accent-soft text-accent border-accent/30' : 'border-border text-ink-muted hover:text-ink'
              }`}>
              第{c.number}章
            </button>
          ))}
        </div>
      )}

      {tab === 'laws' && <WorldLawsPanel novelId={novelId} />}
      {tab === 'image' && <CentralImagePanel novelId={novelId} chapters={chapters} />}
      {tab === 'echo' && <EchoDetector novelId={novelId} chapters={chapters} />}
      {tab === 'question' && <QuestionPenetration chapters={chapters} engineQuestion={engineQuestion} />}
      {tab === 'scene' && <ScenePurposePanel content={checkContent} chapterNum={checkChapter} checking={checking} />}
      {tab === 'reread' && <RereadValuePanel content={checkContent} chapterNum={checkChapter} checking={checking} />}
      {tab === 'emotion' && <EmotionLayerPanel content={checkContent} chapterNum={checkChapter} checking={checking} />}
      {tab === 'deepen' && <ThemeDeepenPanel content={checkContent} chapterNum={checkChapter} checking={checking} engineQuestion={engineQuestion} />}
      {tab === 'compression' && <CompressionLossPanel content={checkContent} chapterNum={checkChapter} checking={checking} />}
      {tab === 'mercy' && <CharacterMercyPanel content={checkContent} chapterNum={checkChapter} checking={checking} />}
      {tab === 'residue' && <EmotionalResiduePanel content={checkContent} chapterNum={checkChapter} checking={checking} />}
      {tab === 'formSoul' && <FormSoulUnityPanel content={checkContent} chapterNum={checkChapter} checking={checking} novelId={novelId} />}

      {/* Seven laws overview */}
      <div className="mt-4 pt-3 border-t border-border">
        <p className="text-[9px] text-ink-subtle leading-relaxed">
          <strong>神作七法则：</strong>
          ①问一个自己回答不了的问题 ②主角做一次不可逆的选择 ③建立世界的人际物理法则
          ④把最重要的东西藏在沉默里 ⑤节奏如呼吸 ⑥找只属于这本书的意象 ⑦结局必须让开头变成新的
        </p>
      </div>
    </div>
  );
}
