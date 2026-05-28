import { useState, useCallback } from 'react';
import { toast } from 'sonner';

interface Scene {
  id: number;
  number: number;
  title: string;
  content: string;
  wordCount: number;
}

interface Props {
  chapterContent: string;
  chapterNumber: number;
  novelId: string;
  onSave: (mergedContent: string) => Promise<void>;
  saving: boolean;
}

const SCENE_BREAK_PATTERN = /^(?:---+|\*{3,}|_{3,}|◆.+|第[一二三四五六七八九十百千\d]+幕.*)$/m;

function detectScenes(text: string): Scene[] {
  if (!text.trim()) return [];

  // Split by scene breaks
  const lines = text.split('\n');
  const scenes: { content: string[]; id: number }[] = [];
  let currentScene: string[] = [];
  let id = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Detect blank line followed by meaningful content = scene break
    // or explicit scene markers
    const isMarker = SCENE_BREAK_PATTERN.test(line.trim());
    const isBlankLineBefore = i > 0 && lines[i - 1].trim() === '';

    if ((isBlankLineBefore && currentScene.length > 0 && line.trim() !== '' && i > 1 && lines[i - 2]?.trim() !== '') || (isMarker && currentScene.length > 0)) {
      scenes.push({ content: [...currentScene], id: id++ });
      currentScene = [];
      if (isMarker) continue; // Skip marker lines
    }

    currentScene.push(line);
  }

  // Push final scene
  if (currentScene.some(l => l.trim() !== '')) {
    scenes.push({ content: [...currentScene], id: id++ });
  }

  // If no scenes detected, treat entire content as one scene
  if (scenes.length <= 1) {
    // Try harder: split on double blank lines
    const parts = text.split(/\n\n\n+/);
    if (parts.length > 1) {
      return parts.map((part, i) => ({
        id: i,
        number: i + 1,
        title: getSceneTitle(part.trim()),
        content: part.trim(),
        wordCount: part.trim().length,
      }));
    }
    return [{
      id: 0,
      number: 1,
      title: getSceneTitle(text.trim()),
      content: text.trim(),
      wordCount: text.trim().length,
    }];
  }

  return scenes.map((scene, i) => ({
    id: scene.id,
    number: i + 1,
    title: getSceneTitle(scene.content.join('\n').trim()),
    content: scene.content.join('\n').trim(),
    wordCount: scene.content.join('\n').trim().length,
  }));
}

function getSceneTitle(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return '(空场景)';

  // Use first 60 chars of first non-empty line, without scene markers
  const firstLine = trimmed.split('\n')[0].replace(/^[#*>_\-]+/, '').trim();
  if (firstLine.length > 60) return firstLine.slice(0, 60) + '...';
  if (firstLine) return firstLine;
  return trimmed.slice(0, 60) + (trimmed.length > 60 ? '...' : '');
}

function mergeScenes(scenes: Scene[]): string {
  return scenes.map(s => s.content).join('\n\n---\n\n');
}

export function SceneEditor({ chapterContent, onSave, saving }: Props) {
  const [scenes, setScenes] = useState<Scene[]>(() => detectScenes(chapterContent));
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState('');
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

  const handleSave = useCallback(async () => {
    const merged = mergeScenes(scenes);
    await onSave(merged);
    toast.success('场景已保存');
  }, [scenes, onSave]);

  const handleDeleteScene = useCallback((id: number) => {
    if (scenes.length <= 1) {
      toast.error('至少保留一个场景');
      return;
    }
    setScenes(prev => prev.filter(s => s.id !== id));
  }, [scenes.length]);

  const handleEditScene = useCallback((id: number) => {
    const scene = scenes.find(s => s.id === id);
    if (scene) {
      setEditContent(scene.content);
      setEditingId(id);
    }
  }, [scenes]);

  const handleSaveEdit = useCallback(() => {
    if (editingId === null) return;
    setScenes(prev => prev.map(s =>
      s.id === editingId
        ? {
            ...s,
            content: editContent,
            wordCount: editContent.length,
            title: getSceneTitle(editContent),
          }
        : s
    ));
    setEditingId(null);
    setEditContent('');
  }, [editingId, editContent]);

  const handleAddScene = useCallback(() => {
    const newId = Math.max(0, ...scenes.map(s => s.id)) + 1;
    setScenes(prev => [
      ...prev,
      {
        id: newId,
        number: prev.length + 1,
        title: '(新场景)',
        content: '',
        wordCount: 0,
      },
    ]);
    setEditContent('');
    setEditingId(newId);
  }, [scenes]);

  const handleMoveScene = useCallback((fromIndex: number, toIndex: number) => {
    if (toIndex < 0 || toIndex >= scenes.length) return;
    setScenes(prev => {
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      // Re-number
      return next.map((s, i) => ({ ...s, number: i + 1 }));
    });
  }, [scenes.length]);

  const toggleCollapse = useCallback((id: number) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <div className="mt-2 space-y-2 animate-[fadeSlideIn_0.2s_ease-out]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-ink-muted">
          {scenes.length} 个场景 · {scenes.reduce((sum, s) => sum + s.wordCount, 0).toLocaleString()} 字
        </span>
        <button
          onClick={handleSave}
          disabled={saving}
          className="text-[10px] px-2.5 py-1 rounded bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-40"
        >
          {saving ? '保存中...' : '💾 保存场景'}
        </button>
      </div>

      <div className="space-y-2">
        {scenes.map((scene, index) => (
          <div
            key={scene.id}
            className="border border-border rounded-lg bg-card overflow-hidden transition-all"
          >
            {/* Scene header */}
            <div
              className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-paper/50 transition-colors"
              onClick={() => toggleCollapse(scene.id)}
            >
              {/* Drag handle */}
              <span
                className="text-ink-subtle cursor-grab active:cursor-grabbing text-xs select-none"
                title="拖动排序"
                onClick={e => e.stopPropagation()}
              >
                ⠿
              </span>

              {/* Scene number & title */}
              <span className="text-[10px] font-semibold text-accent bg-accent-soft/30 px-1.5 py-0.5 rounded tabular-nums shrink-0">
                场景{scene.number}
              </span>
              <span className="text-xs text-ink truncate flex-1">
                {scene.title}
              </span>

              {/* Word count */}
              <span className="text-[10px] text-ink-subtle tabular-nums shrink-0">
                {scene.wordCount.toLocaleString()}字
              </span>

              {/* Move up/down */}
              <button
                onClick={e => {
                  e.stopPropagation();
                  handleMoveScene(index, index - 1);
                }}
                disabled={index === 0}
                className="text-[10px] text-ink-muted hover:text-ink disabled:opacity-30 px-0.5"
                title="上移"
              >
                ▲
              </button>
              <button
                onClick={e => {
                  e.stopPropagation();
                  handleMoveScene(index, index + 1);
                }}
                disabled={index === scenes.length - 1}
                className="text-[10px] text-ink-muted hover:text-ink disabled:opacity-30 px-0.5"
                title="下移"
              >
                ▼
              </button>

              {/* Edit button */}
              <button
                onClick={e => {
                  e.stopPropagation();
                  handleEditScene(scene.id);
                }}
                className="text-[10px] text-ink-muted hover:text-accent px-1"
                title="编辑场景"
              >
                ✏️
              </button>

              {/* Delete button */}
              <button
                onClick={e => {
                  e.stopPropagation();
                  handleDeleteScene(scene.id);
                }}
                disabled={scenes.length <= 1}
                className="text-[10px] text-ink-muted hover:text-red-500 disabled:opacity-30 px-1"
                title="删除场景"
              >
                🗑
              </button>

              {/* Collapse toggle */}
              <span className={`text-xs text-ink-subtle transition-transform ${collapsed.has(scene.id) ? '' : 'rotate-90'}`}>
                ▸
              </span>
            </div>

            {/* Scene content (collapsible) */}
            {!collapsed.has(scene.id) && (
              <div className="px-3 pb-3">
                {editingId === scene.id ? (
                  <div className="space-y-2">
                    <textarea
                      value={editContent}
                      onChange={e => setEditContent(e.target.value)}
                      className="w-full min-h-[200px] bg-paper border border-border rounded-lg p-3 text-sm font-[var(--font-editor)] leading-relaxed resize-y
                        focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20"
                      placeholder="编辑场景内容..."
                      autoFocus
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={handleSaveEdit}
                        className="text-[10px] px-2.5 py-1 rounded bg-accent text-white hover:bg-accent-hover transition-colors"
                      >
                        完成编辑
                      </button>
                      <button
                        onClick={() => { setEditingId(null); setEditContent(''); }}
                        className="text-[10px] px-2.5 py-1 rounded border border-border text-ink-muted hover:text-ink transition-colors"
                      >
                        取消
                      </button>
                    </div>
                  </div>
                ) : (
                  <pre className="text-xs text-ink-muted font-[var(--font-editor)] leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto bg-paper/30 rounded p-2 border border-border/50">
                    {scene.content || <span className="text-ink-subtle italic">(空场景 - 点击 ✏️ 编辑)</span>}
                  </pre>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add scene button */}
      <button
        onClick={handleAddScene}
        className="w-full py-2 rounded-lg border-2 border-dashed border-border text-xs text-ink-muted hover:text-accent hover:border-accent/30 transition-colors"
      >
        + 添加场景
      </button>
    </div>
  );
}
