import { fireEvent, render, screen } from '@testing-library/react';
import { Outlet, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { productSurfaces, type DeferredProductSurface } from './productSurfaces';

vi.mock('./RequireAuth', () => ({ RequireAuth: () => <Outlet /> }));
vi.mock('@/shared/components/layout/MainLayout', () => ({ MainLayout: () => <Outlet /> }));
vi.mock('@/app/pages/DashboardPage', () => ({ DashboardPage: () => <h1>Dashboard</h1> }));

import { createAppRouter } from './router';

const deferredSurfaces = productSurfaces.filter(
  (surface): surface is DeferredProductSurface => surface.readiness === 'deferred',
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
    expect(deferredSurfaces.map((surface) => surface.id)).toEqual([
      'ai-workspace',
      'engineering-review',
      'documentation',
      'insights',
    ]);

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

  it('does not restore AI Workspace as a generic chat surface', async () => {
    const surface = deferredSurfaces.find(({ id }) => id === 'ai-workspace');
    if (!surface) throw new Error('AI Workspace must remain registered as a deferred product surface.');

    renderFreshRoute(surface.path);
    await screen.findByRole('heading', { name: surface.label, level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS });

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /send/i })).not.toBeInTheDocument();
  });
});
