import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuthStore } from './useAuthStore';
import { useAppStore } from './useAppStore';
import { authService, api, getApiConfig } from '@/shared/services/api';
import type { Repository } from '@/shared/types';

function fakeRepository(id: string): Repository {
  return {
    id,
    name: id,
    source: 'upload',
    size: 0,
    fileCount: 0,
    status: 'completed',
    dataSource: 'real',
    analysisStage: 'completed',
    analysisProgress: 100,
    uploadedAt: new Date().toISOString(),
    meta: null,
    fileTree: [],
  };
}

function fakeUser(id: string, email: string) {
  return { id, email, createdAt: new Date().toISOString() };
}

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.setState({ status: 'initialising', accessToken: null, user: null });
    useAppStore.setState({ repositories: [], activeRepositoryId: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('bootstrap refresh sharing', () => {
    it('bootstrap and a simultaneous protected-request 401 share exactly one /auth/refresh call', async () => {
      let refreshCount = 0;
      let authorized = false;

      vi.spyOn(authService, 'refresh').mockImplementation(async () => {
        refreshCount += 1;
        // Long enough that both the bootstrap call and the concurrent
        // protected request are guaranteed to have already reached the
        // shared mutex before either refresh resolves.
        await new Promise((resolve) => setTimeout(resolve, 20));
        authorized = true;
        return { accessToken: 'fresh-token', tokenType: 'bearer' as const, user: fakeUser('u1', 'a@example.com') };
      });
      vi.spyOn(authService, 'me').mockResolvedValue(fakeUser('u1', 'a@example.com'));

      // Stands in for RepositoryProvider's fetch racing bootstrap: 401 until
      // the shared refresh completes, then succeeds on retry.
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => {
          const body = authorized ? { data: [], total: 0 } : { code: 'unauthorized', message: 'expired' };
          return new Response(JSON.stringify(body), {
            status: authorized ? 200 : 401,
            headers: { 'content-type': 'application/json' },
          });
        }),
      );

      const bootstrapPromise = useAuthStore.getState().bootstrap();
      const protectedRequestPromise = api.get('/repositories');

      await Promise.all([bootstrapPromise, protectedRequestPromise]);

      expect(refreshCount).toBe(1);
      expect(useAuthStore.getState().status).toBe('authenticated');
      expect(useAuthStore.getState().user?.id).toBe('u1');

      vi.unstubAllGlobals();
    });

    it('bootstrap does not fetch repositories itself before authentication completes', async () => {
      vi.spyOn(authService, 'refresh').mockResolvedValue({
        accessToken: 'fresh-token',
        tokenType: 'bearer',
        user: fakeUser('u1', 'a@example.com'),
      });
      vi.spyOn(authService, 'me').mockResolvedValue(fakeUser('u1', 'a@example.com'));

      expect(useAppStore.getState().repositories).toEqual([]);

      await useAuthStore.getState().bootstrap();

      // bootstrap's own contract is refresh -> /auth/me only; it must never
      // reach into repository data itself. (RepositoryProvider — mounted only
      // once RequireAuth observes 'authenticated' — owns that fetch.)
      expect(useAppStore.getState().repositories).toEqual([]);
      expect(useAuthStore.getState().status).toBe('authenticated');
    });
  });

  describe('cross-user repository isolation', () => {
    it('clears repository state on logout so a subsequent user never sees stale data', async () => {
      vi.spyOn(authService, 'logout').mockResolvedValue(undefined);
      useAppStore.setState({ repositories: [fakeRepository('repo-a')], activeRepositoryId: 'repo-a' });
      useAuthStore.setState({ status: 'authenticated', accessToken: 'a-token', user: fakeUser('userA', 'a@example.com') });

      await useAuthStore.getState().logout();

      expect(useAppStore.getState().repositories).toEqual([]);
      expect(useAppStore.getState().activeRepositoryId).toBeNull();
      expect(useAuthStore.getState().status).toBe('unauthenticated');
    });

    it('clears stale repository state at the moment a different user logs in', async () => {
      useAppStore.setState({ repositories: [fakeRepository('repo-a')], activeRepositoryId: 'repo-a' });
      vi.spyOn(authService, 'login').mockResolvedValue({
        accessToken: 'b-token',
        tokenType: 'bearer',
        user: fakeUser('userB', 'b@example.com'),
      });

      await useAuthStore.getState().login('b@example.com', 'password123');

      expect(useAppStore.getState().repositories).toEqual([]);
      expect(useAppStore.getState().activeRepositoryId).toBeNull();
      expect(useAuthStore.getState().user?.id).toBe('userB');
      expect(useAuthStore.getState().status).toBe('authenticated');
    });

    it('clears repository state when the API client reports an unrecoverable 401', () => {
      useAppStore.setState({ repositories: [fakeRepository('repo-a')], activeRepositoryId: 'repo-a' });
      useAuthStore.setState({ status: 'authenticated', accessToken: 'a-token', user: fakeUser('userA', 'a@example.com') });

      // Calls the real onUnauthorized callback useAuthStore registered via
      // configureApiClient — the same one the API client's interceptor
      // invokes on a refresh that can't recover a 401.
      getApiConfig().onUnauthorized?.();

      expect(useAppStore.getState().repositories).toEqual([]);
      expect(useAppStore.getState().activeRepositoryId).toBeNull();
      expect(useAuthStore.getState().status).toBe('unauthenticated');
    });
  });
});
