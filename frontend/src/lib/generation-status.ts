export interface GenerationStatusLike {
  status?: string | null;
}

export interface GenerationQueueStatusLike {
  job_id?: string | null;
  status?: string | null;
  progress?: {
    current?: number | null;
    total?: number | null;
  } | null;
  last_error?: string | null;
}

export interface ActiveQueueGenerationStatus {
  status: 'running';
  message: string;
  progress: number;
}

const INACTIVE_STATUSES = new Set([
  '',
  'idle',
  'complete',
  'done',
  'error',
  'failed',
  'finished',
]);

const COMPLETED_STATUSES = new Set(['complete', 'done', 'finished']);
const FAILED_STATUSES = new Set(['error', 'failed']);
const ACTIVE_QUEUE_STATUSES = new Set(['queued', 'running']);

function normalizedStatus(source: GenerationStatusLike | null | undefined): string {
  return (source?.status || '').trim().toLowerCase();
}

export function isActiveGenerationStatus(source: GenerationStatusLike | null | undefined): boolean {
  const status = normalizedStatus(source);
  return !INACTIVE_STATUSES.has(status);
}

export function isCompletedGenerationStatus(source: GenerationStatusLike | null | undefined): boolean {
  return COMPLETED_STATUSES.has(normalizedStatus(source));
}

export function isFailedGenerationStatus(source: GenerationStatusLike | null | undefined): boolean {
  return FAILED_STATUSES.has(normalizedStatus(source));
}

export function isActiveGenerationQueueStatus(source: GenerationQueueStatusLike | null | undefined): boolean {
  return ACTIVE_QUEUE_STATUSES.has(normalizedStatus(source));
}

function queueProgress(source: GenerationQueueStatusLike): number {
  const status = normalizedStatus(source);
  if (status === 'queued') return 5;

  const current = source.progress?.current ?? 0;
  const total = source.progress?.total ?? 0;
  if (total <= 0) return 15;

  const pct = Math.round((current / total) * 100);
  return Math.min(95, Math.max(10, pct));
}

function queueMessage(source: GenerationQueueStatusLike): string {
  const status = normalizedStatus(source);
  const current = source.progress?.current ?? 0;
  const total = source.progress?.total ?? 0;
  const suffix = total > 0 ? `（${current}/${total}章）` : '';

  if (status === 'queued') return `批量生成排队中${suffix}`;
  return `批量生成进行中${suffix}`;
}

export function queueStatusToActiveGenerationStatus(
  source: GenerationQueueStatusLike | null | undefined,
): ActiveQueueGenerationStatus | null {
  if (!source) return null;
  if (!isActiveGenerationQueueStatus(source)) return null;
  return {
    status: 'running',
    message: queueMessage(source),
    progress: queueProgress(source),
  };
}

export function equalIdSets(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false;
  for (const id of a) {
    if (!b.has(id)) return false;
  }
  return true;
}
