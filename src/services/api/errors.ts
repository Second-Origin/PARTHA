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
    switch (error.status) {
      case 401: return 'Authentication required. Please sign in.';
      case 403: return 'You do not have permission to perform this action.';
      case 404: return 'The requested resource was not found.';
      case 422: return 'The request data is invalid.';
      case 429: return 'Too many requests. Please try again later.';
      case 503: return 'Service is temporarily unavailable. Please try again.';
      default: return error.status >= 500 ? 'A server error occurred. Please try again.' : error.message;
    }
  }
  if (isNetworkError(error)) return 'Unable to connect. Check your network connection.';
  if (isTimeoutError(error)) return 'The request timed out. Please try again.';
  if (isCancelledError(error)) return 'Request was cancelled.';
  if (error instanceof Error) return error.message;
  return 'An unknown error occurred.';
}
