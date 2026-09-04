import { createBrowserRouter, Outlet } from 'react-router-dom';
import { MainLayout } from '@/shared/components/layout/MainLayout';
import { RequireAuth } from './RequireAuth';
import { RootHydrateFallback } from './RootHydrateFallback';
import { productSurfaceRoutes } from './productSurfaces';

export function createAppRouter() {
  return createBrowserRouter([
    {
      Component: Outlet,
      HydrateFallback: RootHydrateFallback,
      children: [
        {
          path: '/',
          lazy: async () => {
            const { LandingPage } = await import('@/app/pages/LandingPage');
            return { Component: LandingPage };
          },
        },
        {
          path: '/login',
          lazy: async () => {
            const { LoginPage } = await import('@/app/pages/LoginPage');
            return { Component: LoginPage };
          },
        },
        {
          path: '/register',
          lazy: async () => {
            const { RegisterPage } = await import('@/app/pages/RegisterPage');
            return { Component: RegisterPage };
          },
        },
        {
          // Landing point for every OAuth provider redirect (#288). Public and
          // outside RequireAuth: the browser lands here straight from Google/
          // GitHub, before this tab has any access token in memory.
          path: '/oauth/complete',
          lazy: async () => {
            const { OAuthCompletePage } = await import('@/app/pages/OAuthCompletePage');
            return { Component: OAuthCompletePage };
          },
        },
        {
          element: <RequireAuth />,
          children: [
            {
              element: <MainLayout />,
              children: [
                {
                  path: '/repositories/:id',
                  lazy: async () => {
                    const { RepositoryDetailPage } = await import('@/app/pages/RepositoryDetailPage');
                    return { Component: RepositoryDetailPage };
                  },
                },
                {
                  path: '/analysis/:id',
                  lazy: async () => {
                    const { AnalysisPipelinePage } = await import('@/app/pages/AnalysisPipelinePage');
                    return { Component: AnalysisPipelinePage };
                  },
                },
                {
                  path: '/analysis/:id/architecture',
                  lazy: async () => {
                    const { AnalysisArchitectureRedirect } = await import('@/app/pages/AnalysisArchitectureRedirect');
                    return { Component: AnalysisArchitectureRedirect };
                  },
                },
                ...productSurfaceRoutes,
                {
                  // Catch-all: an unmatched path previously fell through to react-router's
                  // default error boundary ("Unexpected Application Error! 404 Not Found")
                  // instead of a page. This still sits behind RequireAuth, so an
                  // unauthenticated visitor to a bogus path is redirected to /login first.
                  path: '*',
                  lazy: async () => {
                    const { NotFoundPage } = await import('@/app/pages/NotFoundPage');
                    return { Component: NotFoundPage };
                  },
                },
              ],
            },
          ],
        },
      ],
    },
  ]);
}

export const router = createAppRouter();
