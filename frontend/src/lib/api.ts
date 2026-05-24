import type { NovelSummary, NovelDetail, DraftOption, SystemStatus, PublishResult } from 'src/types';

const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  novels: {
    list:      () => get<NovelSummary[]>('/novels'),
    get:       (id: string) => get<NovelDetail>(`/novels/${id}`),
    create:    (d: Record<string, unknown>) => post<NovelSummary>('/novels', d),
    generate:  (id: string) => post(`/novels/${id}/generate`),
    publish:   (id: string) => post<PublishResult>(`/novels/${id}/publish`),
    draft:     (id: string, input: string) => post<{ directions: DraftOption[] }>(`/novels/${id}/draft`, { input }),
    expand:    (id: string, chosenId: string, draft?: { direction: string; preview: string; hook: string }, edits?: string) =>
      post<{ title: string; body: string }>(`/novels/${id}/expand`, { chosen_id: chosenId, direction: draft?.direction, preview: draft?.preview, hook: draft?.hook, edits }),
    chapter:   (id: string, n: number) => get<{ number: number; content: string }>(`/novels/${id}/chapters/${n}`),
    saveChapter: (id: string, n: number, content: string) => put(`/novels/${id}/chapters/${n}`, { content }),
    autoStart: (id: string) => post(`/novels/${id}/auto/start`),
    autoStop:  (id: string) => post(`/novels/${id}/auto/stop`),
    autoOnce:  (id: string) => post(`/novels/${id}/auto/once`),
  },
  status: () => get<SystemStatus>('/status'),
};
