import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '@/components/layout/MainLayout';

export const router = createBrowserRouter([
  {
    element: <MainLayout />,
    children: [
      {
        path: '/',
        lazy: async () => {
          const { DashboardPage } = await import('@/pages/DashboardPage');
          return { Component: DashboardPage };
        },
      },
      {
        path: '/repositories',
        lazy: async () => {
          const { RepositoriesPage } = await import('@/pages/RepositoriesPage');
          return { Component: RepositoriesPage };
        },
      },
      {
        path: '/repositories/:id',
        lazy: async () => {
          const { RepositoryDetailPage } = await import('@/pages/RepositoryDetailPage');
          return { Component: RepositoryDetailPage };
        },
      },
      {
        path: '/upload',
        lazy: async () => {
          const { UploadPage } = await import('@/pages/UploadPage');
          return { Component: UploadPage };
        },
      },
      {
        path: '/analysis/:id',
        lazy: async () => {
          const { AnalysisPipelinePage } = await import('@/pages/AnalysisPipelinePage');
          return { Component: AnalysisPipelinePage };
        },
      },
      {
        path: '/architecture',
        lazy: async () => {
          const { ArchitecturePage } = await import('@/pages/ArchitecturePage');
          return { Component: ArchitecturePage };
        },
      },
      {
        path: '/dependencies',
        lazy: async () => {
          const { DependenciesPage } = await import('@/pages/DependenciesPage');
          return { Component: DependenciesPage };
        },
      },
      {
        path: '/review',
        lazy: async () => {
          const { EngineeringReviewPage } = await import('@/pages/EngineeringReviewPage');
          return { Component: EngineeringReviewPage };
        },
      },
      {
        path: '/ai-workspace',
        lazy: async () => {
          const { AIWorkspacePage } = await import('@/pages/AIWorkspacePage');
          return { Component: AIWorkspacePage };
        },
      },
      {
        path: '/documentation',
        lazy: async () => {
          const { DocumentationPage } = await import('@/pages/DocumentationPage');
          return { Component: DocumentationPage };
        },
      },
      {
        path: '/insights',
        lazy: async () => {
          const { InsightsPage } = await import('@/pages/InsightsPage');
          return { Component: InsightsPage };
        },
      },
      {
        path: '/settings',
        lazy: async () => {
          const { SettingsPage } = await import('@/pages/SettingsPage');
          return { Component: SettingsPage };
        },
      },
    ],
  },
]);
