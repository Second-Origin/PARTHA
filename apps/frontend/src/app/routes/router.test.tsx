import { render, screen } from '@testing-library/react';
import { Outlet, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';

// Bypasses auth/repository-fetch plumbing the same way productSurfaces.test.tsx
// and accessibility.test.tsx do, so these tests exercise real route matching
// (#179) without needing a live backend.
vi.mock('./RequireAuth', () => ({ RequireAuth: () => <Outlet /> }));
vi.mock('@/shared/components/layout/MainLayout', () => ({ MainLayout: () => <Outlet /> }));
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
let activeRouter: ReturnType<typeof createAppRouter> | null = null;

function renderFreshRoute(path: string) {
  window.history.replaceState({}, '', path);
  activeRouter = createAppRouter();
  return render(<RouterProvider router={activeRouter} />);
}

describe('deep-linked route reachability (#179)', () => {
  afterEach(() => {
    activeRouter?.dispose();
    activeRouter = null;
    window.history.replaceState({}, '', '/');
    useAppStore.setState({ activeRepositoryId: null });
  });

  it('renders the public landing page at / without mounting the workspace shell', async () => {
    renderFreshRoute('/');

    expect(
      await screen.findByRole('heading', { name: 'Reveal the system behind the code.', level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS }),
    ).toBeInTheDocument();
    for (const startLink of screen.getAllByRole('link', { name: /analyze a repository/i })) {
      expect(startLink).toHaveAttribute('href', '/register');
    }
  });

  it('renders Dashboard directly at /dashboard instead of 404ing', async () => {
    renderFreshRoute('/dashboard');

    expect(
      await screen.findByRole('heading', { name: 'Dashboard', level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS }),
    ).toBeInTheDocument();
  });

  it('renders Architecture directly at /analysis/{id}/architecture, selecting that repository', async () => {
    renderFreshRoute('/analysis/repo-42/architecture');

    expect(
      await screen.findByRole('heading', { name: 'Architecture', level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS }),
    ).toBeInTheDocument();
    expect(useAppStore.getState().activeRepositoryId).toBe('repo-42');
  });

  it('renders a NotFound page instead of crashing on an unknown route', async () => {
    renderFreshRoute('/this-route-does-not-exist');

    expect(
      await screen.findByRole('heading', { name: 'Page not found', level: 1 }, { timeout: ROUTE_RENDER_TIMEOUT_MS }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Unexpected Application Error/i)).not.toBeInTheDocument();
  });
});
