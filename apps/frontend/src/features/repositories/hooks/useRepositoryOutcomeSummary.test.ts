import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { backendService } from '@/shared/services/backend';
import { ApiError } from '@/shared/services/api';
import type { Repository } from '@/shared/types';
import type { ArchitectureModel } from '@/shared/types/architecture';
import type { EngineeringReview } from '@/shared/types/review';
import type { RepositoryInsights } from '@/shared/types/insights';
import type { DependencyGraphResponse } from '@/shared/services/api/types';
import { useRepositoryOutcomeSummary } from './useRepositoryOutcomeSummary';

const repository: Repository = {
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

const architecture: ArchitectureModel = {
  repositoryId: 'repo-1',
  repositoryName: 'sample',
  architectureType: 'modular-monolith',
  detectedLayers: [],
  nodes: [],
  edges: [],
  modules: [],
  requestFlow: [],
  diagnostics: [],
  summary: {
    language: 'TypeScript',
    framework: 'React',
    totalModules: 12,
    totalNodes: 48,
    entryPoint: 'src/main.tsx',
    architecturePattern: 'Modular monolith',
  },
};

const review: EngineeringReview = {
  schemaVersion: 'engineering-review.v2',
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
  assessmentStatus: 'assessed',
  categories: [
    {
      id: 'relationship_resolution',
      label: 'Relationship resolution',
      state: 'partially_assessed',
      explanation: 'Some relationships could not be resolved.',
      findingCount: 2,
    },
    {
      id: 'authentication_evidence',
      label: 'Authentication evidence',
      state: 'assessed',
      explanation: 'Authentication evidence was assessed.',
      findingCount: 1,
    },
    {
      id: 'security_vulnerability_scanning',
      label: 'Security vulnerability scanning',
      state: 'not_assessed',
      explanation: 'Vulnerability scanning was not performed.',
      findingCount: 0,
    },
  ],
  findings: [],
  pagination: { offset: 0, limit: 50, total: 0 },
  summary: {
    message: 'summary',
    findingsBySeverity: { info: 1, low: 0, medium: 0, high: 2, critical: 0 },
    assessedCategories: 8,
    partiallyAssessedCategories: 0,
    notAssessedCategories: 0,
    insufficientEvidenceCategories: 0,
    evidenceBackedFindingCount: 3,
    fileScopedFindingCount: 0,
    omittedUnsupportedDiagnosticCount: 0,
    vulnerabilityScanning: 'not_assessed',
  },
};

const dependencyGraph: DependencyGraphResponse = {
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
  totalDependencies: 27,
  manifestCount: 1,
  diagnostics: [],
  vulnerabilityAssessment: { status: 'not_computed' },
  outdatedAssessment: { status: 'not_computed' },
};

const insights: RepositoryInsights = {
  schemaVersion: 'repository-insights.v1',
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
  computedAt: '2026-07-25T00:00:00Z',
  snapshotCreatedAt: '2026-07-25T00:00:00Z',
  snapshotSealedAt: '2026-07-25T00:00:00Z',
  extractorSet: [
    { name: 'typescript-extractor', version: '1.0.0', evidenceRecordCount: 10 },
    { name: 'dependency-manifest', version: '1.2.0', evidenceRecordCount: 3 },
  ],
  metrics: [],
  relationshipsByPredicate: [],
  diagnosticsBySeverity: [],
  diagnosticsByCode: [],
  languages: [{ key: 'typescript', label: 'TypeScript', value: 5 }],
  changeOverTime: { assessmentState: 'not_assessed', message: 'not tracked' },
};

describe('useRepositoryOutcomeSummary', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('composes every section from the real Architecture/Review/Dependencies/Insights responses', async () => {
    vi.spyOn(backendService, 'fetchArchitecture').mockResolvedValue(architecture);
    vi.spyOn(backendService, 'fetchReview').mockResolvedValue(review);
    vi.spyOn(backendService, 'fetchDependencyGraph').mockResolvedValue(dependencyGraph);
    vi.spyOn(backendService, 'fetchInsights').mockResolvedValue(insights);

    const { result } = renderHook(() => useRepositoryOutcomeSummary(repository));

    await waitFor(() => expect(result.current.stack.state).toBe('assessed'));

    expect(result.current.stack).toEqual({
      state: 'assessed',
      language: 'TypeScript',
      framework: 'React',
      architecturePattern: 'Modular monolith',
    });
    expect(result.current.structure).toEqual({ state: 'assessed', totalModules: 12, totalNodes: 48 });
    expect(result.current.dependencies).toEqual({ state: 'assessed', totalDependencies: 27 });
    // The highest finding-count category wins -- 2 relationship-resolution
    // findings outrank the 1 authentication-evidence finding. The message
    // names the diagnostic category, not a severity grade (#335).
    expect(result.current.headline).toEqual({
      state: 'assessed',
      message: '2 relationship resolution findings — inspect coverage and filters',
      categoryId: 'relationship_resolution',
    });
    expect(result.current.coverage).toEqual({ state: 'assessed', extractorCount: 2, languageCount: 1 });
  });

  it('reports no findings honestly rather than inventing a clean bill of health', async () => {
    vi.spyOn(backendService, 'fetchArchitecture').mockResolvedValue(architecture);
    vi.spyOn(backendService, 'fetchReview').mockResolvedValue({
      ...review,
      categories: review.categories.map((category) => ({ ...category, findingCount: 0 })),
    });
    vi.spyOn(backendService, 'fetchDependencyGraph').mockResolvedValue(dependencyGraph);
    vi.spyOn(backendService, 'fetchInsights').mockResolvedValue(insights);

    const { result } = renderHook(() => useRepositoryOutcomeSummary(repository));

    await waitFor(() => expect(result.current.headline.state).toBe('assessed'));
    expect(result.current.headline.message).toBe('No evidence-backed findings were surfaced');
    expect(result.current.headline.categoryId).toBeNull();
  });

  it('marks a section not_assessed, never fabricated, when its snapshot API 404s', async () => {
    vi.spyOn(backendService, 'fetchArchitecture').mockResolvedValue(architecture);
    vi.spyOn(backendService, 'fetchReview').mockRejectedValue(new ApiError(404, 'Not Found', null, '/analysis/repo-1/review'));
    vi.spyOn(backendService, 'fetchDependencyGraph').mockRejectedValue(new ApiError(404, 'Not Found', null, '/analysis/repo-1/review'));
    vi.spyOn(backendService, 'fetchInsights').mockRejectedValue(new ApiError(404, 'Not Found', null, '/analysis/repo-1/review'));

    const { result } = renderHook(() => useRepositoryOutcomeSummary(repository));

    await waitFor(() => expect(result.current.stack.state).toBe('assessed'));
    expect(result.current.headline).toEqual({ state: 'not_assessed', message: null, categoryId: null });
    expect(result.current.dependencies).toEqual({ state: 'not_assessed', totalDependencies: null });
    expect(result.current.coverage).toEqual({ state: 'not_assessed', extractorCount: null, languageCount: null });
  });

  it('stays in the loading state and fetches nothing while the repository has not completed analysis', () => {
    const fetchArchitecture = vi.spyOn(backendService, 'fetchArchitecture');
    const { result } = renderHook(() =>
      useRepositoryOutcomeSummary({ ...repository, status: 'analysing' }),
    );

    expect(result.current.stack.state).toBe('loading');
    expect(fetchArchitecture).not.toHaveBeenCalled();
  });
});
