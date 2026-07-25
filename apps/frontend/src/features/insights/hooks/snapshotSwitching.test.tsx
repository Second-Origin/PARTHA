import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Repository } from '@/shared/types';
import type { EngineeringReview } from '@/shared/types/review';
import type { RepositoryInsights } from '@/shared/types/insights';
import { useReview } from '@/features/review/hooks/useReview';
import { useReviewStore } from '@/features/review/store';
import { useInsights } from './useInsights';

const mocks = vi.hoisted(() => ({
  repositoryState: null as {
    activeRepository: Repository | null;
    completedRepositories: Repository[];
  } | null,
  fetchReview: vi.fn(),
  fetchInsights: vi.fn(),
}));

vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => mocks.repositoryState,
}));

vi.mock('@/shared/services/backend', () => ({
  backendService: {
    fetchReview: mocks.fetchReview,
    fetchInsights: mocks.fetchInsights,
  },
}));

vi.mock('@/shared/services/api', () => ({
  getErrorMessage: (error: unknown) => String(error),
}));

function repository(id: string): Repository {
  return {
    id,
    name: id,
    source: 'upload',
    size: 1,
    fileCount: 1,
    status: 'completed',
    dataSource: 'real',
    analysisStage: 'completed',
    analysisProgress: 100,
    uploadedAt: '2026-07-25T00:00:00Z',
    revision: { kind: 'upload', value: `sha256:${id}`, ref: null },
    meta: null,
    fileTree: [],
  };
}

function provenance(snapshotId: string) {
  return {
    source: 'ri.v1' as const,
    snapshotId,
    snapshotSchemaVersion: 'ri.v1',
    canonicalGraphHash: `sha256:graph-${snapshotId}`,
  };
}

function review(repositoryId: string): EngineeringReview {
  const snapshotId = `snapshot-${repositoryId}`;
  return {
    schemaVersion: 'engineering-review.v2',
    repositoryId,
    repositoryName: repositoryId,
    revisionKind: 'upload',
    revisionValue: `sha256:${repositoryId}`,
    snapshotId,
    snapshotSchemaVersion: 'ri.v1',
    canonicalGraphHash: `sha256:graph-${snapshotId}`,
    manifestDigest: `sha256:manifest-${snapshotId}`,
    provenance: provenance(snapshotId),
    generatedAt: '2026-07-25T00:00:00Z',
    assessmentStatus: 'partially_assessed',
    categories: [],
    findings: [],
    summary: {
      message: 'No findings.',
      findingsBySeverity: { info: 0, low: 0, medium: 0, high: 0, critical: 0 },
      assessedCategories: 0,
      partiallyAssessedCategories: 0,
      notAssessedCategories: 1,
      insufficientEvidenceCategories: 0,
      evidenceBackedFindingCount: 0,
      unsupportedFindingCount: 0,
      omittedUnsupportedDiagnosticCount: 0,
      vulnerabilityScanning: 'not_assessed',
    },
  };
}

function insights(repositoryId: string): RepositoryInsights {
  const snapshotId = `snapshot-${repositoryId}`;
  return {
    schemaVersion: 'repository-insights.v1',
    repositoryId,
    repositoryName: repositoryId,
    revisionKind: 'upload',
    revisionValue: `sha256:${repositoryId}`,
    snapshotId,
    snapshotSchemaVersion: 'ri.v1',
    canonicalGraphHash: `sha256:graph-${snapshotId}`,
    manifestDigest: `sha256:manifest-${snapshotId}`,
    provenance: provenance(snapshotId),
    computedAt: '2026-07-25T00:00:00Z',
    snapshotCreatedAt: '2026-07-25T00:00:00Z',
    snapshotSealedAt: '2026-07-25T00:00:00Z',
    extractorSet: [],
    metrics: [],
    relationshipsByPredicate: [],
    diagnosticsBySeverity: [],
    diagnosticsByCode: [],
    languages: [],
    changeOverTime: {
      assessmentState: 'not_assessed',
      message: 'Change-over-time insights are not available yet.',
    },
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe('snapshot-backed surface repository switching', () => {
  const repositoryA = repository('repository-a');
  const repositoryB = repository('repository-b');

  beforeEach(() => {
    vi.clearAllMocks();
    useReviewStore.getState().resetForRepository();
    mocks.repositoryState = {
      activeRepository: repositoryA,
      completedRepositories: [repositoryA, repositoryB],
    };
  });

  it('never publishes a late Review response from repository A after selecting B', async () => {
    const responseA = deferred<EngineeringReview>();
    mocks.fetchReview.mockImplementation((selected: Repository) =>
      selected.id === repositoryA.id ? responseA.promise : Promise.resolve(review(repositoryB.id)),
    );

    const { result, rerender } = renderHook(() => useReview());
    await waitFor(() => expect(result.current.loading).toBe(true));

    mocks.repositoryState = {
      activeRepository: repositoryB,
      completedRepositories: [repositoryA, repositoryB],
    };
    rerender();
    expect(result.current.data).toBeNull();
    await waitFor(() => expect(result.current.data?.repositoryId).toBe(repositoryB.id));

    await act(async () => responseA.resolve(review(repositoryA.id)));
    expect(result.current.data?.repositoryId).toBe(repositoryB.id);
    expect(useReviewStore.getState().review?.repositoryId).toBe(repositoryB.id);
  });

  it('never publishes a late Insights response from repository A after selecting B', async () => {
    const responseA = deferred<RepositoryInsights>();
    mocks.fetchInsights.mockImplementation((selected: Repository) =>
      selected.id === repositoryA.id ? responseA.promise : Promise.resolve(insights(repositoryB.id)),
    );

    const { result, rerender } = renderHook(() => useInsights());
    await waitFor(() => expect(result.current.loading).toBe(true));

    mocks.repositoryState = {
      activeRepository: repositoryB,
      completedRepositories: [repositoryA, repositoryB],
    };
    rerender();
    expect(result.current.data).toBeNull();
    await waitFor(() => expect(result.current.data?.repositoryId).toBe(repositoryB.id));

    await act(async () => responseA.resolve(insights(repositoryA.id)));
    expect(result.current.data?.repositoryId).toBe(repositoryB.id);
  });
});
