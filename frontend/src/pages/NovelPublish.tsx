import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { PlatformChecklist } from 'src/components/novels/PlatformChecklist';
import { SmartRecommend } from 'src/components/novels/SmartRecommend';
import { GenerationStatusBanner } from 'src/components/novels/GenerationStatusBanner';
import { Button } from 'src/components/ui/button';
import { api } from 'src/lib/api';
import { getBatchCompletionNotice } from 'src/lib/batch-generation-status';
import { toast } from 'sonner';
import type { NovelDetail } from 'src/types';
import { BookOpen, Download, Rocket, CheckCircle2, AlertTriangle, Clock, FileText, TrendingUp } from 'lucide-react';

interface GenStatus {
  status: string;
  message: string;
  progress: number;
  overall?: number;
  grade?: string;
}

export function NovelPublish() {
  const { id } = useParams<{ id: string }>();
  const [novel, setNovel] = useState<NovelDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [batchCount, setBatchCount] = useState(10);
  const [batchThreshold, setBatchThreshold] = useState(0.8);
  const [batchPolling, setBatchPolling] = useState(false);
  const [genStatus, setGenStatus] = useState<GenStatus | null>(null);

  useEffect(() => {
    if (!id) return;
    api.novels.get(id).then(setNovel).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
  }, [id]);

  // SSE + polling for batch generation progress
  useEffect(() => {
    if (!batchPolling || !id) return;
    const genStartRef = Date.now();
    let es: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let retries = 0;

    function connectSSE() {
      es = new EventSource(`/api/novels/${id}/generate/stream`);
      es.onmessage = (event) => {
        try {
          const s = JSON.parse(event.data) as GenStatus;
          setGenStatus(s);
          if (s.status === 'complete' || s.status === 'error') {
            cleanup();
            if (s.status === 'complete') {
              const elapsed = Math.round((Date.now() - genStartRef) / 1000);
              const notice = getBatchCompletionNotice(s, elapsed);
              if (notice.kind === 'warning') toast.warning(notice.message);
              else toast.success(notice.message);
              api.novels.get(id!).then(setNovel);
            }
          }
        } catch {}
      };
      es.onerror = () => {
        es?.close();
        if (retries < 3) { retries++; setTimeout(connectSSE, 2000 * retries); }
        else if (!pollTimer) {
          pollTimer = setInterval(async () => {
            try {
              const r = await fetch(`/api/novels/${id}/generate/queue-status`);
              const d = await r.json();
              if (d.status === 'done' || d.status === 'complete') {
                cleanup();
                const notice = getBatchCompletionNotice(d);
                if (notice.kind === 'warning') {
                  setGenStatus({ status: 'complete', message: notice.message, progress: 100 });
                  toast.warning(notice.message);
                } else {
                  toast.success(notice.message);
                }
                api.novels.get(id!).then(setNovel);
              } else if (d.status === 'error') {
                cleanup(); setGenStatus({ status: 'error', message: d.last_error || '生成失败', progress: 0 });
              }
            } catch {}
          }, 5000);
        }
      };
    }

    function cleanup() {
      setBatchPolling(false);
      es?.close();
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    connectSSE();
    return cleanup;
  }, [batchPolling, id]);

  async function startBatch() {
    if (!id) return;
    try {
      setBatchPolling(true);
      setGenStatus({ status: 'generating', message: '正在构思章节...', progress: 5 });
      await api.novels.generateBatch(id, batchCount, batchThreshold);
    } catch (e) {
      toast.error('启动失败: ' + (e as Error).message);
      setBatchPolling(false);
    }
  }

  async function handleExport() {
    if (!id) return;
    try {
      const r = await fetch(`/api/novels/${id}/export?fmt=txt`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${novel?.title || 'novel'}.txt`; a.click();
      URL.revokeObjectURL(url);
      toast.success('导出成功');
    } catch { toast.error('导出失败'); }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-7 w-32" />
        <div className="skeleton h-48 rounded-xl" />
      </div>
    );
  }

  if (!novel) return <p className="text-ink-muted text-sm">小说不存在</p>;

  const genChapters = novel.chapters.filter(c => c.word_count > 0);
  const avgQuality = genChapters.length > 0
    ? genChapters.reduce((s, c) => s + (c.quality_score || 0), 0) / genChapters.length
    : 0;
  const totalWords = genChapters.reduce((s, c) => s + (c.word_count || 0), 0);
  const aChapters = genChapters.filter(c => (c.quality_score || 0) >= 0.8).length;
  const needsMore = genChapters.length < 30;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-ink">出版</h1>
        <p className="text-xs text-ink-muted mt-1">批量生成 · 质量检查 · 导出 · 发布指南</p>
      </div>

      {/* Generation status banner */}
      <GenerationStatusBanner
        genStatus={genStatus}
        onViewChapter={() => {}}
        onRetry={startBatch}
      />

      {/* Quick stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3 bg-card border border-border rounded-xl">
          <p className="text-[10px] text-ink-muted uppercase tracking-wide mb-0.5">已写章节</p>
          <p className="text-xl font-bold text-ink tabular-nums">{genChapters.length}</p>
          <p className="text-[10px] text-ink-subtle">{novel.total_chapters} 章位</p>
        </div>
        <div className="p-3 bg-card border border-border rounded-xl">
          <p className="text-[10px] text-ink-muted uppercase tracking-wide mb-0.5">总字数</p>
          <p className="text-xl font-bold text-ink tabular-nums">{(totalWords / 10000).toFixed(1)}万</p>
          <p className="text-[10px] text-ink-subtle">均{genChapters.length > 0 ? Math.round(totalWords / genChapters.length) : 0}字/章</p>
        </div>
        <div className="p-3 bg-card border border-border rounded-xl">
          <p className="text-[10px] text-ink-muted uppercase tracking-wide mb-0.5">平均质量</p>
          <p className={`text-xl font-bold tabular-nums ${avgQuality >= 0.8 ? 'text-emerald-500' : avgQuality >= 0.65 ? 'text-amber-500' : 'text-red-500'}`}>
            {avgQuality > 0 ? avgQuality.toFixed(2) : '-'}
          </p>
          <p className="text-[10px] text-ink-subtle">{aChapters}章A级</p>
        </div>
        <div className="p-3 bg-card border border-border rounded-xl">
          <p className="text-[10px] text-ink-muted uppercase tracking-wide mb-0.5">发布状态</p>
          {needsMore ? (
            <p className="text-sm font-semibold text-amber-500 flex items-center gap-1"><AlertTriangle size={14} /> 章数不足</p>
          ) : genChapters.length >= 50 ? (
            <p className="text-sm font-semibold text-emerald-500 flex items-center gap-1"><CheckCircle2 size={14} /> 可发布</p>
          ) : (
            <p className="text-sm font-semibold text-blue-500 flex items-center gap-1"><Rocket size={14} /> 可发布</p>
          )}
          <p className="text-[10px] text-ink-subtle">建议≥30章起步</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Batch generation */}
        <div className="p-4 bg-card border border-border rounded-xl">
          <h3 className="text-sm font-semibold text-ink mb-3 flex items-center gap-1.5">
            <Rocket size={15} className="text-accent" /> 批量生成
          </h3>
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <label className="text-xs text-ink-muted flex items-center gap-1.5">
              章数
              <input type="number" value={batchCount} onChange={e => setBatchCount(Math.min(20, Math.max(1, Number(e.target.value))))}
                className="w-14 px-2 py-1 text-xs bg-surface border border-border rounded" min={1} max={20} />
            </label>
            <label className="text-xs text-ink-muted flex items-center gap-1.5">
              质量阈值
              <input type="number" value={batchThreshold} onChange={e => setBatchThreshold(Number(e.target.value))}
                className="w-14 px-2 py-1 text-xs bg-surface border border-border rounded" min={0.5} max={1} step={0.05} />
            </label>
            <Button size="sm" onClick={startBatch} disabled={batchPolling}>
              {batchPolling ? '生成中...' : `生成 ${batchCount} 章`}
            </Button>
          </div>
          <p className="text-[10px] text-ink-subtle leading-relaxed">
            每章约需 5-10 分钟。建议一次 10 章，分批生成。下一章：第 {genChapters.length + 1} 章
          </p>
        </div>

        {/* Export */}
        <div className="p-4 bg-card border border-border rounded-xl">
          <h3 className="text-sm font-semibold text-ink mb-3 flex items-center gap-1.5">
            <Download size={15} className="text-accent" /> 导出
          </h3>
          <div className="space-y-2">
            <button onClick={handleExport}
              className="w-full py-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors text-sm font-medium flex items-center justify-center gap-1.5">
              <FileText size={14} /> 导出 TXT（{genChapters.length}章 · {totalWords.toLocaleString()}字）
            </button>
            <p className="text-[10px] text-ink-subtle">
              TXT 格式可直接导入番茄作家后台。建议导出前确认所有章节质量 ≥0.65。
            </p>
          </div>
        </div>
      </div>

      {/* Platform checks */}
      {genChapters.length > 0 && (
        <>
          <PlatformChecklist chapters={novel.chapters} genre={novel.genre} />
          <SmartRecommend chapters={novel.chapters} genre={novel.genre} />
        </>
      )}

      {/* 番茄小说发布指南 */}
      <div className="p-4 bg-card border border-border rounded-xl">
        <h3 className="text-sm font-semibold text-ink mb-3 flex items-center gap-1.5">
          <BookOpen size={15} className="text-accent" /> 番茄小说发布指南
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="p-3 bg-paper rounded-lg border border-border">
            <p className="text-xs font-semibold text-ink mb-2">发布前</p>
            <ul className="space-y-1.5 text-[11px] text-ink-muted">
              <li className="flex items-start gap-1"><CheckCircle2 size={12} className="text-emerald-500 mt-0.5 shrink-0" /> 前3章每章结尾有钩子</li>
              <li className="flex items-start gap-1"><CheckCircle2 size={12} className="text-emerald-500 mt-0.5 shrink-0" /> 书名3-7字，有悬念感</li>
              <li className="flex items-start gap-1"><CheckCircle2 size={12} className="text-emerald-500 mt-0.5 shrink-0" /> 简介前30字有画面</li>
              <li className="flex items-start gap-1"><CheckCircle2 size={12} className="text-emerald-500 mt-0.5 shrink-0" /> 标签精确匹配内容</li>
            </ul>
          </div>
          <div className="p-3 bg-paper rounded-lg border border-border">
            <p className="text-xs font-semibold text-ink mb-2">发布节奏</p>
            <ul className="space-y-1.5 text-[11px] text-ink-muted">
              <li className="flex items-start gap-1"><Clock size={12} className="text-blue-500 mt-0.5 shrink-0" /> 第1天：一次性发3章</li>
              <li className="flex items-start gap-1"><Clock size={12} className="text-blue-500 mt-0.5 shrink-0" /> 第2-7天：每天2章</li>
              <li className="flex items-start gap-1"><Clock size={12} className="text-blue-500 mt-0.5 shrink-0" /> 第8-30天：每天1章</li>
              <li className="flex items-start gap-1"><Clock size={12} className="text-blue-500 mt-0.5 shrink-0" /> 稳定更新＞断更爆发</li>
            </ul>
          </div>
          <div className="p-3 bg-paper rounded-lg border border-border">
            <p className="text-xs font-semibold text-ink mb-2">数据关注</p>
            <ul className="space-y-1.5 text-[11px] text-ink-muted">
              <li className="flex items-start gap-1"><TrendingUp size={12} className="text-purple-500 mt-0.5 shrink-0" /> 读完率 ≥60% 合格</li>
              <li className="flex items-start gap-1"><TrendingUp size={12} className="text-purple-500 mt-0.5 shrink-0" /> 追读率 连续3章衡量</li>
              <li className="flex items-start gap-1"><TrendingUp size={12} className="text-purple-500 mt-0.5 shrink-0" /> 书架加入率 衡量留存</li>
              <li className="flex items-start gap-1"><TrendingUp size={12} className="text-purple-500 mt-0.5 shrink-0" /> 读完率降→加钩子</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
