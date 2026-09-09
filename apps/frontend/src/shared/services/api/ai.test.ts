import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { aiService } from './ai';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('aiService', () => {
  it('getProviders gets /ai/providers', async () => {
    const capabilities = { providers: [{ provider: 'openai', displayName: 'OpenAI' }] };
    vi.mocked(api.get).mockResolvedValue(capabilities);

    const result = await aiService.getProviders();

    expect(api.get).toHaveBeenCalledWith('/ai/providers', undefined);
    expect(result).toBe(capabilities);
  });

  it('getConfig gets /ai/config', async () => {
    const config = { provider: 'openai', configured: true };
    vi.mocked(api.get).mockResolvedValue(config);

    const result = await aiService.getConfig();

    expect(api.get).toHaveBeenCalledWith('/ai/config', undefined);
    expect(result).toBe(config);
  });

  it('saveConfig puts the request body to /ai/config', async () => {
    const request = { provider: 'openai', apiKey: 'sk-test' };
    const response = { provider: 'openai', configured: true };
    vi.mocked(api.put).mockResolvedValue(response);

    const result = await aiService.saveConfig(request as never);

    expect(api.put).toHaveBeenCalledWith('/ai/config', request, undefined);
    expect(result).toBe(response);
  });

  it('testConfig posts the request body to /ai/test', async () => {
    const request = { provider: 'openai', apiKey: 'sk-test' };
    const response = { status: 'ok' };
    vi.mocked(api.post).mockResolvedValue(response);

    const result = await aiService.testConfig(request as never);

    expect(api.post).toHaveBeenCalledWith('/ai/test', request, undefined);
    expect(result).toBe(response);
  });

  it('query posts the request body to /ai/query', async () => {
    const request = { repositoryId: 'repo-1', message: 'What changed?' };
    const response = { message: { role: 'assistant', content: 'Nothing yet.' } };
    vi.mocked(api.post).mockResolvedValue(response);

    const result = await aiService.query(request as never);

    expect(api.post).toHaveBeenCalledWith('/ai/query', request, undefined);
    expect(result).toBe(response);
  });

  it('listConversations gets /ai/conversations with an encoded repositoryId', async () => {
    const response = { conversations: [] };
    vi.mocked(api.get).mockResolvedValue(response);

    await aiService.listConversations('repo one/two');

    expect(api.get).toHaveBeenCalledWith('/ai/conversations?repositoryId=repo%20one%2Ftwo', undefined);
  });

  it('propagates a rejected query request rather than swallowing it (e.g. no provider configured)', async () => {
    const error = new Error('no provider configured');
    vi.mocked(api.post).mockRejectedValue(error);

    await expect(aiService.query({} as never)).rejects.toBe(error);
  });
});
