import { render, screen } from '@testing-library/react';
import { Outlet, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { productSurfaces, type DeferredProductSurface } from './productSurfaces';

vi.mock('./RequireAuth', () => ({ RequireAuth: () => <Outlet /> }));
vi.mock('@/shared/components/layout/MainLayout', () => ({ MainLayout: () => <Outlet /> }));

import { createAppRouter } from './router';

const deferredSurfaces = productSurfaces.filter(
  (surface): surface is DeferredProductSurface => surface.readiness === 'deferred',
);
const ROUTE_RENDER_TIMEOUT_MS = 3_000;
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

  it('keeps every deferred surface out of primary navigation with an explicit phase and blocking work', () => {
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
    }
  });

  it.each(deferredSurfaces)('renders an honest deferred state after a direct refresh of $path', async (surface) => {
    renderFreshRoute(surface.path);

    expect(
      await screen.findByRole('heading', {
        name: `${surface.label} is not available in the current delivery phase.`,
      }, { timeout: ROUTE_RENDER_TIMEOUT_MS }),
    ).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`Blocking work: ${surface.blockingIssues.map((issue) => `#${issue}`).join(' and ')}\\.`)))
      .toBeInTheDocument();
    expect(screen.queryByText(/subscription|locked|unlock|score|success/i)).not.toBeInTheDocument();
  });

  it('does not restore AI Workspace as a generic chat surface', async () => {
    const surface = deferredSurfaces.find(({ id }) => id === 'ai-workspace');
    if (!surface) throw new Error('AI Workspace must remain registered as a deferred product surface.');

    renderFreshRoute(surface.path);
    await screen.findByRole(
      'heading',
      { name: 'AI Workspace is not available in the current delivery phase.' },
      { timeout: ROUTE_RENDER_TIMEOUT_MS },
    );

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /send/i })).not.toBeInTheDocument();
  });
});
