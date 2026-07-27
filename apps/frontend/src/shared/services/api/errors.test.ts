import { describe, expect, it } from 'vitest';
import {
  ApiError,
  CancelledError,
  NetworkError,
  TimeoutError,
  isApiError,
  isErrorResponse,
  isNetworkError,
  isTimeoutError,
  parseRetryAfter,
} from './errors';

describe('ApiError', () => {
  it('carries status, endpoint, and a readable message', () => {
    const error = new ApiError(404, 'Not Found', { code: 'not_found' }, '/repositories/x');

    expect(error.name).toBe('ApiError');
    expect(error.status).toBe(404);
    expect(error.message).toContain('404');
    expect(error.message).toContain('/repositories/x');
  });

  it('classifies status families the UI branches on', () => {
    expect(new ApiError(401, '', null, '/x').isUnauthorized).toBe(true);
    expect(new ApiError(404, '', null, '/x').isNotFound).toBe(true);
    expect(new ApiError(422, '', null, '/x').isValidation).toBe(true);
    expect(new ApiError(429, '', null, '/x').isRateLimited).toBe(true);
    expect(new ApiError(503, '', null, '/x').isUnavailable).toBe(true);
    expect(new ApiError(500, '', null, '/x').isServerError).toBe(true);
    expect(new ApiError(200, '', null, '/x').isServerError).toBe(false);
  });
});

describe('parseRetryAfter (#169)', () => {
  it('returns null for a missing header', () => {
    expect(parseRetryAfter(null)).toBeNull();
    expect(parseRetryAfter(undefined)).toBeNull();
    expect(parseRetryAfter('')).toBeNull();
    expect(parseRetryAfter('   ')).toBeNull();
  });

  it('returns null for a malformed header', () => {
    expect(parseRetryAfter('not-a-number-or-date')).toBeNull();
    expect(parseRetryAfter('-5')).toBeNull();
  });

  it('parses a delta-seconds value', () => {
    expect(parseRetryAfter('120')).toBe(120);
    expect(parseRetryAfter('0')).toBe(0);
  });

  it('parses an HTTP-date value, clamped to zero if already past', () => {
    const now = () => new Date('2026-01-01T00:00:00Z').getTime();
    expect(parseRetryAfter('Thu, 01 Jan 2026 00:01:00 GMT', now)).toBe(60);
    expect(parseRetryAfter('Wed, 31 Dec 2025 23:59:00 GMT', now)).toBe(0);
  });
});

describe('ApiError.retryAfterSeconds (#169)', () => {
  it('prefers the Retry-After header over the body', () => {
    const error = new ApiError(429, '', { details: { retryAfterSeconds: 5 } }, '/x', '30');
    expect(error.retryAfterSeconds).toBe(30);
  });

  it('falls back to details.retryAfterSeconds when the header is missing or malformed', () => {
    const missingHeader = new ApiError(429, '', { details: { retryAfterSeconds: 12 } }, '/x', null);
    expect(missingHeader.retryAfterSeconds).toBe(12);

    const malformedHeader = new ApiError(429, '', { details: { retryAfterSeconds: 12 } }, '/x', 'garbage');
    expect(malformedHeader.retryAfterSeconds).toBe(12);
  });

  it('returns null when neither the header nor the body carry a value', () => {
    expect(new ApiError(429, '', {}, '/x', null).retryAfterSeconds).toBeNull();
    expect(new ApiError(429, '', null, '/x', null).retryAfterSeconds).toBeNull();
  });
});

describe('type guards', () => {
  it('narrow each error class and reject the others', () => {
    const api = new ApiError(500, 'boom', null, '/x');
    const network = new NetworkError('/x');
    const timeout = new TimeoutError('/x', 30_000);
    const cancelled = new CancelledError('/x');

    expect(isApiError(api)).toBe(true);
    expect(isApiError(network)).toBe(false);
    expect(isNetworkError(network)).toBe(true);
    expect(isNetworkError(timeout)).toBe(false);
    expect(isTimeoutError(timeout)).toBe(true);
    expect(isTimeoutError(cancelled)).toBe(false);
  });

  it('reject plain errors and non-errors', () => {
    expect(isApiError(new Error('plain'))).toBe(false);
    expect(isApiError(undefined)).toBe(false);
    expect(isNetworkError('nope')).toBe(false);
  });

  it('validates the generated error envelope at the untrusted response boundary', () => {
    expect(isErrorResponse({ code: 'unauthorized', message: 'Sign in required' })).toBe(true);
    expect(isErrorResponse({ code: 'unauthorized' })).toBe(false);
    expect(isErrorResponse(null)).toBe(false);
  });
});
