import { beforeEach, describe, expect, it } from 'vitest';
import type { EngineeringReview, ReviewFinding } from '@/shared/types/review';
import { useReviewStore } from './store';

const provenance = {
  source: 'ri.v1' as const,
  snapshotId: 'snap_example',
  snapshotSchemaVersion: 'ri.v1',
  canonicalGraphHash: `sha256:${'1'.repeat(64)}`,
};

function makeFinding(index: number, overrides: Partial<ReviewFinding> = {}): ReviewFinding {
  return {
    id: `finding-${index}`,
    category: 'relationship_resolution',
    severity: 'medium',
    title: 'Unresolved relationship',
    explanation: 'explanation',
    path: `src/file-${index}.ts`,
    startLine: 1,
    endLine: 1,
    snapshotId: 'snap_example',
    factId: `fact-${index}`,
    evidenceId: `evidence-${index}`,
    extractorName: 'typescript-extractor',
    extractorVersion: '1.0.0',
    diagnosticCode: 'RI-RES-UNRESOLVED',
    ruleId: 'engineering-review.v2/RI-RES-UNRESOLVED',
    remediationGuidance: 'remediation',
    supportStatus: 'supported',
    provenance,
    evidence: {
      evidenceId: `evidence-${index}`,
      snapshotId: 'snap_example',
      factId: `fact-${index}`,
      path: `src/file-${index}.ts`,
      startLine: 1,
      endLine: 1,
      extractorName: 'typescript-extractor',
      extractorVersion: '1.0.0',
    },
    ...overrides,
  };
}

function makeReview(findings: ReviewFinding[], total: number): EngineeringReview {
  return {
    schemaVersion: 'engineering-review.v2',
    repositoryId: 'repo-1',
    repositoryName: 'sample',
    revisionKind: 'upload',
    revisionValue: `sha256:${'0'.repeat(64)}`,
    snapshotId: 'snap_example',
    snapshotSchemaVersion: 'ri.v1',
    canonicalGraphHash: provenance.canonicalGraphHash,
    manifestDigest: `sha256:${'2'.repeat(64)}`,
    provenance,
    generatedAt: '2026-07-25T00:00:00Z',
    assessmentStatus: 'assessed',
    categories: [],
    findings,
    pagination: { offset: 0, limit: findings.length, total },
    summary: {
      message: 'summary',
      findingsBySeverity: { info: 0, low: 0, medium: total, high: 0, critical: 0 },
      assessedCategories: 1,
      partiallyAssessedCategories: 0,
      notAssessedCategories: 0,
      insufficientEvidenceCategories: 0,
      evidenceBackedFindingCount: total,
      fileScopedFindingCount: 0,
      omittedUnsupportedDiagnosticCount: 0,
      vulnerabilityScanning: 'not_assessed',
    },
  };
}

describe('useReviewStore', () => {
  beforeEach(() => {
    useReviewStore.getState().resetForRepository();
  });

  it('replaces the review wholesale on setReview', () => {
    const firstPage = Array.from({ length: 50 }, (_, index) => makeFinding(index));
    useReviewStore.getState().setReview(makeReview(firstPage, 120));

    expect(useReviewStore.getState().review?.findings).toHaveLength(50);
    expect(useReviewStore.getState().review?.pagination.total).toBe(120);
  });

  it('appends the next page onto the already-loaded findings', () => {
    const firstPage = Array.from({ length: 50 }, (_, index) => makeFinding(index));
    useReviewStore.getState().setReview(makeReview(firstPage, 120));

    const secondPage = Array.from({ length: 50 }, (_, index) => makeFinding(50 + index));
    useReviewStore.getState().appendFindings(secondPage, { offset: 50, limit: 50, total: 120 });

    const { review } = useReviewStore.getState();
    expect(review?.findings).toHaveLength(100);
    expect(review?.findings[0].id).toBe('finding-0');
    expect(review?.findings[99].id).toBe('finding-99');
    expect(review?.pagination).toEqual({ offset: 50, limit: 50, total: 120 });
  });

  it('appendFindings is a no-op when there is no review loaded yet', () => {
    useReviewStore.getState().appendFindings([makeFinding(0)], { offset: 0, limit: 50, total: 1 });

    expect(useReviewStore.getState().review).toBeNull();
  });

  it('resetForRepository clears the review, selection, and filters', () => {
    useReviewStore.getState().setReview(makeReview([makeFinding(0)], 1));
    useReviewStore.getState().setSelectedFindingId('finding-0');
    useReviewStore.getState().setFilterCategory('relationship_resolution');
    useReviewStore.getState().setFilterSeverity('medium');
    useReviewStore.getState().setFilterDiagnosticCode('RI-RES-UNRESOLVED');

    useReviewStore.getState().resetForRepository();

    const state = useReviewStore.getState();
    expect(state.review).toBeNull();
    expect(state.selectedFindingId).toBeNull();
    expect(state.filterCategory).toBe('all');
    expect(state.filterSeverity).toBe('all');
    expect(state.filterDiagnosticCode).toBeNull();
  });
});
