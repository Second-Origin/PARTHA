import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LandingPage } from './LandingPage';
import { useLandingThemeStore } from '@/features/landing/hooks/useLandingTheme';

function renderLanding() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>
  );
}

describe('LandingPage theme', () => {
  beforeEach(() => {
    window.localStorage.clear();
    useLandingThemeStore.setState({ preference: 'light', resolved: 'light' });
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it('renders in light mode by default, with no landing-dark class anywhere', () => {
    renderLanding();

    const main = screen.getByRole('img').closest('main');
    expect(main).not.toHaveClass('landing-dark');
    expect(screen.getByRole('img').getAttribute('src')).toMatch(/landing-reference\.svg/);
    expect(screen.getByRole('img').getAttribute('src')).not.toMatch(/landing-reference-dark\.svg/);
  });

  it('switching to Dark applies the scoped class and swaps the canvas image', () => {
    renderLanding();

    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }));

    const main = screen.getByRole('img').closest('main');
    expect(main).toHaveClass('landing-dark');
    expect(screen.getByRole('img').getAttribute('src')).toMatch(/landing-reference-dark\.svg/);
  });

  it('switching back to Light removes the scoped class and restores the light canvas', () => {
    renderLanding();

    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }));
    fireEvent.click(screen.getByRole('radio', { name: 'Light' }));

    const main = screen.getByRole('img').closest('main');
    expect(main).not.toHaveClass('landing-dark');
    expect(screen.getByRole('img').getAttribute('src')).toMatch(/landing-reference\.svg/);
    expect(screen.getByRole('img').getAttribute('src')).not.toMatch(/landing-reference-dark\.svg/);
  });

  it('persists the preference under its own landing-scoped storage key', () => {
    renderLanding();

    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }));

    expect(window.localStorage.getItem('partha-landing-theme')).toBe('dark');
  });

  it('never applies any dark class to document.documentElement, in any state', () => {
    renderLanding();

    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.classList.contains('landing-dark')).toBe(false);

    fireEvent.click(screen.getByRole('radio', { name: 'Light' }));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.classList.contains('landing-dark')).toBe(false);
  });

  it('clears the pre-hydration boot marker on mount so it can never persist past first paint', () => {
    document.documentElement.setAttribute('data-landing-theme-boot', 'dark');

    renderLanding();

    expect(document.documentElement.hasAttribute('data-landing-theme-boot')).toBe(false);
  });

  it('unmounting the landing page leaves no trace of the scoped class on the document', () => {
    const { unmount } = renderLanding();
    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }));

    unmount();

    expect(document.documentElement.classList.contains('landing-dark')).toBe(false);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.querySelector('.landing-dark')).toBeNull();
  });
});
