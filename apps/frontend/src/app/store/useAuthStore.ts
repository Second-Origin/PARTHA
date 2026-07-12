import { create } from 'zustand';
import { authService, configureApiClient } from '@/shared/services/api';
import type { UserResponse } from '@/shared/services/api/types';

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
  /** Silent refresh used by the API client's 401 interceptor. Never throws. */
  refreshSession: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>((set) => ({
  status: 'initialising',
  accessToken: null,
  user: null,

  async bootstrap() {
    try {
      const auth = await authService.refresh();
      set({ accessToken: auth.accessToken });
      const user = await authService.me();
      set({ user, status: 'authenticated' });
    } catch {
      set({ accessToken: null, user: null, status: 'unauthenticated' });
    }
  },

  async login(email, password) {
    const auth = await authService.login({ email, password });
    set({ accessToken: auth.accessToken, user: auth.user, status: 'authenticated' });
  },

  async register(email, password) {
    const auth = await authService.register({ email, password });
    set({ accessToken: auth.accessToken, user: auth.user, status: 'authenticated' });
  },

  async logout() {
    try {
      await authService.logout();
    } catch {
      // The user asked to sign out; a failed revocation call shouldn't leave
      // them stuck signed in on the client.
    } finally {
      set({ accessToken: null, user: null, status: 'unauthenticated' });
    }
  },

  async refreshSession() {
    try {
      const auth = await authService.refresh();
      set({ accessToken: auth.accessToken, user: auth.user, status: 'authenticated' });
      return true;
    } catch {
      set({ accessToken: null, user: null, status: 'unauthenticated' });
      return false;
    }
  },
}));

// Wired here (not in client.ts) so the API client stays a generic HTTP layer
// with no knowledge of auth state, and this store is the only thing that
// knows both sides — avoids a circular import between the two modules.
configureApiClient({
  getAuthToken: () => useAuthStore.getState().accessToken,
  refreshSession: () => useAuthStore.getState().refreshSession(),
  onUnauthorized: () => {
    useAuthStore.setState({ accessToken: null, user: null, status: 'unauthenticated' });
  },
});
