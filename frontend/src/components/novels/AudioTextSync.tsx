import { useMemo, useRef, useEffect } from 'react';

interface Sentence {
  text: string;
  startRatio: number;
  endRatio: number;
  index: number;
}

interface AudioTextSyncProps {
  content: string;
  positionSec: number;
  duration: number;
  isPlaying: boolean;
}

/**
 * Split text into sentences, preserving delimiters.
 * Splits on Chinese/English punctuation that marks sentence boundaries.
 */
function splitSentences(text: string): string[] {
  if (!text) return [];
  // Split on sentence-ending punctuation, keeping the delimiter with the sentence
  const parts = text.split(/(?<=[。！？\.!\?\n])(?=[^\s])/g);
  // If the split didn't work well (e.g. no punctuation found), treat each line as a sentence
  if (parts.length === 1 && parts[0] === text) {
    return text.split('\n').filter(Boolean);
  }
  return parts.filter((p) => p.trim().length > 0);
}

function buildSentences(content: string): Sentence[] {
  const raw = splitSentences(content);
  if (raw.length === 0) return [];

  // Calculate total character count (excluding whitespace for ratio)
  const charCounts = raw.map((s) => s.replace(/\s/g, '').length);
  const totalChars = charCounts.reduce((sum, c) => sum + c, 0);

  if (totalChars === 0) {
    // Fallback: equal distribution
    return raw.map((text, i) => ({
      text,
      startRatio: i / raw.length,
      endRatio: (i + 1) / raw.length,
      index: i,
    }));
  }

  let cumulative = 0;
  return raw.map((text, i) => {
    const start = cumulative / totalChars;
    cumulative += charCounts[i];
    const end = cumulative / totalChars;
    return { text, startRatio: start, endRatio: end, index: i };
  });
}

export function AudioTextSync({ content, positionSec, duration, isPlaying }: AudioTextSyncProps) {
  const sentences = useMemo(() => buildSentences(content), [content]);
  const activeRef = useRef<HTMLSpanElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Determine current sentence based on time ratio
  const currentRatio =
    isPlaying && duration > 0 ? Math.min(1, Math.max(0, positionSec / duration)) : -1;

  const activeIndex =
    currentRatio >= 0
      ? sentences.findIndex(
          (s) => currentRatio >= s.startRatio && currentRatio < s.endRatio,
        )
      : -1;

  // Auto-scroll: keep the active sentence visible
  useEffect(() => {
    if (activeIndex < 0 || !activeRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const el = activeRef.current;
    const containerRect = container.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();

    // Scroll if the element is not fully visible in the container
    const isAbove = elRect.top < containerRect.top;
    const isBelow = elRect.bottom > containerRect.bottom;

    if (isAbove || isBelow) {
      el.scrollIntoView({
        block: 'center',
        behavior: 'smooth',
      });
    }
  }, [activeIndex]);

  if (sentences.length === 0) {
    return <p className="text-sm text-ink-muted">（暂无内容）</p>;
  }

  return (
    <div
      ref={containerRef}
      className="audio-sync-container relative text-sm leading-relaxed font-[var(--font-editor)]"
      style={{ lineHeight: '2.2' }}
    >
      {sentences.map((sentence, i) => {
        const isActive = i === activeIndex;
        const isPast = i < activeIndex;

        return (
          <span
            key={i}
            ref={isActive ? activeRef : undefined}
            data-sentence-index={i}
            className={`transition-colors duration-300 ease-in-out ${
              isActive
                ? 'bg-accent/15 dark:bg-accent/25 text-ink rounded-sm'
                : isPast
                  ? 'text-ink-muted'
                  : 'text-ink'
            }`}
          >
            {sentence.text}
            {/* Pulsing cursor after current sentence */}
            {isActive && isPlaying && (
              <span className="inline-block w-[2px] h-[1em] bg-accent align-text-bottom ml-[1px] animate-pulse rounded-full" />
            )}
          </span>
        );
      })}
    </div>
  );
}
