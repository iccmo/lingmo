import { useState, useMemo } from 'react';

interface VersionEntry {
  content: string;
  timestamp: number;
}

interface Props {
  novelId: string;
  chapterNum: number;
  currentContent: string;
}

interface DiffLine {
  type: 'added' | 'removed' | 'unchanged';
  text: string;
  lineNum: number;
}

function computeDiff(oldLines: string[], newLines: string[]): DiffLine[] {
  const result: DiffLine[] = [];
  // Simple LCS-based diff
  const m = oldLines.length;
  const n = newLines.length;

  // Build LCS table
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to produce the diff
  let i = m;
  let j = n;
  const segments: ('added' | 'removed' | 'unchanged')[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      segments.unshift('unchanged');
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      segments.unshift('added');
      j--;
    } else {
      segments.unshift('removed');
      i--;
    }
  }

  // Build output from segments
  let oldIdx = 0;
  let newIdx = 0;
  let lineNum = 0;

  for (const seg of segments) {
    lineNum++;
    if (seg === 'unchanged') {
      result.push({ type: 'unchanged', text: oldLines[oldIdx], lineNum });
      oldIdx++;
      newIdx++;
    } else if (seg === 'removed') {
      result.push({ type: 'removed', text: oldLines[oldIdx], lineNum });
      oldIdx++;
    } else {
      result.push({ type: 'added', text: newLines[newIdx], lineNum });
      newIdx++;
    }
  }

  return result;
}

export function ChapterDiff({ novelId, chapterNum, currentContent }: Props) {
  const [compareIdx, setCompareIdx] = useState<number>(0);
  const [showDiff, setShowDiff] = useState(false);

  const versionHistory = useMemo<VersionEntry[]>(() => {
    try {
      const raw = localStorage.getItem(`chapter-versions-${novelId}`);
      if (!raw) return [];
      const all: Record<string, VersionEntry[]> = JSON.parse(raw);
      return (all[String(chapterNum)] || []).sort((a, b) => b.timestamp - a.timestamp);
    } catch {
      return [];
    }
  }, [novelId, chapterNum]);

  const diffLines = useMemo<DiffLine[]>(() => {
    if (!showDiff || versionHistory.length === 0) return [];
    const oldContent = versionHistory[compareIdx]?.content || '';
    const oldLines = oldContent.split('\n');
    const newLines = currentContent.split('\n');
    return computeDiff(oldLines, newLines);
  }, [showDiff, compareIdx, versionHistory, currentContent]);

  const hasHistory = versionHistory.length > 0;

  if (!hasHistory) return null;

  const selectedVersion = versionHistory[compareIdx];
  const selectedDate = selectedVersion
    ? new Date(selectedVersion.timestamp).toLocaleString('zh-CN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  return (
    <div className="mt-4 pt-4 border-t border-border">
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <button
          onClick={() => setShowDiff(!showDiff)}
          className="text-[11px] px-2 py-1 rounded border border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-colors"
        >
          {showDiff ? '✕ 关闭对比' : '📜 版本对比'}
        </button>

        {showDiff && versionHistory.length > 1 && (
          <select
            value={compareIdx}
            onChange={(e) => setCompareIdx(Number(e.target.value))}
            className="text-[11px] rounded border border-input bg-card text-ink px-2 py-1
              focus:outline-none focus:border-accent"
          >
            {versionHistory.map((v, i) => {
              const date = new Date(v.timestamp).toLocaleString('zh-CN', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              });
              return (
                <option key={i} value={i}>
                  对比版本 {i + 1} - {date}
                </option>
              );
            })}
          </select>
        )}
      </div>

      {showDiff && diffLines.length > 0 && (
        <div className="border border-border rounded-lg overflow-hidden">
          {/* Diff header */}
          <div className="flex text-[10px] text-ink-muted bg-muted/50 border-b border-border px-3 py-1.5">
            <span className="flex-1">
              旧版本 ({selectedDate})
            </span>
            <span className="flex-1 text-right">
              当前版本
            </span>
          </div>

          {/* Diff legend */}
          <div className="flex gap-3 px-3 py-1.5 text-[9px] border-b border-border bg-paper/50">
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-red-100 dark:bg-red-900/40 border border-red-200 dark:border-red-800" />
              删除
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-100 dark:bg-emerald-900/40 border border-emerald-200 dark:border-emerald-800" />
              新增
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-transparent border border-border" />
              未变
            </span>
          </div>

          {/* Diff content */}
          <div className="max-h-[500px] overflow-y-auto bg-card font-mono text-xs leading-6">
            {diffLines.map((line, i) => {
              let bgClass = '';
              let prefix = ' ';
              if (line.type === 'added') {
                bgClass = 'bg-emerald-50 dark:bg-emerald-900/20 border-l-2 border-emerald-400 dark:border-emerald-600';
                prefix = '+';
              } else if (line.type === 'removed') {
                bgClass = 'bg-red-50 dark:bg-red-900/20 border-l-2 border-red-400 dark:border-red-600';
                prefix = '-';
              } else {
                bgClass = 'border-l-2 border-transparent';
              }

              return (
                <div
                  key={i}
                  className={`flex px-3 py-0 ${bgClass}`}
                >
                  <span className="w-6 shrink-0 text-ink-subtle text-right mr-2 select-none">
                    {prefix}
                  </span>
                  <span
                    className={`flex-1 whitespace-pre-wrap break-all ${
                      line.type === 'added'
                        ? 'text-emerald-800 dark:text-emerald-300'
                        : line.type === 'removed'
                          ? 'text-red-800 dark:text-red-300'
                          : 'text-ink-muted'
                    }`}
                  >
                    {line.text || ' '}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
