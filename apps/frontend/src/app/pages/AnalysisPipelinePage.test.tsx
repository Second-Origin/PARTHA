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
  connectionStatus: 'connected' as const,
  retryingConnection: false,
  connectionLost: false,
  rateLimited: false,
  rateLimitSecondsRemaining: null,
  empty: false,
  success: false,
  source: 'upload' as const,
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

  it('shows a non-terminal retrying notice for a transient poll failure, not Analysis Failed', () => {
    vi.mocked(useAnalysisPipeline).mockReturnValue({
      ...baseAnalysis,
      connectionStatus: 'retrying',
      retryingConnection: true,
    });
    renderPage();
    expect(screen.getByText('Connection lost — retrying…')).toBeInTheDocument();
    expect(screen.queryByText('Analysis Failed')).not.toBeInTheDocument();
    // Progress is preserved, not reset or advanced, while retrying.
    expect(screen.getByText('25%')).toBeInTheDocument();
  });

  it('shows a distinct connectivity error with a manual retry action once retries are exhausted', () => {
    vi.mocked(useAnalysisPipeline).mockReturnValue({
      ...baseAnalysis,
      connectionStatus: 'lost',
      connectionLost: true,
    });
    renderPage();
    expect(screen.getByText('Connection lost')).toBeInTheDocument();
    expect(screen.queryByText('Analysis Failed')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry connection' }));
    expect(baseAnalysis.retry).toHaveBeenCalled();
  });

  it('still renders the terminal Analysis Failed state for a real job failure', () => {
    vi.mocked(useAnalysisPipeline).mockReturnValue({
      ...baseAnalysis,
      status: 'error',
      jobStatus: 'failed',
      loading: false,
      error: 'Analysis failed.',
      repository: { ...baseAnalysis.repository, status: 'error', errorMessage: 'Analysis failed.' },
    });
    renderPage();
    expect(screen.getByText('Analysis Failed')).toBeInTheDocument();
    expect(screen.queryByText('Connection lost')).not.toBeInTheDocument();
  });

  it('shows an accessible countdown for a 429 instead of Analysis Failed (#169)', () => {
    vi.mocked(useAnalysisPipeline).mockReturnValue({
      ...baseAnalysis,
      connectionStatus: 'rate-limited',
      rateLimited: true,
      rateLimitSecondsRemaining: 12,
    });
    renderPage();

    const status = screen.getByText(/retrying automatically in 12s/i);
    expect(status).toBeInTheDocument();
    expect(status.closest('[role="status"]')).toBeInTheDocument();
    expect(screen.queryByText('Analysis Failed')).not.toBeInTheDocument();
  });

  it('offers a manual retry once the automatic rate-limit budget is exhausted, without ever reading Analysis Failed', () => {
    vi.mocked(useAnalysisPipeline).mockReturnValue({
      ...baseAnalysis,
      connectionStatus: 'rate-limited',
      rateLimited: true,
      rateLimitSecondsRemaining: null,
    });
    renderPage();

    expect(screen.getByText('Still rate limited')).toBeInTheDocument();
    expect(screen.queryByText('Analysis Failed')).not.toBeInTheDocument();
    const callsBeforeClick = vi.mocked(baseAnalysis.retry).mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'Retry now' }));
    expect(vi.mocked(baseAnalysis.retry).mock.calls.length).toBe(callsBeforeClick + 1);
  });

  it('disables the manual restart action while a rate-limit cooldown is active, to prevent retry-storming', () => {
    vi.mocked(useAnalysisPipeline).mockReturnValue({
      ...baseAnalysis,
      status: 'idle',
      jobStatus: 'cancelled',
      loading: false,
      canCancel: false,
      cancelled: true,
      rateLimited: true,
      rateLimitSecondsRemaining: 7,
    });
    renderPage();

    const restartButton = screen.getByRole('button', { name: /restart analysis/i });
    expect(restartButton).toBeDisabled();
    expect(restartButton).toHaveTextContent('wait 7s');
    const callsBeforeClick = vi.mocked(baseAnalysis.restart).mock.calls.length;
    fireEvent.click(restartButton);
    expect(vi.mocked(baseAnalysis.restart).mock.calls.length).toBe(callsBeforeClick);
  });
});
