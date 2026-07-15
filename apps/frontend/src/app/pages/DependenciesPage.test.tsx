import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useDependencies } from '@/features/dependencies/hooks/useDependencies';
import { DependenciesPage } from './DependenciesPage';

vi.mock('@/features/dependencies/hooks/useDependencies', () => ({
  useDependencies: vi.fn(),
}));

describe('DependenciesPage', () => {
  beforeEach(() => {
    vi.mocked(useDependencies).mockReturnValue({
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
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      source: 'real',
      emptyReason: null,
      graph: {
        repositoryId: 'repo-1',
        nodes: [
          {
            id: 'dependency:npm:lodash',
            name: 'lodash',
            version: '4.17.15',
            type: 'production',
            size: null,
          },
        ],
        edges: [],
        totalDependencies: 1,
        vulnerabilityAssessment: { status: 'not_computed' },
        outdatedAssessment: { status: 'not_computed' },
      },
      retry: vi.fn(),
      refresh: vi.fn(),
      packageManager: 'npm',
    });
  });

  it('shows uncomputed assessments without clean badges or numeric fallbacks', () => {
    render(
      <MemoryRouter>
        <DependenciesPage />
      </MemoryRouter>,
    );

    expect(screen.getAllByText('Not computed')).toHaveLength(2);
    expect(screen.getByText('Vulnerability and outdated-version assessments have not been run.')).toBeInTheDocument();
    expect(screen.getByText('lodash')).toBeInTheDocument();
    expect(screen.queryByText('vulnerable')).not.toBeInTheDocument();
    expect(screen.queryByText('outdated')).not.toBeInTheDocument();
  });
});
