import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CharacterSoul } from 'src/components/novels/CharacterSoul';
import { CharacterGraph } from 'src/components/novels/CharacterGraph';
import { SoulWorkshop } from 'src/components/novels/SoulWorkshop';
import { SoulEngine } from 'src/components/novels/SoulEngine';
import { CharacterVoices } from 'src/components/novels/StoryLab';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelDetail } from 'src/types';

export function NovelCharacters() {
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
        <h1 className="text-lg font-semibold text-ink">角色</h1>
        <p className="text-xs text-ink-muted mt-1">角色卡、关系图、灵魂工坊、声音配置</p>
      </div>

      <div className="space-y-4">
        <CharacterSoul novelId={novel.id} />
        {novel.characters && novel.characters.length > 0 && (
          <div className="p-4 bg-card border border-border rounded-xl">
            <h3 className="text-sm font-semibold text-ink mb-3">角色关系图</h3>
            <CharacterGraph
              characters={novel.characters.map(c => ({
                id: c.id, name: c.name, role: c.role || '', power_level: '', status: '',
              }))}
              chapters={novel.chapters}
            />
          </div>
        )}
        <CharacterVoices chapters={novel.chapters} genre={novel.genre} />
        <SoulWorkshop novelId={novel.id} chapters={novel.chapters} />
        <SoulEngine novelId={novel.id} genre={novel.genre} />
      </div>
    </div>
  );
}
