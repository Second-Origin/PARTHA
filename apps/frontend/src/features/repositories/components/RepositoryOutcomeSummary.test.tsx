import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { backendService } from '@/shared/services/backend';
import { architectureService } from '@/shared/services/api/architecture';
import { ApiError } from '@/shared/services/api';
import type { Repository } from '@/shared/types';
import type { ArchitectureModel } from '@/shared/types/architecture';
import type { EngineeringReview } from '@/shared/types/review';
import type { RepositoryInsights } from '@/shared/types/insights';
import type { DependencyGraphResponse, RevisionManifestResponse } from '@/shared/services/api/types';
import { RepositoryOutcomeSummary } from './RepositoryOutcomeSummary';

vi.mock('@/shared/services/api/architecture', () => ({
  architectureService: { getRevisionManifest: vi.fn() },
}));

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

const baseProvenance = {
  source: 'ri.v1' as const,
  snapshotId: 'snap_example',
  snapshotSchemaVersion: 'ri.v1',
  canonicalGraphHash: `sha256:${'1'.repeat(64)}`,
};

const review: EngineeringReview = {
  schemaVersion: 'engineering-review.v2',
  repositoryId: 'repo-1',
  repositoryName: 'sample',
  revisionKind: 'upload',
  revisionValue: `sha256:${'0'.repeat(64)}`,
  snapshotId: 'snap_example',
  snapshotSchemaVersion: 'ri.v1',
  canonicalGraphHash: baseProvenance.canonicalGraphHash,
  manifestDigest: `sha256:${'2'.repeat(64)}`,
  provenance: baseProvenance,
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
  ],
  findings: [],
  pagination: { offset: 0, limit: 50, total: 0 },
  summary: {
    message: 'summary',
    findingsBySeverity: { info: 0, low: 0, medium: 0, high: 1, critical: 2 },
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
  canonicalGraphHash: baseProvenance.canonicalGraphHash,
  manifestDigest: `sha256:${'2'.repeat(64)}`,
  provenance: baseProvenance,
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
  canonicalGraphHash: baseProvenance.canonicalGraphHash,
  manifestDigest: `sha256:${'2'.repeat(64)}`,
  provenance: baseProvenance,
  computedAt: '2026-07-25T00:00:00Z',
  snapshotCreatedAt: '2026-07-25T00:00:00Z',
  snapshotSealedAt: '2026-07-25T00:00:00Z',
  extractorSet: [{ name: 'typescript-extractor', version: '1.0.0', evidenceRecordCount: 10 }],
  metrics: [],
  relationshipsByPredicate: [],
  diagnosticsBySeverity: [],
  diagnosticsByCode: [],
  languages: [{ key: 'typescript', label: 'TypeScript', value: 5 }],
  changeOverTime: { assessmentState: 'not_assessed', message: 'not tracked' },
};

const revisionManifest: RevisionManifestResponse = {
  manifest: {
    schemaVersion: 'revision-manifest.v1',
    repositoryId: 'repo-1',
    revisionKind: 'upload',
    revisionValue: `sha256:${'0'.repeat(64)}`,
    revisionRef: null,
    snapshotId: 'snap_example',
    snapshotSchemaVersion: 'ri.v1',
    extractors: [{ name: 'typescript-extractor', version: '1.0.0' }],
    producerSetHash: `sha256:${'1'.repeat(64)}`,
    configHash: `sha256:${'2'.repeat(64)}`,
    canonicalGraphHash: baseProvenance.canonicalGraphHash,
    createdAt: '2026-07-25T00:00:00Z',
    sealedAt: '2026-07-25T00:00:05Z',
  },
  manifestDigest: `sha256:${'4'.repeat(64)}`,
  verificationMethod: 'sha256-canonical-json',
  verificationState: 'verified',
  verificationNote: 'This digest is a SHA-256 over the canonical JSON encoding of the manifest fields above.',
};

describe('RepositoryOutcomeSummary', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('leads with real evidence-backed facts, not fabricated values', async () => {
    vi.spyOn(backendService, 'fetchArchitecture').mockResolvedValue(architecture);
    vi.spyOn(backendService, 'fetchReview').mockResolvedValue(review);
    vi.spyOn(backendService, 'fetchDependencyGraph').mockResolvedValue(dependencyGraph);
    vi.spyOn(backendService, 'fetchInsights').mockResolvedValue(insights);

    render(
      <MemoryRouter>
        <RepositoryOutcomeSummary repository={repository} />
      </MemoryRouter>,
    );

    expect(await screen.findByText('TypeScript / React')).toBeInTheDocument();
    expect(screen.getByText('Modular monolith')).toBeInTheDocument();
    expect(screen.getByText('12 modules')).toBeInTheDocument();
    expect(screen.getByText('48 components')).toBeInTheDocument();
    expect(screen.getByText('27 tracked')).toBeInTheDocument();
    // 2 relationship-resolution findings outrank the 1 authentication-evidence
    // finding, and the headline names the category rather than a severity
    // grade (#335). It's also a link into the filtered Review view.
    const headlineLink = screen.getByRole('link', {
      name: '2 relationship resolution findings — inspect coverage and filters',
    });
    expect(headlineLink).toHaveAttribute('href', '/review?category=relationship_resolution');
    expect(screen.getByText(/Assessed via 1 extractor across 1 detected language\./)).toBeInTheDocument();
    // The snapshot/manifest identity is not on the landing strip by default.
    expect(screen.queryByText(revisionManifest.manifestDigest)).not.toBeInTheDocument();
    expect(screen.queryByTestId('revision-manifest')).not.toBeInTheDocument();
  });

  it('reveals the provenance panel only after Verify is clicked, and hides it again on toggle', async () => {
    vi.spyOn(backendService, 'fetchArchitecture').mockResolvedValue(architecture);
    vi.spyOn(backendService, 'fetchReview').mockResolvedValue(review);
    vi.spyOn(backendService, 'fetchDependencyGraph').mockResolvedValue(dependencyGraph);
    vi.spyOn(backendService, 'fetchInsights').mockResolvedValue(insights);
    vi.mocked(architectureService.getRevisionManifest).mockResolvedValue(revisionManifest);

    render(
      <MemoryRouter>
        <RepositoryOutcomeSummary repository={repository} />
      </MemoryRouter>,
    );
    await screen.findByText('TypeScript / React');

    expect(screen.queryByTestId('revision-manifest')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

    await waitFor(() => expect(screen.getByTestId('revision-manifest')).toBeInTheDocument());
    expect(screen.getByText('snap_example')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Hide verification' }));

    expect(screen.queryByTestId('revision-manifest')).not.toBeInTheDocument();
  });

  it('renders an honest not-assessed state instead of a fabricated value when a snapshot section 404s', async () => {
    vi.spyOn(backendService, 'fetchArchitecture').mockRejectedValue(new ApiError(404, 'Not Found', null, '/x'));
    vi.spyOn(backendService, 'fetchReview').mockRejectedValue(new ApiError(404, 'Not Found', null, '/x'));
    vi.spyOn(backendService, 'fetchDependencyGraph').mockRejectedValue(new ApiError(404, 'Not Found', null, '/x'));
    vi.spyOn(backendService, 'fetchInsights').mockRejectedValue(new ApiError(404, 'Not Found', null, '/x'));

    render(
      <MemoryRouter>
        <RepositoryOutcomeSummary repository={repository} />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getAllByText('Not assessed').length).toBeGreaterThan(0));
    expect(screen.queryByText('TypeScript / React')).not.toBeInTheDocument();
    expect(screen.queryByText(/relationship resolution finding|No evidence-backed findings/)).not.toBeInTheDocument();
  });
});
