import { describe, expect, it } from 'vitest';
import {
  ApiError,
  CancelledError,
  NetworkError,
  TimeoutError,
  isApiError,
  isNetworkError,
  isTimeoutError,
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
});
