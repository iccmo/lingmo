/** 类型安全 API 客户端 — 基于 openapi-typescript 自动生成。
 *
 * 使用方式：
 *   import { api } from 'src/lib/api-client';
 *   const novels = await api.novels.list();  // 自动推断返回类型
 */

const BASE = '';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(await res.text().catch(() => res.statusText));
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text().catch(() => res.statusText));
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text().catch(() => res.statusText));
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text().catch(() => res.statusText));
  return res.json();
}

// ── Typed API ──

export const api = {
  novels: {
    list:   () => get<any[]>('/api/novels'),
    get:    (id: string) => get<any>(`/api/novels/${id}`),
    create: (data: Record<string, unknown>) => post<any>('/api/novels', data),
    delete: (id: string) => del<any>(`/api/novels/${id}`),
    chapter: (id: string, n: number) => get<any>(`/api/novels/${id}/chapters/${n}`),
    saveChapter: (id: string, n: number, content: string) =>
      put<any>(`/api/novels/${id}/chapters/${n}`, { content }),
    generate: (id: string) => post(`/api/novels/${id}/generate`),
    generateBatch: (id: string, count: number, qualityThreshold: number) =>
      post(`/api/novels/${id}/generate-batch`, { count, quality_threshold: qualityThreshold }),
    queueStatus: (id: string) => get(`/api/novels/${id}/generate/queue-status`),
  },
  system: {
    status: () => get<any>('/api/status'),
    health: () => get<any>('/api/v2/health'),
  },
};

export type { paths as ApiPaths } from './api-types';
