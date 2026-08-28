import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OAuthCompletePage } from './OAuthCompletePage';
import { useAuthStore } from '@/app/store/useAuthStore';
import { authService } from '@/shared/services/api';

vi.mock('@/shared/services/api', () => ({
  authService: { confirmOAuthLink: vi.fn() },
  getErrorMessage: vi.fn((error: unknown) => String(error)),
  configureApiClient: vi.fn(),
  requestSharedRefresh: vi.fn(),
}));

function DashboardStub() {
  return <p>Dashboard landed</p>;
}
function SettingsStub() {
  return <p>Settings landed</p>;
}
function LoginStub() {
  return <p>Login landed</p>;
}

function renderAt(path: string) {
  const router = createMemoryRouter(
    [
      { path: '/oauth/complete', element: <OAuthCompletePage /> },
      { path: '/dashboard', element: <DashboardStub /> },
      { path: '/settings', element: <SettingsStub /> },
      { path: '/login', element: <LoginStub /> },
    ],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
}

beforeEach(() => {
  vi.mocked(authService.confirmOAuthLink).mockReset();
  useAuthStore.setState({
    status: 'unauthenticated',
    accessToken: null,
    user: null,
    bootstrap: vi.fn().mockResolvedValue(undefined),
  });
});

describe('OAuthCompletePage', () => {
  it('status=success bootstraps the session and lands on /dashboard', async () => {
    const bootstrap = vi.fn().mockResolvedValue(undefined);
    useAuthStore.setState({ bootstrap });

    renderAt('/oauth/complete?status=success');

    await screen.findByText('Dashboard landed');
    expect(bootstrap).toHaveBeenCalled();
  });

  it('status=linked bootstraps the session and lands on Settings', async () => {
    const bootstrap = vi.fn().mockResolvedValue(undefined);
    useAuthStore.setState({ bootstrap });

    renderAt('/oauth/complete?status=linked');

    await screen.findByText('Settings landed');
    expect(bootstrap).toHaveBeenCalled();
  });

  it('status=pending-link shows a password form and confirms the link on submit', async () => {
    const setSession = vi.fn();
    useAuthStore.setState({ setSession });
    vi.mocked(authService.confirmOAuthLink).mockResolvedValue({
      accessToken: 'tok',
      tokenType: 'bearer',
      user: { id: 'u1', email: 'a@example.com', createdAt: new Date().toISOString() },
    });

    renderAt('/oauth/complete?status=pending-link&pendingLinkId=p1&provider=google');

    const passwordInput = await screen.findByLabelText('Password');
    fireEvent.change(passwordInput, { target: { value: 'correct-horse-battery-staple' } });
    fireEvent.click(screen.getByRole('button', { name: /Confirm and link account/ }));

    await waitFor(() =>
      expect(authService.confirmOAuthLink).toHaveBeenCalledWith({
        pendingLinkId: 'p1',
        password: 'correct-horse-battery-staple',
      }),
    );
    await screen.findByText('Dashboard landed');
    expect(setSession).toHaveBeenCalled();
  });

  it('status=pending-link shows an error and does not navigate on a wrong password', async () => {
    vi.mocked(authService.confirmOAuthLink).mockRejectedValue(new Error('Invalid email or password.'));

    renderAt('/oauth/complete?status=pending-link&pendingLinkId=p1&provider=google');

    const passwordInput = await screen.findByLabelText('Password');
    fireEvent.change(passwordInput, { target: { value: 'wrong-password' } });
    fireEvent.click(screen.getByRole('button', { name: /Confirm and link account/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.');
    expect(screen.queryByText('Dashboard landed')).not.toBeInTheDocument();
  });

  it('status=error with a known reason shows the mapped, friendly message', async () => {
    renderAt('/oauth/complete?status=error&reason=signup_requires_invite');

    expect(await screen.findByText(/invite-only during the beta/)).toBeInTheDocument();
  });

  it('status=error with an unrecognized or missing reason shows a generic message', async () => {
    renderAt('/oauth/complete?status=error');

    expect(await screen.findByText('Something went wrong completing sign-in. Please try again.')).toBeInTheDocument();
  });
});
