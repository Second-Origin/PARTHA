export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown,
    public endpoint: string,
  ) {
    super(`API Error ${status}: ${statusText} [${endpoint}]`);
    this.name = 'ApiError';
  }

  get isUnauthorized() { return this.status === 401; }
  get isForbidden() { return this.status === 403; }
  get isNotFound() { return this.status === 404; }
  get isValidation() { return this.status === 422; }
  get isRateLimited() { return this.status === 429; }
  get isServerError() { return this.status >= 500; }
  get isUnavailable() { return this.status === 503; }
  get requestId() { return getBackendRequestId(this.body); }
}

export class NetworkError extends Error {
  constructor(
    public endpoint: string,
    public cause?: unknown,
  ) {
    super(`Network error: ${endpoint}`);
    this.name = 'NetworkError';
  }
}

export class TimeoutError extends Error {
  constructor(
    public endpoint: string,
    public timeoutMs: number,
  ) {
    super(`Request timed out after ${timeoutMs}ms: ${endpoint}`);
    this.name = 'TimeoutError';
  }
}

export class CancelledError extends Error {
  constructor(public endpoint: string) {
    super(`Request cancelled: ${endpoint}`);
    this.name = 'CancelledError';
  }
}

export type ApiErrorType = ApiError | NetworkError | TimeoutError | CancelledError;

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function isNetworkError(error: unknown): error is NetworkError {
  return error instanceof NetworkError;
}

export function isTimeoutError(error: unknown): error is TimeoutError {
  return error instanceof TimeoutError;
}

export function isCancelledError(error: unknown): error is CancelledError {
  return error instanceof CancelledError;
}

export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    const backendMessage = getBackendMessage(error.body);
    const details = getBackendDetails(error.body);
    if (backendMessage && !details.length) return backendMessage;
    if (backendMessage && details.length) {
      return `${backendMessage}\n${details.map((d) => `- ${d}`).join('\n')}`;
    }

    switch (error.status) {
      case 401: return 'Authentication required. Please sign in.';
      case 403: return 'You do not have permission to perform this action.';
      case 404: return 'The requested resource was not found.';
      case 422: return details.length
        ? `The request data is invalid:\n${details.map((d) => `- ${d}`).join('\n')}`
        : 'The request data is invalid.';
      case 409: return 'The request conflicts with an existing resource.';
      case 429: return 'Too many requests. Please try again later.';
      case 503: return 'Service is temporarily unavailable. Please try again.';
      default: return error.status >= 500 ? 'A server error occurred. Please try again.' : error.message;
    }
  }
  if (isNetworkError(error)) return 'Cannot reach the PARTHA backend. Confirm the API server is running and try again.';
  if (isTimeoutError(error)) return 'The request timed out. Please try again.';
  if (isCancelledError(error)) return 'Request was cancelled.';
  if (error instanceof Error) return error.message;
  return 'An unknown error occurred.';
}

/** Structured error for UIs that want to render field-level validation details. */
export function getErrorDetail(error: unknown): { message: string; details: string[] } {
  if (isApiError(error)) {
    const message = getBackendMessage(error.body) ?? getErrorMessage(error);
    return { message, details: getBackendDetails(error.body) };
  }
  return { message: getErrorMessage(error), details: [] };
}

function getBackendMessage(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null;
  const maybeMessage = (body as { message?: unknown }).message;
  return typeof maybeMessage === 'string' && maybeMessage.trim() ? maybeMessage : null;
}

function getBackendDetails(body: unknown): string[] {
  if (!body || typeof body !== 'object') return [];
  const raw = (body as { details?: unknown }).details;
  if (Array.isArray(raw)) {
    return raw
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const loc = (item as { loc?: unknown }).loc;
          const msg = (item as { msg?: unknown }).msg;
          const locStr = Array.isArray(loc) ? loc.filter((p) => typeof p === 'string' || typeof p === 'number').join('.') : '';
          if (typeof msg === 'string') return locStr ? `${locStr}: ${msg}` : msg;
        }
        return null;
      })
      .filter((d): d is string => Boolean(d));
  }
  if (typeof raw === 'string') return [raw];
  return [];
}

function getBackendRequestId(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null;
  const maybeRequestId = (body as { request_id?: unknown }).request_id;
  return typeof maybeRequestId === 'string' && maybeRequestId.trim() ? maybeRequestId : null;
}
