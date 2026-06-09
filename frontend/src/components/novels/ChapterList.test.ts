import { describe, expect, it } from 'vitest';
import { buildChapterRevisionCritique } from './ChapterList';

describe('buildChapterRevisionCritique', () => {
  it('keeps agency and cost as revision invariants', () => {
    const critique = buildChapterRevisionCritique(12, '高潮不够爽，反击太轻', '爽感');

    expect(critique).toContain('重写第12章');
    expect(critique).toContain('作者反馈：高潮不够爽，反击太轻');
    expect(critique).toContain('重点改进爽感');
    expect(critique).toContain('不得削弱主角主动选择');
    expect(critique).toContain('重要收益必须伴随具体代价');
    expect(critique).toContain('关系裂痕');
    expect(critique).toContain('高潮后至少留下一个可延续的麻烦');
  });
});
