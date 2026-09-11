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

/** The footer switch the design draws: monitor / sun / moon in one pill. */
const dark = () => screen.getByRole('button', { name: 'Dark appearance' });
const light = () => screen.getByRole('button', { name: 'Light appearance' });

/** The page's own root -- the only element the dark palette may ever reach. */
const landingRoot = () => document.querySelector('main');

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

    expect(landingRoot()).not.toHaveClass('landing-dark');
    expect(document.querySelector('.landing-dark')).toBeNull();
  });

  it('renders the design canvas itself, not a flattened image of it', () => {
    renderLanding();

    // The canvas is real elements: its controls are reachable by role, which
    // is the whole point of replacing the exported artwork.
    expect(document.querySelector('.landing-canvas')).not.toBeNull();
    expect(screen.getByRole('button', { name: 'Next capability' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Is PARTHA an AI product?' })).toBeInTheDocument();
  });

  it('switching to Dark applies the scoped class', () => {
    renderLanding();

    fireEvent.click(dark());

    expect(landingRoot()).toHaveClass('landing-dark');
  });

  it('switching back to Light removes the scoped class', () => {
    renderLanding();

    fireEvent.click(dark());
    fireEvent.click(light());

    expect(landingRoot()).not.toHaveClass('landing-dark');
  });

  it('marks the selected appearance as pressed so it reads as lit', () => {
    renderLanding();

    fireEvent.click(dark());

    expect(dark()).toHaveAttribute('aria-pressed', 'true');
    expect(light()).toHaveAttribute('aria-pressed', 'false');
  });

  it('persists the preference under its own landing-scoped storage key', () => {
    renderLanding();

    fireEvent.click(dark());

    expect(window.localStorage.getItem('partha-landing-theme')).toBe('dark');
  });

  it('never applies any dark class to document.documentElement, in any state', () => {
    renderLanding();

    fireEvent.click(dark());
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.classList.contains('landing-dark')).toBe(false);

    fireEvent.click(light());
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
    fireEvent.click(dark());

    unmount();

    expect(document.documentElement.classList.contains('landing-dark')).toBe(false);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.querySelector('.landing-dark')).toBeNull();
  });
});

describe('LandingPage interactions', () => {
  beforeEach(() => {
    window.localStorage.clear();
    useLandingThemeStore.setState({ preference: 'light', resolved: 'light' });
  });

  it('advances the capabilities carousel and wraps back round', () => {
    renderLanding();

    const next = screen.getByRole('button', { name: 'Next capability' });
    expect(screen.getByText('Deterministic extraction')).toBeInTheDocument();

    fireEvent.click(next);
    expect(screen.getByText('Evidence backed')).toBeInTheDocument();

    for (let i = 0; i < 5; i += 1) fireEvent.click(next);
    expect(screen.getByText('Deterministic extraction')).toBeInTheDocument();
  });

  it('opens one FAQ answer at a time', () => {
    renderLanding();

    const first = screen.getByRole('button', { name: 'Is PARTHA an AI product?' });
    const second = screen.getByRole('button', { name: 'Where does PARTHA run?' });

    fireEvent.click(first);
    expect(first).toHaveAttribute('aria-expanded', 'true');

    fireEvent.click(second);
    expect(first).toHaveAttribute('aria-expanded', 'false');
    expect(second).toHaveAttribute('aria-expanded', 'true');
  });
});
