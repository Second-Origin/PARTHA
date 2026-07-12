import { create } from 'zustand';
import { authService, configureApiClient, requestSharedRefresh } from '@/shared/services/api';
import type { UserResponse } from '@/shared/services/api/types';
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
  /** Always clears local session state, even if the server call fails. */
  logout: () => Promise<void>;
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

  async bootstrap() {
    const refreshed = await requestSharedRefresh();
    if (!refreshed) {
      clearAuthenticatedState();
      return;
    }
    try {
      const user = await authService.me();
      set({ user, status: 'authenticated' });
    } catch {
      clearAuthenticatedState();
    }
  },

  async login(email, password) {
    const auth = await authService.login({ email, password });
    clearRepositoryState();
    set({ accessToken: auth.accessToken, user: auth.user, status: 'authenticated' });
  },

  async register(email, password) {
    const auth = await authService.register({ email, password });
    clearRepositoryState();
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

// Repository state lives in the separate, unauthenticated-by-default
// useAppStore, so it survives independently of who's signed in unless we
// clear it ourselves. Cleared here — not in RepositoryProvider — so the
// clearing always happens in the same tick as the auth transition, before
// any component can re-render with a newly (or no longer) authenticated
// status and observe the previous user's repositories, even briefly.
function clearRepositoryState() {
  useAppStore.getState().setRepositories([]);
  useAppStore.getState().setActiveRepositoryId(null);
}

function clearAuthenticatedState() {
  useAuthStore.setState({ accessToken: null, user: null, status: 'unauthenticated' });
  clearRepositoryState();
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
