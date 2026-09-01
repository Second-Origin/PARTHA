/**
 * Unit tests for the waitlist serverless function (#382). Run with
 * `npm run test` (node's built-in test runner + tsx loader) -- no real
 * network call is ever made; `global.fetch` is replaced with a fake that
 * only understands the exact GitHub Gist requests this handler issues.
 */

import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it, mock } from 'node:test';
import handler, { type WaitlistRequest, type WaitlistResponse } from './waitlist.ts';

interface JsonErrorBody {
  error?: string;
  message?: string;
}

interface JsonOkBody {
  ok?: boolean;
}

function fakeGitHubResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return { ok, status, json: async () => body };
}

function makeRes(): { res: WaitlistResponse; calls: { status?: number; json?: unknown } } {
  const calls: { status?: number; json?: unknown } = {};
  const res: WaitlistResponse = {
    status(code: number) {
      calls.status = code;
      return res;
    },
    json(body: unknown) {
      calls.json = body;
    },
    setHeader() {},
  };
  return { res, calls };
}

function request(overrides: WaitlistRequest): WaitlistRequest {
  return { method: 'POST', ...overrides };
}

describe('POST /api/waitlist', () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    process.env.WAITLIST_GITHUB_TOKEN = 'fake-token-not-real';
    process.env.WAITLIST_GIST_ID = 'fake-gist-id';
  });

  afterEach(() => {
    process.env = { ...originalEnv };
    mock.reset();
  });

  it('rejects non-POST methods', async () => {
    const { res, calls } = makeRes();
    await handler(request({ method: 'GET' }), res);
    assert.equal(calls.status, 405);
  });

  it('returns 503 when the env vars are not configured', async () => {
    delete process.env.WAITLIST_GITHUB_TOKEN;
    const { res, calls } = makeRes();
    await handler(request({ body: { email: 'a@example.com' } }), res);
    assert.equal(calls.status, 503);
    assert.equal((calls.json as JsonErrorBody).error, 'waitlist_unconfigured');
  });

  it('rejects a missing or malformed email', async () => {
    const { res, calls } = makeRes();
    await handler(request({ body: { email: 'not-an-email' } }), res);
    assert.equal(calls.status, 400);
    assert.equal((calls.json as JsonErrorBody).error, 'invalid_email');
  });

  it('silently accepts (without storing) a submission with the honeypot field filled in', async () => {
    const fetchMock = mock.fn(async () => {
      throw new Error('fetch must not be called for a honeypot submission');
    });
    mock.method(globalThis, 'fetch', fetchMock);

    const { res, calls } = makeRes();
    await handler(request({ body: { email: 'a@example.com', company: 'a bot filled this in' } }), res);
    assert.equal(calls.status, 200);
    assert.equal(fetchMock.mock.callCount(), 0);
  });

  it('appends a valid submission to the Gist, deduping by email', async () => {
    const existing = [{ email: 'existing@example.com', name: null, submittedAt: '2026-01-01T00:00:00.000Z' }];
    const fetchMock = mock.fn(async (url: string | URL, init?: RequestInit) => {
      if (!init || init.method === undefined) {
        // GET
        assert.match(String(url), /\/gists\/fake-gist-id$/);
        return fakeGitHubResponse({ files: { 'waitlist.json': { content: JSON.stringify(existing) } } });
      }
      // PATCH
      assert.equal(init.method, 'PATCH');
      const payload = JSON.parse(String(init.body));
      const rows = JSON.parse(payload.files['waitlist.json'].content);
      assert.equal(rows.length, 2);
      assert.equal(rows[1].email, 'new@example.com');
      assert.equal(rows[1].name, 'New Person');
      return fakeGitHubResponse({ ok: true });
    });
    mock.method(globalThis, 'fetch', fetchMock);

    const { res, calls } = makeRes();
    await handler(request({ body: { email: 'New@Example.com', name: 'New Person' } }), res);
    assert.equal(calls.status, 200);
    assert.equal((calls.json as JsonOkBody).ok, true);
    assert.equal(fetchMock.mock.callCount(), 2);
  });

  it('returns 502 if the GitHub API call fails', async () => {
    mock.method(globalThis, 'fetch', async () => fakeGitHubResponse(null, false, 401));

    const { res, calls } = makeRes();
    await handler(request({ body: { email: 'a@example.com' } }), res);
    assert.equal(calls.status, 502);
    assert.equal((calls.json as JsonErrorBody).error, 'waitlist_storage_failed');
  });
});
