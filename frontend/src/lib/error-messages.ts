/** Map technical error patterns to user-friendly Chinese messages. */

const ERROR_MAP: Array<{ pattern: RegExp; message: string; severity: 'error' | 'warning' | 'info' }> = [
  { pattern: /timeout|timed out|Timeout/i, message: '请求超时，模型响应过慢，请稍后重试', severity: 'warning' },
  { pattern: /492|token.*expired|expired.*token|access token|token.*过期|令牌.*过期/i, message: '模型服务 token 已过期，请在设置页重新填写或刷新 API Key', severity: 'error' },
  { pattern: /401|unauthorized|Invalid.*key|Incorrect.*key|authentication|api key not found|no api key|missing api key|密钥无效|未配置.*api key/i, message: 'API Key 无效，请在设置页更新密钥', severity: 'error' },
  { pattern: /403|forbidden|permission denied/i, message: 'API Key 无权限访问该模型，请检查供应商、模型或账户权限', severity: 'error' },
  { pattern: /model_not_found|model.*not found|model.*does not exist|模型不存在/i, message: '当前模型不存在或不可用，请在设置页选择供应商支持的模型', severity: 'error' },
  { pattern: /429|rate.?limit|too many requests/i, message: '请求过于频繁，请稍等片刻再试', severity: 'warning' },
  { pattern: /500|internal server error/i, message: '模型服务暂时不可用，正在重试...', severity: 'warning' },
  { pattern: /503|service unavailable/i, message: '模型服务繁忙，请稍后重试', severity: 'warning' },
  { pattern: /quota|insufficient|insufficient_quota|billing/i, message: 'API 额度不足，请检查账户余额', severity: 'error' },
  { pattern: /context length|token.*exceed|maximum context/i, message: '内容过长超出模型限制，系统已自动压缩', severity: 'info' },
  { pattern: /connection|network|ECONNREFUSED|ENOTFOUND|fetch failed/i, message: '网络连接失败，请检查网络状态', severity: 'error' },
  { pattern: /content.*empty|empty.*content|返回.*空|empty response/i, message: '模型返回内容为空，请检查 API 配置或重试', severity: 'warning' },
  { pattern: /overloaded/i, message: '模型负载过高，请稍后重试', severity: 'warning' },
];

export interface FriendlyError {
  message: string;
  severity: 'error' | 'warning' | 'info';
  original: string;
}

export function humanizeError(raw: string): FriendlyError {
  for (const entry of ERROR_MAP) {
    if (entry.pattern.test(raw)) {
      return { message: entry.message, severity: entry.severity, original: raw };
    }
  }
  // Fallback: keep original but mark as technical
  return {
    message: raw || '未知错误',
    severity: 'error',
    original: raw,
  };
}

/** Format a generation status error for display in the UI. */
export function genErrorMessage(statusMessage: string): string {
  const { message } = humanizeError(statusMessage);
  // Truncate very long messages
  return message.length > 200 ? message.slice(0, 197) + '...' : message;
}
