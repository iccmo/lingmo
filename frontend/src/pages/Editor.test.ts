import { describe, expect, it } from 'vitest';
import { buildExpansionEdits } from './Editor';

describe('buildExpansionEdits', () => {
  it('normalizes optional draft expansion requirements', () => {
    expect(buildExpansionEdits('  让主角主动押注，突破留下债务  ')).toBe(
      '扩写时必须执行以下作者补充要求：让主角主动押注，突破留下债务',
    );
  });

  it('does not send empty expansion edits', () => {
    expect(buildExpansionEdits('   ')).toBe('');
  });
});
