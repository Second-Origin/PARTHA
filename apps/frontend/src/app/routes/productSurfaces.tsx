import {
  FileText,
  FolderGit2,
  GitBranch,
  BarChart3,
  LayoutDashboard,
  MessageSquareText,
  Network,
  Settings,
  ShieldCheck,
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

/**
 * A surface that works, enforces auth and ownership, and shows only real
 * repository data, but is limited in a way a user must be told about before
 * they trust it. It is reachable and navigable, and always renders its
 * `limitation` as a visible Preview label.
 */
interface PreviewProductSurface extends ProductSurfaceBase {
  readiness: 'preview';
  primaryNavigation: boolean;
  icon: LucideIcon;
  load: NonNullable<RouteObject['lazy']>;
  /** User-facing statement of what is limited about this surface. */
  limitation: string;
}

export interface DeferredProductSurface extends ProductSurfaceBase {
  readiness: 'deferred';
  primaryNavigation: false;
  /** Internal roadmap metadata. Must never be rendered to product users. */
  blockingIssues: readonly number[];
  /** Plain-language, user-facing explanation of what is unavailable and why. */
  unavailableMessage: string;
}

export type ProductSurface = ReadyProductSurface | PreviewProductSurface | DeferredProductSurface;

/** Surfaces a user can actually open. */
export type NavigableProductSurface = ReadyProductSurface | PreviewProductSurface;

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
    // Restored as a primary snapshot-backed surface (#158). Dependency Graph
    // now reads exclusively from the sealed ri.v1 snapshot, the same 404
    // contract as Architecture/Review/Insights; vulnerability and
    // outdated-version assessments remain explicit not_computed statuses.
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
    // Restored for the prototype (#154). The workspace answers the built-in
    // authentication question straight from the sealed ri.v1 snapshot, so it
    // needs no AI provider and every citation is a real stored source span.
    // Free-form provider-backed questions remain limited, hence Preview, but
    // their repository structure now comes from the same sealed snapshot.
    id: 'ai-workspace',
    label: 'AI Workspace',
    path: '/ai-workspace',
    icon: MessageSquareText,
    phase: 3,
    readiness: 'preview',
    primaryNavigation: true,
    limitation:
      'Free-form questions require a configured AI provider. They receive sealed-snapshot structural facts, heuristic roles, and observed paths, but no source-file contents; provider answers therefore have no automatic citations.',
    load: async () => {
      const { AIWorkspacePage } = await import('@/app/pages/AIWorkspacePage');
      return { Component: AIWorkspacePage };
    },
  },
  {
    // Restored as a primary snapshot-backed surface (#154). The active
    // engineering-review.v2 contract contains no scores or generated roadmap:
    // only diagnostics with same-snapshot source evidence become findings.
    id: 'engineering-review',
    label: 'Engineering Review',
    path: '/review',
    icon: ShieldCheck,
    phase: 3,
    readiness: 'ready',
    primaryNavigation: true,
    load: async () => {
      const { EngineeringReviewPage } = await import('@/app/pages/EngineeringReviewPage');
      return { Component: EngineeringReviewPage };
    },
  },
  {
    // Documentation is bound to the current repository revision's sealed
    // snapshot and returns 404 rather than falling back to mutable metadata.
    id: 'documentation',
    label: 'Documentation',
    path: '/documentation',
    icon: FileText,
    phase: 3,
    readiness: 'ready',
    primaryNavigation: true,
    load: async () => {
      const { DocumentationPage } = await import('@/app/pages/DocumentationPage');
      return { Component: DocumentationPage };
    },
  },
  {
    // Restored as a primary snapshot-backed surface (#154). Every displayed
    // value comes from repository-insights.v1 and carries an exact definition,
    // snapshot identity and assessment state.
    id: 'insights',
    label: 'Insights',
    path: '/insights',
    icon: BarChart3,
    phase: 'not-scheduled',
    readiness: 'ready',
    primaryNavigation: true,
    load: async () => {
      const { InsightsPage } = await import('@/app/pages/InsightsPage');
      return { Component: InsightsPage };
    },
  },
];

function isNavigable(surface: ProductSurface): surface is NavigableProductSurface {
  return surface.readiness === 'ready' || surface.readiness === 'preview';
}

export const primaryNavigationSurfaces = productSurfaces.filter(
  (surface): surface is NavigableProductSurface => isNavigable(surface) && surface.primaryNavigation,
);

export const productSurfaceRoutes: RouteObject[] = productSurfaces.map((surface) => ({
  path: surface.path,
  lazy: isNavigable(surface)
    ? surface.load
    : async () => {
      const { DeferredSurfacePage } = await import('@/app/pages/DeferredSurfacePage');
      return { Component: () => <DeferredSurfacePage surface={surface} /> };
    },
}));
