import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { RequireAuth } from './RequireAuth';
import { useAuthStore } from '@/app/store/useAuthStore';
import { authService, repositoryService } from '@/shared/services/api';
import { RepositoryProvider } from '@/features/repositories/context/RepositoryProvider';
import { useRepository } from '@/features/repositories/hooks/useRepository';

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

// Stands in for MainLayout, which wraps its authenticated Outlet with the
// real RepositoryProvider — mirrors that structure without pulling in
// Sidebar/TopBar's unrelated chrome and dependencies.
function RepoProbe() {
  const { repositories, loading } = useRepository();
  return <div>Repos: {repositories.length}{loading ? ' (loading)' : ''}</div>;
}

function renderGuardedWithRepositoryProvider(initialEntry: string) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <div>Login Page</div> },
      {
        element: <RequireAuth />,
        children: [
          {
            path: '/',
            element: (
              <RepositoryProvider>
                <RepoProbe />
              </RepositoryProvider>
            ),
          },
        ],
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

  afterEach(() => {
    vi.restoreAllMocks();
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

describe('RepositoryProvider gating (mirrors MainLayout mounting it inside RequireAuth)', () => {
  beforeEach(() => {
    useAuthStore.setState({ status: 'initialising', accessToken: null, user: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not fetch repositories while the guard is unauthenticated', async () => {
    const listSpy = vi.spyOn(repositoryService, 'list').mockResolvedValue({ data: [], total: 0 });
    useAuthStore.setState({ status: 'unauthenticated' });

    renderGuardedWithRepositoryProvider('/');

    expect(await screen.findByText('Login Page')).toBeInTheDocument();
    expect(listSpy).not.toHaveBeenCalled();
  });

  it('does not fetch repositories while the guard is still initialising', async () => {
    const listSpy = vi.spyOn(repositoryService, 'list').mockResolvedValue({ data: [], total: 0 });
    useAuthStore.setState({ status: 'initialising' });

    renderGuardedWithRepositoryProvider('/');

    await screen.findByRole('status', { name: 'Loading session' });
    expect(listSpy).not.toHaveBeenCalled();
  });

  it('fetches repositories once the guard confirms an authenticated session', async () => {
    const listSpy = vi.spyOn(repositoryService, 'list').mockResolvedValue({ data: [], total: 0 });
    useAuthStore.setState({
      status: 'authenticated',
      user: { id: 'u1', email: 'dev@example.com', createdAt: new Date().toISOString() },
    });

    renderGuardedWithRepositoryProvider('/');

    await waitFor(() => expect(listSpy).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('Repos: 0')).toBeInTheDocument();
  });
});
