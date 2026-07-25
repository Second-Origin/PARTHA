import { fireEvent, render, screen } from '@testing-library/react';
import { Outlet, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  productSurfaces,
  type DeferredProductSurface,
  type ProductSurface,
} from './productSurfaces';

vi.mock('./RequireAuth', () => ({ RequireAuth: () => <Outlet /> }));
vi.mock('@/shared/components/layout/MainLayout', () => ({ MainLayout: () => <Outlet /> }));
vi.mock('@/app/pages/DashboardPage', () => ({ DashboardPage: () => <h1>Dashboard</h1> }));
// Restored preview surfaces read the active repository. No repository is
// selected in this contract test, so they render their empty state -- which
// must still carry the Preview label and limitation.
vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({ activeRepository: null, completedRepositories: [] }),
}));

import { createAppRouter } from './router';

const deferredSurfaces = productSurfaces.filter(
  (surface): surface is DeferredProductSurface => surface.readiness === 'deferred',
);
const previewSurfaces = productSurfaces.filter(
  (surface): surface is Extract<ProductSurface, { readiness: 'preview' }> =>
    surface.readiness === 'preview',
);
const ROUTE_RENDER_TIMEOUT_MS = 3_000;
const FORBIDDEN_INTERNAL_TERMS =
  /#\d+|phase\s*0|phase\s*1|phase\s*2|phase\s*3|not-scheduled|beta|experimental|planned|subscription|locked|unlock|billing|score|success|entitlement/i;
let activeRouter: ReturnType<typeof createAppRouter> | null = null;

function renderFreshRoute(path: string) {
  window.history.replaceState({}, '', path);
  activeRouter = createAppRouter();
  render(<RouterProvider router={activeRouter} />);
}

describe('product surface readiness contract', () => {
  afterEach(() => {
    activeRouter?.dispose();
    activeRouter = null;
    window.history.replaceState({}, '', '/');
  });

  it('keeps every deferred surface out of primary navigation with internal roadmap metadata recorded', () => {
    expect(deferredSurfaces.map((surface) => surface.id)).toEqual([]);

    for (const surface of deferredSurfaces) {
      expect(surface.primaryNavigation).toBe(false);
      expect(surface.blockingIssues.length).toBeGreaterThan(0);
      expect(surface.phase).toBeDefined();
      expect(surface.unavailableMessage.length).toBeGreaterThan(0);
    }
  });

  it.each(deferredSurfaces)(
    'renders an honest, accessible unavailable state for $label after a direct refresh of $path',
    async (surface) => {
      renderFreshRoute(surface.path);

      expect(
        await screen.findByRole('heading', { name: surface.label, level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS }),
      ).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: `${surface.label} isn't available yet.` })).toBeInTheDocument();
      expect(screen.getByText(surface.unavailableMessage)).toBeInTheDocument();

      const backButton = screen.getByRole('button', { name: 'Back to Dashboard' });
      expect(backButton).toBeInTheDocument();
      fireEvent.click(backButton);
      expect(
        await screen.findByRole('heading', { name: 'Dashboard', level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS }),
      ).toBeInTheDocument();
    },
  );

  it.each(deferredSurfaces)(
    'never exposes tracker IDs, phase codes, maturity badges, or entitlement language on $path',
    async (surface) => {
      renderFreshRoute(surface.path);
      await screen.findByRole('heading', { name: surface.label, level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS });

      expect(document.body.textContent).not.toMatch(FORBIDDEN_INTERNAL_TERMS);
    },
  );

  it('records a user-facing limitation for every restored preview surface', () => {
    expect(previewSurfaces.map((surface) => surface.id)).toEqual([
      'dependencies',
      'ai-workspace',
      'documentation',
    ]);

    for (const surface of previewSurfaces) {
      expect(surface.limitation.length).toBeGreaterThan(0);
      // A preview surface is reachable, so it must carry an icon for primary
      // navigation and must not smuggle roadmap metadata into user-facing copy.
      expect(surface.icon).toBeDefined();
      expect(surface.limitation).not.toMatch(FORBIDDEN_INTERNAL_TERMS);
    }
  });

  it('keeps Engineering Review and Insights restored in primary navigation', () => {
    const review = productSurfaces.find((surface) => surface.id === 'engineering-review');
    const insights = productSurfaces.find((surface) => surface.id === 'insights');

    expect(review).toMatchObject({ readiness: 'ready', primaryNavigation: true, path: '/review' });
    expect(insights).toMatchObject({ readiness: 'ready', primaryNavigation: true, path: '/insights' });
  });

  it.each(previewSurfaces)(
    'always labels $label as Preview and states its limitation on $path',
    async (surface) => {
      renderFreshRoute(surface.path);
      await screen.findByRole('heading', { name: surface.label, level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS });

      // The restored surface must never render as if it were fully verified:
      // the Preview label and its limitation are part of the surface itself,
      // not an optional decoration on one of its states.
      expect(screen.getAllByTestId('preview-banner').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Preview').length).toBeGreaterThan(0);
      expect(screen.getAllByText(surface.limitation).length).toBeGreaterThan(0);
    },
  );

  it.each(previewSurfaces)(
    'never exposes tracker IDs, phase codes, or entitlement language on $path',
    async (surface) => {
      renderFreshRoute(surface.path);
      await screen.findByRole('heading', { name: surface.label, level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS });

      expect(document.body.textContent).not.toMatch(FORBIDDEN_INTERNAL_TERMS);
    },
  );
});
