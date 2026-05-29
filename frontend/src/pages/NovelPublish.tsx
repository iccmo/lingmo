import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { PlatformChecklist } from 'src/components/novels/PlatformChecklist';
import { SmartRecommend } from 'src/components/novels/SmartRecommend';
import { Button } from 'src/components/ui/button';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelDetail } from 'src/types';

export function NovelPublish() {
  const { id } = useParams<{ id: string }>();
  const [novel, setNovel] = useState<NovelDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [batchCount, setBatchCount] = useState(5);
  const [batchThreshold, setBatchThreshold] = useState(0.8);
  const [batchStatus, setBatchStatus] = useState<{ job_id: string | null; status: string; progress: { current: number; total: number }; last_error: string | null } | null>(null);
  const [batchPolling, setBatchPolling] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.novels.get(id).then(setNovel).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
  }, [id]);

  // Batch polling
  useEffect(() => {
    if (!batchPolling || !id) return;
    const interval = setInterval(async () => {
      try {
        const r = await fetch(`/api/novels/${id}/batch/status`);
        const data = await r.json();
        setBatchStatus(data);
        if (data.status === 'complete' || data.status === 'error') {
          setBatchPolling(false);
          if (data.status === 'complete') {
            toast.success(`批量生成完成: ${data.progress.current} 章`);
            api.novels.get(id).then(setNovel);
          } else {
            toast.error(`批量生成失败: ${data.last_error}`);
          }
        }
      } catch {}
    }, 3000);
    return () => clearInterval(interval);
  }, [batchPolling, id]);

  async function startBatch() {
    if (!id) return;
    try {
      const r = await fetch(`/api/novels/${id}/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count: batchCount, quality_threshold: batchThreshold }),
      });
      const data = await r.json();
      setBatchStatus({ job_id: data.job_id, status: 'running', progress: { current: 0, total: batchCount }, last_error: null });
      setBatchPolling(true);
      toast.info('批量生成已启动');
    } catch (e) {
      toast.error('启动失败: ' + (e as Error).message);
    }
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-ink">出版</h1>
        <p className="text-xs text-ink-muted mt-1">平台检查、发布策略、批量生成</p>
      </div>

      <div className="space-y-4">
        <PlatformChecklist chapters={novel.chapters} />
        <SmartRecommend genre={novel.genre} chapters={novel.chapters} />

        {/* Batch generation */}
        <div className="p-4 bg-card border border-border rounded-xl">
          <h3 className="text-sm font-semibold text-ink mb-3">批量生成</h3>
          <div className="flex items-center gap-4 mb-4">
            <label className="text-xs text-ink-muted">
              章数
              <input type="number" value={batchCount} onChange={e => setBatchCount(Number(e.target.value))}
                className="ml-2 w-16 px-2 py-1 text-xs bg-surface border border-border rounded" min={1} max={20} />
            </label>
            <label className="text-xs text-ink-muted">
              质量阈值
              <input type="number" value={batchThreshold} onChange={e => setBatchThreshold(Number(e.target.value))}
                className="ml-2 w-16 px-2 py-1 text-xs bg-surface border border-border rounded" min={0.5} max={1} step={0.05} />
            </label>
            <Button size="sm" onClick={startBatch} disabled={batchPolling}>
              {batchPolling ? '生成中...' : '开始批量生成'}
            </Button>
          </div>
          {batchStatus && (
            <div className="text-xs text-ink-muted">
              状态: {batchStatus.status} | 进度: {batchStatus.progress.current}/{batchStatus.progress.total}
              {batchStatus.last_error && <span className="text-destructive ml-2">{batchStatus.last_error}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
