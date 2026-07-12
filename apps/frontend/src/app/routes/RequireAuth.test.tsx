import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { RequireAuth } from './RequireAuth';
import { useAuthStore } from '@/app/store/useAuthStore';
import { authService } from '@/shared/services/api';

function renderGuarded(initialEntry: string) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <div>Login Page</div> },
      {
        element: <RequireAuth />,
        children: [{ path: '/', element: <div>Protected Home</div> }],
      },
    ],
    { initialEntries: [initialEntry] },
  );
  return render(<RouterProvider router={router} />);
}

describe('RequireAuth', () => {
  beforeEach(() => {
    useAuthStore.setState({ status: 'initialising', accessToken: null, user: null });
  });

  it('redirects anonymous users to /login', async () => {
    useAuthStore.setState({ status: 'unauthenticated' });

    renderGuarded('/');

    expect(await screen.findByText('Login Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Home')).not.toBeInTheDocument();
  });

  it('renders the protected route for authenticated users', async () => {
    useAuthStore.setState({
      status: 'authenticated',
      user: { id: 'u1', email: 'dev@example.com', createdAt: new Date().toISOString() },
    });

    renderGuarded('/');

    expect(await screen.findByText('Protected Home')).toBeInTheDocument();
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument();
  });

  it('shows a neutral loading state while initialising, not protected content or the login page', () => {
    useAuthStore.setState({ status: 'initialising' });

    renderGuarded('/');

    expect(screen.queryByText('Protected Home')).not.toBeInTheDocument();
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Loading session' })).toBeInTheDocument();
  });

  it('logout clears the session and the guard redirects to /login', async () => {
    vi.spyOn(authService, 'logout').mockResolvedValue(undefined);
    useAuthStore.setState({
      status: 'authenticated',
      accessToken: 'token-123',
      user: { id: 'u1', email: 'dev@example.com', createdAt: new Date().toISOString() },
    });

    renderGuarded('/');
    expect(await screen.findByText('Protected Home')).toBeInTheDocument();

    await useAuthStore.getState().logout();

    expect(authService.logout).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState()).toMatchObject({
      status: 'unauthenticated',
      accessToken: null,
      user: null,
    });
    expect(await screen.findByText('Login Page')).toBeInTheDocument();
  });
});
