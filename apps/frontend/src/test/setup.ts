import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

// This project runs Vitest without `globals`, so React Testing Library cannot
// auto-register its afterEach cleanup (it only does so when `afterEach` is a
// global). Register it explicitly, or mounted components leak into the next
// test's document.
afterEach(() => {
  cleanup();
});

// jsdom does not implement matchMedia. Anything that reads system theme
// preference (useTheme) needs this present at module-eval time, not just
// inside a test body.
if (typeof window.matchMedia !== 'function') {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }) as MediaQueryList;
}
