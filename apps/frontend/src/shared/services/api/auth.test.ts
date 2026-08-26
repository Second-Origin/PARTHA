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
});
