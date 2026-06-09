export type QualityDetailValue = number | {
  score?: number | null;
  reason?: string | null;
};

export type QualityDetail = Record<string, QualityDetailValue>;

export interface QualityMetric {
  key: string;
  label: string;
  score: number;
  reason: string;
  pct: number;
}

const QUALITY_DIMENSION_LABELS: Record<string, string> = {
  plot: '剧情',
  character: '人物',
  style: '文风',
  emotion: '情绪',
  theme: '主题',
  soul: '灵魂',
  coherence: '连贯',
  consistency: '一致',
  pacing: '节奏',
  hook: '钩子',
  readability: '可读',
  show_dont_tell: '展示',
  formatting: '排版',
  antagonist: '反派',
  agency: '主动性',
  cost: '代价',
};

const QUALITY_DIMENSION_ORDER = [
  'plot',
  'character',
  'style',
  'emotion',
  'theme',
  'soul',
  'coherence',
  'consistency',
  'pacing',
  'hook',
  'readability',
  'show_dont_tell',
  'formatting',
  'antagonist',
  'agency',
  'cost',
];

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

function normalizeScore(raw: number): { score: number; pct: number } {
  const score = raw <= 1 ? raw * 10 : raw;
  return {
    score: clamp(score, 0, 10),
    pct: clamp(score * 10, 0, 100),
  };
}

function parseMetric(key: string, value: QualityDetailValue): QualityMetric | null {
  const rawScore = typeof value === 'number' ? value : value?.score;
  if (typeof rawScore !== 'number' || !Number.isFinite(rawScore)) return null;

  const { score, pct } = normalizeScore(rawScore);
  return {
    key,
    label: QUALITY_DIMENSION_LABELS[key] ?? key,
    score,
    reason: typeof value === 'object' ? value.reason ?? '' : '',
    pct,
  };
}

export function normalizeQualityMetrics(detail?: QualityDetail | null): QualityMetric[] {
  if (!detail) return [];

  const order = new Map(QUALITY_DIMENSION_ORDER.map((key, index) => [key, index]));
  return Object.entries(detail)
    .map(([key, value]) => parseMetric(key, value))
    .filter((metric): metric is QualityMetric => metric !== null)
    .sort((a, b) => {
      const aOrder = order.get(a.key) ?? Number.MAX_SAFE_INTEGER;
      const bOrder = order.get(b.key) ?? Number.MAX_SAFE_INTEGER;
      if (aOrder !== bOrder) return aOrder - bOrder;
      return a.key.localeCompare(b.key);
    });
}
