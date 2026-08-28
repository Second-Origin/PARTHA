import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { authService } from './auth';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('authService', () => {
  it('register posts the request body to /auth/register', async () => {
    const request = { email: 'a@b.com', password: 'x', inviteCode: 'code-1' };
    const response = { accessToken: 'tok', tokenType: 'bearer', user: { id: 'u1' } };
    vi.mocked(api.post).mockResolvedValue(response);

    const result = await authService.register(request);

    expect(api.post).toHaveBeenCalledWith('/auth/register', request, undefined);
    expect(result).toBe(response);
  });

  it('login posts the request body to /auth/login', async () => {
    const request = { email: 'a@b.com', password: 'x' };
    vi.mocked(api.post).mockResolvedValue({ accessToken: 'tok' });

    await authService.login(request);

    expect(api.post).toHaveBeenCalledWith('/auth/login', request, undefined);
  });

  it('refresh posts to /auth/refresh with no body', async () => {
    vi.mocked(api.post).mockResolvedValue({ accessToken: 'tok' });

    await authService.refresh();

    expect(api.post).toHaveBeenCalledWith('/auth/refresh', undefined, undefined);
  });

  it('logout posts to /auth/logout with no body', async () => {
    vi.mocked(api.post).mockResolvedValue(undefined);

    await authService.logout();

    expect(api.post).toHaveBeenCalledWith('/auth/logout', undefined, undefined);
  });

  it('me gets /auth/me', async () => {
    const user = { id: 'u1', email: 'a@b.com' };
    vi.mocked(api.get).mockResolvedValue(user);

    const result = await authService.me();

    expect(api.get).toHaveBeenCalledWith('/auth/me', undefined);
    expect(result).toBe(user);
  });

  it('deleteAccount sends the request body as a DELETE to /auth/me', async () => {
    const request = { password: 'x', confirmEmail: 'a@b.com' };
    vi.mocked(api.delete).mockResolvedValue(undefined);

    await authService.deleteAccount(request);

    expect(api.delete).toHaveBeenCalledWith('/auth/me', request, undefined);
  });

  it('propagates a rejected login request (e.g. bad credentials)', async () => {
    const error = new Error('unauthorized');
    vi.mocked(api.post).mockRejectedValue(error);

    await expect(authService.login({ email: 'a@b.com', password: 'wrong' })).rejects.toBe(error);
  });

  it('getOAuthProviders gets /auth/oauth/providers', async () => {
    const response = { providers: ['google'] };
    vi.mocked(api.get).mockResolvedValue(response);

    const result = await authService.getOAuthProviders();

    expect(api.get).toHaveBeenCalledWith('/auth/oauth/providers', undefined);
    expect(result).toBe(response);
  });

  it('startOAuthLogin gets /auth/oauth/{provider}/start', async () => {
    const response = { authorizeUrl: 'https://example.test/authorize' };
    vi.mocked(api.get).mockResolvedValue(response);

    const result = await authService.startOAuthLogin('google');

    expect(api.get).toHaveBeenCalledWith('/auth/oauth/google/start', undefined);
    expect(result).toBe(response);
  });

  it('startOAuthLink posts to /auth/oauth/{provider}/link with no body', async () => {
    const response = { authorizeUrl: 'https://example.test/authorize' };
    vi.mocked(api.post).mockResolvedValue(response);

    await authService.startOAuthLink('github');

    expect(api.post).toHaveBeenCalledWith('/auth/oauth/github/link', undefined, undefined);
  });

  it('confirmOAuthLink posts the request body to /auth/oauth/link/confirm', async () => {
    const request = { pendingLinkId: 'p1', password: 'x' };
    vi.mocked(api.post).mockResolvedValue({ accessToken: 'tok' });

    await authService.confirmOAuthLink(request);

    expect(api.post).toHaveBeenCalledWith('/auth/oauth/link/confirm', request, undefined);
  });

  it('listLinkedOAuthIdentities gets /auth/oauth/linked', async () => {
    const response = { identities: [] };
    vi.mocked(api.get).mockResolvedValue(response);

    const result = await authService.listLinkedOAuthIdentities();

    expect(api.get).toHaveBeenCalledWith('/auth/oauth/linked', undefined);
    expect(result).toBe(response);
  });

  it('unlinkOAuthProvider deletes /auth/oauth/{provider} with no body', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined);

    await authService.unlinkOAuthProvider('google');

    expect(api.delete).toHaveBeenCalledWith('/auth/oauth/google', undefined, undefined);
  });
});
