/**
 * Canned data for the scripted product simulation (#382).
 *
 * Every category id, severity level, and field name here matches the real
 * product's actual Engineering Review / Repository Insights response shape
 * (apps/backend/app/schemas -- cross-checked against
 * apps/frontend/src/shared/services/api/generated.ts, the generated OpenAPI
 * types) and the real category labels
 * (apps/backend/app/review/review_service.py's `_CATEGORY_LABELS`). The
 * repository, findings, and numbers themselves are entirely made up for a
 * fictional sample repo -- nothing here is captured from a real analysis.
 */

export const SAMPLE_REPO = {
  name: 'acme/checkout-service',
  revision: 'a3f9c21',
  languages: 'Python, TypeScript',
};

export const SIMULATION_STEPS = [
  'Cloning acme/checkout-service at a3f9c21',
  'Extracting structural facts (Python, TypeScript)',
  'Resolving module and dependency relationships',
  'Sealing the ri.v1 snapshot',
  'Running Engineering Review and Repository Insights',
] as const;

export type ReviewSeverity = 'info' | 'low' | 'medium' | 'high' | 'critical';

export type ReviewCategoryId =
  | 'architecture_boundaries'
  | 'relationship_resolution'
  | 'source_extraction'
  | 'dependency_declarations'
  | 'security_vulnerability_scanning'
  | 'authentication_evidence'
  | 'repository_structure'
  | 'analysis_integrity';

// Matches apps/backend/app/review/review_service.py's _CATEGORY_LABELS
// exactly, so the demo never invents category names the real product
// doesn't have.
export const CATEGORY_LABELS: Record<ReviewCategoryId, string> = {
  architecture_boundaries: 'Architecture and boundaries',
  relationship_resolution: 'Relationship resolution',
  source_extraction: 'Source extraction',
  dependency_declarations: 'Dependency declarations',
  security_vulnerability_scanning: 'Security vulnerability scanning',
  authentication_evidence: 'Authentication evidence',
  repository_structure: 'Repository structure',
  analysis_integrity: 'Analysis integrity',
};

export interface SampleFinding {
  id: string;
  title: string;
  category: ReviewCategoryId;
  severity: ReviewSeverity;
  explanation: string;
  remediationGuidance: string;
  path: string;
  startLine: number;
  endLine: number;
}

export const SAMPLE_FINDINGS: SampleFinding[] = [
  {
    id: 'finding-1',
    title: 'Payment adapter imports directly from the checkout domain layer',
    category: 'architecture_boundaries',
    severity: 'medium',
    explanation:
      'src/payments/stripe_adapter.py imports CheckoutOrder directly from src/checkout/domain.py, crossing the boundary the module layout otherwise keeps between payment adapters and the checkout domain.',
    remediationGuidance:
      'Route the dependency through the shared checkout interface (src/checkout/ports.py) instead of importing the domain model directly.',
    path: 'src/payments/stripe_adapter.py',
    startLine: 12,
    endLine: 14,
  },
  {
    id: 'finding-2',
    title: 'Declared dependency pin resolves to a version not requested anywhere',
    category: 'dependency_declarations',
    severity: 'low',
    explanation:
      'package-lock.json resolves "fast-xml-parser" to 4.2.5, but no direct or transitive declaration in package.json requests it -- likely a stale lockfile entry from a removed dependency.',
    remediationGuidance: 'Regenerate the lockfile and confirm the resolved dependency tree still matches package.json.',
    path: 'package-lock.json',
    startLine: 1841,
    endLine: 1841,
  },
  {
    id: 'finding-3',
    title: 'Session cookie is issued without an explicit SameSite attribute',
    category: 'authentication_evidence',
    severity: 'high',
    explanation:
      'src/auth/session.py sets the session cookie without a SameSite attribute, so browsers fall back to a permissive default that varies by browser rather than an explicit, reviewable policy.',
    remediationGuidance: 'Set SameSite explicitly (Lax or Strict) when issuing the session cookie.',
    path: 'src/auth/session.py',
    startLine: 47,
    endLine: 52,
  },
  {
    id: 'finding-4',
    title: 'Two modules independently resolve the same order-total calculation',
    category: 'relationship_resolution',
    severity: 'info',
    explanation:
      'src/checkout/domain.py and src/reporting/order_summary.py both implement order-total logic independently rather than one calling the other, a duplicate-interpretation risk if the two drift.',
    remediationGuidance: 'Consider extracting one shared calculation both call, if the duplication was not intentional.',
    path: 'src/reporting/order_summary.py',
    startLine: 88,
    endLine: 104,
  },
];

export interface SampleCategoryAssessment {
  id: ReviewCategoryId;
  label: string;
  state: 'assessed' | 'partially_assessed' | 'not_assessed' | 'insufficient_evidence';
  findingCount: number;
  explanation: string;
}

export const SAMPLE_CATEGORIES: SampleCategoryAssessment[] = [
  { id: 'architecture_boundaries', label: CATEGORY_LABELS.architecture_boundaries, state: 'assessed', findingCount: 1, explanation: 'Module boundaries were assessed from resolved import relationships.' },
  { id: 'relationship_resolution', label: CATEGORY_LABELS.relationship_resolution, state: 'assessed', findingCount: 1, explanation: 'Cross-module relationships were assessed from resolved facts.' },
  { id: 'source_extraction', label: CATEGORY_LABELS.source_extraction, state: 'assessed', findingCount: 0, explanation: 'No source-extraction diagnostics were raised for this snapshot.' },
  { id: 'dependency_declarations', label: CATEGORY_LABELS.dependency_declarations, state: 'assessed', findingCount: 1, explanation: 'Direct declarations and lockfile pins were assessed for this snapshot.' },
  { id: 'security_vulnerability_scanning', label: CATEGORY_LABELS.security_vulnerability_scanning, state: 'not_assessed', findingCount: 0, explanation: 'Vulnerability scanning is not implemented; this category is not assessed.' },
  { id: 'authentication_evidence', label: CATEGORY_LABELS.authentication_evidence, state: 'assessed', findingCount: 1, explanation: 'The supported Python/FastAPI authentication subgraph was assessed.' },
  { id: 'repository_structure', label: CATEGORY_LABELS.repository_structure, state: 'assessed', findingCount: 0, explanation: 'No repository-structure diagnostics were raised for this snapshot.' },
  { id: 'analysis_integrity', label: CATEGORY_LABELS.analysis_integrity, state: 'assessed', findingCount: 0, explanation: 'The analysis completed with no integrity diagnostics.' },
];

export interface SampleMetric {
  id: string;
  label: string;
  value: string;
  definition: string;
}

export const SAMPLE_METRICS: SampleMetric[] = [
  { id: 'files_analyzed', label: 'Files analyzed', value: '212', definition: 'Files included in this snapshot after extraction.' },
  { id: 'modules', label: 'Modules identified', value: '18', definition: 'Distinct modules resolved from the repository layout.' },
  { id: 'relationships', label: 'Relationships resolved', value: '341', definition: 'Import and dependency edges resolved between facts.' },
  { id: 'evidence_records', label: 'Evidence records', value: '1,204', definition: 'Stored source spans backing supported facts.' },
];

export const SAMPLE_LANGUAGES = [
  { key: 'python', label: 'Python', value: 63 },
  { key: 'typescript', label: 'TypeScript', value: 29 },
  { key: 'other', label: 'Other', value: 8 },
];
