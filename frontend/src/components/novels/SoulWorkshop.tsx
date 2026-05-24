import { useState, useEffect } from 'react';
import { toast } from 'sonner';

/* ─── Soul Profile ─── */
interface SoulProfile {
  soulStatement: string;
  icebergLevel: number;        // 1-10, how much to leave unsaid
  forbiddenWords: string[];    // words that flatten the soul
  detailFocus: string;         // what kind of details matter in this story
  contradictions: { character: string; surface: string; depth: string }[];
}

const DEFAULT_PROFILE: SoulProfile = {
  soulStatement: '',
  icebergLevel: 5,
  forbiddenWords: ['很', '非常', '十分', '极其', '特别'],
  detailFocus: '',
  contradictions: [],
};

function loadProfile(novelId: string): SoulProfile {
  try {
    const saved = localStorage.getItem(`soul-${novelId}`);
    return saved ? { ...DEFAULT_PROFILE, ...JSON.parse(saved) } : DEFAULT_PROFILE;
  } catch { return DEFAULT_PROFILE; }
}

function saveProfile(novelId: string, profile: SoulProfile) {
  localStorage.setItem(`soul-${novelId}`, JSON.stringify(profile));
}

/* ─── Soul Check Result ─── */
interface SoulCheck {
  specificityScore: number;    // 0-100, concrete detail usage
  icebergScore: number;        // 0-100, how much is shown vs told
  contradictionScore: number;  // 0-100, character depth present
  soulAlignment: number;       // 0-100, overall soul presence
  genericLines: string[];      // lines that are too generic
  explainedLines: string[];    // lines that over-explain
  detailLines: string[];       // good concrete details found
  suggestions: string[];
}

function runSoulCheck(text: string, profile: SoulProfile): SoulCheck {
  const suggestions: string[] = [];
  const genericLines: string[] = [];
  const explainedLines: string[] = [];
  const detailLines: string[] = [];

  if (!text) {
    return { specificityScore: 0, icebergScore: 0, contradictionScore: 0, soulAlignment: 0, genericLines, explainedLines, detailLines, suggestions };
  }

  const lines = text.split('\n').filter(l => l.trim().length > 5);
  const dialogueBlocks = text.match(/[「「""''“”].*?[」」""''""]/g) || [];
  const narrationOnly = text.replace(/[「「""''“”].*?[」」""''""]/g, '');

  // ── Specificity: flag generic descriptions ──
  const genericPatterns = [
    /她很?漂亮/g, /他很?帅/g, /非常/g, /十分/g, /极其/g, /特别/g,
    /很强大/g, /很厉害/g, /很好看/g, /很好听/g, /很舒服/g,
    /不知名的/g, /某种/g, /一些/g, /许多/g, /各种/g,
    /美丽的花/g, /高大的树/g, /宽阔的街道/g, /豪华的房间/g,
  ];
  let genericCount = 0;
  for (const pattern of genericPatterns) {
    const matches = narrationOnly.match(pattern) || [];
    genericCount += matches.length;
    for (const m of matches.slice(0, 2)) {
      const line = lines.find(l => l.includes(m));
      if (line && !genericLines.includes(line.slice(0, 60))) {
        genericLines.push(line.slice(0, 60));
      }
    }
  }
  const specificityScore = Math.max(0, 100 - genericCount * 6);

  // ── Iceberg: flag over-explaining ──
  const explainPatterns = [
    /因为.*所以/g, /之所以.*是因为/g, /这意味着/g, /也就是说/g,
    /换句话/g, /简单来说/g, /总而言之/g, /这表明/g,
    /他的意思是/g, /她想表达的是/g, /这说明/g,
  ];
  let explainCount = 0;
  for (const pattern of explainPatterns) {
    const matches = narrationOnly.match(pattern) || [];
    explainCount += matches.length;
    for (const m of matches.slice(0, 1)) {
      const line = lines.find(l => l.includes(m));
      if (line && !explainedLines.includes(line.slice(0, 80))) {
        explainedLines.push(line.slice(0, 80));
      }
    }
  }
  // Also flag "character thinks" exposition
  const thoughtExplains = narrationOnly.match(/他觉得|她认为|他想|她明白|他意识到|她发现/g) || [];
  explainCount += thoughtExplains.length;
  const icebergScore = Math.max(0, 100 - explainCount * 10);

  // ── Detail richness: find concrete details ──
  const detailPatterns = [
    /[0-9零一二三四五六七八九十百千万亿]+[岁年天里步尺米元个只件把张条座]/,  // Numbers + measure words
    /[红橙黄绿蓝靛紫黑白灰褐粉金银铜铁锡][色的]?/,  // Color words
    /[冷暖凉热烫冰温][的]?/,  // Temperature
    /[香甜苦辣咸酸涩腥臭][的]?/,  // Taste/smell
    /[轻重硬软粗糙光滑锋利钝][的]?/,  // Texture
    /[叮咚轰隆啪嗒咔嚓沙沙哗啦滴答]/g,  // Onomatopoeia
  ];
  for (const pattern of detailPatterns) {
    const matches = text.match(pattern) || [];
    for (const m of matches.slice(0, 3)) {
      const line = lines.find(l => l.includes(m));
      if (line && !detailLines.includes(line.slice(0, 60))) {
        detailLines.push(line.slice(0, 60));
      }
    }
  }
  // Score: 1 detail per 200 chars is decent
  const detailDensity = detailLines.length / Math.max(1, text.length / 200);

  // ── Contradiction: check if profile contradictions appear ──
  let contradictionScore = 50;
  if (profile.contradictions.length > 0) {
    let found = 0;
    for (const c of profile.contradictions) {
      const surfacePresent = text.includes(c.surface.slice(0, 4));
      const depthPresent = text.includes(c.depth.slice(0, 4));
      if (surfacePresent && depthPresent) found += 2;
      else if (surfacePresent || depthPresent) found += 1;
    }
    contradictionScore = Math.min(100, Math.round((found / (profile.contradictions.length * 2)) * 100));
  }

  // ── Soul alignment ──
  let soulAlignment = 50;
  if (profile.soulStatement) {
    const keywords = profile.soulStatement.replace(/[，。、；：！？\s]/g, '').slice(0, 30);
    let keywordMatches = 0;
    for (let i = 0; i < keywords.length - 1; i++) {
      const bigram = keywords.slice(i, i + 2);
      if (text.includes(bigram)) keywordMatches++;
    }
    soulAlignment = Math.min(100, keywordMatches * 8 + 30);
  }

  // ── Suggestions ──
  if (specificityScore < 50) suggestions.push(`发现${genericCount}处泛泛描写。试试："她很漂亮"→"她笑起来右边有一个酒窝，左边没有"`);
  if (icebergScore < 50) suggestions.push(`发现${explainCount}处过度解释。读者不笨——删掉"因为...所以..."，让事实自己说话`);
  if (contradictionScore < 40 && profile.contradictions.length > 0) suggestions.push('角色矛盾未充分展现。回顾你设定的人物表面对比内在');
  if (detailLines.length < 3) suggestions.push('细节稀疏。加一个具体的感官细节：声音、气味、温度、触感');
  if (explainCount > 3) suggestions.push('海明威说：如果你知道的事情都写进去，读者看到的就是全部。删掉你知道的80%');

  return {
    specificityScore,
    icebergScore,
    contradictionScore,
    soulAlignment,
    genericLines: genericLines.slice(0, 3),
    explainedLines: explainedLines.slice(0, 3),
    detailLines: detailLines.slice(0, 3),
    suggestions: suggestions.slice(0, 4),
  };
}

/* ─── Soul Workshop Component ─── */
export function SoulWorkshop({ novelId, chapters }: { novelId: string; chapters?: any[] }) {
  const [profile, setProfile] = useState<SoulProfile>(() => loadProfile(novelId));
  const [editing, setEditing] = useState(false);
  const [selectedCh, setSelectedCh] = useState<number | null>(null);
  const [checkResult, setCheckResult] = useState<SoulCheck | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => { saveProfile(novelId, profile); }, [profile, novelId]);

  const gen = (chapters || []).filter((c: any) => c.word_count > 0);

  async function runCheck(chNum: number) {
    setSelectedCh(chNum);
    setChecking(true);
    try {
      const r = await fetch(`/api/novels/${novelId}/chapters/${chNum}`);
      const d = await r.json();
      setCheckResult(runSoulCheck(d.content || '', profile));
    } catch { toast.error('加载章节失败'); }
    finally { setChecking(false); }
  }

  function addContradiction() {
    setProfile(prev => ({
      ...prev,
      contradictions: [...prev.contradictions, { character: '', surface: '', depth: '' }],
    }));
  }

  function updateContradiction(idx: number, field: string, value: string) {
    setProfile(prev => {
      const next = [...prev.contradictions];
      next[idx] = { ...next[idx], [field]: value };
      return { ...prev, contradictions: next };
    });
  }

  function removeContradiction(idx: number) {
    setProfile(prev => ({
      ...prev,
      contradictions: prev.contradictions.filter((_, i) => i !== idx),
    }));
  }

  const soulDefined = profile.soulStatement.length > 5;

  return (
    <div className="p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-heading text-base font-semibold text-ink">💎 灵魂工坊</h3>
          <p className="text-[11px] text-ink-muted">
            定义小说的灵魂，让AI知道「这本书因何而独特」
          </p>
        </div>
        <button onClick={() => setEditing(!editing)}
          className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
            editing ? 'bg-accent text-white border-accent' : 'border-border text-ink-muted hover:text-ink'
          }`}>
          {editing ? '完成' : soulDefined ? '编辑灵魂' : '✎ 定义灵魂'}
        </button>
      </div>

      {/* Soul definition form */}
      {editing && (
        <div className="space-y-4 mb-4 p-4 bg-gradient-to-br from-accent-soft/20 to-transparent border border-accent/10 rounded-xl animate-[fadeSlideIn_0.2s_ease-out]">
          {/* Soul Statement */}
          <div>
            <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
              灵魂陈述 <span className="text-ink-subtle font-normal">——这本书的独特视角是什么？</span>
            </label>
            <textarea
              value={profile.soulStatement}
              onChange={e => setProfile({ ...profile, soulStatement: e.target.value })}
              placeholder="例如：不是写一个人如何变强，而是写变强之后发现自己失去了变强的理由。"
              rows={2}
              className="w-full mt-1.5 rounded-lg border border-input bg-card text-ink text-sm px-3 py-2 resize-none
                placeholder:text-ink-subtle focus:outline-none focus:border-accent transition-all" />
          </div>

          {/* Iceberg level */}
          <div>
            <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
              留白程度 <span className="text-ink-subtle font-normal">——{profile.icebergLevel}/10</span>
            </label>
            <input type="range" min="1" max="10" value={profile.icebergLevel}
              onChange={e => setProfile({ ...profile, icebergLevel: Number(e.target.value) })}
              className="w-full h-1.5 rounded-full appearance-none bg-border cursor-pointer mt-1
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent" />
            <div className="flex justify-between text-[8px] text-ink-subtle">
              <span>1 说尽一切</span><span>5 冰山水面</span><span>10 极简留白</span>
            </div>
          </div>

          {/* Detail focus */}
          <div>
            <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
              细节锚点 <span className="text-ink-subtle font-normal">——这个故事里什么细节最重要？</span>
            </label>
            <input
              value={profile.detailFocus}
              onChange={e => setProfile({ ...profile, detailFocus: e.target.value })}
              placeholder="例如：气味（药香、血腥味、雨后的泥土味）"
              className="w-full mt-1.5 rounded-lg border border-input bg-card text-ink text-sm px-3 py-2
                placeholder:text-ink-subtle focus:outline-none focus:border-accent transition-all" />
          </div>

          {/* Character contradictions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
                人物矛盾 <span className="text-ink-subtle font-normal">——表面 vs 内在</span>
              </label>
              <button onClick={addContradiction}
                className="text-[10px] text-accent hover:underline">+ 添加角色</button>
            </div>
            {profile.contradictions.map((c, i) => (
              <div key={i} className="flex gap-2 mb-2 items-start">
                <input value={c.character} onChange={e => updateContradiction(i, 'character', e.target.value)}
                  placeholder="角色名" className="w-20 text-xs rounded border border-input bg-card px-2 py-1.5" />
                <input value={c.surface} onChange={e => updateContradiction(i, 'surface', e.target.value)}
                  placeholder="表面：冷酷杀手" className="flex-1 text-xs rounded border border-input bg-card px-2 py-1.5" />
                <input value={c.depth} onChange={e => updateContradiction(i, 'depth', e.target.value)}
                  placeholder="内在：会为流浪猫停下" className="flex-1 text-xs rounded border border-input bg-card px-2 py-1.5" />
                <button onClick={() => removeContradiction(i)}
                  className="text-xs text-red-400 hover:text-red-600 dark:hover:text-red-400 px-1">×</button>
              </div>
            ))}
            {profile.contradictions.length === 0 && (
              <p className="text-[10px] text-ink-subtle">还没有添加角色矛盾。点击"+ 添加角色"</p>
            )}
          </div>

          {/* Forbidden words */}
          <div>
            <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
              禁用词 <span className="text-ink-subtle font-normal">——这些词会杀死灵魂</span>
            </label>
            <div className="flex gap-1.5 mt-1.5 flex-wrap">
              {profile.forbiddenWords.map((w, i) => (
                <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800 flex items-center gap-1">
                  {w}
                  <button onClick={() => setProfile(prev => ({
                    ...prev,
                    forbiddenWords: prev.forbiddenWords.filter((_, j) => j !== i),
                  }))} className="hover:text-red-800">×</button>
                </span>
              ))}
              <input
                placeholder="添加禁用词"
                className="text-[10px] w-20 rounded-full border border-input bg-card px-2 py-0.5"
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    const val = (e.target as HTMLInputElement).value.trim();
                    if (val && !profile.forbiddenWords.includes(val)) {
                      setProfile(prev => ({ ...prev, forbiddenWords: [...prev.forbiddenWords, val] }));
                    }
                    (e.target as HTMLInputElement).value = '';
                  }
                }} />
            </div>
          </div>

          <button onClick={() => { setEditing(false); toast.success('灵魂已保存，生成时将注入灵魂陈述'); }}
            className="w-full py-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors text-sm font-medium">
            💎 保存灵魂
          </button>
        </div>
      )}

      {/* Soul status summary */}
      {!editing && soulDefined && (
        <div className="mb-4 p-3 rounded-lg bg-gradient-to-r from-accent-soft/30 to-transparent border border-accent/10 text-xs">
          <p className="text-ink font-medium mb-1">📌 灵魂陈述</p>
          <p className="text-ink-muted italic leading-relaxed">「{profile.soulStatement}」</p>
          <div className="flex gap-3 mt-2 text-[10px] text-ink-subtle">
            <span>留白 {profile.icebergLevel}/10</span>
            <span>矛盾角色 {profile.contradictions.length}人</span>
            <span>禁用词 {profile.forbiddenWords.length}个</span>
          </div>
        </div>
      )}

      {/* Soul check */}
      {soulDefined && gen.length > 0 && (
        <div className="border-t border-border pt-3">
          <p className="text-[11px] text-ink-muted mb-2">选择章节进行灵魂检测：</p>
          <div className="flex gap-1.5 mb-3 flex-wrap">
            {gen.slice(-10).map((c: any) => (
              <button key={c.number} onClick={() => runCheck(c.number)}
                className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                  selectedCh === c.number ? 'bg-accent-soft text-accent border-accent/30' : 'border-border text-ink-muted hover:text-ink'
                }`}>
                第{c.number}章
              </button>
            ))}
          </div>

          {checking && (
            <div className="space-y-2 py-4">
              {[90, 75, 60, 85].map((w, i) => <div key={i} className="skeleton h-4 rounded" style={{ width: `${w}%` }} />)}
            </div>
          )}

          {checkResult && !checking && (
            <div className="space-y-3 animate-[fadeSlideIn_0.2s_ease-out]">
              {/* Four soul scores */}
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: '细节具体度', value: checkResult.specificityScore, tip: '具体>泛泛' },
                  { label: '留白度', value: checkResult.icebergScore, tip: '隐藏>解释' },
                  { label: '角色深度', value: checkResult.contradictionScore, tip: '矛盾>标签' },
                  { label: '灵魂对齐', value: checkResult.soulAlignment, tip: '独特>通用' },
                ].map(m => (
                  <div key={m.label} className="p-2.5 rounded-lg bg-paper border border-border">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-ink-muted">{m.label}</span>
                      <span className={`text-sm font-bold ${m.value >= 60 ? 'text-emerald-500' : m.value >= 35 ? 'text-amber-500' : 'text-red-500'}`}>
                        {m.value}
                      </span>
                    </div>
                    <div className="h-1 bg-border rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${m.value >= 60 ? 'bg-emerald-400' : m.value >= 35 ? 'bg-amber-400' : 'bg-red-400'}`}
                        style={{ width: `${m.value}%` }} />
                    </div>
                  </div>
                ))}
              </div>

              {/* Concrete findings */}
              {checkResult.genericLines.length > 0 && (
                <div className="p-3 rounded-lg bg-amber-50/50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/30">
                  <p className="text-[10px] font-medium text-amber-600 dark:text-amber-400 mb-1">🔍 泛泛描写（建议替换为具体细节）</p>
                  {checkResult.genericLines.map((l, i) => (
                    <p key={i} className="text-[10px] text-amber-700 dark:text-amber-500 leading-relaxed">「{l}」</p>
                  ))}
                </div>
              )}

              {checkResult.explainedLines.length > 0 && (
                <div className="p-3 rounded-lg bg-red-50/50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/30">
                  <p className="text-[10px] font-medium text-red-600 dark:text-red-400 mb-1">🗑️ 过度解释（删掉这些，读者会感谢你）</p>
                  {checkResult.explainedLines.map((l, i) => (
                    <p key={i} className="text-[10px] text-red-700 dark:text-red-500 leading-relaxed">「{l}」</p>
                  ))}
                </div>
              )}

              {checkResult.detailLines.length > 0 && (
                <div className="p-3 rounded-lg bg-emerald-50/50 dark:bg-emerald-900/10 border border-emerald-100 dark:border-emerald-900/30">
                  <p className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400 mb-1">✨ 好细节（这就是灵魂）</p>
                  {checkResult.detailLines.map((l, i) => (
                    <p key={i} className="text-[10px] text-emerald-700 dark:text-emerald-500 leading-relaxed">「{l}」</p>
                  ))}
                </div>
              )}

              {checkResult.suggestions.length > 0 && (
                <div className="space-y-1">
                  {checkResult.suggestions.map((s, i) => (
                    <p key={i} className="text-[10px] text-accent">💡 {s}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
