import { ApiError, NetworkError, TimeoutError, CancelledError } from './errors';
import { frontendEnv } from '../../config/env';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

export interface RequestConfig {
  timeout?: number;
  retries?: number;
  retryDelay?: number;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  onUploadProgress?: (progress: number) => void;
}

export interface ApiClientConfig {
  baseUrl: string;
  defaultTimeout: number;
  defaultRetries: number;
  defaultRetryDelay: number;
  getAuthToken?: () => string | null;
  /** Attempts a silent session refresh; resolves true if a fresh access token
   * is now available and the triggering request should be retried once. */
  refreshSession?: () => Promise<boolean>;
  /** Called when a 401 could not be resolved by a refresh (or refresh isn't
   * configured) — the terminal "give up" signal, e.g. to clear state and
   * redirect to /login. */
  onUnauthorized?: () => void;
}

const DEFAULT_CONFIG: ApiClientConfig = {
  baseUrl: frontendEnv.apiUrl,
  defaultTimeout: 30000,
  defaultRetries: 2,
  defaultRetryDelay: 1000,
};

let clientConfig: ApiClientConfig = { ...DEFAULT_CONFIG };

export function configureApiClient(config: Partial<ApiClientConfig>) {
  clientConfig = { ...clientConfig, ...config };
}

export function getApiConfig(): ApiClientConfig {
  return clientConfig;
}

// The endpoints below must never trigger a silent refresh-and-retry: retrying
// a failed login/register is nonsensical, and refreshing off the back of a
// failed /auth/refresh or /auth/logout would recurse into the same endpoint.
const NO_REFRESH_ENDPOINTS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'];

function isNoRefreshEndpoint(endpoint: string): boolean {
  return NO_REFRESH_ENDPOINTS.some((path) => endpoint === path || endpoint.startsWith(`${path}?`));
}

// Several requests can each hit a 401 for the same expired session around the
// same time; without this, each would fire its own /auth/refresh, and the
// backend's rotating refresh tokens mean only the first would succeed — the
// rest would revoke the whole session as replay. Sharing one in-flight
// promise makes every concurrent 401 await the same single refresh attempt.
//
// This is exported and is the ONLY sanctioned way to trigger a refresh:
// callers outside this module (e.g. the auth store's bootstrap, which also
// needs a refresh before anything else can run) must call this instead of
// invoking their refresh primitive directly, or bootstrap's own refresh and
// a concurrent request's 401 recovery could each fire an independent
// /auth/refresh and race each other into the backend's replay-revocation.
let inFlightRefresh: Promise<boolean> | null = null;

export function requestSharedRefresh(): Promise<boolean> {
  if (!clientConfig.refreshSession) return Promise.resolve(false);
  if (!inFlightRefresh) {
    inFlightRefresh = clientConfig
      .refreshSession()
      .catch(() => false)
      .finally(() => {
        inFlightRefresh = null;
      });
  }
  return inFlightRefresh;
}

/** Resolves true (and the caller should retry once) if this was an
 * unauthorized response on a refreshable endpoint and the shared refresh
 * succeeded; otherwise fires onUnauthorized and resolves false. */
async function tryRecoverFromUnauthorized(endpoint: string, isRetry: boolean): Promise<boolean> {
  if (!isRetry && !isNoRefreshEndpoint(endpoint) && (await requestSharedRefresh())) {
    return true;
  }
  clientConfig.onUnauthorized?.();
  return false;
}

async function request<T>(
  method: HttpMethod,
  endpoint: string,
  body?: unknown,
  config?: RequestConfig,
): Promise<T> {
  const timeout = config?.timeout ?? clientConfig.defaultTimeout;
  const retries = config?.retries ?? clientConfig.defaultRetries;
  const retryDelay = config?.retryDelay ?? clientConfig.defaultRetryDelay;

  let lastError: unknown;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await executeRequest<T>(method, endpoint, body, config, timeout);
    } catch (error) {
      lastError = error;

      if (error instanceof CancelledError) throw error;
      if (error instanceof ApiError && error.status < 500 && error.status !== 429) throw error;

      if (attempt < retries) {
        const delay = retryDelay * Math.pow(2, attempt);
        await sleep(delay);
      }
    }
  }

  throw lastError;
}

async function executeRequest<T>(
  method: HttpMethod,
  endpoint: string,
  body: unknown,
  config: RequestConfig | undefined,
  timeout: number,
  isRetry = false,
): Promise<T> {
  const url = `${clientConfig.baseUrl}${endpoint}`;
  const controller = new AbortController();
  const signal = config?.signal;

  if (signal?.aborted) throw new CancelledError(endpoint);

  const abortListener = signal ? () => controller.abort() : null;
  if (signal && abortListener) signal.addEventListener('abort', abortListener);

  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const headers: Record<string, string> = {
      ...config?.headers,
    };

    const token = clientConfig.getAuthToken?.();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    if (body && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, {
      method,
      headers,
      credentials: 'include',
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (!response.ok) {
      let responseBody: unknown;
      try {
        responseBody = await response.json();
      } catch {
        responseBody = await response.text().catch(() => null);
      }

      const error = new ApiError(response.status, response.statusText, responseBody, endpoint);
      if (error.isUnauthorized) {
        if (await tryRecoverFromUnauthorized(endpoint, isRetry)) {
          return executeRequest<T>(method, endpoint, body, config, timeout, true);
        }
      }
      throw error;
    }

    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      return await response.json() as T;
    }

    return (await response.text()) as unknown as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      if (signal?.aborted) throw new CancelledError(endpoint);
      throw new TimeoutError(endpoint, timeout);
    }
    throw new NetworkError(endpoint, error);
  } finally {
    clearTimeout(timeoutId);
    if (signal && abortListener) signal.removeEventListener('abort', abortListener);
  }
}

export async function uploadFile<T>(
  endpoint: string,
  file: File,
  fields?: Record<string, string>,
  config?: RequestConfig,
  isRetry = false,
): Promise<T> {
  const url = `${clientConfig.baseUrl}${endpoint}`;
  const controller = new AbortController();
  const signal = config?.signal;

  if (signal?.aborted) throw new CancelledError(endpoint);

  const abortListener = signal ? () => controller.abort() : null;
  if (signal && abortListener) signal.addEventListener('abort', abortListener);

  const timeout = config?.timeout ?? 120000;
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const formData = new FormData();
    formData.append('file', file);
    if (fields) {
      Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
    }

    const headers: Record<string, string> = { ...config?.headers };
    const token = clientConfig.getAuthToken?.();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    if (config?.onUploadProgress) {
      return await uploadWithProgress<T>(url, formData, headers, controller.signal, config.onUploadProgress);
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      let responseBody: unknown;
      try { responseBody = await response.json(); } catch { responseBody = null; }
      throw new ApiError(response.status, response.statusText, responseBody, endpoint);
    }

    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.isUnauthorized && (await tryRecoverFromUnauthorized(endpoint, isRetry))) {
        clearTimeout(timeoutId);
        if (signal && abortListener) signal.removeEventListener('abort', abortListener);
        return uploadFile<T>(endpoint, file, fields, config, true);
      }
      throw error;
    }
    if (controller.signal.aborted) {
      if (signal?.aborted) throw new CancelledError(endpoint);
      throw new TimeoutError(endpoint, timeout);
    }
    throw new NetworkError(endpoint, error);
  } finally {
    clearTimeout(timeoutId);
    if (signal && abortListener) signal.removeEventListener('abort', abortListener);
  }
}

async function uploadWithProgress<T>(
  url: string,
  formData: FormData,
  headers: Record<string, string>,
  signal: AbortSignal,
  onProgress: (progress: number) => void,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.withCredentials = true;
    Object.entries(headers).forEach(([key, value]) => xhr.setRequestHeader(key, value));

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          resolve(xhr.responseText as unknown as T);
        }
      } else {
        let body: unknown;
        try { body = JSON.parse(xhr.responseText); } catch { body = xhr.responseText; }
        reject(new ApiError(xhr.status, xhr.statusText, body, url));
      }
    };

    xhr.onerror = () => reject(new NetworkError(url));
    xhr.onabort = () => reject(new CancelledError(url));

    signal.addEventListener('abort', () => xhr.abort());
    xhr.send(formData);
  });
}

export async function streamRequest(
  endpoint: string,
  body: unknown,
  onChunk: (chunk: string) => void,
  config?: RequestConfig,
  isRetry = false,
): Promise<void> {
  const url = `${clientConfig.baseUrl}${endpoint}`;
  const controller = new AbortController();
  const signal = config?.signal;

  if (signal?.aborted) throw new CancelledError(endpoint);
  const abortListener = signal ? () => controller.abort() : null;
  if (signal && abortListener) signal.addEventListener('abort', abortListener);

  const timeout = config?.timeout ?? 60000;
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      ...config?.headers,
    };
    const token = clientConfig.getAuthToken?.();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(url, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      let responseBody: unknown;
      try { responseBody = await response.json(); } catch { responseBody = null; }
      const error = new ApiError(response.status, response.statusText, responseBody, endpoint);
      if (error.isUnauthorized) {
        // A 401 here means the backend rejected the request before any
        // event ever streamed (the SSE body only starts after auth passes),
        // so retrying is exactly as safe as retrying any other request —
        // same recover-once-then-give-up contract as executeRequest.
        if (await tryRecoverFromUnauthorized(endpoint, isRetry)) {
          clearTimeout(timeoutId);
          if (signal && abortListener) signal.removeEventListener('abort', abortListener);
          return streamRequest(endpoint, body, onChunk, config, true);
        }
      }
      throw error;
    }

    const reader = response.body?.getReader();
    if (!reader) throw new NetworkError(endpoint);

    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      clearTimeout(timeoutId);
      const text = decoder.decode(value, { stream: true });
      onChunk(text);
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      if (signal?.aborted) throw new CancelledError(endpoint);
      throw new TimeoutError(endpoint, timeout);
    }
    throw new NetworkError(endpoint, error);
  } finally {
    clearTimeout(timeoutId);
    if (signal && abortListener) signal.removeEventListener('abort', abortListener);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const api = {
  get: <T>(endpoint: string, config?: RequestConfig) => request<T>('GET', endpoint, undefined, config),
  post: <T>(endpoint: string, body?: unknown, config?: RequestConfig) => request<T>('POST', endpoint, body, config),
  put: <T>(endpoint: string, body?: unknown, config?: RequestConfig) => request<T>('PUT', endpoint, body, config),
  patch: <T>(endpoint: string, body?: unknown, config?: RequestConfig) => request<T>('PATCH', endpoint, body, config),
  delete: <T>(endpoint: string, config?: RequestConfig) => request<T>('DELETE', endpoint, undefined, config),
  upload: uploadFile,
  stream: streamRequest,
};
