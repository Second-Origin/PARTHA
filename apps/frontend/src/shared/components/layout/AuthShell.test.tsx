import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LoginPage } from '@/app/pages/LoginPage';
import { RegisterPage } from '@/app/pages/RegisterPage';
import { useLandingThemeStore } from '@/features/landing/hooks/useLandingTheme';

/** #342 originally leaked dark styling into AuthShell (used by /login and
 * /register) because the app's old theme mechanism applied .dark to
 * <html> globally. That mechanism is gone; these routes never had their
 * own toggle and structurally cannot receive dark styling from anywhere
 * now -- this is a regression test for that, not a feature. */
describe('AuthShell is immune to the landing page theme', () => {
  beforeEach(() => {
    window.localStorage.clear();
    // Simulate a visitor who set the landing page to dark before
    // navigating to /login -- a plausible real-world sequence, and the
    // one case that could plausibly leak if scoping were done wrong.
    useLandingThemeStore.setState({ preference: 'dark', resolved: 'dark' });
  });

  afterEach(() => {
    window.localStorage.clear();
    useLandingThemeStore.setState({ preference: 'light', resolved: 'light' });
  });

  it('LoginPage never receives dark or landing-dark styling', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: 'Sign in to PARTHA' })).toBeInTheDocument();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.classList.contains('landing-dark')).toBe(false);
    expect(document.querySelector('.landing-dark')).toBeNull();
  });

  it('RegisterPage never receives dark or landing-dark styling', () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    );

    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.classList.contains('landing-dark')).toBe(false);
    expect(document.querySelector('.landing-dark')).toBeNull();
  });
});
