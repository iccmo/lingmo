import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { NovelCard } from 'src/components/novels/NovelCard';
import { NovelCompare } from 'src/components/novels/NovelCompare';
import { WritingCalendar } from 'src/components/novels/WritingCalendar';
import { DailyPrompt } from 'src/components/novels/DailyPrompt';
import { WritingGoal } from 'src/components/novels/WritingGoal';
import { Button } from 'src/components/ui/button';
import { Input } from 'src/components/ui/input';
import { Textarea } from 'src/components/ui/textarea';
import { Card, CardContent } from 'src/components/ui/card';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelSummary, SystemStatus } from 'src/types';

interface LastRead {
  novelId: string;
  novelTitle: string;
  chapter: number;
  title: string;
  timestamp: number;
}

/* ─── Writing trend bar chart ─── */
function WritingTrend() {
  const dayNames = ['日', '一', '二', '三', '四', '五', '六'];
  const days: { date: string; dayOfWeek: string; words: number; isToday: boolean }[] = [];

  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = `daily-words-${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const words = parseInt(localStorage.getItem(key) || '0', 10) || 0;
    const today = new Date();
    days.push({
      date: key,
      dayOfWeek: dayNames[d.getDay()],
      words,
      isToday: d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth() && d.getDate() === today.getDate(),
    });
  }

  const maxWords = Math.max(...days.map(d => d.words), 1);
  const total = days.reduce((s, d) => s + d.words, 0);

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
          📈 写作趋势
        </h3>
        <span className="text-[10px] text-ink-subtle">{total.toLocaleString()} 字 / 近7日</span>
      </div>
      <div className="flex items-end gap-1.5 h-36 p-4 pt-7 pb-5 bg-card border border-border rounded-xl">
        {days.map((d, i) => {
          const heightPct = maxWords > 0 ? (d.words / maxWords) * 100 : 0;
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-1 group min-w-0">
              {/* Word count tooltip on hover */}
              <span
                className="text-[10px] font-medium text-accent opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap"
              >
                {d.words.toLocaleString()}字
              </span>
              {/* Bar */}
              <div
                className={`w-full rounded-t-md transition-all duration-300 group-hover:brightness-110 ${
                  d.isToday ? 'ring-1 ring-accent/30' : ''
                }`}
                style={{
                  height: `${Math.max(heightPct, 2)}%`,
                  minHeight: '4px',
                  background: d.words > 0
                    ? `linear-gradient(180deg, var(--color-accent), ${d.isToday ? 'var(--color-accent-hover)' : 'var(--color-accent)'})`
                    : 'var(--color-border)',
                  opacity: d.words > 0 ? 1 : 0.4,
                }}
                title={`${d.words.toLocaleString()} 字`}
              />
              {/* Day label */}
              <span
                className={`text-[10px] mt-1 whitespace-nowrap ${
                  d.isToday ? 'text-accent font-semibold' : 'text-ink-muted'
                }`}
              >
                {d.isToday ? '今' : `周${d.dayOfWeek}`}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const [novels, setNovels] = useState<NovelSummary[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [genreFilter, setGenreFilter] = useState('');
  const [sortBy, setSortBy] = useState<'words' | 'chapters' | 'latest'>('latest');
  const [generatingIds, setGeneratingIds] = useState<Set<string>>(new Set());
  const [showCompare, setShowCompare] = useState(false);
  const [costSummary, setCostSummary] = useState<{ total_cost: number; total_tokens: number; total_calls: number; by_novel: { novel_id: string; title: string; cost: number; chapters: number }[]; by_model: { model: string; calls: number; total_cost: number }[] } | null>(null);
  const [showCostBreakdown, setShowCostBreakdown] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importTitle, setImportTitle] = useState('');
  const [importGenre, setImportGenre] = useState('玄幻');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [backupStatus, setBackupStatus] = useState<{ configured: boolean; last_backup: string | null; last_backup_key: string | null; last_backup_size: number | null } | null>(null);

  useEffect(() => {
    Promise.all([api.novels.list(), api.status(), fetch('/api/providers').then(r => r.json()), api.costs.summary().catch(() => null), fetch('/api/backup/status').then(r => r.json()).catch(() => null)])
      .then(([n, s, providers, costs, backup]) => {
        setNovels(n); setStatus(s);
        setCostSummary(costs);
        setBackupStatus(backup);
        const hasKey = providers?.some((p: {api_key: string}) => p.api_key !== '');
        if (!hasKey) toast.info('💡 前往设置页配置 API Key 即可开始创作');
      })
      .catch(e => toast.error('加载失败: ' + (e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  async function handleDemo() {
    toast.info('正在创建 Demo 小说...');
    try {
      const r = await fetch('/api/demo', { method: 'POST' });
      const d = await r.json();
      toast.success('Demo 小说已创建，正在生成第一章...');
      setTimeout(() => navigate(`/novels/${d.novel_id}`), 2000);
    } catch (e: unknown) { toast.error('创建失败: ' + (e as Error).message); }
  }

  async function handleImport(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!importFile || !importTitle.trim()) {
      toast.error('请填写书名并选择文件');
      return;
    }
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append('title', importTitle.trim());
      fd.append('genre', importGenre);
      fd.append('file', importFile);

      const r = await fetch('/api/novels/import', {
        method: 'POST',
        body: fd,
      });
      if (!r.ok) {
        const errText = await r.text();
        throw new Error(errText.slice(0, 200));
      }
      const d = await r.json();
      toast.success(`导入成功: "${d.title}" — ${d.chapters_imported} 章, ${d.total_words.toLocaleString()} 字`);
      setShowImport(false);
      setImportFile(null);
      setImportTitle('');
      // Refresh novel list
      const [n, s] = await Promise.all([api.novels.list(), api.status()]);
      setNovels(n); setStatus(s);
    } catch (e: unknown) {
      toast.error('导入失败: ' + (e as Error).message);
    } finally {
      setImporting(false);
    }
  }

  async function handleCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const id = (fd.get('id') as string).trim();
    const title = (fd.get('title') as string).trim();
    if (!id || !title) { toast.error('请填写 ID 和书名'); return; }
    try {
      await api.novels.create({
        id, title,
        synopsis: (fd.get('synopsis') as string).trim(),
        genre: (fd.get('genre') as string).trim() || '玄幻',
      });
      toast.success(`"${title}" 创建成功`);
      setShowForm(false);
      const [n, s] = await Promise.all([api.novels.list(), api.status()]);
      setNovels(n); setStatus(s);
    } catch (e: unknown) {
      toast.error('创建失败: ' + (e as Error).message);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-7 w-32" />
        <div className="skeleton h-5 w-48" />
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4 mt-6">
          {[1,2,3].map(i => <div key={i} className="skeleton h-40 rounded-lg" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="page-enter">
      <div className="mb-8">
        <h1 className="font-heading text-[28px] font-semibold text-ink leading-tight">工作台</h1>
        <p className="text-sm text-ink-muted mt-1">管理你的 AI 小说创作</p>
      </div>

      {/* Writing Goal Tracker — most important daily task */}
      <WritingGoal />

      {/* Daily writing prompt */}
      <DailyPrompt />

      {/* Writing Calendar */}
      {novels.length > 0 && (
        <div className="mb-6">
          <WritingCalendar />
        </div>
      )}

      {/* Getting Started Checklist */}
      {novels.length <= 2 && (
        <div className="mb-6 p-4 bg-gradient-to-r from-accent-soft/30 to-transparent border border-accent/10 rounded-xl">
          <h3 className="font-heading text-sm font-semibold text-ink mb-3">🚀 快速开始</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
            {[
              { done: !!status && novels.some(n => n.total_chapters > 0), label: '创建第一部小说', tip: '点击「+ 创建新小说」' },
              { done: (() => { try { return localStorage.getItem('app-password') !== null; } catch { return false; } })(), label: '设置访问密码', tip: '在展示页点击进入后台时设置' },
              { done: (() => { try { const p = JSON.parse(localStorage.getItem('starred-novels') || '[]'); return p.length > 0; } catch { return false; } })(), label: '收藏你最看重的小说', tip: '点击卡片上的 ☆ 收藏' },
            ].map((item, i) => (
              <div key={i} className={`flex items-center gap-2 p-2.5 rounded-lg ${item.done ? 'bg-emerald-50/50 dark:bg-emerald-950/20' : 'bg-paper'}`}>
                <span>{item.done ? '✅' : '○'}</span>
                <div>
                  <span className={item.done ? 'text-ink line-through opacity-60' : 'text-ink font-medium'}>{item.label}</span>
                  {!item.done && <span className="text-ink-subtle block text-[10px]">{item.tip}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Writing Trend Chart */}
      {novels.length > 0 && <WritingTrend />}

      {/* Stats row */}
      {status && (
        <div className="flex gap-8 mb-6 flex-wrap">
          {[
            [status.novels_count, '部小说'],
            [status.total_chapters, '总章节'],
            [status.total_words.toLocaleString(), '总字数'],
          ].map(([v, l]) => (
            <div key={l as string} className="bg-paper border border-border rounded-lg px-5 py-3 min-w-[100px]">
              <div className="font-heading text-[28px] font-semibold text-ink leading-none">{String(v)}</div>
              <div className="text-[11px] text-ink-muted mt-1">{l}</div>
            </div>
          ))}
          {novels.length > 0 && (
            <div className="bg-paper border border-border rounded-lg px-5 py-3 min-w-[100px]">
              <div className="font-heading text-[28px] font-semibold text-emerald-500 leading-none">
                {novels.filter(n=>n.total_chapters>0).length}
              </div>
              <div className="text-[11px] text-ink-muted mt-1">有内容的书</div>
            </div>
          )}
          {costSummary && costSummary.total_cost > 0 && (
            <div className="relative">
              <button
                onClick={() => setShowCostBreakdown(!showCostBreakdown)}
                className="bg-paper border border-border rounded-lg px-5 py-3 min-w-[100px] hover:border-amber-300 transition-colors cursor-pointer text-left w-full"
              >
                <div className="font-heading text-[28px] font-semibold text-amber-600 leading-none">
                  ${costSummary.total_cost.toFixed(4)}
                </div>
                <div className="text-[11px] text-ink-muted mt-1">API 花费</div>
              </button>
              {showCostBreakdown && (
                <div className="absolute top-full mt-2 right-0 z-20 bg-card border border-border rounded-xl shadow-xl p-4 min-w-[260px] animate-[fadeSlideIn_0.15s_ease-out]"
                  onClick={e => e.stopPropagation()}>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-xs font-semibold text-ink">💰 花费明细</h4>
                    <button onClick={() => setShowCostBreakdown(false)} className="text-[10px] text-ink-muted hover:text-ink">✕</button>
                  </div>
                  {costSummary.by_novel && costSummary.by_novel.length > 0 && (
                    <div className="mb-3">
                      <p className="text-[10px] font-medium text-ink-muted uppercase tracking-wide mb-1.5">按小说</p>
                      {costSummary.by_novel.map(n => (
                        <div key={n.novel_id} className="flex items-center justify-between py-1 text-[11px]">
                          <span className="text-ink truncate max-w-[150px]">{n.title || n.novel_id}</span>
                          <span className="text-amber-600 font-mono">${n.cost.toFixed(4)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {costSummary.by_model && costSummary.by_model.length > 0 && (
                    <div>
                      <p className="text-[10px] font-medium text-ink-muted uppercase tracking-wide mb-1.5">按模型</p>
                      {costSummary.by_model.map(m => (
                        <div key={m.model} className="flex items-center justify-between py-1 text-[11px]">
                          <span className="text-ink">{m.model}</span>
                          <span className="text-amber-600 font-mono">${m.total_cost.toFixed(4)} ({m.calls}次)</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="border-t border-border mt-3 pt-2 text-[10px] text-ink-subtle">
                    总调用 {costSummary.total_calls} 次 · 总 Token {costSummary.total_tokens.toLocaleString()}
                  </div>
                </div>
              )}
            </div>
          )}
          {/* Cloud backup status */}
          {backupStatus && (
            <div
              className="bg-paper border border-border rounded-lg px-5 py-3 min-w-[100px]"
              title={backupStatus.configured
                ? `最近备份: ${backupStatus.last_backup || '无'}`
                : '未配置云备份（设置 S3_* 环境变量启用）'}
            >
              <div className="font-heading text-[15px] font-semibold text-sky-500 leading-none">
                ☁️ 云备份
              </div>
              <div className="text-[11px] text-ink-muted mt-1">
                {backupStatus.configured
                  ? backupStatus.last_backup
                    ? `上次: ${new Date(backupStatus.last_backup).toLocaleDateString('zh-CN')}`
                    : '已配置 · 无记录'
                  : '未配置'}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <select value={genreFilter} onChange={e => setGenreFilter(e.target.value)}
          className="text-xs rounded-md border border-input bg-card text-ink px-2 py-1.5">
          <option value="">全部题材</option>
          {['玄幻','仙侠','武侠','都市','官场','悬疑','灵异','科幻','末世','游戏','历史','系统流','无限流','奇幻','二次元','轻小说','种田','体育','军事','现代言情','古代言情','纯爱','同人'].map(g => <option key={g} value={g}>{g}</option>)}
        </select>
        <select value={sortBy} onChange={e => setSortBy(e.target.value as 'words'|'chapters'|'latest')}
          className="text-xs rounded-md border border-input bg-card text-ink px-2 py-1.5">
          <option value="latest">最近更新</option>
          <option value="words">按字数</option>
          <option value="chapters">按章节数</option>
        </select>
      </div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-heading text-xl font-semibold text-ink">我的小说</h2>
        <div className="flex gap-2">
          <Button size="sm" className="bg-accent hover:bg-accent-hover" onClick={() => setShowForm(!showForm)}>+ 创建新小说</Button>
          <Button size="sm" variant="outline" onClick={() => setShowImport(true)}>📥 导入</Button>
          {novels.length >= 2 && (
            <Button size="sm" variant="outline" onClick={() => setShowCompare(true)}>📊 对比</Button>
          )}
          <Button size="sm" variant="outline" onClick={handleDemo}>⚡ 一键 Demo</Button>
        </div>
      </div>

      {showForm && (
        <Card className="mb-6 border-border">
          <CardContent className="p-5">
            {/* Quick Templates */}
            <div className="flex gap-2 mb-4">
              {['玄幻','悬疑','都市','科幻','历史','官场'].map(g => (
                <button key={g} type="button" className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors"
                  onClick={() => {
                    const f = document.querySelector('form') as HTMLFormElement;
                    if(f) {
                      (f.querySelector('input[name=id]') as HTMLInputElement).value = g.toLowerCase()+'-'+Date.now().toString(36);
                      (f.querySelector('input[name=title]') as HTMLInputElement).value = '未命名·'+g;
                      (f.querySelector('select') as HTMLSelectElement).value = g;
                    }
                  }}>{g}</button>
              ))}
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">小说 ID</label>
                  <Input name="id" placeholder="例如: immortal-path" className="mt-1.5" required />
                </div>
                <div className="w-32">
                  <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">题材</label>
                  <select name="genre" defaultValue="玄幻" className="w-full mt-1.5 rounded-md border border-input bg-card text-ink text-sm px-3 py-2">
                    {['玄幻','悬疑','都市','科幻','历史','官场','系统流','女频'].map(g=><option key={g}>{g}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">书名</label>
                <Input name="title" placeholder="例如: 修仙从炼丹开始" className="mt-1.5" required />
              </div>
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">一句话简介</label>
                <Textarea name="synopsis" placeholder="故事一句话概要..." rows={2} className="mt-1.5" />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" className="bg-accent hover:bg-accent-hover">✓ 创建</Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setShowForm(false)}>取消</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Recently viewed */}
      {(() => {
        try {
          const recent: string[] = JSON.parse(localStorage.getItem('recent-novels') || '[]');
          const recentNovels = recent.map(id => novels.find(n => n.id === id)).filter(Boolean) as NovelSummary[];
          if (recentNovels.length < 2) return null;
          return (
            <div className="mb-6">
              <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide mb-2">最近访问</h3>
              <div className="flex gap-2 flex-wrap">
                {recentNovels.slice(0, 5).map(n => (
                  <button key={n.id} onClick={() => navigate(`/novels/${n.id}`)}
                    className="text-xs px-3 py-1.5 rounded-full border border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-colors">
                    📖 {n.title}
                  </button>
                ))}
              </div>
            </div>
          );
        } catch { return null; }
      })()}

      {/* Starred filter */}
      <div className="flex items-center gap-2 mb-4">
        {(() => {
          try {
            const starred: string[] = JSON.parse(localStorage.getItem('starred-novels') || '[]');
            const hasStarred = novels.some(n => starred.includes(n.id));
            if (!hasStarred) return null;
            return (
              <button
                onClick={() => {
                }}
                className="text-[11px] px-2 py-1 rounded border border-amber-200 text-amber-600 hover:bg-amber-50 dark:border-amber-800 dark:text-amber-400 transition-colors">
                ⭐ 已收藏 ({starred.filter(id => novels.some(n => n.id === id)).length})
              </button>
            );
          } catch { return null; }
        })()}
      </div>

      {/* Continue last reading — grouped with novel cards */}
      {(() => {
        let latest: LastRead | null = null;
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (!key || !key.startsWith('last-read-')) continue;
          try {
            const data: LastRead = JSON.parse(localStorage.getItem(key) || '');
            if (!latest || data.timestamp > latest.timestamp) latest = data;
          } catch {}
        }
        if (!latest || !novels.find(n => n.id === latest!.novelId)) return null;
        const novel = novels.find(n => n.id === latest!.novelId)!;
        const timeAgo = Date.now() - latest.timestamp;
        const agoStr = timeAgo < 60000 ? '刚刚'
          : timeAgo < 3600000 ? `${Math.floor(timeAgo / 60000)}分钟前`
          : timeAgo < 86400000 ? `${Math.floor(timeAgo / 3600000)}小时前`
          : `${Math.floor(timeAgo / 86400000)}天前`;

        return (
          <button
            onClick={() => navigate(`/novels/${latest!.novelId}`)}
            className="w-full text-left mb-4 p-4 rounded-xl bg-gradient-to-r from-accent-soft/20 to-card border border-accent/10 hover:border-accent/30 transition-all group"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] text-ink-subtle uppercase tracking-wider mb-0.5">📖 继续上次</p>
                <p className="text-sm font-medium text-ink group-hover:text-accent transition-colors">{novel.title}</p>
                <p className="text-xs text-ink-muted mt-0.5">
                  第{latest.chapter}章 {latest.title || ''}
                  <span className="text-ink-subtle ml-2">{agoStr}</span>
                </p>
              </div>
              <span className="shrink-0 px-3 py-1.5 bg-accent text-white text-xs rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                继续 →
              </span>
            </div>
          </button>
        );
      })()}

      {(() => {
        try {
          const starred: string[] = JSON.parse(localStorage.getItem('starred-novels') || '[]');
          const favNovels = novels.filter(n => starred.includes(n.id));
          const restNovels = novels.filter(n => !starred.includes(n.id));

          if (favNovels.length === 0 && restNovels.length === 0) return (
        <div className="text-center py-24">
          <div className="text-6xl mb-6 opacity-40">✍️</div>
          <h3 className="font-heading text-2xl font-semibold text-ink mb-2">开始你的第一部 AI 小说</h3>
          <p className="text-sm text-ink-muted mb-8 max-w-md mx-auto">从一句话简介到完整小说，AI 负责写作、润色、质检，你只需要做决策</p>
          <div className="flex gap-3 justify-center">
            <button className="px-6 py-3 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors font-medium text-base" onClick={() => setShowForm(true)}>🚀 创建小说</button>
            <button className="px-6 py-3 rounded-lg border border-border text-ink-muted hover:text-ink transition-colors text-base" onClick={() => navigate('/settings')}>⚙ API Key</button>
          </div>
        </div>
          );

          return (
        <div>
          {/* Favorites section */}
          {favNovels.length > 0 && (
            <div className="mb-6">
              <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide mb-2">⭐ 收藏</h3>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
                {favNovels
                  .filter(n => !genreFilter || n.genre === genreFilter)
                  .sort((a, b) => {
                    if (sortBy === 'words') return (b.total_words||0) - (a.total_words||0);
                    if (sortBy === 'chapters') return (b.total_chapters||0) - (a.total_chapters||0);
                    return 0;
                  })
                  .map(n => <NovelCard key={n.id} novel={n}
                    onDelete={id => setNovels(prev => prev.filter(x => x.id !== id))}
                    isGenerating={generatingIds.has(n.id)}
                    onGenerate={id => {
                      setGeneratingIds(prev => new Set(prev).add(id));
                      fetch(`/api/novels/${id}/generate`,{method:'POST'}).then(()=>toast.success('已触发')).catch(()=>toast.error('失败')).finally(()=>setGeneratingIds(prev=>{const s=new Set(prev);s.delete(id);return s;}));
                    }} />)}
              </div>
            </div>
          )}

          {/* All novels */}
          {restNovels.length > 0 && (
            <div>
              {favNovels.length > 0 && <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide mb-2 mt-4">全部小说</h3>}
              <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
                {restNovels
                  .filter(n => !genreFilter || n.genre === genreFilter)
                  .sort((a, b) => {
                    if (sortBy === 'words') return (b.total_words||0) - (a.total_words||0);
                    if (sortBy === 'chapters') return (b.total_chapters||0) - (a.total_chapters||0);
                    return 0;
                  })
                  .map(n => <NovelCard key={n.id} novel={n}
                    onDelete={id => setNovels(prev => prev.filter(x => x.id !== id))}
                    isGenerating={generatingIds.has(n.id)}
                    onGenerate={id => {
                      setGeneratingIds(prev => new Set(prev).add(id));
                      fetch(`/api/novels/${id}/generate`,{method:'POST'}).then(()=>toast.success('已触发')).catch(()=>toast.error('失败')).finally(()=>setGeneratingIds(prev=>{const s=new Set(prev);s.delete(id);return s;}));
                    }} />)}
              </div>
            </div>
          )}
        </div>
          );
        } catch { return null; }
      })()}

      {/* Import modal */}
      {showImport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowImport(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-md p-6 animate-[fadeSlideIn_0.2s_ease-out]"
            onClick={e => e.stopPropagation()}>
            <h3 className="font-heading text-lg font-semibold text-ink mb-1">📥 导入外部小说</h3>
            <p className="text-xs text-ink-muted mb-4">支持 .txt 和 .epub 格式。自动识别章节结构。</p>

            <form onSubmit={handleImport} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">书名</label>
                <input
                  value={importTitle}
                  onChange={e => setImportTitle(e.target.value)}
                  placeholder="输入书名..."
                  className="w-full mt-1.5 rounded-md border border-input bg-card text-ink text-sm px-3 py-2
                    placeholder:text-ink-subtle focus:outline-none focus:border-accent"
                  required
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">题材</label>
                <select
                  value={importGenre}
                  onChange={e => setImportGenre(e.target.value)}
                  className="w-full mt-1.5 rounded-md border border-input bg-card text-ink text-sm px-3 py-2"
                >
                  {['玄幻','悬疑','都市','科幻','历史','官场','系统流','女频','仙侠','武侠','游戏','末世','轻小说'].map(g => (
                    <option key={g} value={g}>{g}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">选择文件</label>
                <div className="mt-1.5">
                  <input
                    type="file"
                    accept=".txt,.epub"
                    onChange={e => setImportFile(e.target.files?.[0] || null)}
                    className="w-full text-xs text-ink-muted file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0
                      file:text-xs file:font-medium file:bg-accent-soft file:text-accent
                      hover:file:bg-accent-soft/80 file:cursor-pointer file:transition-colors"
                  />
                </div>
                {importFile && (
                  <p className="text-[10px] text-ink-subtle mt-1">
                    已选择: {importFile.name} ({(importFile.size / 1024).toFixed(1)} KB)
                  </p>
                )}
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => { setShowImport(false); setImportFile(null); setImportTitle(''); }}
                  className="flex-1 py-2 rounded-lg border border-input text-ink-muted text-sm hover:bg-paper transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={importing || !importFile}
                  className="flex-1 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
                >
                  {importing ? '导入中...' : '开始导入'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Compare modal */}
      {showCompare && novels.length >= 2 && (
        <NovelCompare novels={novels} onClose={() => setShowCompare(false)} />
      )}

    </div>
  );
}
