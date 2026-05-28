import { useState } from 'react';
import type { ChapterMeta } from 'src/types';

interface DNAProfile {
  pacing: number;       // 节奏快慢
  dialogue: number;     // 对话密度
  description: number;  // 描写密度
  action: number;       // 动作强度
  emotion: number;      // 情感深度
  hook: number;         // 钩子强度
}

function analyzeDNA(ch: ChapterMeta, content?: string): DNAProfile {
  const text = content || ch.summary || '';
  const len = text.length || 1;

  // Pacing: shorter paragraphs = faster pace
  const paragraphs = text.split('\n').filter(l => l.trim().length > 0);
  const avgParaLen = paragraphs.reduce((s, p) => s + p.length, 0) / Math.max(1, paragraphs.length);
  const pacing = Math.min(100, Math.round((1 - Math.min(1, avgParaLen / 200)) * 80 + 20));

  // Dialogue density
  const dialogueMarkers = (text.match(/[「「""''“”说问道答讲喊叫骂吵]/g) || []).length;
  const dialogue = Math.min(100, Math.round((dialogueMarkers / Math.min(len, 500)) * 100 * 1.5));

  // Description density (adjectives, scenery words)
  const descWords = (text.match(/[的得地着]{1}|风景|天空|房间|街道|山|水|树|花|光|影|红|蓝|绿|白|黑|大|小|高|低]/g) || []).length;
  const description = Math.min(100, Math.round((descWords / Math.min(len, 300)) * 100));

  // Action intensity (verbs, fight words)
  const actionWords = (text.match(/[打攻击杀砍刺射爆炸飞跑跳冲撞推拉拽摔]/g) || []).length;
  const action = Math.min(100, Math.round((actionWords / Math.min(len, 300)) * 100 * 1.8));

  // Emotional depth from quality score + length
  const emotion = ch.quality_score ? Math.round(ch.quality_score * 100) : 50;

  // Hook strength
  const hook = ch.ending_hook ? (ch.ending_hook.length > 10 ? 80 : 50) : 30;

  return { pacing, dialogue, description, action, emotion, hook };
}

function RadarChart({ a, b }: { a: DNAProfile; b?: DNAProfile; labelA: string; labelB?: string }) {
  const dims: { key: keyof DNAProfile; label: string }[] = [
    { key: 'pacing', label: '节奏' },
    { key: 'dialogue', label: '对话' },
    { key: 'description', label: '描写' },
    { key: 'action', label: '动作' },
    { key: 'emotion', label: '情感' },
    { key: 'hook', label: '钩子' },
  ];

  const cx = 100, cy = 100, r = 75;
  const angle = (i: number) => (Math.PI * 2 * i) / dims.length - Math.PI / 2;

  function point(val: number, i: number) {
    const a = angle(i);
    return { x: cx + (val / 100) * r * Math.cos(a), y: cy + (val / 100) * r * Math.sin(a) };
  }

  const pathA = dims.map((d, i) => {
    const p = point(a[d.key], i);
    return `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`;
  }).join(' ') + ' Z';

  const pathB = b ? dims.map((d, i) => {
    const p = point(b[d.key], i);
    return `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`;
  }).join(' ') + ' Z' : '';

  return (
    <svg viewBox="0 0 200 200" className="w-full max-w-[260px]">
      {/* Grid */}
      {[25, 50, 75, 100].map(v => {
        const pts = dims.map((_, i) => {
          const p = point(v, i);
          return `${p.x},${p.y}`;
        }).join(' ');
        return <polygon key={v} points={pts} fill="none" stroke="var(--color-border)" strokeWidth="0.5" />;
      })}
      {/* Axes */}
      {dims.map((_, i) => {
        const p = point(100, i);
        return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="var(--color-border)" strokeWidth="0.5" />;
      })}
      {/* Profile A */}
      <path d={pathA} fill="var(--color-accent)" fillOpacity="0.15" stroke="var(--color-accent)" strokeWidth="1.5" />
      {/* Profile B */}
      {b && <path d={pathB} fill="#34D399" fillOpacity="0.15" stroke="#34D399" strokeWidth="1.5" strokeDasharray="4,2" />}
      {/* Labels */}
      {dims.map((d, i) => {
        const p = point(110, i);
        return <text key={i} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="middle"
          fill="var(--color-ink-subtle)" fontSize="8">{d.label}</text>;
      })}
    </svg>
  );
}

export function ChapterDNA({ chapters, novelId }: { chapters?: ChapterMeta[]; novelId: string }) {
  const [leftCh, setLeftCh] = useState<number | null>(null);
  const [rightCh, setRightCh] = useState<number | null>(null);
  const [leftContent, setLeftContent] = useState('');
  const [rightContent, setRightContent] = useState('');

  const writable = (chapters || []).filter(c => c.word_count > 0);
  if (writable.length < 2) return null;

  const leftDNA = leftCh ? analyzeDNA(writable.find(c => c.number === leftCh)!, leftContent) : null;
  const rightDNA = rightCh ? analyzeDNA(writable.find(c => c.number === rightCh)!, rightContent) : null;

  async function selectChapter(num: number, side: 'left' | 'right') {
    if (side === 'left') setLeftCh(num); else setRightCh(num);
    try {
      const data = await fetch(`/api/novels/${novelId}/chapters/${num}`).then(r => r.json());
      if (side === 'left') setLeftContent(data.content || '');
      else setRightContent(data.content || '');
    } catch { /* ignore */ }
  }

  const leftLabel = leftCh ? `第${leftCh}章` : '';
  const rightLabel = rightCh ? `第${rightCh}章` : '';

  return (
    <div className="p-4 bg-card border border-border rounded-xl">
      <h3 className="font-heading text-base font-semibold text-ink mb-3">🧬 章节 DNA 对比</h3>
      <p className="text-[11px] text-ink-muted mb-3">选择两章，对比节奏/对话/描写/动作/情感/钩子六维特征</p>

      <div className="flex gap-3 mb-3">
        <select value={leftCh || ''} onChange={e => selectChapter(parseInt(e.target.value), 'left')}
          className="flex-1 text-xs rounded border border-input bg-card px-2 py-1.5">
          <option value="">选择章节 A</option>
          {writable.slice(-20).map(c => <option key={c.number} value={c.number}>第{c.number}章 {c.title}</option>)}
        </select>
        <select value={rightCh || ''} onChange={e => selectChapter(parseInt(e.target.value), 'right')}
          className="flex-1 text-xs rounded border border-input bg-card px-2 py-1.5">
          <option value="">选择章节 B</option>
          {writable.slice(-20).map(c => <option key={c.number} value={c.number}>第{c.number}章 {c.title}</option>)}
        </select>
      </div>

      {(leftDNA || rightDNA) && (
        <div className="flex items-start gap-4">
          <RadarChart a={leftDNA || rightDNA!} b={rightDNA || undefined} labelA={leftLabel} labelB={rightLabel} />
          <div className="flex-1 space-y-1 text-[10px]">
            <div className="flex items-center gap-2">
              <span className="w-3 h-0.5 rounded bg-accent inline-block" />
              <span className="text-ink-muted">{leftLabel || '章节A'}</span>
            </div>
            {rightDNA && (
              <div className="flex items-center gap-2">
                <span className="w-3 h-0.5 rounded bg-emerald-400 inline-block" style={{ borderTop: '2px dotted #34D399' }} />
                <span className="text-ink-muted">{rightLabel || '章节B'}</span>
              </div>
            )}
            {leftDNA && rightDNA && (
              <div className="mt-2 pt-2 border-t border-border space-y-0.5">
                {(['pacing', 'dialogue', 'action', 'emotion'] as const).map(k => {
                  const diff = rightDNA[k] - leftDNA[k];
                  const labels: Record<string, string> = { pacing: '节奏', dialogue: '对话', action: '动作', emotion: '情感' };
                  return (
                    <div key={k} className="flex justify-between">
                      <span className="text-ink-muted">{labels[k]}</span>
                      <span className={diff > 10 ? 'text-emerald-500' : diff < -10 ? 'text-amber-500' : 'text-ink-subtle'}>
                        {diff > 0 ? '↑' : diff < 0 ? '↓' : '→'} {Math.abs(diff)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
