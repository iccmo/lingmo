import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';

interface VisualCharacter {
  char_key: string;
  name?: string;
  appearance: string;
  default_expression: string;
  signature_pose: string;
  color_palette: string;
  costume: string;
  injury_marks: string;
  voice_character: string;
}

interface Props {
  novelId: string;
}

export function VisualBiblePanel({ novelId }: Props) {
  const [characters, setCharacters] = useState<VisualCharacter[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  const fetchCharacters = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/novels/${novelId}/visual-bible`);
      if (res.ok) {
        const data = await res.json();
        setCharacters(data.characters || []);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [novelId]);

  useEffect(() => { fetchCharacters(); }, [fetchCharacters]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`/api/novels/${novelId}/visual-bible/generate`, { method: 'POST' });
      if (res.ok) {
        toast.success('视觉圣经生成已启动');
        // Poll for completion
        const poll = setInterval(async () => {
          const sRes = await fetch(`/api/novels/${novelId}/generate/status`);
          if (sRes.ok) {
            const s = await sRes.json();
            if (s.status === 'idle' || s.status === 'error') {
              clearInterval(poll);
              setGenerating(false);
              if (s.status === 'idle') {
                toast.success(s.message || '生成完成');
                fetchCharacters();
              } else {
                toast.error(s.message || '生成失败');
              }
            }
          }
        }, 2000);
      }
    } catch (e) {
      setGenerating(false);
      toast.error('请求失败');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">角色视觉描述</h3>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-3 py-1.5 text-xs font-medium bg-accent text-white rounded-md hover:bg-accent/80 disabled:opacity-50 transition flex items-center gap-1.5"
        >
          {generating && <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
          {generating ? '生成中...' : '生成视觉圣经'}
        </button>
        {characters.length > 0 && (
          <button
            onClick={() => {
              const url = `/api/novels/${novelId}/visual-bible/export`;
              const a = document.createElement('a');
              a.href = url;
              a.download = `visual_bible_${novelId}.zip`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              toast.success('角色卡片导出中...');
            }}
            className="px-3 py-1.5 text-xs font-medium border border-border rounded-md text-ink hover:bg-card transition flex items-center gap-1.5"
          >
            📦 导出卡片
          </button>
        )}
      </div>

      {loading && (
        <div className="grid gap-3 sm:grid-cols-2">
          {[1, 2].map(i => (
            <div key={i} className="border border-border rounded-lg p-3 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <div className="skeleton w-3 h-3 rounded-full shrink-0" />
                <div className="skeleton h-4 w-16 rounded" />
              </div>
              <div className="space-y-1.5">
                <div className="skeleton h-3 w-full rounded" />
                <div className="skeleton h-3 w-3/4 rounded" />
                <div className="skeleton h-3 w-1/2 rounded" />
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && characters.length === 0 && (
        <div className="text-center py-10">
          <div className="text-3xl mb-3">🎨</div>
          <p className="text-sm text-ink-muted">暂无视觉描述</p>
          <p className="text-xs text-ink-subtle mt-1">点击上方按钮为角色生成视觉形象</p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {characters.map((char) => (
          <div
            key={char.char_key}
            className="border border-border rounded-lg p-3 bg-card hover:shadow-sm transition"
          >
            <div className="flex items-center gap-2 mb-2">
              <div
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: char.color_palette?.split(',')[0]?.trim() || '#666' }}
              />
              <span className="text-sm font-semibold text-ink">{char.char_key || char.name}</span>
            </div>
            <div className="space-y-1 text-xs text-ink-muted">
              <p><span className="text-ink font-medium">外貌：</span>{char.appearance}</p>
              <p><span className="text-ink font-medium">服装：</span>{char.costume}</p>
              <p><span className="text-ink font-medium">表情：</span>{char.default_expression}</p>
              <p><span className="text-ink font-medium">姿态：</span>{char.signature_pose}</p>
              {char.injury_marks && char.injury_marks !== '无' && (
                <p><span className="text-ink font-medium">标记：</span>{char.injury_marks}</p>
              )}
              <p><span className="text-ink font-medium">声音：</span>{char.voice_character}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
