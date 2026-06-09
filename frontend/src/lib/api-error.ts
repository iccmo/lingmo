import { humanizeError } from './error-messages';

function detailToMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'msg' in item) return String(item.msg);
        return '';
      })
      .filter(Boolean);
    return messages.join('；');
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: unknown }).message);
  }
  return '';
}

export function parseApiErrorBody(body: string, fallback = '请求失败'): string {
  const text = body.trim();
  if (!text) return fallback;

  const friendly = (message: string): string => {
    const mapped = humanizeError(message);
    return mapped.message !== message ? mapped.message : message;
  };

  try {
    const parsed = JSON.parse(text) as { detail?: unknown; message?: unknown; error?: unknown };
    return friendly(
      detailToMessage(parsed.detail) ||
      detailToMessage(parsed.message) ||
      detailToMessage(parsed.error) ||
      text,
    );
  } catch {
    return friendly(text);
  }
}

export async function responseErrorMessage(response: Response): Promise<string> {
  const fallback = response.statusText || `HTTP ${response.status}`;
  const body = await response.text().catch(() => '');
  return parseApiErrorBody(body, fallback);
}

export async function throwApiError(response: Response): Promise<void> {
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
}
