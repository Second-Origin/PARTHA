import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAnalysisPipeline } from '@/features/analysis/hooks/useAnalysisPipeline';
import { ANALYSIS_STAGES } from '@/shared/types';
import { AnalysisPipelinePage } from './AnalysisPipelinePage';

vi.mock('@/features/analysis/hooks/useAnalysisPipeline', () => ({
  useAnalysisPipeline: vi.fn(),
}));

const baseAnalysis = {
  repository: {
    id: 'repo-1',
    name: 'sample',
    source: 'upload' as const,
    size: 10,
    fileCount: 1,
    status: 'analysing' as const,
    dataSource: 'real' as const,
    analysisStage: 'reading-structure' as const,
    analysisProgress: 25,
    uploadedAt: '2026-07-22T08:00:00Z',
    meta: null,
    fileTree: [],
  },
  stages: ANALYSIS_STAGES,
  currentStageIndex: 2,
  status: 'loading' as const,
  jobStatus: 'running' as const,
  loading: true,
  error: null,
  empty: false,
  success: false,
  source: 'real' as const,
  retry: vi.fn(),
  refresh: vi.fn(),
  cancel: vi.fn().mockResolvedValue(undefined),
  restart: vi.fn().mockResolvedValue(undefined),
  cancelling: false,
  canCancel: true,
  cancelled: false,
  completedRepositoryPath: null,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/analysis/repo-1']}>
      <Routes>
        <Route path="/analysis/:id" element={<AnalysisPipelinePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AnalysisPipelinePage', () => {
  beforeEach(() => {
    vi.mocked(useAnalysisPipeline).mockReturnValue(baseAnalysis);
  });

  it('shows a cancellation action only while work is active', () => {
    renderPage();
    expect(screen.getByRole('button', { name: 'Cancel analysis' })).toBeInTheDocument();
  });

  it('shows the cancelled terminal state without another cancel action', () => {
    vi.mocked(useAnalysisPipeline).mockReturnValue({
      ...baseAnalysis,
      status: 'idle',
      jobStatus: 'cancelled',
      loading: false,
      canCancel: false,
      cancelled: true,
    });
    renderPage();
    expect(screen.getByText('Analysis cancelled')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel analysis' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Restart analysis' }));
    expect(baseAnalysis.restart).toHaveBeenCalled();
  });
});
