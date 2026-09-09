import { afterEach, describe, expect, it, vi } from 'vitest';

async function loadFrontendEnv(apiUrl: string | undefined) {
  vi.stubEnv('VITE_API_URL', apiUrl ?? '');
  vi.resetModules();
  const { frontendEnv } = await import('./env');
  return frontendEnv;
}

describe('frontendEnv.apiUrl', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('uses the explicit VITE_API_URL when set', async () => {
    const env = await loadFrontendEnv('https://api.example.com');
    expect(env.apiUrl).toBe('https://api.example.com');
  });

  it('strips any path/query from an explicit URL down to its origin', async () => {
    const env = await loadFrontendEnv('https://api.example.com/some/path?x=1');
    expect(env.apiUrl).toBe('https://api.example.com');
  });

  it('falls back to localhost:8000 in dev when unset', async () => {
    const env = await loadFrontendEnv(undefined);
    expect(env.apiUrl).toBe('http://localhost:8000');
  });

  it('falls back to localhost:8000 in dev on an invalid URL', async () => {
    const env = await loadFrontendEnv('not a url');
    expect(env.apiUrl).toBe('http://localhost:8000');
  });

  it('falls back to same-origin (empty string) in production when unset', async () => {
    vi.stubEnv('PROD', true);
    const env = await loadFrontendEnv(undefined);
    expect(env.apiUrl).toBe('');
  });

  it('falls back to same-origin in production on an invalid URL too', async () => {
    vi.stubEnv('PROD', true);
    const env = await loadFrontendEnv('not a url');
    expect(env.apiUrl).toBe('');
  });

  it('still honors an explicit VITE_API_URL in production', async () => {
    vi.stubEnv('PROD', true);
    const env = await loadFrontendEnv('https://api.example.com');
    expect(env.apiUrl).toBe('https://api.example.com');
  });
});
