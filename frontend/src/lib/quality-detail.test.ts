import { describe, expect, it } from 'vitest';
import { normalizeQualityMetrics } from './quality-detail';

describe('normalizeQualityMetrics', () => {
  it('keeps agency and cost dimensions with Chinese labels', () => {
    const metrics = normalizeQualityMetrics({
      plot: { score: 8, reason: '主线推进清楚' },
      agency: { score: 9, reason: '主角主动选择承担风险' },
      cost: { score: 7, reason: '胜利带来后患' },
    });

    expect(metrics.map(m => m.key)).toEqual(['plot', 'agency', 'cost']);
    expect(metrics.find(m => m.key === 'agency')).toMatchObject({
      label: '主动性',
      score: 9,
      reason: '主角主动选择承担风险',
      pct: 90,
    });
    expect(metrics.find(m => m.key === 'cost')?.label).toBe('代价');
  });

  it('normalizes local 0-1 scores to display as 0-10', () => {
    const metrics = normalizeQualityMetrics({
      hook: 0.82,
      pacing: 0.6,
    });

    expect(metrics.find(m => m.key === 'hook')).toMatchObject({ score: 8.2, pct: 82 });
    expect(metrics.find(m => m.key === 'pacing')).toMatchObject({ score: 6, pct: 60 });
  });

  it('drops malformed scores instead of producing NaN', () => {
    const metrics = normalizeQualityMetrics({
      plot: { score: Number.NaN, reason: 'bad' },
      style: { reason: 'missing score' },
      emotion: 6,
    });

    expect(metrics).toHaveLength(1);
    expect(metrics[0]).toMatchObject({ key: 'emotion', score: 6 });
  });
});
