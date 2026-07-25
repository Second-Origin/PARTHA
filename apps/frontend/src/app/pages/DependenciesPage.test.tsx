import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useDependencies } from '@/features/dependencies/hooks/useDependencies';
import type { DependencyDiagnostic, DependencyGraphResponse } from '@/shared/services/api/types';
import { DependenciesPage } from './DependenciesPage';

vi.mock('@/features/dependencies/hooks/useDependencies', () => ({
  useDependencies: vi.fn(),
}));

const graph: DependencyGraphResponse = {
  repositoryId: 'repo-1',
  nodes: [
    {
      id: 'dependency:npm:lodash',
      name: 'lodash',
      version: '4.17.15',
      type: 'production',
      ecosystem: 'npm',
      declarations: [
        {
          name: 'lodash',
          manifestPath: 'package.json',
          workspacePath: '.',
          startLine: 3,
          endLine: 3,
          extractor: 'dependency-manifest',
          extractorVersion: '1.2.0',
          ecosystem: 'npm',
          version: '4.17.15',
          type: 'production',
        },
      ],
      size: null,
    },
  ],
  edges: [],
  totalDependencies: 1,
  manifestCount: 1,
  diagnostics: [],
  vulnerabilityAssessment: { status: 'not_computed' },
  outdatedAssessment: { status: 'not_computed' },
  provenance: {
    source: 'legacy-heuristic',
    limitation: 'Derived from declared manifests by the legacy analysis engine.',
  },
};

const dependencies: ReturnType<typeof useDependencies> = {
  activeRepository: {
    id: 'repo-1',
    name: 'sample',
    source: 'upload',
    size: 100,
    fileCount: 2,
    status: 'completed',
    dataSource: 'real',
    analysisStage: 'completed',
    analysisProgress: 100,
    uploadedAt: '2026-07-15T00:00:00Z',
    meta: {
      language: 'TypeScript',
      framework: 'React',
      totalFiles: 2,
      totalFolders: 1,
      entryPoint: 'src/main.tsx',
      configFiles: ['package.json'],
      packageManager: 'npm',
      hasReadme: false,
      hasLicense: false,
      licenseName: null,
    },
    fileTree: [],
  },
  completedRepositories: [],
  status: 'success' as const,
  loading: false,
  error: null,
  empty: false,
  success: true,
  source: 'upload' as const,
  emptyReason: null,
  graph,
  retry: vi.fn(),
  refresh: vi.fn(),
  packageManager: 'npm',
};

function renderPage() {
  return render(
    <MemoryRouter>
      <DependenciesPage />
    </MemoryRouter>,
  );
}

function mockDependencies(overrides: Partial<typeof dependencies> = {}) {
  vi.mocked(useDependencies).mockReturnValue({ ...dependencies, ...overrides });
}

function diagnostic(severity: DependencyDiagnostic['severity']): DependencyDiagnostic {
  return {
    code: 'RI-SRC-MALFORMED',
    category: 'malformed source',
    severity,
    message: 'dependency manifest could not be parsed or has an unsupported structure',
    path: 'apps/broken/package.json',
    producer: 'dependency-manifest@1.2.0',
    details: null,
  };
}

describe('DependenciesPage', () => {
  beforeEach(() => {
    mockDependencies();
  });

  it('shows uncomputed assessments without clean badges or numeric fallbacks', () => {
    renderPage();

    expect(screen.getAllByText('Not computed')).toHaveLength(2);
    expect(screen.getByText('Vulnerability and outdated-version assessments have not been run.')).toBeInTheDocument();
    expect(screen.getByText('lodash')).toBeInTheDocument();
    expect(screen.queryByText('vulnerable')).not.toBeInTheDocument();
    expect(screen.queryByText('outdated')).not.toBeInTheDocument();
  });

  it('shows an empty inventory instead of a search-miss message', () => {
    mockDependencies({
      graph: {
        ...graph,
        nodes: [],
        totalDependencies: 0,
        manifestCount: 0,
      },
    });

    renderPage();

    expect(screen.getByText('No dependencies were discovered.')).toBeInTheDocument();
    expect(screen.getByText('Detected package manager: npm.')).toBeInTheDocument();
    expect(screen.queryByText('No dependencies match your search.')).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Search dependencies...'), { target: { value: 'not-present' } });

    expect(screen.getByText('No dependencies were discovered.')).toBeInTheDocument();
    expect(screen.queryByText('No dependencies match your search.')).not.toBeInTheDocument();
  });

  it.each(['error', 'fatal'] as const)('does not present a %s extraction diagnostic as an empty inventory', (severity) => {
    mockDependencies({
      graph: {
        ...graph,
        nodes: [],
        totalDependencies: 0,
        diagnostics: [diagnostic(severity)],
      },
    });

    renderPage();

    expect(screen.getByText('Dependency inventory may be incomplete.')).toBeInTheDocument();
    expect(screen.getByText('1 blocking extraction issue was reported. Review the affected source files and analyse the repository again.')).toBeInTheDocument();
    expect(screen.queryByText('No dependencies were discovered.')).not.toBeInTheDocument();
    expect(screen.queryByText('No dependencies match your search.')).not.toBeInTheDocument();
  });

  it.each(['info', 'warning'] as const)('treats a %s diagnostic as a complete empty inventory', (severity) => {
    mockDependencies({
      graph: {
        ...graph,
        nodes: [],
        totalDependencies: 0,
        manifestCount: 0,
        diagnostics: [diagnostic(severity)],
      },
      packageManager: null,
    });

    renderPage();

    expect(screen.getByText('No dependencies were discovered.')).toBeInTheDocument();
    expect(screen.queryByText('Dependency inventory may be incomplete.')).not.toBeInTheDocument();
    expect(screen.getByText(/Package-manager information is unavailable for this repository\./)).toBeInTheDocument();
    expect(screen.queryByText(/Detected package manager:/)).not.toBeInTheDocument();
  });

  it('warns when a populated inventory has blocking extraction diagnostics', () => {
    mockDependencies({
      graph: {
        ...graph,
        diagnostics: [diagnostic('error')],
      },
    });

    renderPage();

    expect(screen.getByText('Dependency inventory may be incomplete.')).toBeInTheDocument();
    expect(screen.getByText('1 blocking extraction issue was reported. Review the affected source files and analyse the repository again.')).toBeInTheDocument();
    expect(screen.getByText('lodash')).toBeInTheDocument();
  });

  it('shows a search-miss message only when a populated inventory has no matches', () => {
    renderPage();

    fireEvent.change(screen.getByPlaceholderText('Search dependencies...'), { target: { value: 'not-present' } });

    expect(screen.getByText('No dependencies match your search.')).toBeInTheDocument();
    expect(screen.queryByText('No dependencies were discovered.')).not.toBeInTheDocument();
  });

  it('keeps an unavailable inventory distinct from an empty inventory', () => {
    mockDependencies({ graph: null });

    renderPage();

    expect(screen.getByText('Dependency inventory unavailable')).toBeInTheDocument();
    expect(screen.getByText('No dependency inventory is available for this repository yet. Analyse the repository again to generate dependency data.')).toBeInTheDocument();
    expect(screen.queryByText('No dependencies were discovered.')).not.toBeInTheDocument();
    expect(screen.queryByText('No dependencies match your search.')).not.toBeInTheDocument();
  });

  it('keeps loading and error states distinct from an unavailable inventory', () => {
    mockDependencies({ graph: null, loading: true });
    const { unmount } = renderPage();

    expect(screen.getByText('Loading dependency graph...')).toBeInTheDocument();
    expect(screen.queryByText('Dependency inventory unavailable')).not.toBeInTheDocument();

    unmount();
    mockDependencies({ graph: null, error: 'Dependency service is unavailable.' });
    renderPage();

    expect(screen.getByText('Dependency service is unavailable.')).toBeInTheDocument();
    expect(screen.queryByText('Dependency inventory unavailable')).not.toBeInTheDocument();
  });

  it('discloses that the dependency graph comes from the legacy engine', () => {
    mockDependencies({ graph });
    renderPage();

    expect(screen.getByTestId('provenance-notice')).toBeInTheDocument();
    expect(
      screen.getByText(/Derived from declared manifests by the legacy analysis engine\./),
    ).toBeInTheDocument();
  });
});
