const DEFAULT_API_URL = 'http://localhost:8000';

function normalizeApiUrl(value: string | undefined): string {
  const candidate = value?.trim() || DEFAULT_API_URL;
  try {
    const url = new URL(candidate);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      return DEFAULT_API_URL;
    }
    return url.origin;
  } catch {
    return DEFAULT_API_URL;
  }
}

export const frontendEnv = {
  apiUrl: normalizeApiUrl(import.meta.env.VITE_API_URL),
};
