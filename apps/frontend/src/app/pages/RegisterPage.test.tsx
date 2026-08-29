import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RegisterPage } from './RegisterPage';
import { authService } from '@/shared/services/api';
import { ApiError } from '@/shared/services/api/errors';

// #374: registration no longer takes an invite code -- these lock in the
// field's removal and the allowlist-rejection error surfacing correctly.
describe('RegisterPage (#374 approved-email allowlist)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function renderPage() {
    const router = createMemoryRouter([{ path: '/register', element: <RegisterPage /> }], {
      initialEntries: ['/register'],
    });
    return render(<RouterProvider router={router} />);
  }

  it('has no invite code field', () => {
    renderPage();

    expect(screen.queryByLabelText(/invite code/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('still points an unapproved visitor at a way to get access', () => {
    renderPage();

    expect(screen.getByText(/not approved yet/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Get in touch' })).toHaveAttribute(
      'href',
      'https://discord.gg/qvk9DcxDA',
    );
  });

  it('submits only email and password, and surfaces the allowlist rejection message', async () => {
    vi.spyOn(authService, 'register').mockRejectedValue(
      new ApiError(
        422,
        'Unprocessable Content',
        { code: 'validation_error', message: "This email hasn't been approved for access yet. Join the waitlist and we'll be in touch." },
        '/auth/register',
        null,
      ),
    );

    renderPage();
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'nobody@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'longenoughpassword' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() =>
      expect(authService.register).toHaveBeenCalledWith({ email: 'nobody@example.com', password: 'longenoughpassword' }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent("hasn't been approved");
  });
});
