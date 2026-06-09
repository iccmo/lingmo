import { describe, expect, it } from 'vitest';
import { waitForNovelTaskCompletion } from './task-status';

describe('waitForNovelTaskCompletion', () => {
  it('waits through initial idle, active status, and resolves on completion', async () => {
    const statuses = [
      { status: 'idle', message: '' },
      { status: 'revising', message: '正在重写' },
      { status: 'complete', message: '完成' },
    ];

    const result = await waitForNovelTaskCompletion(
      async () => statuses.shift() ?? { status: 'complete', message: '完成' },
      { intervalMs: 0, maxPolls: 5 },
    );

    expect(result).toEqual({ status: 'complete', message: '完成' });
  });

  it('ignores stale terminal status until the new active task is observed', async () => {
    const statuses = [
      { status: 'complete', message: '上一轮完成' },
      { status: 'revising', message: '正在重写' },
      { status: 'complete', message: '本轮完成' },
    ];

    const result = await waitForNovelTaskCompletion(
      async () => statuses.shift() ?? { status: 'complete', message: '本轮完成' },
      { intervalMs: 0, maxPolls: 5 },
    );

    expect(result).toEqual({ status: 'complete', message: '本轮完成' });
  });

  it('throws friendly message when task fails', async () => {
    const statuses = [
      { status: 'revising', message: '正在重写' },
      { status: 'error', message: '修订失败' },
    ];

    await expect(waitForNovelTaskCompletion(
      async () => statuses.shift() ?? { status: 'error', message: '修订失败' },
      { intervalMs: 0, maxPolls: 2 },
    )).rejects.toThrow('修订失败');
  });
});
