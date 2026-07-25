import {
  FileText,
  FolderGit2,
  GitBranch,
  LayoutDashboard,
  MessageSquareText,
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
    // Free-form provider-backed questions remain limited, hence Preview.
    id: 'ai-workspace',
    label: 'AI Workspace',
    path: '/ai-workspace',
    icon: MessageSquareText,
    phase: 3,
    readiness: 'preview',
    primaryNavigation: true,
    limitation:
      'Evidence-backed answers currently cover authentication and are derived only from the sealed snapshot for the selected revision. Free-form questions need a configured AI provider and use the legacy repository context.',
    load: async () => {
      const { AIWorkspacePage } = await import('@/app/pages/AIWorkspacePage');
      return { Component: AIWorkspacePage };
    },
  },
  {
    // Stays deferred: the review builder derives 0-100 category scores by
    // subtracting per-severity costs from 100 (app/review/review_service.py).
    // That number is not computed from measured evidence, and the prototype
    // must not present opaque grades as analysis.
    id: 'engineering-review',
    label: 'Engineering Review',
    path: '/review',
    phase: 3,
    readiness: 'deferred',
    primaryNavigation: false,
    blockingIssues: [96, 113],
    unavailableMessage: 'Evidence-based engineering review is not available yet.',
  },
  {
    // Restored as Preview (#154): the endpoint is real, owner-scoped and reads
    // genuine repository content, but it is generated by the legacy heuristic
    // engine rather than the sealed snapshot, which the page discloses.
    id: 'documentation',
    label: 'Documentation',
    path: '/documentation',
    icon: FileText,
    phase: 3,
    readiness: 'preview',
    primaryNavigation: true,
    limitation:
      'Generated by the legacy analysis engine, not from a sealed evidence snapshot. Content is not bound to a verifiable revision manifest and may differ from snapshot-backed surfaces.',
    load: async () => {
      const { DocumentationPage } = await import('@/app/pages/DocumentationPage');
      return { Component: DocumentationPage };
    },
  },
  {
    // Stays deferred: there is no Insights backend endpoint at all, so every
    // metric the page could show would be invented.
    id: 'insights',
    label: 'Insights',
    path: '/insights',
    phase: 'not-scheduled',
    readiness: 'deferred',
    primaryNavigation: false,
    blockingIssues: [117],
    unavailableMessage: 'Repository insights are not available yet.',
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
