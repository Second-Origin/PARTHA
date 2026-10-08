import { afterEach, describe, expect, it, vi } from 'vitest';
import { configureApiClient, getApiConfig } from './client';
import { repositoryService } from './repositories';
import { CancelledError, TimeoutError } from './errors';

const original = getApiConfig();
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); configureApiClient(original); });

describe('synchronous import transport', () => {
  it.each(['import', 'reanalyse'])('does not retry a server failure for %s', async (operation) => {
    const fetcher = vi.fn(async () => new Response('{}', { status: 500, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetcher);
    configureApiClient({ defaultRetries: 2, defaultRetryDelay: 1 });
    const result = operation === 'import' ? repositoryService.importFromGithub({ url: 'https://github.com/a/b' }, { retries: 3 }) : repositoryService.reanalyse('repo');
    await expect(result).rejects.toMatchObject({ status: 500 });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('reports timeout once even if the server operation later finishes', async () => {
    vi.useFakeTimers();
    let serverFinished = false;
    const fetcher = vi.fn((_url: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
      setTimeout(() => { serverFinished = true; }, 100);
      options.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    }));
    vi.stubGlobal('fetch', fetcher);
    const outcome = repositoryService.importFromGithub({ url: 'https://github.com/a/b' }, { timeout: 10 }).catch(error => error);
    await vi.advanceTimersByTimeAsync(10);
    expect(await outcome).toBeInstanceOf(TimeoutError);
    await vi.advanceTimersByTimeAsync(100);
    expect(serverFinished).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('does not start a cancelled request', async () => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    const controller = new AbortController();
    controller.abort();
    await expect(repositoryService.importFromGithub({ url: 'https://github.com/a/b' }, { signal: controller.signal })).rejects.toBeInstanceOf(CancelledError);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
