import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { useLandingThemeStore } from './useLandingTheme';

describe('useLandingThemeStore', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it('resolves and persists the choice when set to dark', () => {
    useLandingThemeStore.getState().setPreference('dark');

    expect(window.localStorage.getItem('partha-landing-theme')).toBe('dark');
    expect(useLandingThemeStore.getState().resolved).toBe('dark');
  });

  it('resolves and persists the choice when set to light', () => {
    useLandingThemeStore.getState().setPreference('dark');
    useLandingThemeStore.getState().setPreference('light');

    expect(window.localStorage.getItem('partha-landing-theme')).toBe('light');
    expect(useLandingThemeStore.getState().resolved).toBe('light');
  });

  it('falls back to system preference when set to system', () => {
    useLandingThemeStore.getState().setPreference('system');

    expect(window.localStorage.getItem('partha-landing-theme')).toBe('system');
    // jsdom's mocked matchMedia always reports light, so system resolves light here.
    expect(useLandingThemeStore.getState().resolved).toBe('light');
  });

  it('never touches document.documentElement -- callers own where the class is applied', () => {
    useLandingThemeStore.getState().setPreference('dark');

    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.classList.contains('landing-dark')).toBe(false);
  });

  it('uses its own storage key, independent of any app-wide theme key', () => {
    useLandingThemeStore.getState().setPreference('dark');

    expect(window.localStorage.getItem('partha-theme')).toBeNull();
  });
});
