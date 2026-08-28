import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useOAuthAccounts } from './useOAuthAccounts';
import { authService } from '@/shared/services/api';

vi.mock('@/shared/services/api', () => ({
  authService: {
    getOAuthProviders: vi.fn(),
    listLinkedOAuthIdentities: vi.fn(),
    startOAuthLink: vi.fn(),
    unlinkOAuthProvider: vi.fn(),
  },
  getErrorMessage: vi.fn((error: unknown) => String(error)),
}));

beforeEach(() => {
  vi.mocked(authService.getOAuthProviders).mockReset().mockResolvedValue({ providers: ['google', 'github'] });
  vi.mocked(authService.listLinkedOAuthIdentities).mockReset();
  vi.mocked(authService.startOAuthLink).mockReset();
  vi.mocked(authService.unlinkOAuthProvider).mockReset();
});

describe('useOAuthAccounts', () => {
  it('loads linked identities and reports the remaining providers as linkable', async () => {
    vi.mocked(authService.listLinkedOAuthIdentities).mockResolvedValue({
      identities: [{ provider: 'google', email: 'a@example.com', createdAt: new Date().toISOString() }],
    });

    const { result } = renderHook(() => useOAuthAccounts());

    await waitFor(() => expect(result.current.identities).not.toBeNull());
    expect(result.current.identities).toHaveLength(1);
    expect(result.current.linkableProviders).toEqual(['github']);
  });

  it('link() navigates the browser to the returned authorize URL', async () => {
    vi.mocked(authService.listLinkedOAuthIdentities).mockResolvedValue({ identities: [] });
    vi.mocked(authService.startOAuthLink).mockResolvedValue({ authorizeUrl: 'https://example.test/link' });
    const assignSpy = vi.fn();
    vi.stubGlobal('location', { ...window.location, assign: assignSpy });

    const { result } = renderHook(() => useOAuthAccounts());
    await waitFor(() => expect(result.current.identities).not.toBeNull());

    await act(async () => {
      await result.current.link('google');
    });

    expect(authService.startOAuthLink).toHaveBeenCalledWith('google');
    expect(assignSpy).toHaveBeenCalledWith('https://example.test/link');

    vi.unstubAllGlobals();
  });

  it('unlink() removes the identity and reloads the list', async () => {
    vi.mocked(authService.listLinkedOAuthIdentities)
      .mockResolvedValueOnce({
        identities: [{ provider: 'google', email: 'a@example.com', createdAt: new Date().toISOString() }],
      })
      .mockResolvedValueOnce({ identities: [] });
    vi.mocked(authService.unlinkOAuthProvider).mockResolvedValue(undefined);

    const { result } = renderHook(() => useOAuthAccounts());
    await waitFor(() => expect(result.current.identities).toHaveLength(1));

    await act(async () => {
      await result.current.unlink('google');
    });

    expect(authService.unlinkOAuthProvider).toHaveBeenCalledWith('google');
    await waitFor(() => expect(result.current.identities).toEqual([]));
  });

  it('surfaces an unlink failure as actionError without clearing the list', async () => {
    vi.mocked(authService.listLinkedOAuthIdentities).mockResolvedValue({
      identities: [{ provider: 'google', email: 'a@example.com', createdAt: new Date().toISOString() }],
    });
    vi.mocked(authService.unlinkOAuthProvider).mockRejectedValue(new Error('only sign-in method'));

    const { result } = renderHook(() => useOAuthAccounts());
    await waitFor(() => expect(result.current.identities).toHaveLength(1));

    await act(async () => {
      await result.current.unlink('google');
    });

    expect(result.current.actionError).toBe('Error: only sign-in method');
    expect(result.current.identities).toHaveLength(1);
  });
});
