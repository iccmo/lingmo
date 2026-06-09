import { describe, expect, it } from 'vitest';
import { parseApiErrorBody, throwApiError } from './api-error';

describe('parseApiErrorBody', () => {
  it('extracts FastAPI string detail', () => {
    expect(parseApiErrorBody('{"detail":"已有生成任务进行中，请等待完成"}')).toBe('已有生成任务进行中，请等待完成');
  });

  it('extracts validation messages from FastAPI detail arrays', () => {
    expect(parseApiErrorBody('{"detail":[{"msg":"Field required"},{"msg":"Input should be a string"}]}')).toBe(
      'Field required；Input should be a string',
    );
  });

  it('keeps plain text errors readable', () => {
    expect(parseApiErrorBody('No chapters')).toBe('No chapters');
  });

  it('humanizes provider token expiration details', () => {
    expect(parseApiErrorBody('{"detail":"Error code: 492 - access token expired"}')).toBe(
      '模型服务 token 已过期，请在设置页重新填写或刷新 API Key',
    );
  });

  it('humanizes provider model errors from JSON error fields', () => {
    expect(parseApiErrorBody('{"error":"model_not_found: model does not exist"}')).toBe(
      '当前模型不存在或不可用，请在设置页选择供应商支持的模型',
    );
  });

  it('uses fallback for empty bodies', () => {
    expect(parseApiErrorBody('', 'Not Found')).toBe('Not Found');
  });

  it('does not throw for ok responses', async () => {
    await expect(throwApiError(new Response('{}', { status: 200 }))).resolves.toBeUndefined();
  });

  it('throws readable FastAPI details for failed responses', async () => {
    const response = new Response('{"detail":"角色标识不能为空"}', {
      status: 400,
      statusText: 'Bad Request',
    });

    await expect(throwApiError(response)).rejects.toThrow('角色标识不能为空');
  });
});
