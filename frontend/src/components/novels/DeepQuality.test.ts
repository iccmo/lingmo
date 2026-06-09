import { describe, expect, it } from 'vitest';
import { analyzeDeep, buildDeepRevisionCritique } from './DeepQuality';

describe('analyzeDeep', () => {
  it('flags chapters where gains lack agency and cost', () => {
    const metrics = analyzeDeep('叶凡只能接受安排。他只好获得神丹，突破成功，赢下胜利。众人称赞他。');

    expect(metrics.agencyScore).toBeLessThan(60);
    expect(metrics.costScore).toBeLessThan(65);
    expect(metrics.suggestions).toContain('主角主动性不足——让主角在压力下做一个明确选择，并承担选择后果');
    expect(metrics.suggestions).toContain('胜利代价偏轻——每次获得都要留下伤口、债务、暴露风险或关系裂痕');
  });

  it('rewards choices with consequences', () => {
    const metrics = analyzeDeep('叶凡决定主动拒绝退让，亲自站出来反击。他押上线索救下同伴，却因此受伤流血，欠下债务，还暴露了身份。');

    expect(metrics.agencyScore).toBeGreaterThanOrEqual(80);
    expect(metrics.costScore).toBeGreaterThanOrEqual(80);
    expect(metrics.suggestions).toContain('主角主动性强，剧情由选择推动而不是被事件推着走');
    expect(metrics.suggestions).toContain('代价兑现充分，爽点有后患，读者会相信胜利来之不易');
  });

  it('turns low agency and cost diagnostics into revision critique', () => {
    const metrics = analyzeDeep('叶凡只能接受安排。他只好获得神丹，突破成功，赢下胜利。众人称赞他。');
    const suggestion = metrics.suggestions.find(s => s.includes('代价偏轻'))!;

    const { dimension, critique } = buildDeepRevisionCritique(7, metrics, suggestion);

    expect(dimension).toBe('胜利代价偏轻');
    expect(critique).toContain('重写第7章');
    expect(critique).toContain('补强主角主动性');
    expect(critique).toContain('清晰选择');
    expect(critique).toContain('补强胜利代价');
    expect(critique).toContain('受伤流血');
    expect(critique).toContain('关系裂痕');
    expect(critique).toContain(suggestion);
  });
});
