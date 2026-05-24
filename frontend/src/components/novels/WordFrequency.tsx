import { useMemo, useState } from 'react';

interface PhraseEntry {
  phrase: string;
  count: number;
  perThousand: number; // per 1000 characters
  level: 'normal' | 'cliche' | 'overused';
}

interface Props {
  /** Full chapter/content text to analyze */
  content: string;
  /** Optional label for context (e.g. chapter number) */
  label?: string;
}

// Common cliche words in Chinese web novels
const CLICHE_PATTERNS = new Set([
  '微微一笑',
  '眼中闪过',
  '嘴角上扬',
  '眉头一皱',
  '心中一惊',
  '倒吸一口',
  '目光一凝',
  '脸色一变',
  '心头一震',
  '瞳孔一缩',
  '不由自主',
  '不可思议',
  '前所未有',
  '与此同时',
  '毫不犹豫',
  '脱口而出',
  '喃喃自语',
  '自言自语',
]);

// Common overused phrases that usually indicate lazy writing
const OVERUSE_PATTERNS = new Set([
  '突然',
  '竟然',
  '居然',
  '说道',
  '淡淡道',
  '冷笑道',
  '微微一笑',
  '冷哼一声',
]);

/** Extract 2-4 character phrases from text */
function extractPhrases(text: string): Map<string, number> {
  // Remove punctuation, spaces, and non-Chinese characters for phrase extraction
  const cleaned = text.replace(
    /[\s，。！？；：""''「」『』《》、（）【】\[\]\-—…\.\,\!\?\;\:\"\'\(\)\[\]\d\w]/g,
    '',
  );

  const freq = new Map<string, number>();

  // Extract 2-char, 3-char, and 4-char phrases using sliding window
  for (const windowSize of [2, 3, 4]) {
    for (let i = 0; i <= cleaned.length - windowSize; i++) {
      const phrase = cleaned.slice(i, i + windowSize);
      freq.set(phrase, (freq.get(phrase) || 0) + 1);
    }
  }

  return freq;
}

function analyzeFrequency(content: string, label?: string): {
  phrases: PhraseEntry[];
  totalChars: number;
} {
  const text = content || '';
  const totalChars = text.replace(/\s/g, '').length;

  if (totalChars === 0) {
    return { phrases: [], totalChars: 0 };
  }

  const phraseFreq = extractPhrases(text);

  // Calculate per-1000 ratio and classify
  const entries: PhraseEntry[] = [];
  for (const [phrase, count] of phraseFreq) {
    // Only include phrases appearing at least 3 times
    if (count < 3) continue;

    const perThousand = (count / totalChars) * 1000;

    // Only include phrases with notable frequency (>0.5 per 1000)
    if (perThousand < 1) continue;

    let level: PhraseEntry['level'] = 'normal';
    if (CLICHE_PATTERNS.has(phrase) || perThousand > 5) {
      level = 'cliche';
    }
    if (OVERUSE_PATTERNS.has(phrase) || perThousand > 10) {
      level = 'overused';
    }

    entries.push({
      phrase,
      count,
      perThousand: Math.round(perThousand * 10) / 10,
      level,
    });
  }

  // Sort by count descending and take top 30
  entries.sort((a, b) => b.count - a.count);
  const topEntries = entries.slice(0, 30);

  return { phrases: topEntries, totalChars };
}

function levelStyle(level: PhraseEntry['level']): {
  bg: string;
  text: string;
  border: string;
  badge: string;
} {
  if (level === 'overused') {
    return {
      bg: 'bg-red-50 dark:bg-red-950/20',
      text: 'text-red-600 dark:text-red-400',
      border: 'border-red-200 dark:border-red-800',
      badge: '过度使用',
    };
  }
  if (level === 'cliche') {
    return {
      bg: 'bg-amber-50 dark:bg-amber-950/20',
      text: 'text-amber-600 dark:text-amber-400',
      border: 'border-amber-200 dark:border-amber-800',
      badge: '陈词滥调',
    };
  }
  return {
    bg: '',
    text: 'text-ink-muted',
    border: 'border-transparent',
    badge: '',
  };
}

export function WordFrequency({ content, label }: Props) {
  const { phrases, totalChars } = useMemo(
    () => analyzeFrequency(content, label),
    [content, label],
  );

  const [expanded, setExpanded] = useState(false);

  if (phrases.length === 0) {
    return (
      <div className="text-center py-6 text-[11px] text-ink-subtle">
        词频分析需要至少 2000 字正文
      </div>
    );
  }

  const displayed = expanded ? phrases : phrases.slice(0, 20);
  const overuseCount = phrases.filter((p) => p.level === 'overused').length;
  const clicheCount = phrases.filter((p) => p.level === 'cliche').length;

  // Max count for bar scaling
  const maxCount = Math.max(...phrases.map((p) => p.count), 1);

  return (
    <div className="space-y-3">
      {/* Header stats */}
      <div className="flex items-center gap-4 text-[10px] text-ink-muted">
        <span>
          总字数：<span className="text-ink tabular-nums">{totalChars.toLocaleString()}</span>
        </span>
        <span>
          高频词：<span className="text-ink tabular-nums">{phrases.length}</span>
        </span>
        {overuseCount > 0 && (
          <span className="text-red-500 dark:text-red-400 font-medium">
            {overuseCount} 个过度使用
          </span>
        )}
        {clicheCount > 0 && (
          <span className="text-amber-500 dark:text-amber-400 font-medium">
            {clicheCount} 个陈词
          </span>
        )}
      </div>

      {/* Warn if too many overused/cliche words */}
      {(overuseCount > 3 || clicheCount > 5) && (
        <div className="p-2.5 rounded-lg bg-red-50/50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 text-[11px] text-red-600 dark:text-red-400">
          <span className="font-semibold">语言多样性警告：</span>
          本章有{overuseCount}个过度使用词和{clicheCount}个陈词滥调，建议使用同义词替换，增加语言丰富度。
        </div>
      )}

      {/* Phrase frequency list */}
      <div className="space-y-1 max-h-80 overflow-y-auto">
        {displayed.map((entry) => {
          const styles = levelStyle(entry.level);
          const barWidth = (entry.count / maxCount) * 100;

          return (
            <div
              key={entry.phrase}
              className={`flex items-center gap-2 py-1.5 px-2 rounded-md text-[11px] relative overflow-hidden ${styles.bg} border ${styles.border} transition-colors`}
            >
              {/* Background bar */}
              <div
                className={`absolute inset-y-0 left-0 transition-all ${
                  entry.level === 'overused'
                    ? 'bg-red-500/10 dark:bg-red-500/15'
                    : entry.level === 'cliche'
                      ? 'bg-amber-500/10 dark:bg-amber-500/15'
                      : 'bg-accent/5'
                }`}
                style={{ width: `${barWidth}%` }}
              />

              {/* Content */}
              <span className={`relative z-10 font-medium min-w-[4rem] ${styles.text}`}>
                {entry.phrase}
              </span>

              <span className="relative z-10 tabular-nums text-ink-muted min-w-[3rem] text-right">
                {entry.count}次
              </span>

              <span className="relative z-10 tabular-nums text-[10px] text-ink-subtle min-w-[5rem] text-right">
                {entry.perThousand}/千字
              </span>

              {entry.level !== 'normal' && (
                <span
                  className={`relative z-10 text-[9px] px-1.5 py-0.5 rounded font-medium ${styles.text} bg-white/50 dark:bg-black/20 border ${styles.border}`}
                >
                  {styles.badge}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Show more/less */}
      {phrases.length > 20 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-accent hover:underline transition-colors"
        >
          {expanded ? '收起' : `查看全部 ${phrases.length} 个高频词`}
        </button>
      )}
    </div>
  );
}
