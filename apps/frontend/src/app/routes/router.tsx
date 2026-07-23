import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '@/shared/components/layout/MainLayout';
import { RequireAuth } from './RequireAuth';
import { productSurfaceRoutes } from './productSurfaces';

export function createAppRouter() {
  return createBrowserRouter([
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
            ...productSurfaceRoutes,
          ],
        },
      ],
    },
  ]);
}

export const router = createAppRouter();
