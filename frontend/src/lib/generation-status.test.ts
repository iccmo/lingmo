import { describe, expect, it } from 'vitest';
import {
  equalIdSets,
  isActiveGenerationQueueStatus,
  isActiveGenerationStatus,
  isCompletedGenerationStatus,
  isFailedGenerationStatus,
  queueStatusToActiveGenerationStatus,
} from './generation-status';

describe('isActiveGenerationStatus', () => {
  it('treats running generation phases as active', () => {
    expect(isActiveGenerationStatus({ status: 'generating' })).toBe(true);
    expect(isActiveGenerationStatus({ status: 'reviewing' })).toBe(true);
    expect(isActiveGenerationStatus({ status: 'running' })).toBe(true);
  });

  it('treats terminal and empty states as inactive', () => {
    expect(isActiveGenerationStatus({ status: 'complete' })).toBe(false);
    expect(isActiveGenerationStatus({ status: 'done' })).toBe(false);
    expect(isActiveGenerationStatus({ status: 'error' })).toBe(false);
    expect(isActiveGenerationStatus({ status: '' })).toBe(false);
    expect(isActiveGenerationStatus(null)).toBe(false);
  });
});

describe('generation queue status helpers', () => {
  it('treats queued and running batch jobs as active', () => {
    expect(isActiveGenerationQueueStatus({ job_id: 'a', status: 'queued' })).toBe(true);
    expect(isActiveGenerationQueueStatus({ job_id: 'a', status: 'running' })).toBe(true);
  });

  it('treats idle and recent terminal batch jobs as inactive', () => {
    expect(isActiveGenerationQueueStatus({ job_id: null, status: 'idle' })).toBe(false);
    expect(isActiveGenerationQueueStatus({ job_id: 'a', status: 'done' })).toBe(false);
    expect(isActiveGenerationQueueStatus({ job_id: 'a', status: 'error' })).toBe(false);
    expect(isActiveGenerationQueueStatus(null)).toBe(false);
  });

  it('converts an active queue job into a writer generation status', () => {
    expect(queueStatusToActiveGenerationStatus({
      job_id: 'a',
      status: 'running',
      progress: { current: 2, total: 5 },
      last_error: null,
    })).toEqual({
      status: 'running',
      message: '批量生成进行中（2/5章）',
      progress: 40,
    });
  });

  it('does not convert terminal queue jobs into writer generation status', () => {
    expect(queueStatusToActiveGenerationStatus({
      job_id: 'a',
      status: 'done',
      progress: { current: 5, total: 5 },
      last_error: null,
    })).toBeNull();
  });
});

describe('terminal generation status helpers', () => {
  it('recognizes completion aliases', () => {
    expect(isCompletedGenerationStatus({ status: 'complete' })).toBe(true);
    expect(isCompletedGenerationStatus({ status: 'done' })).toBe(true);
    expect(isCompletedGenerationStatus({ status: 'finished' })).toBe(true);
    expect(isCompletedGenerationStatus({ status: 'generating' })).toBe(false);
  });

  it('recognizes failure aliases', () => {
    expect(isFailedGenerationStatus({ status: 'error' })).toBe(true);
    expect(isFailedGenerationStatus({ status: 'failed' })).toBe(true);
    expect(isFailedGenerationStatus({ status: 'complete' })).toBe(false);
  });
});

describe('equalIdSets', () => {
  it('compares id sets by value', () => {
    expect(equalIdSets(new Set(['a', 'b']), new Set(['b', 'a']))).toBe(true);
    expect(equalIdSets(new Set(['a']), new Set(['a', 'b']))).toBe(false);
    expect(equalIdSets(new Set(['a']), new Set(['b']))).toBe(false);
  });
});
