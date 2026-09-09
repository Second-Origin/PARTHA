import { create } from 'zustand';
import { authService, configureApiClient, requestSharedRefresh } from '@/shared/services/api';
import type { AuthResponse, UserResponse } from '@/shared/services/api/types';
import { useAppStore } from './useAppStore';

export type AuthStatus = 'initialising' | 'authenticated' | 'unauthenticated';

interface AuthState {
  status: AuthStatus;
  accessToken: string | null;
  user: UserResponse | null;

  /** Runs once at app start: silently refresh the session from the httpOnly
   * cookie, then confirm identity via /auth/me. Never throws. */
  bootstrap: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  /** Adopts an AuthResponse this component already has in hand (e.g. from
   * confirming a pending OAuth link, #288) without making its own network
   * call -- the same local-state transition login()/register() make after
   * theirs. */
  setSession: (auth: AuthResponse) => void;
  /** Always clears local session state, even if the server call fails. */
  logout: () => Promise<void>;
  /** Clears local session state after the account itself was deleted
   * server-side. Unlike logout(), this never calls the backend: DELETE
   * /auth/me already revoked every session and cleared the refresh cookie
   * in its own response, so there is nothing left to sign out of. */
  accountDeleted: () => void;
  /** The refresh primitive. Only ever called through requestSharedRefresh's
   * single-flight mutex (wired below as the client's refreshSession hook) —
   * nothing else may call this directly, so every refresh in the app,
   * bootstrap included, goes through that one shared operation and can never
   * race a concurrent request's 401 recovery into two independent
   * /auth/refresh calls. */
  refreshSession: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>((set) => ({
  status: 'initialising',
  accessToken: null,
  user: null,

  bootstrap,

  async login(email, password) {
    const auth = await authService.login({ email, password });
    clearUserScopedAppState();
    set({ accessToken: auth.accessToken, user: auth.user, status: 'authenticated' });
  },

  async register(email, password) {
    const auth = await authService.register({ email, password });
    clearUserScopedAppState();
    set({ accessToken: auth.accessToken, user: auth.user, status: 'authenticated' });
  },

  setSession(auth) {
    clearUserScopedAppState();
    set({ accessToken: auth.accessToken, user: auth.user, status: 'authenticated' });
  },

  async logout() {
    try {
      await authService.logout();
    } catch {
      // The user asked to sign out; a failed revocation call shouldn't leave
      // them stuck signed in on the client.
    } finally {
      clearAuthenticatedState();
    }
  },

  accountDeleted() {
    clearAuthenticatedState();
  },

  async refreshSession() {
    try {
      const auth = await authService.refresh();
      set({ accessToken: auth.accessToken, user: auth.user, status: 'authenticated' });
      return true;
    } catch {
      clearAuthenticatedState();
      return false;
    }
  },
}));

// React 18 StrictMode deliberately double-invokes mount effects in
// development, so a naive bootstrap() would fire twice on every dev load.
// requestSharedRefresh() already dedupes the /auth/refresh call itself, but
// without this, each invocation would still independently race ahead to its
// own /auth/me call — harmless in itself, but bootstrap() should be safe to
// call concurrently as a whole, not just safe in its riskiest sub-step. One
// shared in-flight promise makes every concurrent bootstrap() call (and its
// caller) await the exact same run and land on the exact same final state.
let inFlightBootstrap: Promise<void> | null = null;

function bootstrap(): Promise<void> {
  if (!inFlightBootstrap) {
    inFlightBootstrap = performBootstrap().finally(() => {
      inFlightBootstrap = null;
    });
  }
  return inFlightBootstrap;
}

async function performBootstrap(): Promise<void> {
  const refreshed = await requestSharedRefresh();
  if (!refreshed) {
    clearAuthenticatedState();
    return;
  }
  try {
    const user = await authService.me();
    useAuthStore.setState({ user, status: 'authenticated' });
  } catch {
    clearAuthenticatedState();
  }
}

// User-scoped app state lives in the separate, unauthenticated-by-default
// useAppStore, so it survives independently of who's signed in unless we
// clear it ourselves. Cleared here — not in RepositoryProvider — so the
// clearing always happens in the same tick as the auth transition, before
// any component can re-render with a newly (or no longer) authenticated
// status and observe the previous user's data, even briefly.
function clearUserScopedAppState() {
  const appStore = useAppStore.getState();
  appStore.setRepositories([]);
  appStore.setActiveRepositoryId(null);
  appStore.cancelAnalysis();
  appStore.clearNotifications();
}

function clearAuthenticatedState() {
  useAuthStore.setState({ accessToken: null, user: null, status: 'unauthenticated' });
  clearUserScopedAppState();
}

// Wired here (not in client.ts) so the API client stays a generic HTTP layer
// with no knowledge of auth state, and this store is the only thing that
// knows both sides — avoids a circular import between the two modules.
configureApiClient({
  getAuthToken: () => useAuthStore.getState().accessToken,
  refreshSession: () => useAuthStore.getState().refreshSession(),
  onUnauthorized: () => {
    clearAuthenticatedState();
  },
});
