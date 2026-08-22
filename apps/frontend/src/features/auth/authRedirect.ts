export interface AuthRedirectState {
  from?: {
    pathname?: string;
    search?: string;
    hash?: string;
  };
}

// Shared by login and register so the two behave identically: whichever one
// the user completes, they land back on the exact route RequireAuth sent
// them away from (path, query string, and hash), not just its pathname.
export function resolveRedirectTarget(state: unknown): string {
  const from = (state as AuthRedirectState | null)?.from;
  if (!from?.pathname) return '/dashboard';
  return `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`;
}
