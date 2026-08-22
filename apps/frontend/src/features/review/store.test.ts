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

const findings: ReviewFinding[] = Array.from({ length: 120 }, (_, index) => makeFinding(index));

const review: EngineeringReview = {
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
  summary: {
    message: 'summary',
    findingsBySeverity: { info: 0, low: 0, medium: 120, high: 0, critical: 0 },
    assessedCategories: 1,
    partiallyAssessedCategories: 0,
    notAssessedCategories: 0,
    insufficientEvidenceCategories: 0,
    evidenceBackedFindingCount: 120,
    fileScopedFindingCount: 0,
    omittedUnsupportedDiagnosticCount: 0,
    vulnerabilityScanning: 'not_assessed',
  },
};

describe('useReviewStore findings pagination', () => {
  beforeEach(() => {
    useReviewStore.getState().resetForRepository();
    useReviewStore.getState().setReview(review);
  });

  it('renders only the first page of a large findings list', () => {
    expect(useReviewStore.getState().filteredFindings()).toHaveLength(120);
    expect(useReviewStore.getState().visibleFindings()).toHaveLength(50);
  });

  it('reveals more findings in bounded steps', () => {
    useReviewStore.getState().showMoreFindings();
    expect(useReviewStore.getState().visibleFindings()).toHaveLength(100);

    useReviewStore.getState().showMoreFindings();
    // Caps at the actual total rather than overshooting.
    expect(useReviewStore.getState().visibleFindings()).toHaveLength(120);
  });

  it('resets the visible page whenever a filter changes', () => {
    useReviewStore.getState().showMoreFindings();
    expect(useReviewStore.getState().visibleFindings()).toHaveLength(100);

    useReviewStore.getState().setFilterSeverity('medium');
    expect(useReviewStore.getState().visibleFindings()).toHaveLength(50);

    useReviewStore.getState().showMoreFindings();
    useReviewStore.getState().setFilterCategory('relationship_resolution');
    expect(useReviewStore.getState().visibleFindings()).toHaveLength(50);

    useReviewStore.getState().showMoreFindings();
    useReviewStore.getState().setFilterDiagnosticCode('RI-RES-UNRESOLVED');
    expect(useReviewStore.getState().visibleFindings()).toHaveLength(50);
  });
});
