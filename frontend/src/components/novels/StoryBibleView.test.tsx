import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StoryBibleView } from './StoryBibleView';

const toast = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
}));

vi.mock('sonner', () => ({ toast }));
vi.mock('./ConsistencyScoreView', () => ({
  ConsistencyScoreView: () => <div data-testid="consistency-score" />,
}));

const storyBible = {
  characters: [],
  foreshadowing: [
    {
      id: 7,
      description: '玉佩裂开',
      created_chapter: 1,
      due_by_chapter: 3,
      status: 'active',
    },
  ],
  timeline: [],
  consistency_log: [],
};

function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

function mockInitialFetch(postResponse = jsonResponse({ ok: true })) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === 'POST') return postResponse;
    if (url.includes('/story-bible')) return jsonResponse(storyBible);
    if (url.includes('/reader-state')) return jsonResponse(null);
    if (url.includes('/counterpoint')) return jsonResponse(null);
    return jsonResponse({});
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('StoryBibleView foreshadowing resolve', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    toast.error.mockReset();
    toast.success.mockReset();
  });

  it('rejects invalid chapter input before posting to the API', async () => {
    const fetchMock = mockInitialFetch();
    vi.spyOn(window, 'prompt').mockReturnValue('第三章');

    render(<StoryBibleView novelId="book" />);
    fireEvent.click(await screen.findByText('回收'));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('请输入有效章节号'));
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining('/foreshadowing/7/resolve'),
      expect.anything(),
    );
  });

  it('marks a foreshadowing thread as resolved without reloading the page', async () => {
    const fetchMock = mockInitialFetch();
    vi.spyOn(window, 'prompt').mockReturnValue('3');

    render(<StoryBibleView novelId="book" />);
    fireEvent.click(await screen.findByText('回收'));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('伏笔已标记回收'));
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/novels/book/foreshadowing/7/resolve',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ chapter_num: 3, text: '' }),
      }),
    );
    expect(screen.queryByText('回收')).not.toBeInTheDocument();
  });
});
