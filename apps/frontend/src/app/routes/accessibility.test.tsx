import { render, screen } from '@testing-library/react';
import { Outlet, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { productSurfaces } from './productSurfaces';
import { describeViolations, findAccessibilityViolations } from '@/test/axe';

vi.mock('./RequireAuth', () => ({ RequireAuth: () => <Outlet /> }));
vi.mock('@/shared/components/layout/MainLayout', () => ({ MainLayout: () => <Outlet /> }));
// No repository is selected, so each surface renders its empty state. That is
// the state a first-time user actually meets, and it must be accessible too.
vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({
    repositories: [],
    completedRepositories: [],
    activeRepository: null,
    loading: false,
    error: null,
    selectRepository: () => undefined,
    removeRepository: async () => undefined,
    refresh: () => undefined,
    retry: () => undefined,
  }),
}));

import { createAppRouter } from './router';

const ROUTE_RENDER_TIMEOUT_MS = 3_000;

/** Every surface a prototype user can actually open. */
const activeSurfaces = productSurfaces.filter(
  (surface) => surface.readiness === 'ready' || surface.readiness === 'preview',
);

let activeRouter: ReturnType<typeof createAppRouter> | null = null;

describe('accessibility smoke checks for active prototype routes', () => {
  afterEach(() => {
    activeRouter?.dispose();
    activeRouter = null;
    window.history.replaceState({}, '', '/');
  });

  it.each(activeSurfaces)('has no detectable accessibility violations on $path', async (surface) => {
    window.history.replaceState({}, '', surface.path);
    activeRouter = createAppRouter();
    const { container } = render(<RouterProvider router={activeRouter} />);

    await screen.findByRole(
      'heading',
      { name: surface.label, level: 1 },
      { timeout: ROUTE_RENDER_TIMEOUT_MS },
    );

    const violations = await findAccessibilityViolations(container);
    expect(violations, describeViolations(violations)).toEqual([]);
  }, 20_000);
});
