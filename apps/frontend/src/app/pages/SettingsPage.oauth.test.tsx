import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsPage } from './SettingsPage';
import { settingsTabs, useSettings } from '@/features/settings/hooks/useSettings';
import { useOAuthAccounts } from '@/features/settings/hooks/useOAuthAccounts';
import { useAuthStore } from '@/app/store/useAuthStore';

// #288: dedicated to the "Connected accounts" card, kept out of
// SettingsPage.test.tsx to avoid entangling with that file's AI-provider
// mocking setup -- useOAuthAccounts is mocked directly here instead of
// exercising the real API layer.
vi.mock('@/features/settings/hooks/useSettings', async () => {
  const actual = await vi.importActual<typeof import('@/features/settings/hooks/useSettings')>(
    '@/features/settings/hooks/useSettings',
  );
  return { ...actual, useSettings: vi.fn() };
});

vi.mock('@/features/settings/hooks/useOAuthAccounts', () => ({
  useOAuthAccounts: vi.fn(),
}));

// Only the fields the "General" tab actually reads -- cast rather than
// filling in every field of useSettings()'s much larger AI-provider-setup
// shape, which this file never touches.
function baseSettings(): ReturnType<typeof useSettings> {
  return {
    tabs: settingsTabs,
    activeTab: 'General',
    setActiveTab: vi.fn(),
  } as unknown as ReturnType<typeof useSettings>;
}

function baseOAuthAccounts() {
  return {
    identities: [] as { provider: string; email: string | null; createdAt: string }[],
    loadError: null,
    linkableProviders: [] as ('google' | 'github')[],
    pendingAction: null,
    actionError: null,
    link: vi.fn(),
    unlink: vi.fn(),
  };
}

beforeEach(() => {
  vi.mocked(useSettings).mockReturnValue(baseSettings());
  useAuthStore.setState({
    user: { id: 'u1', email: 'a@example.com', createdAt: new Date().toISOString() },
  });
});

describe('SettingsPage connected accounts (#288)', () => {
  it('renders nothing extra when no provider is configured and nothing is linked', () => {
    vi.mocked(useOAuthAccounts).mockReturnValue(baseOAuthAccounts());

    render(<SettingsPage />);

    expect(screen.queryByText('Connected accounts')).not.toBeInTheDocument();
  });

  it('offers to link a configured, not-yet-linked provider', async () => {
    const link = vi.fn();
    vi.mocked(useOAuthAccounts).mockReturnValue({ ...baseOAuthAccounts(), linkableProviders: ['google'], link });

    render(<SettingsPage />);

    expect(screen.getByText('Connected accounts')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Link' }));
    expect(link).toHaveBeenCalledWith('google');
  });

  it('lists a linked identity with its email and an Unlink action', async () => {
    const unlink = vi.fn();
    vi.mocked(useOAuthAccounts).mockReturnValue({
      ...baseOAuthAccounts(),
      identities: [{ provider: 'github', email: 'dev@example.com', createdAt: new Date().toISOString() }],
      unlink,
    });

    render(<SettingsPage />);

    expect(screen.getByText('GitHub')).toBeInTheDocument();
    expect(screen.getByText('dev@example.com')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Unlink' }));
    await waitFor(() => expect(unlink).toHaveBeenCalledWith('github'));
  });

  it('shows an action error (e.g. refusing to remove the only sign-in method)', () => {
    vi.mocked(useOAuthAccounts).mockReturnValue({
      ...baseOAuthAccounts(),
      identities: [{ provider: 'google', email: 'a@example.com', createdAt: new Date().toISOString() }],
      actionError: 'This is your only way to sign in to this account. Link another provider before removing it.',
    });

    render(<SettingsPage />);

    expect(screen.getByRole('alert')).toHaveTextContent('This is your only way to sign in');
  });
});
