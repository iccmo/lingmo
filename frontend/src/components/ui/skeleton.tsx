/** 骨架屏组件 — 加载中占位 */

export function Skeleton({ className = '', lines = 3 }: { className?: string; lines?: number }) {
  return (
    <div className={`space-y-3 animate-pulse ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-3 bg-surface rounded" style={{ width: `${85 - i * 10}%` }} />
      ))}
    </div>
  );
}

export function ChapterSkeleton() {
  return (
    <div className="space-y-4 p-4 animate-pulse">
      <div className="h-5 bg-surface rounded w-1/3" />
      <div className="flex gap-4">
        <div className="h-3 bg-surface rounded w-16" /><div className="h-3 bg-surface rounded w-20" />
      </div>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-3 bg-surface rounded" style={{ width: `${95 - i * 8}%` }} />
      ))}
    </div>
  );
}

export function CardSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-20 bg-surface rounded-xl animate-pulse" />
      ))}
    </div>
  );
}
