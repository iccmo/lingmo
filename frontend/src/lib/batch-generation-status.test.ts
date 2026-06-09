import { describe, expect, it } from 'vitest';
import { getBatchCompletionNotice } from './batch-generation-status';

describe('getBatchCompletionNotice', () => {
  it('returns success with elapsed seconds for a clean completion', () => {
    expect(getBatchCompletionNotice({ status: 'complete' }, 12)).toEqual({
      kind: 'success',
      message: '批量生成完成！耗时12秒',
    });
  });

  it('returns warning when queue polling reports a partial completion detail', () => {
    expect(getBatchCompletionNotice({
      status: 'done',
      last_error: '批量生成完成：1/2章（第1章内容为空，已跳过）',
    })).toEqual({
      kind: 'warning',
      message: '批量生成完成：1/2章（第1章内容为空，已跳过）',
    });
  });

  it('returns warning when SSE completion message says a chapter was skipped', () => {
    expect(getBatchCompletionNotice({
      status: 'complete',
      message: '批量生成完成：1/2章（第1章内容为空，已跳过）',
    }, 20)).toEqual({
      kind: 'warning',
      message: '批量生成完成：1/2章（第1章内容为空，已跳过）',
    });
  });
});
