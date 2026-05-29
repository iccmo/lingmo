import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from 'src/components/ui/button';
import { PenLine, BarChart3, BookOpen } from 'lucide-react';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelDetail } from 'src/types';

export function NovelOverview() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [novel, setNovel] = useState<NovelDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [coverSvg, setCoverSvg] = useState<string | null>(null);
  const [loadingCover, setLoadingCover] = useState(false);
  const [novelNotes, setNovelNotes] = useState('');
  const [editingNotes, setEditingNotes] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.novels.get(id).then(setNovel).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (id) setNovelNotes(localStorage.getItem(`novel-notes-${id}`) || '');
  }, [id]);

  async function generateCover() {
    if (!id) return;
    setLoadingCover(true);
    try {
      const r = await fetch(`/api/novels/${id}/cover`, { method: 'POST' });
      const data = await r.json();
      setCoverSvg(data.svg);
      setCoverPrompt(data.prompt);
    } catch (e) {
      toast.error('封面生成失败');
    } finally {
      setLoadingCover(false);
    }
  }

  function saveNotes() {
    if (id) {
      localStorage.setItem(`novel-notes-${id}`, novelNotes);
      setEditingNotes(false);
      toast.success('笔记已保存');
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-7 w-48" />
        <div className="skeleton h-4 w-64" />
        <div className="skeleton h-48 rounded-xl" />
      </div>
    );
  }

  if (!novel) return <p className="text-ink-muted text-sm">小说不存在</p>;

  const latestChapter = novel.chapters.filter(c => c.word_count > 0).pop();
  const avgQuality = novel.chapters.length > 0
    ? (novel.chapters.reduce((s, c) => s + (c.quality_score || 0), 0) / novel.chapters.filter(c => c.quality_score).length) || 0
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink">{novel.title}</h1>
          <p className="text-xs text-ink-muted mt-1">{novel.genre} / {novel.total_chapters} 章 / {novel.total_words.toLocaleString()} 字</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => navigate(`/novels/${id}/write`)}>
            <PenLine size={14} className="mr-1" /> 写作
          </Button>
          <Button size="sm" variant="outline" onClick={() => navigate(`/novels/${id}/analysis`)}>
            <BarChart3 size={14} className="mr-1" /> 分析
          </Button>
        </div>
      </div>

      {/* Synopsis */}
      {novel.synopsis && (
        <div className="p-4 bg-card border border-border rounded-xl">
          <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide mb-2">简介</h3>
          <p className="text-sm text-ink leading-relaxed">{novel.synopsis}</p>
        </div>
      )}

      {/* Quick stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 bg-card border border-border rounded-xl">
          <p className="text-[10px] text-ink-muted uppercase tracking-wide">章节数</p>
          <p className="text-xl font-bold text-ink mt-1">{novel.total_chapters}</p>
        </div>
        <div className="p-4 bg-card border border-border rounded-xl">
          <p className="text-[10px] text-ink-muted uppercase tracking-wide">总字数</p>
          <p className="text-xl font-bold text-ink mt-1">{(novel.total_words / 1000).toFixed(1)}k</p>
        </div>
        <div className="p-4 bg-card border border-border rounded-xl">
          <p className="text-[10px] text-ink-muted uppercase tracking-wide">平均质量</p>
          <p className="text-xl font-bold text-ink mt-1">{avgQuality > 0 ? (avgQuality * 100).toFixed(0) + '%' : '--'}</p>
        </div>
        <div className="p-4 bg-card border border-border rounded-xl">
          <p className="text-[10px] text-ink-muted uppercase tracking-wide">最新章节</p>
          <p className="text-xl font-bold text-ink mt-1">{latestChapter ? `第${latestChapter.number}章` : '--'}</p>
        </div>
      </div>

      {/* Cover */}
      <div className="p-4 bg-card border border-border rounded-xl">
        <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide mb-3">封面</h3>
        {coverSvg ? (
          <div dangerouslySetInnerHTML={{ __html: coverSvg }} className="max-w-[200px]" />
        ) : (
          <Button size="sm" variant="outline" onClick={generateCover} disabled={loadingCover}>
            <BookOpen size={14} className="mr-1" />
            {loadingCover ? '生成中...' : '生成封面'}
          </Button>
        )}
      </div>

      {/* Notes */}
      <div className="p-4 bg-card border border-border rounded-xl">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide">创作笔记</h3>
          {editingNotes ? (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setEditingNotes(false)}>取消</Button>
              <Button size="sm" onClick={saveNotes}>保存</Button>
            </div>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setEditingNotes(true)}>编辑</Button>
          )}
        </div>
        {editingNotes ? (
          <textarea
            value={novelNotes}
            onChange={e => setNovelNotes(e.target.value)}
            className="w-full h-32 text-sm bg-surface border border-border rounded-lg p-3 resize-none focus:outline-none focus:ring-1 focus:ring-accent"
            placeholder="记录创作灵感、角色设定、剧情走向..."
          />
        ) : (
          <p className="text-sm text-ink-muted whitespace-pre-wrap">
            {novelNotes || '点击编辑添加创作笔记...'}
          </p>
        )}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {[
          { label: '角色管理', path: `/novels/${id}/characters` },
          { label: '世界观', path: `/novels/${id}/world` },
          { label: '出版准备', path: `/novels/${id}/publish` },
          { label: '工具箱', path: `/novels/${id}/tools` },
          { label: '记忆库', path: `/novels/${id}/memory` },
          { label: '大纲', path: `/novels/${id}/outline` },
        ].map(item => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className="p-3 bg-card border border-border rounded-xl text-sm text-ink hover:bg-surface-hover transition-colors text-left"
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
