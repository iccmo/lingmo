import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { QualityTrend } from 'src/components/novels/QualityTrend';
import { PacingCurve } from 'src/components/novels/PacingCurve';
import { EmotionalArc } from 'src/components/novels/EmotionalArc';
import { DialogueRatio } from 'src/components/novels/DialogueRatio';
import { EmotionRecipe } from 'src/components/novels/EmotionRecipe';
import { ChapterDNA } from 'src/components/novels/ChapterDNA';
import { WritingDigest } from 'src/components/novels/WritingDigest';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelDetail } from 'src/types';

export function NovelAnalysis() {
  const { id } = useParams<{ id: string }>();
  const [novel, setNovel] = useState<NovelDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    api.novels.get(id).then(setNovel).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-7 w-32" />
        <div className="skeleton h-48 rounded-xl" />
        <div className="skeleton h-48 rounded-xl" />
      </div>
    );
  }

  if (!novel) return <p className="text-ink-muted text-sm">小说不存在</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-ink">分析</h1>
        <p className="text-xs text-ink-muted mt-1">质量趋势、节奏曲线、情感分布、章节 DNA</p>
      </div>

      <div className="space-y-4">
        <QualityTrend chapters={novel.chapters} />
        <PacingCurve chapters={novel.chapters} />
        <EmotionalArc chapters={novel.chapters} />
        <DialogueRatio chapters={novel.chapters} />
        <EmotionRecipe chapters={novel.chapters} />
        <ChapterDNA chapters={novel.chapters} novelId={novel.id} />
        <WritingDigest chapters={novel.chapters} novelId={novel.id} />
      </div>
    </div>
  );
}
