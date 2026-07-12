import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '@/shared/components/layout/MainLayout';
import { RequireAuth } from './RequireAuth';

export const router = createBrowserRouter([
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
            path: '/',
            lazy: async () => {
              const { DashboardPage } = await import('@/app/pages/DashboardPage');
              return { Component: DashboardPage };
            },
          },
          {
            path: '/repositories',
            lazy: async () => {
              const { RepositoriesPage } = await import('@/app/pages/RepositoriesPage');
              return { Component: RepositoriesPage };
            },
          },
          {
            path: '/repositories/:id',
            lazy: async () => {
              const { RepositoryDetailPage } = await import('@/app/pages/RepositoryDetailPage');
              return { Component: RepositoryDetailPage };
            },
          },
          {
            path: '/upload',
            lazy: async () => {
              const { UploadPage } = await import('@/app/pages/UploadPage');
              return { Component: UploadPage };
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
            path: '/architecture',
            lazy: async () => {
              const { ArchitecturePage } = await import('@/app/pages/ArchitecturePage');
              return { Component: ArchitecturePage };
            },
          },
          {
            path: '/dependencies',
            lazy: async () => {
              const { DependenciesPage } = await import('@/app/pages/DependenciesPage');
              return { Component: DependenciesPage };
            },
          },
          {
            path: '/review',
            lazy: async () => {
              const { EngineeringReviewPage } = await import('@/app/pages/EngineeringReviewPage');
              return { Component: EngineeringReviewPage };
            },
          },
          {
            path: '/ai-workspace',
            lazy: async () => {
              const { AIWorkspacePage } = await import('@/app/pages/AIWorkspacePage');
              return { Component: AIWorkspacePage };
            },
          },
          {
            path: '/documentation',
            lazy: async () => {
              const { DocumentationPage } = await import('@/app/pages/DocumentationPage');
              return { Component: DocumentationPage };
            },
          },
          {
            path: '/insights',
            lazy: async () => {
              const { InsightsPage } = await import('@/app/pages/InsightsPage');
              return { Component: InsightsPage };
            },
          },
          {
            path: '/settings',
            lazy: async () => {
              const { SettingsPage } = await import('@/app/pages/SettingsPage');
              return { Component: SettingsPage };
            },
          },
        ],
      },
    ],
  },
]);
