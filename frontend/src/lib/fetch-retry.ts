/**
 * Fetch wrapper with automatic retry and timeout.
 */
export async function fetchWithRetry(
  url: string,
  options?: RequestInit,
  retries = 2,
  timeoutMs = 30000,
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);

      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });

      clearTimeout(timer);

      if (!response.ok && attempt < retries && response.status >= 500) {
        // Server error, retry after backoff
        await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
        continue;
      }

      return response;
    } catch (e: unknown) {
      lastError = e as Error;
      if (attempt < retries) {
        // Network error, retry after backoff
        await new Promise(r => setTimeout(r, 800 * (attempt + 1)));
      }
    }
  }

  throw lastError || new Error('Fetch failed after retries');
}

/** Simple offline detection */
export function useOnlineStatus(): boolean {
  if (typeof navigator === 'undefined') return true;
  return navigator.onLine;
}
