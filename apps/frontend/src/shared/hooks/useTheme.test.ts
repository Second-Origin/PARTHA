import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { useThemeStore } from './useTheme';

describe('useThemeStore', () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('applies the dark class and persists the choice when set to dark', () => {
    useThemeStore.getState().setPreference('dark');

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(window.localStorage.getItem('partha-theme')).toBe('dark');
    expect(useThemeStore.getState().resolved).toBe('dark');
  });

  it('removes the dark class and persists the choice when set to light', () => {
    useThemeStore.getState().setPreference('dark');
    useThemeStore.getState().setPreference('light');

    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(window.localStorage.getItem('partha-theme')).toBe('light');
    expect(useThemeStore.getState().resolved).toBe('light');
  });

  it('falls back to system preference when set to system', () => {
    useThemeStore.getState().setPreference('system');

    expect(window.localStorage.getItem('partha-theme')).toBe('system');
    // jsdom's mocked matchMedia always reports light, so system resolves light here.
    expect(useThemeStore.getState().resolved).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});
