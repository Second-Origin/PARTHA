import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { Repository } from '@/shared/types';
import { RepositoryDetailPage } from './RepositoryDetailPage';

const repositoryState = vi.hoisted(() => ({ repositories: [] as Repository[] }));
const explorerProps = vi.hoisted(() => ({ initialPath: null as string | null }));

vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({ repositories: repositoryState.repositories }),
}));

vi.mock('@/features/repositories/components/RepositoryOutcomeSummary', () => ({
  RepositoryOutcomeSummary: ({ repository }: { repository: Repository }) => (
    <div data-testid="outcome-summary-stub">Outcome summary for {repository.name}</div>
  ),
}));

vi.mock('@/features/explorer/components/RepositoryExplorer', () => ({
  RepositoryExplorer: ({ initialPath }: { initialPath?: string | null }) => {
    explorerProps.initialPath = initialPath ?? null;
    return <div data-testid="repository-explorer-stub">Explorer</div>;
  },
}));

const completedRepository: Repository = {
  id: 'repo-1',
  name: 'sample',
  source: 'upload',
  size: 10,
  fileCount: 5,
  status: 'completed',
  analysisStage: 'completed',
  analysisProgress: 100,
  uploadedAt: '2026-07-22T08:00:00Z',
  meta: {
    language: 'TypeScript',
    framework: 'React',
    totalFiles: 5,
    totalFolders: 2,
    entryPoint: 'src/main.tsx',
    configFiles: [],
    packageManager: 'npm',
    hasReadme: true,
    hasLicense: true,
    licenseName: 'MIT',
  },
  fileTree: [],
};

function renderPage(repositoryId = 'repo-1', search = '') {
  return render(
    <MemoryRouter initialEntries={[`/repositories/${repositoryId}${search}`]}>
      <Routes>
        <Route path="/repositories/:id" element={<RepositoryDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RepositoryDetailPage', () => {
  it('leads the completed repository landing view with the outcome summary, before the tabs (#176)', () => {
    repositoryState.repositories = [completedRepository];

    renderPage();

    const summary = screen.getByTestId('outcome-summary-stub');
    expect(summary).toHaveTextContent('Outcome summary for sample');

    const overviewTab = screen.getByRole('button', { name: 'Overview' });
    expect(summary.compareDocumentPosition(overviewTab) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('does not show the outcome summary for a repository that failed analysis', () => {
    repositoryState.repositories = [
      { ...completedRepository, status: 'error', errorMessage: 'Extraction crashed.', meta: null },
    ];

    renderPage();

    expect(screen.queryByTestId('outcome-summary-stub')).not.toBeInTheDocument();
    expect(screen.getByText('Extraction crashed.')).toBeInTheDocument();
  });

  it('opens the Explorer and forwards a global-search file path from the route', () => {
    repositoryState.repositories = [completedRepository];

    renderPage('repo-1', '?tab=Explorer&path=src%2Fmain.tsx');

    expect(screen.getByTestId('repository-explorer-stub')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Explorer' })).toHaveClass('text-foreground');
    expect(explorerProps.initialPath).toBe('src/main.tsx');
  });
});
