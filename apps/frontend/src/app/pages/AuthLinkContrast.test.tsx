import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { LoginPage } from './LoginPage';
import { RegisterPage } from './RegisterPage';

// #240: the register/login inline links must not rely on color alone to
// signal that they are links -- they need a persistent, non-hover
// distinction (an underline) at rest.
describe('auth inline link non-color affordance (#240)', () => {
  it('underlines the login page register link at rest, not only on hover', () => {
    const router = createMemoryRouter([{ path: '/login', element: <LoginPage /> }], {
      initialEntries: ['/login'],
    });
    render(<RouterProvider router={router} />);

    const link = screen.getByRole('link', { name: 'Create one' });
    expect(link.className.split(' ')).toEqual(expect.arrayContaining(['underline']));
    expect(link.className).not.toContain('hover:underline');
  });

  it('underlines the register page sign-in link at rest, not only on hover', () => {
    const router = createMemoryRouter([{ path: '/register', element: <RegisterPage /> }], {
      initialEntries: ['/register'],
    });
    render(<RouterProvider router={router} />);

    const link = screen.getByRole('link', { name: 'Sign in' });
    expect(link.className.split(' ')).toEqual(expect.arrayContaining(['underline']));
    expect(link.className).not.toContain('hover:underline');
  });
});
