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
        // suite measures today (60.29% stmts / 55.95% branches / 57.21% funcs
        // / 62.77% lines over the whole src tree, after #338 raised coverage
        // on the API client/service layer and core layout). Raise it as
        // coverage grows; never lower it.
        //
        // These were left at their original seed values (1.5 / 0.25 / 2 / 1.5)
        // long after real coverage had overtaken them, so a large regression
        // could not fail the build (#154). The previous ratchet (45/37/39/47)
        // had the same problem: real coverage had climbed well past it.
        thresholds: {
          statements: 58,
          branches: 53,
          functions: 55,
          lines: 60,
        },
      },
    },
  }),
);
