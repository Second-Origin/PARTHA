import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { backendService } from '@/shared/services/backend';
import { NetworkError } from '@/shared/services/api';
import type { Repository } from '@/shared/types';
import { AnalysisPipelinePage } from './AnalysisPipelinePage';

// Exercises the real hook wired to the real store, unlike the sibling
// AnalysisPipelinePage.test.tsx which mocks the hook entirely -- #175 was a
// gap between a hook that transitions correctly in isolation and a page that
// never actually saw the transition land.
vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({ repositories: useAppStore((state) => state.repositories) }),
}));

const repository: Repository = {
  id: 'repo-1',
  name: 'sample',
  source: 'github',
  size: 10,
  fileCount: 1,
  status: 'analysing',
  analysisStage: null,
  analysisProgress: 0,
  uploadedAt: '2026-07-22T08:00:00Z',
  meta: null,
  fileTree: [],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/analysis/repo-1']}>
      <Routes>
        <Route path="/analysis/:id" element={<AnalysisPipelinePage />} />
        <Route path="/repositories/:id" element={<div>Repo Detail Page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AnalysisPipelinePage integration with the real polling hook', () => {
  beforeEach(() => {
    useAppStore.setState({ repositories: [repository], analysisRunning: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('navigates to the analysed repository as soon as the backend reports completed, without a reload', async () => {
    vi.useFakeTimers();
    vi.spyOn(backendService, 'startAnalysis').mockResolvedValue({
      repositoryId: repository.id,
      status: 'queued',
      jobId: 'job-1',
    });
    vi.spyOn(backendService, 'fetchAnalysisStatus').mockResolvedValue({
      repositoryId: repository.id,
      status: 'completed',
      jobId: 'job-1',
      stage: 'completed',
      progress: 100,
      startedAt: '2026-07-22T08:00:01Z',
      completedAt: '2026-07-22T08:00:02Z',
      error: null,
    });

    // MemoryRouter navigation is a client-side state transition, not a
    // browser reload -- this test proves the SPA route swap happens on its
    // own, with no manual reload step anywhere in the flow.
    renderPage();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByText('Repo Detail Page')).toBeInTheDocument();
  });

  it('renders the Analysis Failed terminal state when the job fails server-side', async () => {
    vi.useFakeTimers();
    vi.spyOn(backendService, 'fetchAnalysisStatus').mockResolvedValue({
      repositoryId: repository.id,
      status: 'failed',
      jobId: 'job-1',
      stage: 'extracting-modules',
      progress: 35,
      startedAt: '2026-07-22T08:00:01Z',
      completedAt: '2026-07-22T08:00:02Z',
      error: 'Extraction crashed.',
    });

    renderPage();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByText('Analysis Failed')).toBeInTheDocument();
    expect(screen.getByText('Extraction crashed.')).toBeInTheDocument();
  });

  it('recovers from a transient poll error into the completed terminal state, without ever showing Analysis Failed', async () => {
    vi.useFakeTimers();
    const fetchStatus = vi
      .spyOn(backendService, 'fetchAnalysisStatus')
      .mockRejectedValueOnce(new NetworkError('/analysis/repo-1/status'))
      .mockResolvedValueOnce({
        repositoryId: repository.id,
        status: 'running',
        jobId: 'job-1',
        stage: 'extracting-modules',
        progress: 35,
        startedAt: '2026-07-22T08:00:01Z',
        completedAt: null,
        error: null,
      })
      .mockResolvedValue({
        repositoryId: repository.id,
        status: 'completed',
        jobId: 'job-1',
        stage: 'completed',
        progress: 100,
        startedAt: '2026-07-22T08:00:01Z',
        completedAt: '2026-07-22T08:00:02Z',
        error: null,
      });

    renderPage();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText('Connection lost — retrying…')).toBeInTheDocument();
    expect(screen.queryByText('Analysis Failed')).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(screen.getByText('Repo Detail Page')).toBeInTheDocument();
    expect(fetchStatus.mock.calls.length).toBeGreaterThanOrEqual(3);
  });
});
