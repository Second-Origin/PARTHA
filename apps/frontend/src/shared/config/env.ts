const DEFAULT_DEV_API_URL = 'http://localhost:8000';

/**
 * No explicit VITE_API_URL: fall back to same-origin in a production build
 * (the built frontend is served by the same backend it talks to -- see
 * app.main's static mount) rather than localhost, which only makes sense
 * when the Vite dev server and the backend run on different ports.
 * Same-origin is expressed as '' since baseUrl is only ever concatenated
 * with a request path (`${baseUrl}${endpoint}`), never parsed as a URL on
 * its own -- the browser resolves the resulting relative URL against the
 * current page origin.
 */
function defaultApiUrl(): string {
  return import.meta.env.PROD ? '' : DEFAULT_DEV_API_URL;
}

function normalizeApiUrl(value: string | undefined): string {
  const candidate = value?.trim();
  if (!candidate) return defaultApiUrl();
  try {
    const url = new URL(candidate);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      return defaultApiUrl();
    }
    return url.origin;
  } catch {
    return defaultApiUrl();
  }
}

export const frontendEnv = {
  apiUrl: normalizeApiUrl(import.meta.env.VITE_API_URL),
};
