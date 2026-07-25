export type ReviewSeverity = 'info' | 'low' | 'medium' | 'high' | 'critical';
export type ReviewAssessmentState =
  | 'assessed'
  | 'partially_assessed'
  | 'not_assessed'
  | 'insufficient_evidence';

export type ReviewCategory =
  | 'architecture_boundaries'
  | 'relationship_resolution'
  | 'source_extraction'
  | 'dependency_declarations'
  | 'security_vulnerability_scanning'
  | 'authentication_evidence'
  | 'repository_structure'
  | 'analysis_integrity';

export interface ReviewProvenance {
  source: 'ri.v1';
  snapshotId: string;
  snapshotSchemaVersion: string;
  canonicalGraphHash: string;
}

export interface ReviewEvidenceReference {
  evidenceId: string;
  snapshotId: string;
  factId: string;
  path: string;
  startLine: number;
  endLine: number;
  extractorName: string;
  extractorVersion: string;
}

export interface ReviewFinding {
  id: string;
  category: ReviewCategory;
  severity: ReviewSeverity;
  title: string;
  explanation: string;
  path: string;
  startLine: number;
  endLine: number;
  snapshotId: string;
  factId: string;
  evidenceId: string;
  extractorName: string;
  extractorVersion: string;
  diagnosticCode: string;
  ruleId: string;
  remediationGuidance: string;
  supportStatus: 'supported';
  provenance: ReviewProvenance;
  evidence: ReviewEvidenceReference;
}

export interface ReviewCategoryAssessment {
  id: ReviewCategory;
  label: string;
  state: ReviewAssessmentState;
  explanation: string;
  findingCount: number;
}

export interface ReviewSeverityCounts {
  info: number;
  low: number;
  medium: number;
  high: number;
  critical: number;
}

export interface ReviewSummary {
  message: string;
  findingsBySeverity: ReviewSeverityCounts;
  assessedCategories: number;
  partiallyAssessedCategories: number;
  notAssessedCategories: number;
  insufficientEvidenceCategories: number;
  evidenceBackedFindingCount: number;
  unsupportedFindingCount: number;
  omittedUnsupportedDiagnosticCount: number;
  vulnerabilityScanning: 'not_assessed';
}

export interface EngineeringReview {
  schemaVersion: 'engineering-review.v2';
  repositoryId: string;
  repositoryName: string;
  revisionKind: 'git' | 'upload';
  revisionValue: string;
  snapshotId: string;
  snapshotSchemaVersion: string;
  canonicalGraphHash: string;
  manifestDigest: string;
  provenance: ReviewProvenance;
  generatedAt: string;
  assessmentStatus: ReviewAssessmentState;
  categories: ReviewCategoryAssessment[];
  findings: ReviewFinding[];
  summary: ReviewSummary;
}
