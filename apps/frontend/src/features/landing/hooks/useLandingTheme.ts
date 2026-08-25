import { create } from 'zustand';

export type LandingThemePreference = 'light' | 'dark' | 'system';
type ResolvedLandingTheme = 'light' | 'dark';

const STORAGE_KEY = 'partha-landing-theme';

function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function resolve(preference: LandingThemePreference): ResolvedLandingTheme {
  return preference === 'system' ? (systemPrefersDark() ? 'dark' : 'light') : preference;
}

function readStoredPreference(): LandingThemePreference {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
}

interface LandingThemeState {
  preference: LandingThemePreference;
  resolved: ResolvedLandingTheme;
  setPreference: (preference: LandingThemePreference) => void;
}

/** Deliberately does not touch document.documentElement or any class
 * outside the landing page's own subtree (see LandingPage.tsx, which
 * applies `.landing-dark` to its own root element only) -- the app's
 * own routes must never be able to receive dark styling through this
 * store, by construction rather than by convention. */
export const useLandingThemeStore = create<LandingThemeState>((set) => ({
  preference: readStoredPreference(),
  resolved: resolve(readStoredPreference()),
  setPreference: (preference) => {
    window.localStorage.setItem(STORAGE_KEY, preference);
    set({ preference, resolved: resolve(preference) });
  },
}));

if (typeof window !== 'undefined') {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const { preference } = useLandingThemeStore.getState();
    if (preference !== 'system') return;
    useLandingThemeStore.setState({ resolved: resolve('system') });
  });
}

export function useLandingTheme() {
  return useLandingThemeStore();
}
