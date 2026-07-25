export type InsightAssessmentState = 'assessed' | 'not_assessed' | 'insufficient_evidence';

export interface InsightProvenance {
  source: 'ri.v1';
  snapshotId: string;
  snapshotSchemaVersion: string;
  canonicalGraphHash: string;
}

export interface InsightExtractor {
  name: string;
  version: string;
  evidenceRecordCount: number;
}

export interface InsightMetric {
  id: string;
  label: string;
  value: number | string | null;
  unit: string;
  definition: string;
  provenance: InsightProvenance;
  assessmentState: InsightAssessmentState;
  snapshotId: string;
  numerator: number | null;
  denominator: number | null;
}

export interface InsightBreakdown {
  key: string;
  label: string;
  value: number;
}

export interface RepositoryInsights {
  schemaVersion: 'repository-insights.v1';
  repositoryId: string;
  repositoryName: string;
  revisionKind: 'git' | 'upload';
  revisionValue: string;
  snapshotId: string;
  snapshotSchemaVersion: string;
  canonicalGraphHash: string;
  manifestDigest: string;
  provenance: InsightProvenance;
  computedAt: string;
  snapshotCreatedAt: string;
  snapshotSealedAt: string;
  extractorSet: InsightExtractor[];
  metrics: InsightMetric[];
  relationshipsByPredicate: InsightBreakdown[];
  diagnosticsBySeverity: InsightBreakdown[];
  diagnosticsByCode: InsightBreakdown[];
  languages: InsightBreakdown[];
  changeOverTime: {
    assessmentState: 'not_assessed';
    message: string;
  };
}
