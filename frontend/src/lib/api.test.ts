import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';

describe('api.novels.reviseChapter', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('posts critique to the current chapter revise endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'revising', novel_id: 'book', chapter: 3 }),
    } as Response);

    const result = await api.novels.reviseChapter('book', 3, '补主角主动选择和代价');

    expect(result).toEqual({ status: 'revising', novel_id: 'book', chapter: 3 });
    expect(fetchMock).toHaveBeenCalledWith('/api/novels/book/chapters/3/revise', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ critique: '补主角主动选择和代价' }),
    });
  });
});
