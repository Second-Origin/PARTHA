import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { backendService } from '@/shared/services/backend';
import { ApiError } from '@/shared/services/api';
import type { Repository } from '@/shared/types';
import type { DependencyGraphResponse } from '@/shared/services/api/types';
import { useDependencies } from './useDependencies';

const repositoryState = vi.hoisted(() => ({
  activeRepository: null as Repository | null,
  completedRepositories: [] as Repository[],
}));

vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({
    activeRepository: repositoryState.activeRepository,
    completedRepositories: repositoryState.completedRepositories,
  }),
}));

function repository(overrides: Partial<Repository> = {}): Repository {
  return {
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
    meta: { packageManager: 'npm' } as Repository['meta'],
    fileTree: [],
    ...overrides,
  };
}

const graph: DependencyGraphResponse = {
  schemaVersion: 'dependency-graph.v2',
  repositoryId: 'repo-1',
  repositoryName: 'sample',
  revisionKind: 'upload',
  revisionValue: `sha256:${'0'.repeat(64)}`,
  snapshotId: 'snap_example',
  snapshotSchemaVersion: 'ri.v1',
  canonicalGraphHash: `sha256:${'1'.repeat(64)}`,
  manifestDigest: `sha256:${'2'.repeat(64)}`,
  provenance: {
    source: 'ri.v1',
    snapshotId: 'snap_example',
    snapshotSchemaVersion: 'ri.v1',
    canonicalGraphHash: `sha256:${'1'.repeat(64)}`,
  },
  generatedAt: '2026-07-25T00:00:00Z',
  nodes: [],
  edges: [],
  totalDependencies: 0,
  manifestCount: 0,
  diagnostics: [],
  vulnerabilityAssessment: { status: 'not_computed' },
  outdatedAssessment: { status: 'not_computed' },
};

describe('useDependencies', () => {
  beforeEach(() => {
    repositoryState.activeRepository = null;
    repositoryState.completedRepositories = [];
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads the sealed snapshot graph for a completed repository', async () => {
    repositoryState.activeRepository = repository();
    repositoryState.completedRepositories = [repository()];
    vi.spyOn(backendService, 'fetchDependencyGraph').mockResolvedValue(graph);

    const { result } = renderHook(() => useDependencies());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.graph).toEqual(graph);
    expect(result.current.noSnapshot).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('distinguishes a 404 no-sealed-snapshot response from a generic error', async () => {
    repositoryState.activeRepository = repository();
    repositoryState.completedRepositories = [repository()];
    vi.spyOn(backendService, 'fetchDependencyGraph').mockRejectedValue(
      new ApiError(404, 'Not Found', { message: 'No sealed Repository Intelligence snapshot is available.' }, '/analysis/repo-1/dependencies'),
    );

    const { result } = renderHook(() => useDependencies());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.noSnapshot).toBe(true);
    expect(result.current.graph).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('surfaces a non-404 failure as a normal error, not a no-snapshot state', async () => {
    repositoryState.activeRepository = repository();
    repositoryState.completedRepositories = [repository()];
    vi.spyOn(backendService, 'fetchDependencyGraph').mockRejectedValue(
      new ApiError(500, 'Internal Server Error', null, '/analysis/repo-1/dependencies'),
    );

    const { result } = renderHook(() => useDependencies());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.noSnapshot).toBe(false);
    expect(result.current.graph).toBeNull();
    expect(result.current.error).not.toBeNull();
  });

  it('reports the detected package manager from repository metadata', async () => {
    repositoryState.activeRepository = repository({ meta: { packageManager: 'pnpm' } as Repository['meta'] });
    repositoryState.completedRepositories = [repository()];
    vi.spyOn(backendService, 'fetchDependencyGraph').mockResolvedValue(graph);

    const { result } = renderHook(() => useDependencies());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.packageManager).toBe('pnpm');
  });

  it('does not fetch when there is no completed active repository', () => {
    repositoryState.activeRepository = null;
    repositoryState.completedRepositories = [];
    const fetchSpy = vi.spyOn(backendService, 'fetchDependencyGraph');

    const { result } = renderHook(() => useDependencies());

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result.current.graph).toBeNull();
    expect(result.current.noSnapshot).toBe(false);
  });
});
