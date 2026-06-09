export interface BatchCompletionSource {
  status: string;
  message?: string | null;
  last_error?: string | null;
}

export interface BatchCompletionNotice {
  kind: 'success' | 'warning';
  message: string;
}

function partialDetail(source: BatchCompletionSource): string {
  const fallback = source.last_error || '';
  if (fallback.trim()) return fallback.trim();

  const message = (source.message || '').trim();
  if (!message) return '';

  const isPartial =
    message.includes('已跳过') ||
    message.includes('内容为空') ||
    /完成：\d+\/\d+章/.test(message);

  return isPartial ? message : '';
}

export function getBatchCompletionNotice(
  source: BatchCompletionSource,
  elapsedSeconds?: number,
): BatchCompletionNotice {
  const detail = partialDetail(source);
  if (detail) {
    return { kind: 'warning', message: detail };
  }

  const elapsed = typeof elapsedSeconds === 'number' ? `耗时${elapsedSeconds}秒` : '';
  return { kind: 'success', message: `批量生成完成！${elapsed}` };
}
