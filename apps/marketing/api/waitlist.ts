/**
 * Waitlist submission endpoint (#382), deployed by Vercel as a serverless
 * function at /api/waitlist.
 *
 * No live Postgres to write to (the real backend is paused, not deployed --
 * see #375/#377). Instead of introducing a new third-party account nobody
 * has yet, this appends each submission to a private GitHub Gist using a
 * fine-grained Personal Access Token -- both GitHub and Vercel are
 * platforms the project already has accounts on, this needs no new
 * service, and a Gist has no realistic volume limit for a waitlist.
 *
 * Required environment variables (set in the Vercel project's Environment
 * Variables, never committed):
 *   WAITLIST_GITHUB_TOKEN -- a fine-grained PAT with read/write access to
 *     exactly one Gist (Gists -> Read and write). Create it at
 *     https://github.com/settings/personal-access-tokens/new
 *   WAITLIST_GIST_ID -- the id of that Gist (the segment after the last
 *     slash in its URL). Create an empty secret Gist first, containing one
 *     file named waitlist.json with the content "[]".
 *
 * If either is unset, this returns 503 rather than silently dropping
 * submissions or crashing -- see apps/marketing/README.md for the one-time
 * setup steps.
 *
 * Typed against a minimal local interface (below) rather than importing
 * @vercel/node for VercelRequest/VercelResponse: Vercel's actual runtime
 * behavior (JSON body parsing onto `.body`, the `.status().json()` response
 * helpers) is unaffected by which types this file imports -- it's a
 * platform behavior, not something the npm package provides at runtime --
 * and @vercel/node pulls in a deep, currently-vulnerable dev-only
 * dependency chain (ajv/path-to-regexp/undici via @vercel/static-config)
 * purely for type declarations this file doesn't need more than a few
 * lines of.
 */

// Exported so tests can construct properly-typed requests/responses instead
// of casting through `any`.
export interface WaitlistRequest {
  method?: string;
  body?: unknown;
}

export interface WaitlistResponse {
  status(code: number): WaitlistResponse;
  json(body: unknown): void;
  setHeader(name: string, value: string): void;
}

const GIST_FILENAME = 'waitlist.json';
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MAX_EMAIL_LENGTH = 320;
const MAX_NAME_LENGTH = 200;

interface WaitlistEntry {
  email: string;
  name: string | null;
  submittedAt: string;
}

function isValidBody(body: unknown): body is { email: string; name?: string; company?: string } {
  if (typeof body !== 'object' || body === null) return false;
  const record = body as Record<string, unknown>;
  return typeof record.email === 'string';
}

export default async function handler(req: WaitlistRequest, res: WaitlistResponse) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'method_not_allowed', message: 'Use POST.' });
  }

  const token = process.env.WAITLIST_GITHUB_TOKEN;
  const gistId = process.env.WAITLIST_GIST_ID;
  if (!token || !gistId) {
    return res.status(503).json({
      error: 'waitlist_unconfigured',
      message: 'The waitlist is not configured yet. Please try again later.',
    });
  }

  if (!isValidBody(req.body)) {
    return res.status(400).json({ error: 'invalid_request', message: 'A valid email is required.' });
  }

  // Honeypot: a hidden field real visitors never fill in. A bot that fills
  // every field trips this silently -- reported as success so it doesn't
  // learn to skip the field, but nothing is stored.
  if (typeof req.body.company === 'string' && req.body.company.trim().length > 0) {
    return res.status(200).json({ ok: true });
  }

  const email = req.body.email.trim().toLowerCase();
  const name = typeof req.body.name === 'string' ? req.body.name.trim() : '';

  if (!email || email.length > MAX_EMAIL_LENGTH || !EMAIL_PATTERN.test(email)) {
    return res.status(400).json({ error: 'invalid_email', message: 'Enter a valid email address.' });
  }
  if (name.length > MAX_NAME_LENGTH) {
    return res.status(400).json({ error: 'invalid_name', message: 'Name is too long.' });
  }

  const entry: WaitlistEntry = { email, name: name || null, submittedAt: new Date().toISOString() };

  try {
    await appendToGist(token, gistId, entry);
  } catch (error) {
    console.error('waitlist: failed to record submission', error);
    return res.status(502).json({
      error: 'waitlist_storage_failed',
      message: 'Could not record your submission right now. Please try again shortly.',
    });
  }

  return res.status(200).json({ ok: true });
}

async function appendToGist(token: string, gistId: string, entry: WaitlistEntry): Promise<void> {
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };

  const getResponse = await fetch(`https://api.github.com/gists/${gistId}`, { headers });
  if (!getResponse.ok) {
    throw new Error(`GET gist failed: ${getResponse.status}`);
  }
  const gist = await getResponse.json();
  const file = gist.files?.[GIST_FILENAME];
  const existing: WaitlistEntry[] = file?.content ? safeParseArray(file.content) : [];

  // Never store the same email twice -- a resubmission (e.g. a retried
  // request) updates its position rather than duplicating the entry.
  const deduped = existing.filter((row) => row.email !== entry.email);
  deduped.push(entry);

  const patchResponse = await fetch(`https://api.github.com/gists/${gistId}`, {
    method: 'PATCH',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      files: { [GIST_FILENAME]: { content: JSON.stringify(deduped, null, 2) } },
    }),
  });
  if (!patchResponse.ok) {
    throw new Error(`PATCH gist failed: ${patchResponse.status}`);
  }
}

function safeParseArray(raw: string): WaitlistEntry[] {
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
