import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { MasterworkLab } from 'src/components/novels/MasterworkLab';
import { CreativeLab } from 'src/components/novels/CreativeLab';
import { ReaderSim } from 'src/components/novels/ReaderSim';
import { OpeningABTest } from 'src/components/novels/StoryLab';
import { WordSprint } from 'src/components/novels/WordSprint';
import { PomodoroTimer } from 'src/components/novels/PomodoroTimer';
import { AgentDashboard } from 'src/components/novels/AgentDashboard';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelDetail } from 'src/types';

export function NovelTools() {
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
      </div>
    );
  }

  if (!novel) return <p className="text-ink-muted text-sm">小说不存在</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-ink">工具箱</h1>
        <p className="text-xs text-ink-muted mt-1">大师工坊、创意实验室、读者模拟、A/B 测试</p>
      </div>

      <div className="space-y-4">
        <MasterworkLab novelId={novel.id} chapters={novel.chapters} genre={novel.genre} />
        <CreativeLab chapters={novel.chapters} genre={novel.genre} novelId={novel.id} />
        <ReaderSim chapters={novel.chapters} />
        <OpeningABTest synopsis={novel.synopsis} genre={novel.genre} />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <WordSprint />
          <PomodoroTimer />
        </div>
        <AgentDashboard novelId={novel.id} />
      </div>
    </div>
  );
}
