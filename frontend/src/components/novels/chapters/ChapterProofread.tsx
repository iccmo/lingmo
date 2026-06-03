/** AI 校对结果面板 — 从 ChapterList.tsx 提取 */
import { Search } from 'lucide-react';

export interface ProofreadIssue {
  type: string;
  original: string;
  suggestion: string;
  reason: string;
}

interface Props {
  issues: ProofreadIssue[];
  onClose: () => void;
}

function typeLabel(type: string): string {
  const map: Record<string, string> = {
    typo: '错别字',
    repetition: '重复用词',
    inconsistency: '逻辑不连贯',
    punctuation: '标点错误',
  };
  return map[type] || type;
}

export function ChapterProofread({ issues, onClose }: Props) {
  if (issues.length === 0) return null;

  return (
    <div className="mt-3 p-3 rounded-lg bg-warn-soft/50 border border-warn/20 animate-[fadeSlideIn_0.2s_ease-out]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-300">
          <Search size={12} className="mr-1" /> 校对结果 — {issues.length} 处问题
        </span>
        <button
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          className="text-[10px] text-ink-muted hover:text-ink"
        >
          收起
        </button>
      </div>
      <div className="space-y-1.5 max-h-64 overflow-y-auto">
        {issues.map((issue, i) => {
          const label = typeLabel(issue.type);
          const isError = issue.type === 'typo' || issue.type === 'punctuation';
          return (
            <div key={i} className="text-[10px] p-1.5 rounded bg-card border border-border/50">
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className={`px-1 rounded text-[9px] font-medium ${
                  isError
                    ? 'bg-destructive-soft text-red-700 dark:bg-red-900/30'
                    : 'bg-warn-soft text-amber-700 dark:bg-amber-900/30'
                }`}>
                  {label}
                </span>
                <span className="text-ink-subtle">{issue.reason}</span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className={`line-through ${isError ? 'text-destructive' : 'text-warn'}`}>
                  {issue.original}
                </span>
                <span className="text-success font-medium">
                  → {issue.suggestion}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
