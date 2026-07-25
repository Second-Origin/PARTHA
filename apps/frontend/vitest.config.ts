import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      coverage: {
        provider: 'v8',
        all: true,
        include: ['src/**'],
        exclude: ['src/test/**', 'src/**/*.test.{ts,tsx}', 'src/vite-env.d.ts'],
        // Ratchet baseline, not an aspiration: pinned just under what the
        // suite measures today (45.94% stmts / 38.25% branches / 39.68% funcs
        // / 47.88% lines over the whole src tree). Raise it as coverage grows;
        // never lower it.
        //
        // These were left at their original seed values (1.5 / 0.25 / 2 / 1.5)
        // long after real coverage had overtaken them, so a large regression
        // could not fail the build (#154).
        thresholds: {
          statements: 45,
          branches: 37,
          functions: 39,
          lines: 47,
        },
      },
    },
  }),
);
