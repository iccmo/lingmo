import {
  isActiveGenerationStatus,
  isCompletedGenerationStatus,
  isFailedGenerationStatus,
} from './generation-status';

export interface NovelTaskStatus {
  status?: string | null;
  message?: string | null;
}

interface WaitOptions {
  intervalMs?: number;
  maxPolls?: number;
  requireActive?: boolean;
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => window.setTimeout(resolve, ms));
}

export async function waitForNovelTaskCompletion(
  fetchStatus: () => Promise<NovelTaskStatus>,
  options: WaitOptions = {},
): Promise<NovelTaskStatus> {
  const intervalMs = options.intervalMs ?? 2000;
  const maxPolls = options.maxPolls ?? 150;
  const requireActive = options.requireActive ?? true;
  let sawActive = false;

  for (let poll = 0; poll < maxPolls; poll++) {
    const status = await fetchStatus();
    if (isFailedGenerationStatus(status) && (!requireActive || sawActive)) {
      throw new Error(status.message || '任务失败');
    }
    if (isCompletedGenerationStatus(status) && (!requireActive || sawActive)) return status;

    if (isActiveGenerationStatus(status)) {
      sawActive = true;
    } else if (!requireActive || sawActive) {
      return status;
    }

    if (intervalMs > 0) await delay(intervalMs);
  }

  throw new Error('任务超时，请稍后刷新查看结果');
}
