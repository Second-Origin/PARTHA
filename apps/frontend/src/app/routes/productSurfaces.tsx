import {
  FolderGit2,
  GitBranch,
  LayoutDashboard,
  Network,
  Settings,
  Upload,
  type LucideIcon,
} from 'lucide-react';
import type { RouteObject } from 'react-router-dom';

export type DeliveryPhase = 0 | 1 | 2 | 3 | 'not-scheduled';

interface ProductSurfaceBase {
  id: string;
  label: string;
  path: string;
  phase: DeliveryPhase;
}

interface ReadyProductSurface extends ProductSurfaceBase {
  readiness: 'ready';
  primaryNavigation: true;
  icon: LucideIcon;
  load: NonNullable<RouteObject['lazy']>;
}

export interface DeferredProductSurface extends ProductSurfaceBase {
  readiness: 'deferred';
  primaryNavigation: false;
  blockingIssues: readonly number[];
}

export type ProductSurface = ReadyProductSurface | DeferredProductSurface;

export const productSurfaces: readonly ProductSurface[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    path: '/',
    icon: LayoutDashboard,
    phase: 0,
    readiness: 'ready',
    primaryNavigation: true,
    load: async () => {
      const { DashboardPage } = await import('@/app/pages/DashboardPage');
      return { Component: DashboardPage };
    },
  },
  {
    id: 'repositories',
    label: 'Repositories',
    path: '/repositories',
    icon: FolderGit2,
    phase: 0,
    readiness: 'ready',
    primaryNavigation: true,
    load: async () => {
      const { RepositoriesPage } = await import('@/app/pages/RepositoriesPage');
      return { Component: RepositoriesPage };
    },
  },
  {
    id: 'upload',
    label: 'Upload Repository',
    path: '/upload',
    icon: Upload,
    phase: 0,
    readiness: 'ready',
    primaryNavigation: true,
    load: async () => {
      const { UploadPage } = await import('@/app/pages/UploadPage');
      return { Component: UploadPage };
    },
  },
  {
    id: 'architecture',
    label: 'Architecture',
    path: '/architecture',
    icon: Network,
    phase: 0,
    readiness: 'ready',
    primaryNavigation: true,
    load: async () => {
      const { ArchitecturePage } = await import('@/app/pages/ArchitecturePage');
      return { Component: ArchitecturePage };
    },
  },
  {
    id: 'dependencies',
    label: 'Dependency Graph',
    path: '/dependencies',
    icon: GitBranch,
    phase: 0,
    readiness: 'ready',
    primaryNavigation: true,
    load: async () => {
      const { DependenciesPage } = await import('@/app/pages/DependenciesPage');
      return { Component: DependenciesPage };
    },
  },
  {
    id: 'settings',
    label: 'Settings',
    path: '/settings',
    icon: Settings,
    phase: 0,
    readiness: 'ready',
    primaryNavigation: true,
    load: async () => {
      const { SettingsPage } = await import('@/app/pages/SettingsPage');
      return { Component: SettingsPage };
    },
  },
  {
    id: 'ai-workspace',
    label: 'AI Workspace',
    path: '/ai-workspace',
    phase: 3,
    readiness: 'deferred',
    primaryNavigation: false,
    blockingIssues: [95, 113],
  },
  {
    id: 'engineering-review',
    label: 'Engineering Review',
    path: '/review',
    phase: 3,
    readiness: 'deferred',
    primaryNavigation: false,
    blockingIssues: [95, 113],
  },
  {
    id: 'documentation',
    label: 'Documentation',
    path: '/documentation',
    phase: 3,
    readiness: 'deferred',
    primaryNavigation: false,
    blockingIssues: [95, 113],
  },
  {
    id: 'insights',
    label: 'Insights',
    path: '/insights',
    phase: 'not-scheduled',
    readiness: 'deferred',
    primaryNavigation: false,
    blockingIssues: [117],
  },
];

export const primaryNavigationSurfaces = productSurfaces.filter(
  (surface): surface is ReadyProductSurface => surface.readiness === 'ready' && surface.primaryNavigation,
);

export const productSurfaceRoutes: RouteObject[] = productSurfaces.map((surface) => ({
  path: surface.path,
  lazy: surface.readiness === 'ready'
    ? surface.load
    : async () => {
      const { DeferredSurfacePage } = await import('@/app/pages/DeferredSurfacePage');
      return { Component: () => <DeferredSurfacePage surface={surface} /> };
    },
}));
