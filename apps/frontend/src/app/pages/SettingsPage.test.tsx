import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsPage } from './SettingsPage';
import { useAuthStore } from '@/app/store/useAuthStore';
import { authService } from '@/shared/services/api';
import { ApiError } from '@/shared/services/api/errors';

const mockActiveTab = vi.hoisted(() => vi.fn(() => 'Notifications'));
vi.mock('@/features/settings/hooks/useSettings', () => ({
  useSettings: () => ({
    tabs: ['General', 'AI Providers', 'Notifications', 'API Keys'],
    activeTab: mockActiveTab(),
    setActiveTab: vi.fn(),
  }),
}));

describe('SettingsPage notification preferences', () => {
  it('discloses the upcoming state and gives each disabled switch a unique accessible name', () => {
    render(<SettingsPage />);

    expect(screen.getByText('Coming Soon')).toBeVisible();
    expect(
      screen.getByText('Notification preferences are in development and cannot be configured yet.'),
    ).toBeVisible();

    for (const preference of ['Analysis complete', 'Error alerts', 'New insights available']) {
      const control = screen.getByRole('switch', {
        name: `${preference} notifications (coming soon)`,
      });

      expect(control).toBeDisabled();
      expect(control).toHaveAttribute('aria-checked', 'false');
      const thumb = within(control).getByRole('generic', { hidden: true });
      expect(thumb).toHaveAttribute('aria-hidden', 'true');
      expect(thumb).toHaveClass('left-0.5');
      expect(thumb).not.toHaveClass('right-0.5');
    }
  });
});

describe('SettingsPage account deletion', () => {
  beforeEach(() => {
    mockActiveTab.mockReturnValue('General');
    useAuthStore.setState({
      status: 'authenticated',
      accessToken: 'a-token',
      user: { id: 'user-1', email: 'alice@example.com', createdAt: '2026-01-01T00:00:00Z' },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    useAuthStore.setState({ status: 'initialising', accessToken: null, user: null });
  });

  it('keeps the confirm button disabled until the account email is typed back exactly', () => {
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete Account' }));

    const confirmButton = screen.getByRole('button', { name: 'Permanently Delete Account' });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Type alice@example.com to confirm/i), {
      target: { value: 'wrong@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'correct-horse-battery' } });
    expect(confirmButton).toBeDisabled();
  });

  it('deletes the account and clears local session state on success', async () => {
    const deleteAccount = vi.spyOn(authService, 'deleteAccount').mockResolvedValue(undefined);
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete Account' }));
    fireEvent.change(screen.getByLabelText(/Type alice@example.com to confirm/i), {
      target: { value: 'alice@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'correct-horse-battery' } });

    const confirmButton = screen.getByRole('button', { name: 'Permanently Delete Account' });
    expect(confirmButton).toBeEnabled();
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(deleteAccount).toHaveBeenCalledWith({
        password: 'correct-horse-battery',
        confirmEmail: 'alice@example.com',
      });
    });
    await waitFor(() => expect(useAuthStore.getState().status).toBe('unauthenticated'));
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('surfaces a wrong-password rejection without clearing the session', async () => {
    vi.spyOn(authService, 'deleteAccount').mockRejectedValue(
      new ApiError(401, 'Unauthorized', { code: 'unauthorized', message: 'Invalid password.' }, '/auth/me'),
    );
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete Account' }));
    fireEvent.change(screen.getByLabelText(/Type alice@example.com to confirm/i), {
      target: { value: 'alice@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Permanently Delete Account' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid password.');
    expect(useAuthStore.getState().status).toBe('authenticated');
  });

  it('cancel collapses the panel and clears the entered fields', () => {
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete Account' }));
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'some-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.getByRole('button', { name: 'Delete Account' })).toBeVisible();
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
  });
});
