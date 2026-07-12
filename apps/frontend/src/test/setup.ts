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
