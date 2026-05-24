import { useState, useEffect } from 'react';
import { toast } from 'sonner';

interface CharacterBlueprint {
  id: string;
  name: string;
  role: string;               // 主角/反派/导师/配角
  entrance: string;            // 出场方式——令人难忘的第一印象
  signature: string;           // 标志性特征——让人一眼认出的特质
  speechPattern: string;       // 说话方式——独特的语言风格
  coreWound: string;           // 核心创伤——驱动一切的内在伤痕
  surfaceTrait: string;        // 表面性格——别人眼中的他
  hiddenSelf: string;          // 隐藏自我——只有读者知道的真实
  arcStart: string;            // 弧线起点——故事开始时他是谁
  arcEnd: string;              // 弧线终点——故事结束时他变成谁
  obsession: string;           // 执念——他反复想/做/说的一件事
  contradiction: string;       // 内在矛盾——他身上的悖论
  voiceSample: string;         // 台词样本——一句最能体现他性格的话
  contrastWith: string;        // 与谁形成对比
  contrastHow: string;         // 如何形成对比
}

const DEFAULT_BLUEPRINT: CharacterBlueprint = {
  id: '',
  name: '',
  role: '配角',
  entrance: '',
  signature: '',
  speechPattern: '',
  coreWound: '',
  surfaceTrait: '',
  hiddenSelf: '',
  arcStart: '',
  arcEnd: '',
  obsession: '',
  contradiction: '',
  voiceSample: '',
  contrastWith: '',
  contrastHow: '',
};

function loadCharacters(novelId: string): CharacterBlueprint[] {
  try {
    const saved = localStorage.getItem(`characters-soul-${novelId}`);
    return saved ? JSON.parse(saved) : [];
  } catch { return []; }
}

function saveCharacters(novelId: string, chars: CharacterBlueprint[]) {
  localStorage.setItem(`characters-soul-${novelId}`, JSON.stringify(chars));
}

/* ─── Character Card ─── */
function CharacterCard({ char, onEdit, onDelete }: {
  char: CharacterBlueprint;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const roleColors: Record<string, string> = {
    '主角': 'border-l-accent bg-accent-soft/20',
    '反派': 'border-l-red-500 bg-red-50/30 dark:bg-red-950/20',
    '导师': 'border-l-emerald-500 bg-emerald-50/30 dark:bg-emerald-950/20',
    '配角': 'border-l-purple-500 bg-purple-50/30 dark:bg-purple-950/20',
  };
  const borderColor = roleColors[char.role] || 'border-l-border';

  return (
    <div className={`p-4 rounded-xl border border-border border-l-[3px] ${borderColor} bg-card hover:shadow-sm transition-all group`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-heading text-base font-bold text-ink">{char.name}</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
              char.role === '主角' ? 'bg-accent text-white' :
              char.role === '反派' ? 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' :
              char.role === '导师' ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400' :
              'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400'
            }`}>{char.role}</span>
          </div>
          {char.voiceSample && (
            <p className="text-xs text-ink-muted italic mt-1.5 leading-relaxed">「{char.voiceSample}」</p>
          )}
        </div>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={onEdit} className="text-[10px] text-ink-muted hover:text-accent px-1">✎</button>
          <button onClick={onDelete} className="text-[10px] text-ink-muted hover:text-red-500 px-1">🗑</button>
        </div>
      </div>

      {/* Core identity */}
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        {char.signature && (
          <div className="p-2 rounded-lg bg-paper">
            <span className="text-ink-subtle">标志</span>
            <p className="text-ink mt-0.5">{char.signature}</p>
          </div>
        )}
        {char.coreWound && (
          <div className="p-2 rounded-lg bg-paper">
            <span className="text-ink-subtle">创伤</span>
            <p className="text-ink mt-0.5">{char.coreWound}</p>
          </div>
        )}
        {char.surfaceTrait && char.hiddenSelf && (
          <div className="p-2 rounded-lg bg-paper col-span-2">
            <span className="text-ink-subtle">矛盾</span>
            <p className="text-ink mt-0.5">
              <span className="text-ink-muted">表面</span> {char.surfaceTrait}
              <span className="text-ink-subtle mx-1">·</span>
              <span className="text-ink-muted">内在</span> {char.hiddenSelf}
            </p>
          </div>
        )}
        {char.entrance && (
          <div className="p-2 rounded-lg bg-paper col-span-2">
            <span className="text-ink-subtle">出场</span>
            <p className="text-ink mt-0.5">{char.entrance}</p>
          </div>
        )}
      </div>

      {/* Arc */}
      {char.arcStart && char.arcEnd && (
        <div className="mt-2 flex items-center gap-2 text-[10px]">
          <span className="text-ink-muted shrink-0">{char.arcStart}</span>
          <div className="flex-1 h-0.5 bg-gradient-to-r from-border via-accent to-border rounded" />
          <span className="text-ink-muted shrink-0">{char.arcEnd}</span>
        </div>
      )}

      {/* Contrast */}
      {char.contrastWith && (
        <p className="text-[10px] text-ink-subtle mt-2">
          ⚡ 与 <span className="text-ink font-medium">{char.contrastWith}</span> 形成对比：{char.contrastHow}
        </p>
      )}
    </div>
  );
}

/* ─── Character Editor Form ─── */
function CharacterForm({ initial, onSave, onCancel }: {
  initial: CharacterBlueprint;
  onSave: (c: CharacterBlueprint) => void;
  onCancel: () => void;
}) {
  const [c, setC] = useState<CharacterBlueprint>(initial);

  function field(key: keyof CharacterBlueprint, label: string, placeholder: string, rows = 1) {
    const Comp = rows > 1 ? 'textarea' : 'input';
    return (
      <div>
        <label className="text-[10px] font-semibold text-ink-muted uppercase tracking-wide">{label}</label>
        <Comp
          value={c[key] as string}
          onChange={e => setC({ ...c, [key]: e.target.value })}
          placeholder={placeholder}
          rows={rows > 1 ? rows : undefined}
          className={`w-full mt-1 rounded-lg border border-input bg-card text-ink text-xs px-3 py-2
            placeholder:text-ink-subtle focus:outline-none focus:border-accent transition-all
            ${rows > 1 ? 'resize-none' : ''}`}
        />
      </div>
    );
  }

  return (
    <div className="p-4 bg-paper border border-accent/20 rounded-xl space-y-3 mb-4 animate-[fadeSlideIn_0.2s_ease-out]">
      <div className="flex items-center justify-between">
        <h4 className="font-heading text-sm font-semibold text-ink">{c.name || '新角色'}</h4>
        <select value={c.role} onChange={e => setC({ ...c, role: e.target.value })}
          className="text-xs rounded border border-input bg-card px-2 py-1">
          {['主角','反派','导师','配角'].map(r => <option key={r}>{r}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {field('name', '姓名', '角色名')}
        {field('signature', '标志特征', '如：黄蓉的机智·杨过的独臂·郭靖的憨厚')}
      </div>

      {field('entrance', '出场方式 ★', '令人难忘的第一印象。如：偷鸡烤鸡的乞丐少女 / 抱着母鸡的脏孩子', 2)}
      {field('voiceSample', '台词样本 ★', '一句最能体现他性格的话。如："靖哥哥" / "我偏要勉强"', 2)}
      {field('speechPattern', '说话方式', '如：机智调侃 / 简短冷语 / 憨厚直白 / 阴阳怪气')}

      <div className="grid grid-cols-2 gap-3">
        {field('surfaceTrait', '表面性格', '别人眼中的他')}
        {field('hiddenSelf', '隐藏自我', '只有读者知道的真实')}
      </div>

      {field('coreWound', '核心创伤 ★', '驱动一切的内在伤痕。如：杨过的父亲之谜 / 张无忌的父母双亡', 2)}
      {field('obsession', '执念', '他反复做/想/说的一件事。如：周伯通的武痴 / 段誉的痴情')}

      <div className="grid grid-cols-2 gap-3">
        {field('arcStart', '弧线起点', '故事开始时他是谁')}
        {field('arcEnd', '弧线终点', '故事结束时他变成谁')}
      </div>

      <div className="grid grid-cols-2 gap-3">
        {field('contrastWith', '对比角色', '与哪个角色形成化学反应的对比')}
        {field('contrastHow', '对比方式', '如：杨过的狂 vs 郭靖的稳 / 黄蓉的巧 vs 郭靖的拙')}
      </div>

      <div className="flex gap-2">
        <button onClick={() => onSave(c)}
          className="px-4 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors text-xs font-medium">
          保存角色
        </button>
        <button onClick={onCancel}
          className="px-4 py-2 rounded-lg border border-border text-ink-muted hover:text-ink transition-colors text-xs">
          取消
        </button>
      </div>
    </div>
  );
}

/* ─── Main Component ─── */
export function CharacterSoul({ novelId }: { novelId: string }) {
  const [characters, setCharacters] = useState<CharacterBlueprint[]>(() => loadCharacters(novelId));
  const [editing, setEditing] = useState<CharacterBlueprint | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => { saveCharacters(novelId, characters); }, [characters, novelId]);

  function handleSave(c: CharacterBlueprint) {
    if (!c.name.trim()) { toast.error('角色名不能为空'); return; }
    const id = c.id || `char-${Date.now()}`;
    const updated = { ...c, id };
    setCharacters(prev => {
      const idx = prev.findIndex(x => x.id === id);
      if (idx >= 0) { const next = [...prev]; next[idx] = updated; return next; }
      return [...prev, updated];
    });
    setEditing(null);
    setShowForm(false);
    toast.success(`角色「${c.name}」已保存`);
  }

  function handleDelete(id: string) {
    setCharacters(prev => prev.filter(c => c.id !== id));
    toast.success('角色已删除');
  }

  // Character web insights
  const pairs: { a: CharacterBlueprint; b: CharacterBlueprint; insight: string }[] = [];
  for (let i = 0; i < characters.length; i++) {
    for (let j = i + 1; j < characters.length; j++) {
      const a = characters[i], b = characters[j];
      let insight = '';
      if (a.surfaceTrait && b.surfaceTrait && a.surfaceTrait !== b.surfaceTrait) {
        insight = `${a.name}的${a.surfaceTrait} vs ${b.name}的${b.surfaceTrait}——性格反差产生戏剧张力`;
      }
      if (a.role === '主角' && b.role === '反派') {
        insight = `${a.name}(主角)与${b.name}(反派)：${a.coreWound ? a.name + '的' + a.coreWound : ''} vs ${b.obsession ? b.name + '的执念：' + b.obsession : ''}`;
      }
      if (insight) pairs.push({ a, b, insight });
    }
  }

  return (
    <div className="p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-heading text-base font-semibold text-ink">👥 角色灵魂</h3>
          <p className="text-[11px] text-ink-muted">
            {characters.length === 0 ? '金庸的人物为什么难忘？因为每个人都有自己的出场·标志·创伤·弧线' : `${characters.length} 个角色已设计`}
          </p>
        </div>
        <button onClick={() => { setEditing({ ...DEFAULT_BLUEPRINT }); setShowForm(true); }}
          className="text-xs px-3 py-1.5 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors">
          + 设计角色
        </button>
      </div>

      {/* Character grid */}
      {characters.length > 0 ? (
        <div className="space-y-3 mb-4">
          {characters.map(c => (
            <CharacterCard key={c.id} char={c}
              onEdit={() => { setEditing(c); setShowForm(true); }}
              onDelete={() => handleDelete(c.id)} />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 border border-dashed border-border rounded-lg mb-4">
          <p className="text-sm text-ink-muted mb-1">还没有设计角色</p>
          <p className="text-xs text-ink-subtle">点击「+ 设计角色」，像金庸一样为每个角色注入灵魂</p>
        </div>
      )}

      {/* Edit form */}
      {showForm && editing && (
        <CharacterForm
          initial={editing}
          onSave={handleSave}
          onCancel={() => { setEditing(null); setShowForm(false); }}
        />
      )}

      {/* Character web insights */}
      {pairs.length > 0 && (
        <div className="pt-3 border-t border-border">
          <p className="text-[10px] font-semibold text-ink-muted uppercase tracking-wide mb-2">🕸️ 角色化学反应</p>
          <div className="space-y-1.5">
            {pairs.slice(0, 4).map((p, i) => (
              <div key={i} className="p-2 rounded-lg bg-accent-soft/20 border border-accent/5 text-[11px] text-ink leading-relaxed">
                {p.insight}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Jin Yong checklist */}
      {characters.length > 0 && (() => {
        const missing = characters.filter(c => !c.entrance || !c.voiceSample || !c.coreWound);
        const complete = characters.filter(c => c.entrance && c.voiceSample && c.coreWound);
        if (missing.length === 0) return (
          <div className="pt-3 border-t border-border">
            <p className="text-[10px] text-emerald-500">✅ 所有角色都拥有出场·台词·创伤——金庸级角色设计完成</p>
          </div>
        );
        return (
          <div className="pt-3 border-t border-border">
            <p className="text-[10px] text-amber-500">
              ⚠️ {missing.length} 个角色缺少关键要素（出场/台词/创伤至少一项）：
              <span className="ml-1">{missing.map(c => c.name || '未命名').join('、')}</span>
            </p>
            <p className="text-[9px] text-ink-subtle mt-1">
              金庸的每个角色都有令人难忘的出场方式、一句标志性台词、一个驱动一切的核心创伤。{complete.length}个角色已达标。
            </p>
          </div>
        );
      })()}

      {/* Design principles */}
      <div className="mt-4 pt-3 border-t border-border grid grid-cols-3 gap-2 text-[9px] text-ink-subtle">
        <div>
          <span className="text-ink font-medium">出场定终身</span>
          <p>金庸：黄蓉出场是乞丐少女，这个印象贯穿全书</p>
        </div>
        <div>
          <span className="text-ink font-medium">一句入魂</span>
          <p>好的台词胜过千字描写。"靖哥哥"三个字就是黄蓉</p>
        </div>
        <div>
          <span className="text-ink font-medium">创伤驱动</span>
          <p>杨过一生都在解父亲之谜。人物的核心动机必须来自伤痛</p>
        </div>
      </div>
    </div>
  );
}
