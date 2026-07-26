import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useReview } from '@/features/review/hooks/useReview';
import { useReviewStore } from '@/features/review/store';
import { architectureService } from '@/shared/services/api/architecture';
import type { EngineeringReview } from '@/shared/types/review';
import type { RevisionManifestResponse } from '@/shared/services/api/types';
import { EngineeringReviewPage } from './EngineeringReviewPage';

vi.mock('@/features/review/hooks/useReview', () => ({
  useReview: vi.fn(),
}));

vi.mock('@/shared/services/api/architecture', () => ({
  architectureService: { getRevisionManifest: vi.fn() },
}));

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
  categories: [],
  findings: [],
  summary: {
    message: 'No findings were surfaced for this snapshot.',
    findingsBySeverity: { info: 0, low: 0, medium: 0, high: 0, critical: 0 },
    assessedCategories: 8,
    partiallyAssessedCategories: 0,
    notAssessedCategories: 0,
    insufficientEvidenceCategories: 0,
    evidenceBackedFindingCount: 0,
    fileScopedFindingCount: 0,
    omittedUnsupportedDiagnosticCount: 0,
    vulnerabilityScanning: 'not_assessed',
  },
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
    canonicalGraphHash: `sha256:${'3'.repeat(64)}`,
    createdAt: '2026-07-25T00:00:00Z',
    sealedAt: '2026-07-25T00:00:05Z',
  },
  manifestDigest: `sha256:${'4'.repeat(64)}`,
  verificationMethod: 'sha256-canonical-json',
  verificationState: 'verified',
  verificationNote: 'This digest is a SHA-256 over the canonical JSON encoding of the manifest fields above.',
};

function renderPage() {
  return render(
    <MemoryRouter>
      <EngineeringReviewPage />
    </MemoryRouter>,
  );
}

describe('EngineeringReviewPage', () => {
  beforeEach(() => {
    vi.mocked(useReview).mockReturnValue({
      review,
      data: review,
      source: 'upload',
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      retry: vi.fn(),
      refresh: vi.fn(),
      activeRepository: null,
      completedRepositories: [],
      emptyReason: null,
    });
    useReviewStore.setState({
      review,
      selectedFindingId: null,
      filterCategory: 'all',
      filterSeverity: 'all',
      filterDiagnosticCode: null,
    });
    vi.mocked(architectureService.getRevisionManifest).mockResolvedValue(revisionManifest);
  });

  it('keeps the sealed snapshot identity one click away instead of on the landing strip (#176)', async () => {
    renderPage();

    await waitFor(() => expect(screen.getByTestId('revision-manifest')).toBeInTheDocument());
    expect(screen.getByText('snap_example')).toBeInTheDocument();
    expect(screen.queryByText(revisionManifest.manifestDigest)).not.toBeInTheDocument();
    expect(screen.queryByText(revisionManifest.manifest.canonicalGraphHash!)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /details/i }));

    expect(screen.getByText('Manifest digest')).toBeInTheDocument();
    expect(screen.getByText(revisionManifest.manifestDigest)).toBeInTheDocument();
    expect(screen.getByText(revisionManifest.manifest.canonicalGraphHash!)).toBeInTheDocument();
  });

  it('still renders the evidence-backed summary and assessment matrix', () => {
    renderPage();

    expect(screen.getByText('Evidence-backed summary')).toBeInTheDocument();
    expect(screen.getByText('No findings were surfaced for this snapshot.')).toBeInTheDocument();
    expect(
      screen.getByText('No overall score, grade, health percentage, or category score is produced.'),
    ).toBeInTheDocument();
  });
});
