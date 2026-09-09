import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useOAuthProviders } from './useOAuthProviders';
import { authService } from '@/shared/services/api';

vi.mock('@/shared/services/api', () => ({
  authService: { getOAuthProviders: vi.fn() },
}));

beforeEach(() => {
  vi.mocked(authService.getOAuthProviders).mockReset();
});

describe('useOAuthProviders', () => {
  it('starts empty and reports the configured providers once the check resolves', async () => {
    vi.mocked(authService.getOAuthProviders).mockResolvedValue({ providers: ['google', 'github'] });

    const { result } = renderHook(() => useOAuthProviders());

    expect(result.current.providers).toEqual([]);
    await waitFor(() => expect(result.current.loaded).toBe(true));
    expect(result.current.providers).toEqual(['google', 'github']);
  });

  it('stays empty, without throwing, if the capability check fails', async () => {
    vi.mocked(authService.getOAuthProviders).mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useOAuthProviders());

    await waitFor(() => expect(result.current.loaded).toBe(true));
    expect(result.current.providers).toEqual([]);
  });

  it('reports no providers when the backend has none configured', async () => {
    vi.mocked(authService.getOAuthProviders).mockResolvedValue({ providers: [] });

    const { result } = renderHook(() => useOAuthProviders());

    await waitFor(() => expect(result.current.loaded).toBe(true));
    expect(result.current.providers).toEqual([]);
  });
});
