import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { Repository } from '@/shared/types';
import { DashboardPage } from './DashboardPage';

const mockDashboard = vi.hoisted(() => vi.fn());
vi.mock('@/features/repositories/hooks/useRepositoryDashboard', () => ({
  useRepositoryDashboard: () => mockDashboard(),
}));

function makeRepository(overrides: Partial<Repository>): Repository {
  return {
    id: 'repo-1',
    name: 'partha',
    source: 'github',
    size: 1024,
    fileCount: 42,
    status: 'completed',
    analysisStage: null,
    analysisProgress: 100,
    uploadedAt: '2026-08-01T00:00:00Z',
    meta: null,
    fileTree: [],
    ...overrides,
  };
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

describe('DashboardPage', () => {
  it('surfaces the most recently completed analysis with its real revision identity', () => {
    const older = makeRepository({
      id: 'repo-older',
      name: 'older-repo',
      analysedAt: '2026-08-01T10:00:00Z',
      revision: { kind: 'git', ref: 'refs/heads/main', value: '1234567890abcdef1234567890abcdef12345678' },
    });
    const newer = makeRepository({
      id: 'repo-newer',
      name: 'newest-repo',
      analysedAt: '2026-08-09T15:30:00Z',
      revision: { kind: 'git', ref: 'refs/heads/main', value: 'abcdef1234567890abcdef1234567890abcdef12' },
    });
    mockDashboard.mockReturnValue({
      repositories: [older, newer],
      metrics: { totalRepositories: 2, completedRepositories: 2, totalFiles: 84, totalSize: 2048 },
      selectRepository: vi.fn(),
    });

    renderDashboard();

    const summary = screen.getByTestId('latest-analysis-summary');
    expect(within(summary).getByText('newest-repo')).toBeInTheDocument();
    expect(within(summary).getByText('abcdef1')).toBeInTheDocument();
    expect(within(summary).queryByText('older-repo')).not.toBeInTheDocument();
  });

  it('renders an upload revision as a short content hash, not the raw sha256 value', () => {
    const repo = makeRepository({
      analysedAt: '2026-08-09T15:30:00Z',
      revision: { kind: 'upload', value: 'sha256:deadbeefcafefeed1234567890abcdef1234567890abcdef1234567890abcd' },
    });
    mockDashboard.mockReturnValue({
      repositories: [repo],
      metrics: { totalRepositories: 1, completedRepositories: 1, totalFiles: 42, totalSize: 1024 },
      selectRepository: vi.fn(),
    });

    renderDashboard();

    expect(within(screen.getByTestId('latest-analysis-summary')).getByText('upload deadbee')).toBeInTheDocument();
  });

  it('omits the summary line when no repository has a completed analysis yet', () => {
    const repo = makeRepository({ status: 'analysing', analysedAt: undefined, revision: null });
    mockDashboard.mockReturnValue({
      repositories: [repo],
      metrics: { totalRepositories: 1, completedRepositories: 0, totalFiles: 42, totalSize: 1024 },
      selectRepository: vi.fn(),
    });

    renderDashboard();

    expect(screen.queryByText(/Most recently analysed:/)).not.toBeInTheDocument();
  });

  it('still shows the empty state, without the summary line, when there are no repositories at all', () => {
    mockDashboard.mockReturnValue({
      repositories: [],
      metrics: { totalRepositories: 0, completedRepositories: 0, totalFiles: 0, totalSize: 0 },
      selectRepository: vi.fn(),
    });

    renderDashboard();

    expect(screen.getByText('Welcome to PARTHA')).toBeInTheDocument();
    expect(screen.queryByText(/Most recently analysed:/)).not.toBeInTheDocument();
  });
});
