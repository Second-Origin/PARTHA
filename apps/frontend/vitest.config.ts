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
        // seed tests measure today (1.69% stmts / 0.28% branches / 2.52%
        // funcs / 1.87% lines over the whole src tree). Raise it as coverage
        // grows; never lower it.
        thresholds: {
          statements: 1.5,
          branches: 0.25,
          functions: 2,
          lines: 1.5,
        },
      },
    },
  }),
);
