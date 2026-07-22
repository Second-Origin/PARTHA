import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, configureApiClient, getApiConfig } from './client';
import { ApiError } from './errors';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('api client 401 handling', () => {
  const baseConfig = getApiConfig();

  beforeEach(() => {
    configureApiClient({ ...baseConfig, getAuthToken: () => 'stale-token', refreshSession: undefined, onUnauthorized: undefined });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    configureApiClient(baseConfig);
  });

  it('shares one in-flight refresh across concurrent 401s and retries each request exactly once', async () => {
    let authorized = false;
    const refreshSession = vi.fn(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
      authorized = true;
      return true;
    });
    const onUnauthorized = vi.fn();

    const fetchMock = vi.fn(async () =>
      authorized ? jsonResponse(200, { ok: true }) : jsonResponse(401, { code: 'unauthorized', message: 'expired' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    configureApiClient({ refreshSession, onUnauthorized });

    const results = await Promise.all([
      api.get('/repositories'),
      api.get('/repositories'),
      api.get('/repositories'),
    ]);

    expect(refreshSession).toHaveBeenCalledTimes(1);
    expect(onUnauthorized).not.toHaveBeenCalled();
    results.forEach((result) => expect(result).toEqual({ ok: true }));
  });

  it('gives up after one failed refresh instead of retrying indefinitely', async () => {
    const refreshSession = vi.fn(async () => false);
    const onUnauthorized = vi.fn();
    const fetchMock = vi.fn(async () => jsonResponse(401, { code: 'unauthorized', message: 'expired' }));
    vi.stubGlobal('fetch', fetchMock);
    configureApiClient({ refreshSession, onUnauthorized });

    await expect(api.get('/repositories')).rejects.toBeInstanceOf(ApiError);

    expect(refreshSession).toHaveBeenCalledTimes(1);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    // The refresh failed, so there's nothing worth retrying with — exactly
    // the one original attempt, no retry loop.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('never refreshes for the auth endpoints themselves', async () => {
    const refreshSession = vi.fn(async () => true);
    const onUnauthorized = vi.fn();
    const fetchMock = vi.fn(async () => jsonResponse(401, { code: 'unauthorized', message: 'bad credentials' }));
    vi.stubGlobal('fetch', fetchMock);
    configureApiClient({ refreshSession, onUnauthorized });

    await expect(api.post('/auth/login', { email: 'a@b.com', password: 'x' })).rejects.toBeInstanceOf(ApiError);

    expect(refreshSession).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does not invalidate an existing session on a failed login or register attempt', async () => {
    // A wrong password or a duplicate email is a guest-only failure — it must
    // surface as a form error, not clear some OTHER already-authenticated
    // session (e.g. a user who opens /login in a second tab while still
    // signed in elsewhere).
    const onUnauthorized = vi.fn();
    const fetchMock = vi.fn(async () => jsonResponse(401, { code: 'unauthorized', message: 'bad credentials' }));
    vi.stubGlobal('fetch', fetchMock);
    configureApiClient({ onUnauthorized });

    await expect(api.post('/auth/login', { email: 'a@b.com', password: 'wrong' })).rejects.toBeInstanceOf(ApiError);
    await expect(api.post('/auth/register', { email: 'a@b.com', password: 'x' })).rejects.toBeInstanceOf(ApiError);

    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('still reports a failed refresh or logout through onUnauthorized (unlike login/register)', async () => {
    const onUnauthorized = vi.fn();
    const fetchMock = vi.fn(async () => jsonResponse(401, { code: 'unauthorized', message: 'invalid refresh token' }));
    vi.stubGlobal('fetch', fetchMock);
    configureApiClient({ onUnauthorized });

    await expect(api.post('/auth/refresh')).rejects.toBeInstanceOf(ApiError);
    await expect(api.post('/auth/logout')).rejects.toBeInstanceOf(ApiError);

    expect(onUnauthorized).toHaveBeenCalledTimes(2);
  });
});
