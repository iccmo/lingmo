import { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';

const BASE_SUGGESTIONS = [
  { emoji: '⚔️', label: '打斗场面', text: '本章需要有激烈的打斗场面' },
  { emoji: '💕', label: '感情戏', text: '发展主角与重要角色的感情线' },
  { emoji: '📜', label: '推进主线', text: '推动主线剧情，揭露关键信息' },
  { emoji: '🔮', label: '埋下伏笔', text: '为后续剧情埋下1-2个伏笔' },
  { emoji: '😱', label: '反转', text: '本章结尾需要有一个出人意料的转折' },
  { emoji: '🌅', label: '过渡章节', text: '承上启下的过渡，为下一章高潮铺垫' },
  { emoji: '👤', label: '角色成长', text: '主角在本章需要有明显的成长或觉悟' },
  { emoji: '🏙️', label: '世界观展开', text: '揭示更多世界观设定和背景' },
];

const SOUL_SUGGESTIONS: Record<string, { emoji: string; label: string; text: string }[]> = {
  'silence-expression': [
    { emoji: '🤫', label: '不说破', text: '用动作暗示情感——不直接写"他很难过"，写他反复擦桌子' },
    { emoji: '👀', label: '眼神戏', text: '关键对话中，让角色的眼神和动作说出他们的话说不出的东西' },
    { emoji: '🌧️', label: '景物暗示', text: '用天气/环境的变化暗示角色的内心——雨天的沉默比晴天的告白更有力' },
  ],
  'body-mind': [
    { emoji: '🤢', label: '身体反应', text: '写角色的身体感受——胃收缩、手心出汗、嘴里发苦——而不是心理活动' },
    { emoji: '👃', label: '气味描写', text: '加入具体的气味——血腥味、药味、雨后的泥土味' },
    { emoji: '🫀', label: '生理极限', text: '让角色在疲惫/饥饿/疼痛中做决定——身体的极限状态逼出真实的性格' },
  ],
  'desire-constraint': [
    { emoji: '⚖️', label: '两难选择', text: '角色面对两个都不想选的选项——但必须选一个。写出代价。' },
    { emoji: '💔', label: '放弃所爱', text: '为了更重要的事，角色必须放弃自己最想要的' },
    { emoji: '🪞', label: '自我欺骗', text: '角色说服自己"我不想要"——但读者能看到他在撒谎' },
  ],
  'freedom-fate': [
    { emoji: '🎲', label: '自由选择', text: '角色做一个主动的选择——但这个选择会带来意想不到的命运后果' },
    { emoji: '🔄', label: '越想逃越逃不掉', text: '角色努力避开某件事，但每一个躲避的动作都在靠近它' },
  ],
  'individual-society': [
    { emoji: '🔍', label: '一个细节', text: '用一个具体的细节写出时代对个人的碾压——不是宏大叙事' },
    { emoji: '🪨', label: '无能为力', text: '角色想改变什么但发现自己什么都改变不了——不是不努力' },
  ],
  'belonging-alienation': [
    { emoji: '🎭', label: '假装合群', text: '角色在人群中扮演"正常人"——但内心是疏离的' },
    { emoji: '🌌', label: '孤独时刻', text: '写一个角色独处的场景——他们的真实自我只在没人的时候出现' },
  ],
};

function getAdaptiveSuggestions(novelId: string) {
  try {
    const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${novelId}`) || 'null');
    const soulSuggestions = fp?.primaryPolarity ? SOUL_SUGGESTIONS[fp.primaryPolarity] : null;
    if (soulSuggestions) return [...soulSuggestions, ...BASE_SUGGESTIONS.slice(0, 5)];
  } catch {}
  return BASE_SUGGESTIONS;
}

export function GenerateDialog({ open, onClose, onGenerate, chapterNumber, prevHook, novelId, prefillDirection }: {
  open: boolean;
  onClose: () => void;
  onGenerate: (direction: string, qualityThreshold: number, revisionMode: string, model?: string) => void;
  chapterNumber: number;
  prevHook?: string;
  novelId: string;
  prefillDirection?: string;
}) {
  const [direction, setDirection] = useState('');
  const [memoryInput, setMemoryInput] = useState('');
  const [qualityThreshold, setQualityThreshold] = useState(() =>
    Number(localStorage.getItem('quality-threshold') || '0.80')
  );
  const [showFullPrompt, setShowFullPrompt] = useState(false);
  const [creativeRisk, setCreativeRisk] = useState(false);
  const [revisionMode, setRevisionMode] = useState<'quick' | 'deep'>('deep');
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem('selected-model') || '');
  const [availableModels, setAvailableModels] = useState<{ id: string; name: string; model: string }[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const SUGGESTIONS = getAdaptiveSuggestions(novelId);

  useEffect(() => {
    fetch('/api/providers').then(r => r.json()).then(providers => {
      const models: { id: string; name: string; model: string }[] = [];
      for (const p of providers) {
        if (p.api_key && p.models) {
          for (const m of (Array.isArray(p.models) ? p.models : [p.models])) {
            models.push({ id: p.id, name: p.name, model: m });
          }
        }
      }
      setAvailableModels(models);
      if (!selectedModel && models.length > 0) setSelectedModel(models[0].model);
    }).catch(() => {});
  }, []);

  // Build full context preview
  const fullContext = (() => {
    const parts: string[] = [];
    try {
      const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${novelId}`) || 'null');
      if (fp?.answer) parts.push(`【灵魂】${fp.answer}`);
    } catch {}
    try {
      const soul = JSON.parse(localStorage.getItem(`soul-${novelId}`) || 'null');
      if (soul?.soulStatement) parts.push(`【灵魂陈述】${soul.soulStatement}`);
      if (soul?.forbiddenWords?.length) parts.push(`【禁用词】${soul.forbiddenWords.join('、')}`);
    } catch {}
    try {
      const chars = JSON.parse(localStorage.getItem(`characters-soul-${novelId}`) || '[]');
      if (chars.length) parts.push(`【角色】${chars.length}个角色已配置`);
    } catch {}
    try {
      const laws = JSON.parse(localStorage.getItem(`world-laws-${novelId}`) || '{"laws":[]}');
      if (laws.laws?.length) parts.push(`【世界法则】${laws.laws.length}条`);
    } catch {}
    if (direction) parts.push(`【方向】${direction}`);
    return parts.join(' · ');
  })();

  useEffect(() => {
    if (open) {
      setDirection(prefillDirection || '');
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open, prefillDirection]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onGenerate(direction, qualityThreshold);
      }
    };
    if (open) window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, direction, qualityThreshold, onClose, onGenerate]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm"
      onClick={onClose}>
      <div className="bg-card border border-border rounded-xl p-6 w-[480px] max-w-[92vw] shadow-xl animate-[fadeSlideIn_0.2s_ease-out]"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-lg">✍️</span>
          <h3 className="font-heading text-lg font-semibold text-ink">生成第 {chapterNumber} 章</h3>
        </div>
        <p className="text-xs text-ink-muted mb-3">
          输入本章方向，AI 将据此创作。留空则自动构思。
        </p>

        {/* Configuration status — one-click auto-fill for missing items */}
        {(() => {
          const status: { key: string; label: string; ready: boolean; autoFill: () => void }[] = [];
          // Soul
          try {
            const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${novelId}`) || 'null');
            const soulReady = !!(fp?.primaryPolarity && fp?.answer);
            status.push({
              key: 'soul', label: '灵魂矛盾', ready: soulReady,
              autoFill: () => {
                if (soulReady) return;
                const genreFit: Record<string, string> = { '玄幻':'freedom-fate', '武侠':'freedom-fate', '悬疑':'truth-deception', '都市':'desire-constraint', '官场':'individual-society', '科幻':'scale-intimacy', '历史':'individual-society', '仙侠':'freedom-fate', '系统流':'meaning-absurdity', '末世':'life-death' };
                const polarity = genreFit[chapterNumber > 0 ? '' : '玄幻'] || 'desire-constraint';
                const data = { primaryPolarity: polarity, position: 5, answer: `在这本书的世界里，${polarity.includes('fate') ? '每个选择都引向注定的结局' : '真相和谎言交织在一起'}。` };
                localStorage.setItem(`soul-fingerprint-${novelId}`, JSON.stringify(data));
                toast.success('已自动配置灵魂矛盾');
              }
            });
          } catch { status.push({ key: 'soul', label: '灵魂矛盾', ready: false, autoFill: () => {} }); }
          // Characters
          try {
            const chars = JSON.parse(localStorage.getItem(`characters-soul-${novelId}`) || '[]');
            const charReady = chars.length > 0;
            status.push({
              key: 'chars', label: '角色设计', ready: charReady,
              autoFill: () => {
                if (charReady) return;
                const protagonist = { id: `char-${Date.now()}`, name: '主角', role: '主角', entrance: '故事开始时出现', signature: '独特的性格特征', voiceSample: '一句标志性台词', coreWound: '驱动一切的内在伤痕', speechPattern: '自然的说话方式', surfaceTrait: '表面性格', hiddenSelf: '隐藏的真实自我', arcStart: '故事开始时的状态', arcEnd: '故事结束时的状态' };
                localStorage.setItem(`characters-soul-${novelId}`, JSON.stringify([protagonist]));
                toast.success('已自动创建主角模板');
              }
            });
          } catch { status.push({ key: 'chars', label: '角色设计', ready: false, autoFill: () => {} }); }
          // World laws
          try {
            const laws = JSON.parse(localStorage.getItem(`world-laws-${novelId}`) || '{"laws":[]}');
            const lawReady = (laws.laws || []).length > 0;
            status.push({
              key: 'laws', label: '世界法则', ready: lawReady,
              autoFill: () => {
                if (lawReady) return;
                localStorage.setItem(`world-laws-${novelId}`, JSON.stringify({ laws: [{ rule: '每个选择都有相应的代价' }] }));
                toast.success('已自动设定世界法则');
              }
            });
          } catch { status.push({ key: 'laws', label: '世界法则', ready: false, autoFill: () => {} }); }

          const allReady = status.every(s => s.ready);
          const hasUnready = status.some(s => !s.ready);
          // When all ready, just show a subtle indicator
          if (allReady) {
            return <div className="mb-3 text-[10px] text-emerald-500 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> 全部配置就绪</div>;
          }
          return (
            <div className="mb-3 p-2 rounded-lg text-[10px] bg-paper border border-border">
              <div className="flex items-center gap-2 flex-wrap">
                {status.map(s => (
                  <label key={s.key} className={`flex items-center gap-1 cursor-pointer ${s.ready ? 'text-emerald-600 dark:text-emerald-400' : 'text-ink-subtle hover:text-ink'}`}
                    onClick={s.autoFill}>
                    {s.ready ? '✅' : <span className="w-3.5 h-3.5 rounded border border-border flex items-center justify-center text-[9px] hover:border-accent transition-colors">+</span>}
                    {s.label}
                  </label>
                ))}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <button onClick={() => { status.filter(s => !s.ready).forEach(s => s.autoFill()); }}
                  className="text-[9px] px-2 py-0.5 rounded bg-accent text-white hover:bg-accent-hover transition-colors">
                  ⚡ 全部补全
                </button>
                <span className="text-[9px] text-ink-subtle">或点击单个 ○ 选择性补全</span>
              </div>
            </div>
          );
        })()}

        {/* Context summary */}
        {fullContext && (
          <div className="mb-3 p-2.5 rounded-lg bg-accent-soft/10 border border-accent/5">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-ink-muted">注入上下文</span>
              <button onClick={() => setShowFullPrompt(!showFullPrompt)}
                className="text-[9px] text-accent hover:underline">
                {showFullPrompt ? '收起' : '查看详情'}
              </button>
            </div>
            <p className="text-[10px] text-ink-subtle leading-relaxed line-clamp-2">{fullContext}</p>
            {showFullPrompt && (
              <pre className="mt-2 p-2 rounded bg-ink text-white text-[9px] leading-relaxed whitespace-pre-wrap font-mono max-h-[200px] overflow-y-auto">
                {fullContext.replace(/ · /g, '\n')}
              </pre>
            )}
          </div>
        )}

        {/* Previous chapter hook context */}
        {prevHook && (
          <div className="mb-3 p-2.5 rounded-lg bg-amber-50/50 border border-amber-100 dark:bg-amber-900/10 dark:border-amber-900/30">
            <p className="text-[10px] text-amber-700 dark:text-amber-400 font-medium mb-0.5">📌 上章结尾钩子</p>
            <p className="text-[11px] text-ink-muted leading-relaxed line-clamp-2">{prevHook}</p>
          </div>
        )}

        {/* Quick suggestion chips */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {SUGGESTIONS.map(s => (
            <button key={s.label}
              onClick={() => setDirection(s.text)}
              className={`text-[11px] px-2.5 py-1 rounded-full border transition-all ${
                direction === s.text
                  ? 'bg-accent-soft text-accent border-accent/30'
                  : 'border-border text-ink-muted hover:text-ink hover:border-accent/20'
              }`}>
              {s.emoji} {s.label}
            </button>
          ))}
        </div>

        {/* Direction input */}
        {/* Memory injection — personal details */}
        <div className="mb-3 p-2.5 rounded-lg bg-paper border border-border">
          <p className="text-[10px] text-ink-muted mb-1">🧠 记忆注入（让 AI 写出只有你能写的东西）</p>
          <input
            value={memoryInput}
            onChange={e => setMemoryInput(e.target.value)}
            placeholder="一个真实的细节——你今天看到的、想到的、记得的。例如：地铁上一个老人用手帕擦扶手的动作 / 雨打在铁皮屋顶上的声音 / 小时候外婆做的红烧肉的味道"
            className="w-full text-xs rounded border border-input bg-card px-2 py-1.5 placeholder:text-ink-subtle focus:outline-none focus:border-accent transition-all" />
        </div>

        <textarea
          ref={inputRef}
          value={direction}
          onChange={e => setDirection(e.target.value)}
          placeholder="例如：主角在拍卖会上拍得神秘古鼎，但被宿敌盯上，散场后遭到伏击..."
          rows={3}
          className="w-full rounded-lg border border-input bg-paper text-ink text-sm px-3 py-2.5 resize-none
            placeholder:text-ink-subtle focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
            transition-all"
        />

        {/* Actions */}
        <div className="flex gap-2 mt-4 justify-between">
        {/* Model selector */}
        {availableModels.length > 1 && (
          <div className="mb-3 flex items-center gap-2">
            <span className="text-[10px] text-ink-muted shrink-0">模型</span>
            <select value={selectedModel} onChange={e => { setSelectedModel(e.target.value); localStorage.setItem('selected-model', e.target.value); }}
              className="flex-1 text-[10px] rounded border border-input bg-card text-ink px-2 py-1.5">
              {availableModels.map(m => (
                <option key={m.model} value={m.model}>{m.name} · {m.model}</option>
              ))}
            </select>
          </div>
        )}

        {/* Revision mode + Risk toggle */}
        <div className="flex gap-3 mb-3">
          <div className="flex-1 p-2.5 rounded-lg bg-paper border border-border">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-ink-muted">精修模式</span>
              <div className="flex gap-1">
                {[
                  { key: 'quick' as const, label: '快速', desc: '1次生成+评审' },
                  { key: 'deep' as const, label: '精雕', desc: '3轮定向修改' },
                ].map(m => (
                  <button key={m.key} onClick={() => setRevisionMode(m.key)}
                    className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                      revisionMode === m.key ? 'bg-accent text-white border-accent' : 'border-border text-ink-muted hover:text-ink'
                    }`}
                    title={m.desc}>{m.label}</button>
                ))}
              </div>
            </div>
            <p className="text-[9px] text-ink-subtle mt-1">
              {revisionMode === 'deep' ? '生成→评审节奏→修改→评审对话→修改→最终润色→质检' : '生成→评审→质检'}
            </p>
          </div>
          <label className="flex items-center gap-1.5 p-2.5 rounded-lg bg-paper border border-border cursor-pointer">
            <input type="checkbox" checked={creativeRisk} onChange={e => setCreativeRisk(e.target.checked)}
              className="w-3 h-3 rounded accent-accent" />
            <span className="text-[10px] text-ink-muted">打破常规</span>
          </label>
        </div>

        {/* Quality threshold */}
        <div className="mb-3 p-2.5 rounded-lg bg-paper border border-border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-ink-muted">最低质量要求</span>
            <span className={`text-[10px] font-semibold tabular-nums ${
              qualityThreshold >= 0.8 ? 'text-red-500' : qualityThreshold >= 0.65 ? 'text-amber-500' : 'text-emerald-500'
            }`}>
              {qualityThreshold.toFixed(2)}
              {qualityThreshold >= 0.8 ? ' (严格·慢)' : qualityThreshold >= 0.65 ? ' (标准)' : ' (宽松·快)'}
            </span>
          </div>
          <input type="range" min="0.4" max="0.9" step="0.05"
            value={qualityThreshold}
            onChange={e => { setQualityThreshold(Number(e.target.value)); localStorage.setItem('quality-threshold', e.target.value); }}
            className="w-full h-1.5 rounded-full appearance-none bg-border cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
              [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent [&::-webkit-slider-thumb]:cursor-pointer" />
          <div className="flex justify-between text-[8px] text-ink-subtle mt-0.5">
            <span>0.5 C级·宽松</span><span>0.7 B级·标准</span><span>0.8 A级·神作</span><span>0.9 S级</span>
          </div>
        </div>

        <div className="flex gap-2 justify-between">
          {prevHook && (
            <button onClick={() => {
              let d = `延续上章结尾：${prevHook.slice(0, 100)}`;
              if (memoryInput.trim()) d = `【记忆注入】${memoryInput.trim()}\n\n${d}`;
              onGenerate(d, qualityThreshold, revisionMode, selectedModel);
            }}
              className="text-xs px-3 py-2 rounded-md border border-accent/30 text-accent hover:bg-accent-soft transition-colors">
              ⚡ 直接续写
            </button>
          )}
          <div className="flex gap-2 ml-auto">
            <button onClick={onClose}
              className="px-4 py-2 text-sm rounded-md text-ink-muted hover:text-ink transition-colors">
              取消
            </button>
            <button onClick={() => {
              let finalDir = direction || '';
              if (memoryInput.trim()) finalDir = `【记忆注入】将以下真实细节融入本章：${memoryInput.trim()}。\n\n${finalDir}`;
              if (creativeRisk) finalDir = `【打破常规模式】不要写读者能预测到的内容。至少做一件让读者完全意想不到的事——但要合理。${finalDir}`;
              onGenerate(finalDir, qualityThreshold, revisionMode, selectedModel);
            }}
              className="px-4 py-2 text-sm rounded-md bg-accent text-white hover:bg-accent-hover transition-colors font-medium flex items-center gap-1.5">
              {revisionMode === 'deep' ? '💎' : '⚡'} {direction ? '按方向生成' : '自动构思'}
              <span className="text-[10px] opacity-60 font-mono">⌘↵</span>
            </button>
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
