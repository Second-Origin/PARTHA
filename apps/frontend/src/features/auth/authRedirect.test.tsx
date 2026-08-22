import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { resolveRedirectTarget } from './authRedirect';
import { LoginPage } from '@/app/pages/LoginPage';
import { RegisterPage } from '@/app/pages/RegisterPage';
import { authService } from '@/shared/services/api';
import { useAuthStore } from '@/app/store/useAuthStore';

describe('resolveRedirectTarget', () => {
  it('returns / when there is no captured destination', () => {
    expect(resolveRedirectTarget(null)).toBe('/dashboard');
    expect(resolveRedirectTarget(undefined)).toBe('/dashboard');
    expect(resolveRedirectTarget({})).toBe('/dashboard');
  });

  it('reconstructs the full destination from pathname, search, and hash', () => {
    expect(resolveRedirectTarget({ from: { pathname: '/repositories/abc' } })).toBe('/repositories/abc');
    expect(
      resolveRedirectTarget({ from: { pathname: '/repositories/abc', search: '?tab=files', hash: '#section' } }),
    ).toBe('/repositories/abc?tab=files#section');
  });
});

describe('login/register redirect-destination consistency', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useAuthStore.setState({ status: 'initialising', accessToken: null, user: null });
  });

  it('preserves the intended destination through the login<->register link and after a successful register', async () => {
    const capturedFrom = { pathname: '/repositories/abc', search: '?tab=files', hash: '#section' };
    const router = createMemoryRouter(
      [
        { path: '/login', element: <LoginPage /> },
        { path: '/register', element: <RegisterPage /> },
        { path: '/repositories/:id', element: <div>Repo Detail</div> },
      ],
      { initialEntries: [{ pathname: '/login', state: { from: capturedFrom } }] },
    );
    render(<RouterProvider router={router} />);

    // Same destination RequireAuth would have captured on the way to /login.
    fireEvent.click(screen.getByRole('link', { name: 'Create one' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/register'));
    expect(router.state.location.state).toEqual({ from: capturedFrom });

    vi.spyOn(authService, 'register').mockResolvedValue({
      accessToken: 'tok',
      tokenType: 'bearer',
      user: { id: 'u1', email: 'new@example.com', createdAt: new Date().toISOString() },
    });

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'new@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'longenoughpassword' } });
    fireEvent.change(screen.getByLabelText('Invite code'), { target: { value: 'test-invite-code' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/repositories/abc'));
    expect(router.state.location.search).toBe('?tab=files');
    expect(router.state.location.hash).toBe('#section');
  });
});
