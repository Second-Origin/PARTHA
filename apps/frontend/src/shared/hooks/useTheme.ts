import { create } from 'zustand';

export type ThemePreference = 'light' | 'dark' | 'system';
type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'partha-theme';

function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function resolve(preference: ThemePreference): ResolvedTheme {
  return preference === 'system' ? (systemPrefersDark() ? 'dark' : 'light') : preference;
}

function readStoredPreference(): ThemePreference {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
}

/** Keeps `<html>.dark` in sync so every `dark:`-aware and token-driven style
 * updates immediately. The same class toggle also runs pre-hydration in
 * index.html to avoid a flash of the wrong theme on first paint. */
function applyResolvedTheme(resolved: ResolvedTheme): void {
  document.documentElement.classList.toggle('dark', resolved === 'dark');
}

interface ThemeState {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setPreference: (preference: ThemePreference) => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  preference: readStoredPreference(),
  resolved: resolve(readStoredPreference()),
  setPreference: (preference) => {
    window.localStorage.setItem(STORAGE_KEY, preference);
    const resolved = resolve(preference);
    applyResolvedTheme(resolved);
    set({ preference, resolved });
  },
}));

if (typeof window !== 'undefined') {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const { preference } = useThemeStore.getState();
    if (preference !== 'system') return;
    const resolved = resolve('system');
    applyResolvedTheme(resolved);
    useThemeStore.setState({ resolved });
  });
}

export function useTheme() {
  return useThemeStore();
}
